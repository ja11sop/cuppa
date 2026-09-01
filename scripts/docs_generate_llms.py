#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

"""Generate llms.txt, per-page Markdown, and llms-full.txt from Antora HTML.

Reads ``_docs_build/site`` after ``antora generate``. Prefers the ``latest``
version tree (release-default). Converts each ``article.doc`` body with Pandoc
to GFM. Omits integration-test leaves from the curated index and full file.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

from lxml import html as lxml_html


REPO_ROOT = Path(__file__).resolve().parents[1]
SITE_ROOT = REPO_ROOT / "_docs_build" / "site"
SITE_URL = "https://ja11sop.github.io/cuppa"
COMPONENT = "cuppa"

# Relative to the versioned component root (…/cuppa/latest/…).
CURATED_PAGES = [
    "index.html",
    "install.html",
    "quickstart.html",
    "concepts.html",
    "cli-reference.html",
    "methods.html",
    "methods/method-index.html",
    "methods/build.html",
    "methods/test-run.html",
    "methods/coverage.html",
    "toolchains.html",
    "dependencies.html",
    "cxx-modules.html",
    "cxx-profiles.html",
    "packages.html",
    "contributing.html",
    "contributing/versioning.html",
    "contributing/release.html",
]

SECTION_MAP = [
    ("Overview", ["index.html", "install.html", "quickstart.html", "concepts.html"]),
    ("CLI", ["cli-reference.html"]),
    ("Methods", [
        "methods.html",
        "methods/method-index.html",
        "methods/build.html",
        "methods/test-run.html",
        "methods/coverage.html",
    ]),
    ("Toolchains and language", [
        "toolchains.html",
        "cxx-modules.html",
        "cxx-profiles.html",
    ]),
    ("Dependencies and packages", ["dependencies.html", "packages.html"]),
    ("Contributing", [
        "contributing.html",
        "contributing/versioning.html",
        "contributing/release.html",
    ]),
]


def find_component_root(site_root: Path) -> Path:
    """Prefer …/cuppa/latest; fall back to the newest non-next version directory."""
    preferred = site_root / COMPONENT / "latest"
    if (preferred / "index.html").is_file():
        return preferred
    component_dir = site_root / COMPONENT
    if not component_dir.is_dir():
        raise RuntimeError("Antora site missing {}/ under {}".format(COMPONENT, site_root))
    candidates = []
    for path in component_dir.iterdir():
        if not path.is_dir():
            continue
        if path.name in ("_",) or path.name.startswith("."):
            continue
        if not (path / "index.html").is_file():
            continue
        candidates.append(path.name)
    stable = [name for name in candidates if name != "next"]

    def sort_key(name: str):
        parts = name.split(".")
        if all(part.isdigit() for part in parts):
            return (0, tuple(int(part) for part in parts))
        return (1, name)

    ordered = sorted(stable, key=sort_key) if stable else sorted(candidates, key=sort_key)
    if not ordered:
        raise RuntimeError("no component versions under {}".format(component_dir))
    return component_dir / ordered[-1]


def extract_article_html(page_path: Path) -> str:
    tree = lxml_html.parse(str(page_path))
    articles = tree.xpath('//article[contains(@class,"doc")]')
    if not articles:
        raise RuntimeError("no article.doc in {}".format(page_path))
    article = articles[0]
    # Drop UI-only chrome that sometimes nests inside the article.
    for xpath in (
        './/*[contains(@class,"nav-container")]',
        './/*[contains(@class,"toolbar")]',
        './/*[contains(@class,"edit-this-page")]',
    ):
        for node in article.xpath(xpath):
            parent = node.getparent()
            if parent is not None:
                parent.remove(node)
    return lxml_html.tostring(article, encoding="unicode", method="html")


def html_to_gfm(article_html: str, pandoc: str) -> str:
    completed = subprocess.run(
        [pandoc, "-f", "html", "-t", "gfm", "--wrap=none"],
        input=article_html,
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip() + "\n"


def page_title(markdown: str, fallback: str) -> str:
    for line in markdown.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return fallback


def write_page_markdown(component_root: Path, relative_html: str, markdown: str) -> Path:
    md_rel = Path(relative_html).with_suffix(".md")
    out = component_root / "agent" / md_rel
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(markdown, encoding="utf-8")
    return out


def absolute_html_url(relative_html: str) -> str:
    return "{}/{}/latest/{}".format(SITE_URL, COMPONENT, relative_html)


def absolute_md_url(relative_html: str) -> str:
    md_rel = Path(relative_html).with_suffix(".md").as_posix()
    return "{}/{}/latest/agent/{}".format(SITE_URL, COMPONENT, md_rel)


def build_llms_txt(pages: dict[str, str]) -> str:
    lines = [
        "# Cuppa",
        "",
        "> Cuppa is a SCons-based C++ build system. This file indexes agent-oriented",
        "> Markdown derived from the published Antora docs (latest release).",
        ">",
        "> Human HTML docs: {}/{}/latest/".format(SITE_URL, COMPONENT),
        "> Repo coding-agent notes (CI, commits): AGENTS.md in the GitHub repository",
        "> (different audience — not a substitute for this index).",
        "",
    ]
    for section, rels in SECTION_MAP:
        lines.append("## {}".format(section))
        lines.append("")
        for rel in rels:
            if rel not in pages:
                continue
            title = pages[rel]
            lines.append(
                "- [{}]({}): HTML {}".format(
                    title,
                    absolute_md_url(rel),
                    absolute_html_url(rel),
                )
            )
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def build_llms_full(ordered: list[tuple[str, str]]) -> str:
    chunks = []
    for rel, markdown in ordered:
        chunks.append("## Source: {}".format(absolute_html_url(rel)))
        chunks.append("")
        chunks.append(markdown.rstrip())
        chunks.append("")
        chunks.append("---")
        chunks.append("")
    return "\n".join(chunks).rstrip() + "\n"


def generate(site_root: Path, pandoc: str) -> dict:
    component_root = find_component_root(site_root)
    titles: dict[str, str] = {}
    ordered: list[tuple[str, str]] = []
    missing = []
    for rel in CURATED_PAGES:
        page_path = component_root / rel
        if not page_path.is_file():
            missing.append(rel)
            continue
        article = extract_article_html(page_path)
        markdown = html_to_gfm(article, pandoc)
        write_page_markdown(component_root, rel, markdown)
        title = page_title(markdown, Path(rel).stem)
        titles[rel] = title
        ordered.append((rel, markdown))
    if missing and not ordered:
        raise RuntimeError("no curated pages found; missing: {}".format(", ".join(missing)))
    llms_txt = build_llms_txt(titles)
    llms_full = build_llms_full(ordered)
    (site_root / "llms.txt").write_text(llms_txt, encoding="utf-8")
    (site_root / "llms-full.txt").write_text(llms_full, encoding="utf-8")
    return {
        "component_root": str(component_root),
        "pages": len(ordered),
        "missing": missing,
        "llms_txt": str(site_root / "llms.txt"),
        "llms_full": str(site_root / "llms-full.txt"),
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--site-root",
        type=Path,
        default=SITE_ROOT,
        help="Antora output directory (default: _docs_build/site)",
    )
    parser.add_argument(
        "--pandoc",
        default=shutil.which("pandoc") or "pandoc",
        help="pandoc executable",
    )
    args = parser.parse_args(argv)
    if not shutil.which(args.pandoc) and args.pandoc == "pandoc":
        print("cuppa docs generate-llms: pandoc not on PATH", file=sys.stderr)
        return 1
    try:
        info = generate(args.site_root, args.pandoc)
    except (RuntimeError, OSError, subprocess.CalledProcessError) as error:
        print("cuppa docs generate-llms: {}".format(error), file=sys.stderr)
        return 1
    print(
        "Wrote llms.txt / llms-full.txt from {} pages under {}".format(
            info["pages"], info["component_root"]
        )
    )
    if info["missing"]:
        print("Missing curated pages (skipped): {}".format(", ".join(info["missing"])))
    return 0


if __name__ == "__main__":
    sys.exit(main())
