#!/usr/bin/env python3
#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

"""Build std_init_golden.json from a Profiles example build log on stdin."""

from __future__ import print_function

import json
import re
import sys

from cuppa.cpp.profiles_report import parse_profiles_diagnostic

_ANSI_ESCAPE = re.compile( r'\x1b\[[0-9;]*m' )

# Documented Alliance Clang wording (profiles-framework DiagnosticSemaKinds.td).
_SYNTHETIC_LINES = {
    'destroy_uninit': (
        "destroy_rules.cpp:43:17: error: uninitialized storage is destroyed by a "
        "'[[now_uninit]]' function under profile 'std::init'"
    ),
    'double_destroy': (
        "destroy_rules.cpp:57:17: error: storage already destroyed by a "
        "'[[now_uninit]]' function is destroyed again under profile 'std::init'"
    ),
}

_ALTERNATE_KEYS = (
    ( 'uninit_decl', 'union type must be initialized', 'uninit_decl_union' ),
    ( 'uninit_read', 'member ', 'uninit_read_member' ),
    ( 'uninit_read', 'read through', 'uninit_read_through_ref' ),
    ( 'ref_to_uninit', 'marked', 'ref_to_uninit_marked_direction' ),
    ( 'ctor_uninit_member', 'base class', 'ctor_uninit_member_base' ),
)


def _alternate_key( rule_id, line ):
    for expected_rule, needle, key in _ALTERNATE_KEYS:
        if rule_id != expected_rule:
            continue
        if expected_rule == 'ref_to_uninit' and 'must refer' not in line:
            continue
        if needle in line:
            return key
    return None


def main():
    by_rule = {}
    alternates = {}

    for raw_line in sys.stdin:
        line = _ANSI_ESCAPE.sub( '', raw_line ).strip()
        if ': error:' not in line or "under profile 'std::init'" not in line:
            continue
        diagnostic = parse_profiles_diagnostic( line )
        if diagnostic is None:
            continue

        alt_key = _alternate_key( diagnostic.rule_id, line )
        if alt_key is not None:
            alternates.setdefault( alt_key, line )
            continue

        if diagnostic.rule_id not in by_rule:
            by_rule[ diagnostic.rule_id ] = line

    golden = dict( by_rule )
    golden.update( alternates )

    for rule_id, line in _SYNTHETIC_LINES.items():
        golden.setdefault( rule_id, line )

    ordered = {}
    for key in sorted( golden ):
        ordered[ key ] = golden[ key ]

    json.dump( ordered, sys.stdout, indent=2, sort_keys=True )
    sys.stdout.write( '\n' )
    return 0


if __name__ == '__main__':
    sys.exit( main() )
