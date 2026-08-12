#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

from cuppa.cpp.profiles_report.classify import classify_rule
from cuppa.cpp.profiles_report.constants import DEFAULT_COMPILER
from cuppa.cpp.profiles_report.types import ProfilesDiagnostic
from cuppa.cpp.profiles_report.parse_clang import parse_clang_profiles_line


def parse_profiles_diagnostic( line, compiler=DEFAULT_COMPILER ):
    """Parse one Profiles diagnostic line for ``compiler``, or return ``None``."""
    if compiler != 'clang':
        return None

    parsed = parse_clang_profiles_line( line )
    if parsed is None:
        return None

    rule_id = classify_rule( parsed.profile, parsed.normalised_message )
    return ProfilesDiagnostic(
        path=parsed.path,
        line=parsed.line,
        column=parsed.column,
        message=parsed.message,
        profile=parsed.profile,
        normalised_message=parsed.normalised_message,
        rule_id=rule_id,
    )
