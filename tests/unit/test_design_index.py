"""Keep design/README.md honest about the documents beside it."""

import re
from datetime import datetime
from pathlib import Path

import pytest


pytestmark = pytest.mark.unit


DESIGN_DIR = Path(__file__).resolve().parents[2] / "design"
INDEX_FILE = DESIGN_DIR / "README.md"

STATUSES = ("proposal", "in progress", "issue draft", "shipped")

# A folder implies a status: an unfiled issue draft in plans/, or a shipped plan left in plans/,
# means the lifecycle described in design/README.md has been skipped.
FOLDER_STATUSES = {
    "plans": ("proposal", "in progress"),
    "issues": ("issue draft",),
    "archive": ("shipped",),
}

INDEX_ROW = re.compile(r"^\|\s*\[`(?P<label>[^`]+)`\]\((?P<path>[^)]+)\)\s*\|\s*(?P<status>[^|]+?)\s*\|")
HEADER_FIELD = r"^- \*\*{}:\*\*\s*(?P<value>.+?)\s*$"
MARKDOWN_LINK = re.compile(r"\[[^\]]*\]\((?P<target>[^)\s]+)\)")


def design_documents():
    return sorted(
        path
        for path in DESIGN_DIR.rglob("*.md")
        if path != INDEX_FILE and not path.name.endswith(".local.md")
    )


def indexed_documents():
    rows = {}
    in_index = False
    for line in INDEX_FILE.read_text(encoding="utf-8").splitlines():
        if line.startswith("## "):
            in_index = line.strip() == "## Index"
            continue
        if not in_index:
            continue
        match = INDEX_ROW.match(line)
        if match:
            rows[(DESIGN_DIR / match.group("path")).resolve()] = match.group("status")
    return rows


def header_field(document, name):
    pattern = re.compile(HEADER_FIELD.format(name), re.MULTILINE)
    match = pattern.search(document.read_text(encoding="utf-8"))
    return match and match.group("value")


def relative_path(path):
    return path.relative_to(DESIGN_DIR.parent).as_posix()


def test_design_documents_exist():
    """The index only means something if it has documents to describe."""
    assert design_documents()


@pytest.mark.parametrize("document", design_documents(), ids=relative_path)
def test_document_is_indexed(document):
    assert document.resolve() in indexed_documents(), (
        "{} is not listed in the Index table of design/README.md".format(relative_path(document))
    )


def test_index_rows_point_at_existing_documents():
    missing = [path for path in indexed_documents() if not path.is_file()]
    assert not missing, "design/README.md lists documents that do not exist: {}".format(missing)


@pytest.mark.parametrize("document", design_documents(), ids=relative_path)
def test_document_header_parses(document):
    status = header_field(document, "Status")
    assert status in STATUSES, "{} has status [{}], expected one of {}".format(
        relative_path(document), status, STATUSES
    )
    assert header_field(document, "Related"), "{} has no Related field".format(relative_path(document))

    updated = header_field(document, "Updated")
    assert updated, "{} has no Updated field".format(relative_path(document))
    datetime.strptime(updated, "%Y-%m-%d")


@pytest.mark.parametrize("document", design_documents(), ids=relative_path)
def test_document_status_matches_index_and_folder(document):
    status = header_field(document, "Status")
    indexed = indexed_documents().get(document.resolve())
    assert indexed == status, "{} says [{}] but design/README.md says [{}]".format(
        relative_path(document), status, indexed
    )

    folder = document.parent.name
    assert status in FOLDER_STATUSES[folder], "{} is [{}] but sits in {}/".format(
        relative_path(document), status, folder
    )


def prose_lines(document):
    """Lines outside fenced code blocks, where a link is a link and not an example."""
    fenced = False
    for line in document.read_text(encoding="utf-8").splitlines():
        if line.lstrip().startswith("```"):
            fenced = not fenced
        elif not fenced:
            yield line


@pytest.mark.parametrize("document", design_documents() + [INDEX_FILE], ids=relative_path)
def test_relative_links_resolve(document):
    broken = []
    for line in prose_lines(document):
        for match in MARKDOWN_LINK.finditer(line):
            target = match.group("target")
            if target.startswith(("http://", "https://", "mailto:", "#")):
                continue
            target = target.split("#", 1)[0]
            if target and not (document.parent / target).exists():
                broken.append(target)
    assert not broken, "{} links to missing paths: {}".format(relative_path(document), broken)
