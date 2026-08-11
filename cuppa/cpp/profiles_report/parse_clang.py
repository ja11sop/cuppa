#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   Alliance Clang Profiles diagnostic line shape
#-------------------------------------------------------------------------------

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

_PROFILE_SUFFIX = " under profile '"


def parse_clang_profiles_line( line ):
    """Parse one Clang ``: error: … under profile '…'`` line, or return ``None``."""
    text = line.rstrip( '\r\n' )
    suffix_index = text.rfind( _PROFILE_SUFFIX )
    if suffix_index == -1:
        return None

    profile_end = text.rfind( "'", len( text ) - 1 )
    if profile_end <= suffix_index:
        return None

    profile = text[ suffix_index + len( _PROFILE_SUFFIX ):profile_end ]
    before_profile = text[ :suffix_index ]

    error_marker = ': error: '
    error_index = before_profile.find( error_marker )
    if error_index == -1:
        return None

    message = before_profile[ error_index + len( error_marker ):]
    location_part = before_profile[ :error_index ]

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

    normalised = normalise_message( message )
    return ClangProfilesLine(
        path=path,
        line=line_number,
        column=column,
        message=message,
        profile=profile,
        normalised_message=normalised,
    )
