#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   C++ Profiles violation report — layered parser and inventory
#-------------------------------------------------------------------------------

from cuppa.cpp.profiles_report.classify import classify_rule
from cuppa.cpp.profiles_report.constants import DEFAULT_COMPILER, UNCLASSIFIED_RULE_ID
from cuppa.cpp.profiles_report.inventory import (
    ProfilesInventory,
    ProfilesScopeStack,
    format_capture_summary,
    location_dedupe_key,
    parse_progress_line,
    parse_variant_scope_fields,
    profiles_scope_from_construction_env,
    filter_inventory_for_index,
    normalize_sconscript_path,
    replay_profiles_capture,
)
from cuppa.cpp.profiles_report.types import (
    ProfilesDiagnostic,
    ProfilesLocation,
    ProfilesScope,
    unscoped_profiles_scope,
)
from cuppa.cpp.profiles_report.normalise import normalise_message
from cuppa.cpp.profiles_report.parse import parse_profiles_diagnostic
from cuppa.cpp.profiles_report.parse_clang import (
    parse_clang_profiles_line,
    parse_clang_profiles_line_from_capture,
)

__all__ = [
    'DEFAULT_COMPILER',
    'ProfilesDiagnostic',
    'ProfilesInventory',
    'ProfilesLocation',
    'ProfilesScope',
    'ProfilesScopeStack',
    'UNCLASSIFIED_RULE_ID',
    'classify_rule',
    'filter_inventory_for_index',
    'format_capture_summary',
    'location_dedupe_key',
    'normalise_message',
    'normalize_sconscript_path',
    'parse_clang_profiles_line',
    'parse_clang_profiles_line_from_capture',
    'parse_profiles_diagnostic',
    'parse_progress_line',
    'parse_variant_scope_fields',
    'profiles_scope_from_construction_env',
    'replay_profiles_capture',
    'unscoped_profiles_scope',
]
