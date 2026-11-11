#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

"""Fail if changed public prose contains private consumer names or home paths.

**Required before every ``git commit`` and ``git push``** (see ``AGENTS.md`` Hard
rules). Prefer ``python -m scripts.local_gate --unit`` so this check runs first;
a maintainer go-ahead to commit/push does not waive a clean run. Pass ``--file``
for PR bodies before ``create-pr``.

When ``design/INTERNAL_PROJECTS.local.md`` is present (gitignored), extract a
denylist from **Real** / **Private** table columns and scan files changed
relative to ``origin/master`` (or ``master``). Without the map, still forbid
personal ``/home/<user>/`` paths other than the documented ``/home/user/``
placeholder.

    python -m scripts.check_public_prose
    python -m scripts.check_public_prose --file /tmp/pr.md

Exit 0 when clean or when there is nothing to scan; 1 on hits; 2 on usage error.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path( __file__ ).resolve().parents[1]
LOCAL_MAP = REPO_ROOT / 'design' / 'INTERNAL_PROJECTS.local.md'

_SKIP_NAME_SUFFIXES = (
        '/INTERNAL_PROJECTS.local.md',
        '.local.md',
)
_SKIP_DIR_PARTS = (
        '/.git/',
        '/venv/',
        '/__pycache__/',
        '/.pytest_cache/',
)

# Placeholders and public OSS names that may appear in Real columns.
_ALLOW_TOKENS = frozenset( {
        'widget',
        'gizmo',
        'sample_pkg',
        'other_pkg',
        'project',
        'boost',
        'abseil',
        'protobuf',
        'grpc',
        'google_cloud_cpp',
        'google-cloud-cpp',
        'gitlab.example',
        '/home/user/...',
        '/home/<user>/...',
} )

_HOME_RE = re.compile( r'/home/(?!user(?:/|\b))([A-Za-z0-9._-]+)/' )
_BACKTICK_RE = re.compile( r'`([^`]+)`' )
_TABLE_ROW_RE = re.compile( r'^\|' )
_PROSE_SUFFIXES = (
        '.md', '.adoc', '.rst', '.txt', '.py', '.yml', '.yaml',
)
_GENERIC_SEGMENTS = frozenset( {
        'coding', 'packages', 'include', 'sconstruct', 'sconscript',
        'publishers', 'home', 'user', '...',
} )


def _git( *args: str ) -> str:
    try:
        completed = subprocess.run(
                [ 'git', *args ],
                cwd=str( REPO_ROOT ),
                check=False,
                capture_output=True,
                text=True,
        )
    except OSError:
        return ''
    if completed.returncode != 0:
        return ''
    return completed.stdout


def merge_base_ref() -> str | None:
    for candidate in ( 'origin/master', 'master' ):
        base = _git( 'merge-base', 'HEAD', candidate ).strip()
        if base:
            return base
    return None


def changed_paths( *, base: str | None ) -> list[Path]:
    names: set[str] = set()
    if base:
        for line in _git( 'diff', '--name-only', '{}...HEAD'.format( base ) ).splitlines():
            if line.strip():
                names.add( line.strip() )
        for line in _git( 'diff', '--name-only', base ).splitlines():
            if line.strip():
                names.add( line.strip() )
    for line in _git( 'diff', '--name-only' ).splitlines():
        if line.strip():
            names.add( line.strip() )
    for line in _git( 'diff', '--name-only', '--cached' ).splitlines():
        if line.strip():
            names.add( line.strip() )
    paths = []
    for name in sorted( names ):
        path = REPO_ROOT / name
        if not path.is_file():
            continue
        if not _should_scan_path( path ):
            continue
        paths.append( path )
    return paths


def _should_scan_path( path: Path ) -> bool:
    text = str( path ).replace( '\\', '/' )
    for part in _SKIP_DIR_PARTS:
        if part in text:
            return False
    for suffix in _SKIP_NAME_SUFFIXES:
        if text.endswith( suffix ):
            return False
    if path.suffix.lower() not in _PROSE_SUFFIXES:
        return False
    return True


def _split_table_cells( line: str ) -> list[str]:
    raw = line.strip()
    if not raw.startswith( '|' ):
        return []
    parts = raw.split( '|' )
    # Leading/trailing empties from edge pipes.
    if parts and parts[0].strip() == '':
        parts = parts[1:]
    if parts and parts[-1].strip() == '':
        parts = parts[:-1]
    return [ part.strip() for part in parts ]


def _is_separator_row( cells: list[str] ) -> bool:
    if not cells:
        return False
    for cell in cells:
        cleaned = cell.replace( ':', '' ).replace( '-', '' ).strip()
        if cleaned:
            return False
    return True


def _real_column_indexes( headers: list[str] ) -> list[int]:
    indexes = []
    for index, header in enumerate( headers ):
        lowered = header.lower()
        if 'real' in lowered or 'private' in lowered:
            indexes.append( index )
    return indexes


def _tokens_from_cell( cell: str ) -> set[str]:
    found: set[str] = set()
    spans = _BACKTICK_RE.findall( cell )
    if not spans:
        # Non-backtick private phrasing (e.g. "Cedar style").
        text = cell.strip()
        if not text or text.startswith( 'http' ) or text.startswith( '(' ):
            return found
        if ' ' not in text:
            if len( text ) >= 4 and text.lower() not in _ALLOW_TOKENS:
                found.add( text )
        elif len( text ) >= 6 and any( ch.isupper() for ch in text ):
            found.add( text )
        return found

    for raw in spans:
        raw = raw.strip()
        if not raw or raw.startswith( 'http' ):
            continue
        if raw.lower() in _ALLOW_TOKENS:
            continue
        if raw.startswith( '~/_cuppa' ) or raw.startswith( '~/.cuppa' ):
            continue

        # Whole span when it is a private id or org/name (not a home/~ path).
        if not raw.startswith( '~' ) and not raw.startswith( '/' ):
            if ' ' not in raw and len( raw ) >= 4:
                found.add( raw )

        path_body = raw
        if path_body.startswith( '~/' ):
            path_body = path_body[2:]
        if path_body.startswith( '/home/' ):
            # Username is covered by the always-on /home/ rule; keep the rest.
            parts = path_body.split( '/' )
            path_body = '/'.join( parts[3:] ) if len( parts ) > 3 else ''

        segments = [ seg for seg in re.split( r'[/\\]+', path_body ) if seg ]
        marked: list[str] = []
        for segment in segments:
            segment = segment.strip()
            if len( segment ) < 4:
                if segment and segment not in _GENERIC_SEGMENTS:
                    marked.append( segment )
                continue
            if segment.lower() in _ALLOW_TOKENS or segment in _GENERIC_SEGMENTS:
                continue
            if segment.startswith( '<' ) and segment.endswith( '>' ):
                continue
            marked.append( segment )
            # Bare path segments only when they look project-like.
            if '_' in segment or '-' in segment:
                found.add( segment )

        if len( marked ) >= 2:
            left, right = marked[-2], marked[-1]
            if left not in _GENERIC_SEGMENTS:
                found.add( '{}/{}'.format( left, right ) )
    return found


def tokens_from_local_map( map_path: Path ) -> list[str]:
    """Pull private identifiers from Real/Private columns in the local map."""
    if not map_path.is_file():
        return []
    try:
        body = map_path.read_text( encoding='utf-8' )
    except OSError:
        return []

    found: set[str] = set()
    headers: list[str] | None = None
    real_indexes: list[int] = []

    for line in body.splitlines():
        if not _TABLE_ROW_RE.match( line ):
            headers = None
            real_indexes = []
            continue
        cells = _split_table_cells( line )
        if not cells:
            continue
        if _is_separator_row( cells ):
            continue
        if headers is None:
            headers = cells
            real_indexes = _real_column_indexes( headers )
            continue
        if not real_indexes:
            continue
        for index in real_indexes:
            if index >= len( cells ):
                continue
            found.update( _tokens_from_cell( cells[index] ) )

    # Drop allowlisted and too-generic leftovers.
    cleaned = []
    for token in found:
        if token.lower() in _ALLOW_TOKENS:
            continue
        if token in _GENERIC_SEGMENTS:
            continue
        if len( token ) < 4:
            continue
        cleaned.append( token )
    return sorted( cleaned, key=len, reverse=True )


def find_hits( text: str, tokens: list[str] ) -> list[str]:
    hits = []
    for match in _HOME_RE.finditer( text ):
        hits.append( '/home/{}/'.format( match.group( 1 ) ) )
    for token in tokens:
        if token in text:
            hits.append( token )
    seen = set()
    ordered = []
    for hit in hits:
        if hit not in seen:
            seen.add( hit )
            ordered.append( hit )
    return ordered


def scan_file( path: Path, tokens: list[str] ) -> list[tuple[int, str, str]]:
    try:
        lines = path.read_text( encoding='utf-8', errors='replace' ).splitlines()
    except OSError as error:
        return [ ( 0, str( path ), 'unreadable: {}'.format( error ) ) ]
    findings = []
    for number, line in enumerate( lines, 1 ):
        for hit in find_hits( line, tokens ):
            findings.append( ( number, hit, line.strip()[:120] ) )
    return findings


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
            description=(
                    'Scan changed public prose for private consumer names '
                    '(from INTERNAL_PROJECTS.local.md) and personal home paths.'
            ),
    )
    parser.add_argument(
            '--file',
            action='append',
            default=[],
            metavar='PATH',
            help='Extra file to scan (e.g. a PR body). Repeatable.',
    )
    parser.add_argument(
            '--all-tracked',
            action='store_true',
            help='Scan every tracked prose file (noisy; for audits).',
    )
    return parser


def main( argv: list[str] | None = None ) -> int:
    args = build_parser().parse_args( argv )
    tokens = tokens_from_local_map( LOCAL_MAP )
    paths: list[Path] = []
    if args.all_tracked:
        listed = _git( 'ls-files' ).splitlines()
        for name in listed:
            path = REPO_ROOT / name
            if path.is_file() and _should_scan_path( path ):
                paths.append( path )
    else:
        paths = changed_paths( base=merge_base_ref() )
    for extra in args.file:
        path = Path( extra ).expanduser()
        if not path.is_file():
            print(
                    'check_public_prose: not a file: {}'.format( path ),
                    file=sys.stderr,
            )
            return 2
        paths.append( path.resolve() )

    # Deduplicate while preserving order.
    unique_paths = []
    seen_paths = set()
    for path in paths:
        key = str( path )
        if key in seen_paths:
            continue
        seen_paths.add( key )
        unique_paths.append( path )
    paths = unique_paths

    if not paths:
        if not LOCAL_MAP.is_file():
            print(
                    'check_public_prose: no local map and no changed prose; ok'
            )
        else:
            print( 'check_public_prose: no changed prose to scan; ok' )
        return 0

    if not LOCAL_MAP.is_file():
        try:
            map_display = LOCAL_MAP.relative_to( REPO_ROOT )
        except ValueError:
            map_display = LOCAL_MAP
        print(
                'check_public_prose: {} absent — checking personal /home/ '
                'paths only'.format( map_display )
        )
    else:
        print(
                'check_public_prose: {} denylist token(s) from local map; '
                'scanning {} file(s)'.format( len( tokens ), len( paths ) )
        )

    failed = False
    for path in paths:
        findings = scan_file( path, tokens )
        if not findings:
            continue
        failed = True
        try:
            display = path.relative_to( REPO_ROOT )
        except ValueError:
            display = path
        for number, hit, snippet in findings:
            where = '{}:{}'.format( display, number ) if number else str( display )
            print(
                    'check_public_prose: {} matches [{}] — {}'.format(
                            where, hit, snippet
                    ),
                    file=sys.stderr,
            )

    if failed:
        print(
                'check_public_prose: use project labels / widget / gitlab.example '
                '/ /home/user/... — see AGENTS.md Hard rules',
                file=sys.stderr,
        )
        return 1
    print( 'check_public_prose: ok' )
    return 0


if __name__ == '__main__':
    sys.exit( main() )
