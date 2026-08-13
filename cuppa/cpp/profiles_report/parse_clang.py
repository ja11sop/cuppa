#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   Alliance Clang Profiles diagnostic line shape
#-------------------------------------------------------------------------------

import re

from collections import namedtuple

from cuppa.cpp.profiles_report.normalise import normalise_message

ClangProfilesLine = namedtuple(
    'ClangProfilesLine',
    [
        'path',
        'line',
        'column',
        'message',
        'profile',
        'normalised_message',
    ],
)

# Profile name appears either as a line suffix or inside the message (before ';').
_PROFILE_IN_MESSAGE = re.compile(
    r" under profile '([^']+)'(?:$|;)",
)

# Capture replay only: find embedded ``path:line:column: error:`` when parallel
# ``tee`` output interleaves source-context rows with diagnostics on one line.
_CLANG_ERROR_LOCATION_RE = re.compile(
    r'(?P<path>'
    r'(?:'
    r'/[^\s:]+'
    r'|(?:\.\./)+[^\s:]+'
    r'|\./[^\s:]+'
    r'|[^\s:/|[\]][^\s:]+'
    r')'
    r'\.(?:hpp|cpp|h|c|cc|cxx|ixx|ipp|tpp|c\+\+)'
    r')'
    r':(?P<line>\d+):(?P<column>\d+): error: ',
)

_ERROR_MARKER = ': error: '


def _is_plausible_source_path( path ):
    if not path or len( path ) > 4096:
        return False
    if ' | ' in path:
        return False
    return True


def _find_clang_error_location_simple( text ):
    """Parse the leading ``path:line:column: error:`` on a normal Clang line."""
    error_index = text.find( _ERROR_MARKER )
    if error_index == -1:
        return None

    location_part = text[ :error_index ]
    column_index = location_part.rfind( ':' )
    if column_index == -1:
        return None
    try:
        column = int( location_part[ column_index + 1: ] )
    except ValueError:
        return None

    rest = location_part[ :column_index ]
    line_index = rest.rfind( ':' )
    if line_index == -1:
        return None
    try:
        line_number = int( rest[ line_index + 1: ] )
    except ValueError:
        return None

    path = rest[ :line_index ]
    if not path:
        return None

    return path, line_number, column, error_index + len( _ERROR_MARKER )


def _find_clang_error_location_embedded( text ):
    """Scan for the rightmost plausible ``path:line:column: error:`` suffix."""
    matches = [
        match
        for match in _CLANG_ERROR_LOCATION_RE.finditer( text )
        if _is_plausible_source_path( match.group( 'path' ) )
    ]
    if not matches:
        return None

    match = matches[ -1 ]
    return (
        match.group( 'path' ),
        int( match.group( 'line' ) ),
        int( match.group( 'column' ) ),
        match.end(),
    )


def _parse_clang_profiles_line( text, find_location ):
    location = find_location( text )
    if location is None:
        return None

    path, line_number, column, message_start = location
    if not _is_plausible_source_path( path ):
        return None

    message = text[ message_start:]

    profile_matches = list( _PROFILE_IN_MESSAGE.finditer( message ) )
    if not profile_matches:
        return None

    profile_match = profile_matches[ -1 ]
    profile = profile_match.group( 1 )
    if profile_match.end() == len( message ):
        message = message[ :profile_match.start() ].rstrip()

    normalised = normalise_message( message )
    return ClangProfilesLine(
        path=path,
        line=line_number,
        column=column,
        message=message,
        profile=profile,
        normalised_message=normalised,
    )


def parse_clang_profiles_line( line ):
    """Parse one Clang Profiles diagnostic from live per-spawn compiler output."""
    text = line.rstrip( '\r\n' )
    return _parse_clang_profiles_line( text, _find_clang_error_location_simple )


def parse_clang_profiles_line_from_capture( line ):
    """Parse one Profiles diagnostic from saved build capture text.

    Uses the fast leading-location parser for normal lines, then falls back to
    embedded-location scanning for interleaved parallel ``tee`` rows.
    """
    text = line.rstrip( '\r\n' )
    parsed = _parse_clang_profiles_line( text, _find_clang_error_location_simple )
    if parsed is not None:
        return parsed
    return _parse_clang_profiles_line( text, _find_clang_error_location_embedded )
