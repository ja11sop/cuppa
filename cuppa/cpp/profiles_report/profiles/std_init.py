#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   std::init profile — message classifiers and doc anchors (Clang Alliance prose)
#-------------------------------------------------------------------------------

import re

from cuppa.cpp.profiles_report.constants import UNCLASSIFIED_RULE_ID

PROFILE_NAME = 'std::init'

# P4222 / ProfilesFramework.rst rule ids with observed Clang diagnostic patterns.
_RULE_CLASSIFIERS = (
    (
        re.compile(
            r"^variable '…' must be initialized or marked '…'$"
        ),
        'uninit_decl',
    ),
    (
        re.compile(
            r"^non-local variable '…' requires constant initialization$"
        ),
        'static_runtime_init',
    ),
    (
        re.compile(
            r"^constructor does not initialize member '…'$"
        ),
        'ctor_uninit_member',
    ),
    (
        re.compile(
            r"^constructor does not initialize base class '…'$"
        ),
        'ctor_uninit_member',
    ),
    (
        re.compile(
            r"^pointer to uninitialized memory must be marked '…'$"
        ),
        'ref_to_uninit',
    ),
)

# Documented std::init rules awaiting golden Clang capture (extend classifiers when seen).
DOCUMENTED_RULE_IDS = (
    'uninit_read',
    'destroy_uninit',
)

RULE_DOC_REFERENCES = {
    'uninit_decl': {
        'p4222': 'P4222 §4.1 — uninitialized variables',
        'clang_doc': 'ProfilesFramework.rst — uninit_decl',
    },
    'static_runtime_init': {
        'p4222': 'P4222 — static / constant initialization',
        'clang_doc': 'ProfilesFramework.rst — static_runtime_init',
    },
    'ctor_uninit_member': {
        'p4222': 'P4222 §5.1 — constructor member initialization',
        'clang_doc': 'ProfilesFramework.rst — ctor obligations',
    },
    'ref_to_uninit': {
        'p4222': 'P4222 §4.3 — references / pointers to uninitialized storage',
        'clang_doc': 'ProfilesFramework.rst — ref_to_uninit',
    },
}


def classify( normalised_message ):
    """Map a normalised ``std::init`` diagnostic message to a rule id."""
    for pattern, rule_id in _RULE_CLASSIFIERS:
        if pattern.match( normalised_message ):
            return rule_id
    return UNCLASSIFIED_RULE_ID
