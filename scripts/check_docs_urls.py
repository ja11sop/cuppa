#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

"""Docs URL integrity: versioned site paths must not rot to versionless /cuppa/….

    python -m scripts.check_docs_urls
    python -m scripts.check_docs_urls --built-site _docs_build/site

After ``latest_version_segment: latest``, absolute and supplemental-UI links of the form
``…/cuppa/contributing.html`` 404; they must be ``…/cuppa/latest/…`` (or ``…/cuppa/next/…``
for intentional prerelease pointers). This check runs from unit tests, ``check_release``,
and the documentation workflow.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]

# Absolute product-docs URLs in tracked Markdown (README, AGENTS, …).
ABSOLUTE_VERSIONLESS = re.compile(
    r"https://ja11sop\.github\.io/cuppa/cuppa/(?!latest/|next/)([^\s\)\"']+)"
)

# Supplemental UI header: {{{siteRootPath}}}/cuppa/<page> without latest/.
HEADER_VERSIONLESS = re.compile(
    r"\{\{\{siteRootPath\}\}\}/cuppa/(?!latest/)([^\"'\s]+)"
)

# Built multi-version site: from …/cuppa/latest/…, ../../cuppa/foo.html is versionless.
BUILT_NAVBAR_VERSIONLESS = re.compile(
    r"""href=["']\.\./\.\./cuppa/(?!latest/|next/)([^"']+)["']"""
)


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def check_header_partial(text: str, *, label: str) -> list[str]:
    found = []
    for match in HEADER_VERSIONLESS.finditer(text):
        found.append(
            "{}: versionless docs href …/cuppa/{} "
            "(use …/cuppa/latest/… after latest_version_segment)".format(
                label, match.group(1)
            )
        )
    return found


def check_markdown_absolute_urls(text: str, *, label: str) -> list[str]:
    found = []
    for match in ABSOLUTE_VERSIONLESS.finditer(text):
        found.append(
            "{}: versionless absolute URL …/cuppa/{} "
            "(use …/cuppa/latest/… or …/cuppa/next/…)".format(label, match.group(1))
        )
    return found


def check_built_site(site_root: Path) -> list[str]:
    if not site_root.is_dir():
        return ["built site [{}] does not exist".format(site_root)]
    found = []
    # Sample pages under the latest (or sole) component tree.
    html_files = sorted(site_root.rglob("*.html"))
    if not html_files:
        return ["built site [{}] has no HTML files".format(site_root)]
    for path in html_files:
        try:
            relative = path.relative_to(site_root).as_posix()
        except ValueError:
            relative = str(path)
        text = _read(path)
        for match in BUILT_NAVBAR_VERSIONLESS.finditer(text):
            found.append(
                "{}: navbar/versionless href ../../cuppa/{} "
                "(supplemental-ui must use /cuppa/latest/…)".format(
                    relative, match.group(1)
                )
            )
            # One hit per file is enough to fail loudly without flooding.
            break
    return found


def check_sources(repo_root: Path | None = None) -> list[str]:
    root = repo_root or REPO_ROOT
    found = []
    header = root / "docs" / "supplemental-ui" / "partials" / "header-content.hbs"
    if header.is_file():
        found.extend(
            check_header_partial(_read(header), label=str(header.relative_to(root)))
        )
    else:
        found.append("missing {}".format(header.relative_to(root)))

    for relative in ("README.md", "AGENTS.md"):
        path = root / relative
        if path.is_file():
            found.extend(
                check_markdown_absolute_urls(
                    _read(path), label=relative
                )
            )
    return found


def check(
    *,
    repo_root: Path | None = None,
    built_site: Path | None = None,
) -> list[str]:
    found = check_sources(repo_root)
    if built_site is not None:
        found.extend(check_built_site(built_site))
    return found


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--built-site",
        type=Path,
        help="Also scan Antora HTML under this directory (e.g. _docs_build/site)",
    )
    args = parser.parse_args(argv)
    found = check(built_site=args.built_site)
    if found:
        print("Docs URL integrity check failed:")
        for problem in found:
            print("  - {}".format(problem))
        return 1
    print("Docs URL integrity check passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
