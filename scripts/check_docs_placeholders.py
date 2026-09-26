#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

"""Forbid Unicode ellipsis (U+2026) in authored Antora / AGENTS docs.

Console *samples* under ``partials/samples/`` may still contain ``…`` when they
mirror CLI truncation; those files are excluded. Lines that *document* the
forbidden character (mention ``U+2026`` or ``Unicode ellipsis``) are allowed.

    python -m scripts.check_docs_placeholders
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
ELLIPSIS = "\u2026"

# Authored prose only — not generated console fragments.
SCAN_GLOBS = (
    "docs/modules/ROOT/pages/**/*.adoc",
    "docs/modules/ROOT/partials/**/*.adoc",
    "AGENTS.md",
)

EXCLUDE_PARTS = (
    "partials/samples/",
)


def _is_excluded(path: Path, repo_root: Path) -> bool:
    relative = path.relative_to(repo_root).as_posix()
    return any(part in relative for part in EXCLUDE_PARTS)


def _line_documents_forbidden_glyph(line: str) -> bool:
    """True when the line is teaching that U+2026 must not be used."""
    if "U+2026" in line:
        return True
    if "Unicode ellipsis" in line or "unicode ellipsis" in line:
        return True
    # Explicit "do not write …" examples in the style table.
    if "not" in line.lower() and ELLIPSIS in line:
        return True
    return False


def check(repo_root: Path | None = None) -> list[str]:
    root = repo_root or REPO_ROOT
    found: list[str] = []
    seen: set[Path] = set()
    for pattern in SCAN_GLOBS:
        for path in sorted(root.glob(pattern)):
            if not path.is_file() or path in seen:
                continue
            seen.add(path)
            if _is_excluded(path, root):
                continue
            text = path.read_text(encoding="utf-8")
            if ELLIPSIS not in text:
                continue
            relative = path.relative_to(root).as_posix()
            for number, line in enumerate(text.splitlines(), start=1):
                if ELLIPSIS not in line:
                    continue
                if _line_documents_forbidden_glyph(line):
                    continue
                found.append(
                    "{}:{}: Unicode ellipsis (U+2026) — use `...` for omissions "
                    "or `<name>` / `<...>` for placeholders "
                    "(see AGENTS.md Placeholders and omissions)".format(
                        relative, number
                    )
                )
    return found


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args(argv)
    found = check()
    if found:
        print("Docs placeholder check failed:")
        for problem in found:
            print("  - {}".format(problem))
        return 1
    print("Docs placeholder check passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
