#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   Shared dependency tokens — [selector]name[/qualifier] for remove/purge/wipe
#-------------------------------------------------------------------------------

"""Parse and resolve ``[selector]name[/qualifier]`` tokens for dependency management.

See ``design/plans/removal-options.md`` §4.15.
"""

from __future__ import annotations

import fnmatch
import re

from cuppa.core.dependency_storage import normalise_storage_type


# Canonical storage_type → accepted selector spellings (no single-letter forms).
SELECTOR_ALIASES = {
    'archive': (
        'archive', 'source', 'source_archive', 'source-archive', 'sa',
    ),
    'gitlab': (
        'gitlab', 'gitlab_package', 'gitlab-package', 'gl',
    ),
    'repository': (
        'repository', 'repo', 'vcs', 'vcs_dependency', 'repository_dependency',
        'location',  # quiet deprecated alias
    ),
    'conan': (
        'conan', 'conan_package', 'cn',
    ),
    'toolchain': (
        'toolchain', 'toolchains', 'tc', 'compiler',
    ),
}

# Reserved for a future GitHub generic package kind — must not map to gitlab.
RESERVED_SELECTORS = frozenset( { 'gh', 'github', 'github_package', 'github-package' } )

_SELECTOR_RE = re.compile( r'^\[([^\]]+)\](.+)$' )

# Session toolchain id: clang24_profiles_2026_08_07_27 → family + qualifier.
_REGISTERED_TOOLCHAIN_NAME = re.compile(
    r'^(?P<family>clang|gcc|vc)(?P<major>\d+)_(?P<qualifier>.+)$',
    re.IGNORECASE,
)


def _build_selector_lookup():
    lookup = {}
    for canonical, aliases in SELECTOR_ALIASES.items():
        for alias in aliases:
            lookup[alias.lower()] = canonical
    return lookup


_SELECTOR_LOOKUP = _build_selector_lookup()


def known_selector_help():
    """Human-readable alias groups for error messages."""
    parts = []
    for canonical, aliases in SELECTOR_ALIASES.items():
        # Prefer user-facing names; omit quiet location alias from lead list.
        shown = [ a for a in aliases if a != 'location' ]
        parts.append( "{} ({})".format( canonical, ', '.join( shown ) ) )
    return '; '.join( parts )


def resolve_selector( name ):
    """Return canonical storage_type for a selector spelling, or raise ValueError."""
    key = ( name or '' ).strip().lower()
    if not key:
        raise ValueError( "empty selector" )
    if key in RESERVED_SELECTORS:
        raise ValueError(
                "selector [{}] is reserved for a future package kind "
                "(use [gl] / [gitlab] for GitLab packages)".format( name )
        )
    canonical = _SELECTOR_LOOKUP.get( key )
    if not canonical:
        raise ValueError(
                "unknown selector [{}]; known: {}".format( name, known_selector_help() )
        )
    return canonical


def format_token( storage_type, name, qualifier ):
    """Rebuild a display form for error messages."""
    body = name if qualifier is None else "{}/{}".format( name, qualifier )
    if not storage_type:
        return body
    # Prefer a short documented alias for the canonical type.
    short = {
        'archive': 'source',
        'gitlab': 'gl',
        'repository': 'repo',
        'conan': 'conan',
        'toolchain': 'toolchain',
    }.get( storage_type, storage_type )
    return "[{}]{}".format( short, body )


def is_wildcard_pattern( text ):
    return any( char in ( text or '' ) for char in '*?[' )


def parse_dependency_token( token ):
    """Parse one token into ``(storage_type_or_None, name, qualifier_or_None)``.

    Forms:
    - ``name``
    - ``name/qualifier``
    - ``[selector]name``
    - ``[selector]name/qualifier``
    """
    raw = ( token or '' ).strip()
    if not raw:
        return None, "empty dependency token"

    storage_type = None
    rest = raw
    match = _SELECTOR_RE.match( raw )
    if match:
        try:
            storage_type = resolve_selector( match.group( 1 ) )
        except ValueError as error:
            return None, str( error )
        rest = match.group( 2 ).strip()
        if not rest:
            return None, "dependency token [{}] has a selector but no name".format( raw )

    if '/' in rest:
        name, qualifier = rest.split( '/', 1 )
        name = name.strip()
        qualifier = qualifier.strip()
        if not name or not qualifier:
            return None, (
                    "dependency token [{}] must be name/qualifier "
                    "with both sides non-empty".format( raw )
            )
        return ( storage_type, name, qualifier ), None

    name = rest.strip()
    if not name:
        return None, "empty dependency token"
    return ( storage_type, name, None ), None


def parse_dependency_tokens( spec ):
    """Parse a comma-separated token list.

    Returns ``(tokens, error)`` where each token is
    ``(storage_type_or_None, name, qualifier_or_None)``.
    """
    if spec is None:
        return [], "no dependency tokens given"
    if isinstance( spec, ( list, tuple ) ):
        spec = spec[0] if spec else ''
    parts = [ part.strip() for part in str( spec ).split( ',' ) if part.strip() ]
    if not parts:
        return [], "no dependency tokens given"
    tokens = []
    for part in parts:
        parsed, error = parse_dependency_token( part )
        if error:
            return [], error
        tokens.append( parsed )
    return tokens, None


def name_matches( pattern, *candidates ):
    """Case-insensitive exact or fnmatch against any non-empty candidate."""
    want = ( pattern or '' ).strip()
    if not want:
        return False
    names = [ ( c or '' ).strip() for c in candidates if ( c or '' ).strip() ]
    if not names:
        return False
    if is_wildcard_pattern( want ):
        want_l = want.lower()
        return any( fnmatch.fnmatch( name.lower(), want_l ) for name in names )
    want_l = want.lower()
    return any( name.lower() == want_l for name in names )


def row_storage_type( row ):
    value = row.get( 'type' ) or row.get( 'kind' ) or ''
    return normalise_storage_type( value ) or value


def parse_registered_toolchain_name( name ):
    """Split ``clang24_profiles_…`` into ``(family, qualifier)``, or ``None``.

    Accepts the same string users pass to ``--toolchains=`` after an archive fetch.
    Wildcards in the qualifier portion are preserved (``clang24_profiles*``).
    """
    text = ( name or '' ).strip()
    if not text or '/' in text:
        return None
    match = _REGISTERED_TOOLCHAIN_NAME.match( text )
    if not match:
        return None
    return match.group( 'family' ).lower(), match.group( 'qualifier' )


def row_matches_token( row, storage_type, name, qualifier, require_qualifier=False ):
    """Whether a list/download row matches a parsed token."""
    row_type = row_storage_type( row )
    if storage_type and row_type != storage_type:
        return False

    effective_name = name
    effective_qualifier = qualifier
    # Paste-friendly session ids: [toolchain]clang24_profiles_2026_08_07_27
    if effective_qualifier is None:
        registered = parse_registered_toolchain_name( name )
        if registered and ( storage_type == 'toolchain' or row_type == 'toolchain' ):
            if storage_type and storage_type != 'toolchain':
                return False
            if row_type != 'toolchain':
                return False
            effective_name, effective_qualifier = registered

    if effective_qualifier is not None:
        from cuppa.core import dependency_removal
        return dependency_removal._row_matches_force_token(
                row, effective_name, effective_qualifier
        )
    if require_qualifier:
        return False
    return name_matches(
            effective_name,
            row.get( 'short_name' ),
            row.get( 'dependency' ),
            row.get( 'stem' ),
    )
