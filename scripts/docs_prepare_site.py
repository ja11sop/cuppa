#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

"""Prepare Antora content sources for the public multi-version docs site.

Exports the latest release tag's ``docs/`` tree into ``_docs_build/sources/stable``
with ``antora.yml`` rewritten to the settled naming:

* ``version`` — minor line (``1.8`` from ``v1.8.2``)
* ``display_version`` — full SemVer (``1.8.2``)

The current checkout remains the ``next`` (prerelease) source via ``playbook-site.yml``.
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
STABLE_ROOT = REPO_ROOT / "_docs_build" / "sources" / "stable"
TAG_RE = re.compile(r"^v?(\d+)\.(\d+)\.(\d+)$")


def parse_release_tag(tag: str) -> tuple[str, str, str]:
    """Return (tag_with_v, minor_line, display_semver)."""
    raw = tag.strip()
    if not raw:
        raise ValueError("release tag is empty")
    match = TAG_RE.match(raw if raw.startswith("v") else "v" + raw)
    if not match:
        raise ValueError(
            "release tag [{}] must look like v1.8.2 (or 1.8.2)".format(tag)
        )
    major, minor, patch = match.group(1), match.group(2), match.group(3)
    display = "{}.{}.{}".format(major, minor, patch)
    tag_with_v = "v" + display
    return tag_with_v, "{}.{}".format(major, minor), display


def resolve_release_tag(explicit: str | None) -> str:
    if explicit:
        tag_with_v, _, _ = parse_release_tag(explicit)
        return tag_with_v
    env_tag = os.environ.get("CUPPA_DOCS_RELEASE_TAG", "").strip()
    if env_tag:
        tag_with_v, _, _ = parse_release_tag(env_tag)
        return tag_with_v
    # Prefer the newest SemVer tag reachable from this clone.
    completed = subprocess.run(
        ["git", "tag", "-l", "v*"],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    tags = []
    for line in completed.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            tag_with_v, _, display = parse_release_tag(line)
        except ValueError:
            continue
        parts = tuple(int(p) for p in display.split("."))
        tags.append((parts, tag_with_v))
    if not tags:
        raise RuntimeError(
            "no v*.*.* tags found; fetch tags or set CUPPA_DOCS_RELEASE_TAG"
        )
    tags.sort()
    return tags[-1][1]


def rewrite_antora_yml(path: Path, *, version: str, display_version: str) -> None:
    text = path.read_text(encoding="utf-8")
    lines = []
    saw_version = False
    saw_display = False
    saw_prerelease = False
    for line in text.splitlines():
        if re.match(r"^version\s*:", line):
            lines.append("version: '{}'".format(version))
            saw_version = True
            continue
        if re.match(r"^display_version\s*:", line):
            lines.append("display_version: '{}'".format(display_version))
            saw_display = True
            continue
        if re.match(r"^prerelease\s*:", line):
            # Stable must not be a prerelease.
            saw_prerelease = True
            continue
        lines.append(line)
    if not saw_version:
        # Insert after title if present, else after name.
        insert_at = 0
        for index, line in enumerate(lines):
            if line.startswith("title:"):
                insert_at = index + 1
                break
            if line.startswith("name:"):
                insert_at = index + 1
        lines.insert(insert_at, "version: '{}'".format(version))
        insert_at += 1
        lines.insert(insert_at, "display_version: '{}'".format(display_version))
    elif not saw_display:
        for index, line in enumerate(lines):
            if line.startswith("version:"):
                lines.insert(index + 1, "display_version: '{}'".format(display_version))
                break
    if saw_prerelease:
        pass  # already dropped
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _remove_tree(path: Path) -> None:
    if not path.exists():
        return
    for child in sorted(path.rglob("*"), reverse=True):
        if child.is_file() or child.is_symlink():
            child.unlink()
        elif child.is_dir():
            child.rmdir()
    if path.exists():
        path.rmdir()


def export_docs_from_tag(tag: str, destination: Path) -> None:
    _remove_tree(destination)
    destination.mkdir(parents=True, exist_ok=True)
    archive = subprocess.run(
        ["git", "archive", "--format=tar", tag, "docs"],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["tar", "-x", "--strip-components=1", "-C", str(destination)],
        input=archive.stdout,
        check=True,
    )


def make_antora_content_repo(destination: Path) -> None:
    """Antora requires local content sources to be git repositories."""
    git_dir = destination / ".git"
    if git_dir.exists():
        _remove_tree(git_dir)
    subprocess.run(
        ["git", "init", "-q"],
        cwd=destination,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "add", "-A"],
        cwd=destination,
        check=True,
        capture_output=True,
    )
    env = os.environ.copy()
    env.update(
        {
            "GIT_AUTHOR_NAME": "cuppa-docs",
            "GIT_AUTHOR_EMAIL": "docs@cuppa.local",
            "GIT_COMMITTER_NAME": "cuppa-docs",
            "GIT_COMMITTER_EMAIL": "docs@cuppa.local",
        }
    )
    subprocess.run(
        ["git", "commit", "-q", "-m", "stable docs snapshot for Antora"],
        cwd=destination,
        check=True,
        capture_output=True,
        env=env,
    )


def prepare(tag: str | None = None) -> dict:
    tag_with_v, minor, display = parse_release_tag(resolve_release_tag(tag))
    # Ensure the tag object exists locally.
    probe = subprocess.run(
        ["git", "rev-parse", "--verify", "refs/tags/" + tag_with_v],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    if probe.returncode != 0:
        raise RuntimeError(
            "tag [{}] is not in this clone; git fetch --tags first".format(tag_with_v)
        )
    export_docs_from_tag(tag_with_v, STABLE_ROOT)
    rewrite_antora_yml(
        STABLE_ROOT / "antora.yml",
        version=minor,
        display_version=display,
    )
    make_antora_content_repo(STABLE_ROOT)
    return {
        "tag": tag_with_v,
        "version": minor,
        "display_version": display,
        "stable_root": str(STABLE_ROOT),
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--tag",
        help="release tag to export (default: newest v*.*.* tag or CUPPA_DOCS_RELEASE_TAG)",
    )
    args = parser.parse_args(argv)
    try:
        info = prepare(args.tag)
    except (RuntimeError, ValueError) as error:
        print("cuppa docs prepare-site: {}".format(error), file=sys.stderr)
        return 1
    print(
        "Prepared stable docs from {tag} as version={version} display_version={display_version}".format(
            **info
        )
    )
    print("Stable tree: {}".format(info["stable_root"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
