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

# P4222 / ProfilesFramework.rst — order most-specific patterns first.
_RULE_CLASSIFIERS = (
    (
        re.compile(
            r"^storage already destroyed by a '…' function is destroyed again$"
        ),
        'double_destroy',
    ),
    (
        re.compile(
            r"^uninitialized storage is destroyed by a '…' function$"
        ),
        'destroy_uninit',
    ),
    (
        re.compile(
            r"^'…' cannot be applied to variable '…' with static storage duration "
            r"under profile '…'; it is zero-initialized$"
        ),
        'static_marker',
    ),
    (
        re.compile(
            r"^'…' cannot be applied to variable '…' with thread storage duration "
            r"under profile '…'; it is zero-initialized$"
        ),
        'static_marker',
    ),
    (
        re.compile(
            r"^'…' cannot be applied to a pointer under profile '…'; "
            r"initialize the pointer \(for example to '…'\)$"
        ),
        'pointer_marker',
    ),
    (
        re.compile(
            r"^'…' cannot be applied to a variable of union type$"
        ),
        'union_marker',
    ),
    (
        re.compile(
            r"^'…' cannot be applied to a union member$"
        ),
        'union_marker',
    ),
    (
        re.compile(
            r"^'…' cannot be applied to a data member of union type$"
        ),
        'union_marker',
    ),
    (
        re.compile(
            r"^variable '…' cannot be both '…' and have an initializer$"
        ),
        'uninit_with_initializer',
    ),
    (
        re.compile(
            r"^member '…' cannot be both '…' and have an initializer$"
        ),
        'uninit_with_initializer',
    ),
    (
        re.compile(
            r"^variable '…' cannot be marked '…'; "
            r"default-initialization of its type '…' does not leave it uninitialized$"
        ),
        'uninit_with_initializer',
    ),
    (
        re.compile(
            r"^member '…' cannot be marked '…'; "
            r"default-initialization of its type '…' does not leave it uninitialized$"
        ),
        'uninit_with_initializer',
    ),
    (
        re.compile(
            r"^writing a member of an '…' object does not initialize it under profile '…'; "
            r"initialize the whole object$"
        ),
        'uninit_write',
    ),
    (
        re.compile(
            r"^writing an element of an '…' object does not initialize it under profile '…'; "
            r"initialize the whole object$"
        ),
        'uninit_write',
    ),
    (
        re.compile(
            r"^writing a member of uninitialized storage reached through a '…' pointer or "
            r"reference does not initialize it under profile '…'; initialize the whole object$"
        ),
        'uninit_write',
    ),
    (
        re.compile(
            r"^writing an element of uninitialized storage reached through a '…' pointer or "
            r"reference does not initialize it under profile '…'; initialize the whole object$"
        ),
        'uninit_write',
    ),
    (
        re.compile(
            r"^read through a '…' pointer or reference accesses uninitialized memory$"
        ),
        'uninit_read',
    ),
    (
        re.compile(
            r"^read of a subobject of an '…' object accesses uninitialized memory$"
        ),
        'uninit_read',
    ),
    (
        re.compile(
            r"^variable '…' is read before initialization$"
        ),
        'uninit_read',
    ),
    (
        re.compile(
            r"^member '…' is read before initialization$"
        ),
        'uninit_read',
    ),
    (
        re.compile(
            r"^pointer marked '…' must refer to uninitialized memory$"
        ),
        'ref_to_uninit',
    ),
    (
        re.compile(
            r"^reference marked '…' must refer to uninitialized memory$"
        ),
        'ref_to_uninit',
    ),
    (
        re.compile(
            r"^pointer to uninitialized memory must be marked '…'$"
        ),
        'ref_to_uninit',
    ),
    (
        re.compile(
            r"^reference to uninitialized memory must be marked '…'$"
        ),
        'ref_to_uninit',
    ),
    (
        re.compile(
            r"^constructor does not initialize base class '…'$"
        ),
        'ctor_uninit_member',
    ),
    (
        re.compile(
            r"^constructor does not initialize member '…'$"
        ),
        'ctor_uninit_member',
    ),
    (
        re.compile(
            r"^constructor does not initialize any member of the anonymous union$"
        ),
        'ctor_uninit_member',
    ),
    (
        re.compile(
            r"^non-local variable '…' requires constant initialization$"
        ),
        'static_runtime_init',
    ),
    (
        re.compile(
            r"^variable '…' of union type must be initialized$"
        ),
        'uninit_decl',
    ),
    (
        re.compile(
            r"^anonymous union must be initialized; give one member a default member initializer$"
        ),
        'uninit_decl',
    ),
    (
        re.compile(
            r"^variable '…' must be initialized or marked '…'$"
        ),
        'uninit_decl',
    ),
)

# Documented rules whose example patterns are not yet emitted by every Profiles Clang snapshot.
DOCUMENTED_RULE_IDS_AWAITING_LIVE_CAPTURE = (
    'destroy_uninit',
    'double_destroy',
)

RULE_DOC_REFERENCES = {
    'uninit_decl': {
        'p4222': 'P4222 §4.1 — uninitialized variables',
        'clang_doc': 'ProfilesFramework.rst — uninit_decl',
    },
    'uninit_read': {
        'p4222': 'P4222 §4.5 — reads of uninitialized storage',
        'clang_doc': 'ProfilesFramework.rst — uninit_read',
    },
    'uninit_write': {
        'p4222': 'P4222 §4.6 — subobject writes',
        'clang_doc': 'ProfilesFramework.rst — uninit_write',
    },
    'ref_to_uninit': {
        'p4222': 'P4222 §4.3 — references / pointers to uninitialized storage',
        'clang_doc': 'ProfilesFramework.rst — ref_to_uninit',
    },
    'double_destroy': {
        'p4222': 'P4222 §4.4 — double destruction',
        'clang_doc': 'ProfilesFramework.rst — double_destroy',
    },
    'destroy_uninit': {
        'p4222': 'P4222 §4.4 — destroy of uninitialized storage',
        'clang_doc': 'ProfilesFramework.rst — destroy_uninit',
    },
    'ctor_uninit_member': {
        'p4222': 'P4222 §5.1 — constructor member initialization',
        'clang_doc': 'ProfilesFramework.rst — ctor_uninit_member',
    },
    'static_runtime_init': {
        'p4222': 'P4222 §5.4 — static / constant initialization',
        'clang_doc': 'ProfilesFramework.rst — static_runtime_init',
    },
    'uninit_with_initializer': {
        'p4222': 'P4222 §4.2 / §5.3 — [[uninit]] with an initializer',
        'clang_doc': 'ProfilesFramework.rst — uninit_with_initializer',
    },
    'pointer_marker': {
        'p4222': 'P4222 §4.3 — [[uninit]] on pointers',
        'clang_doc': 'ProfilesFramework.rst — pointer_marker',
    },
    'union_marker': {
        'p4222': 'P4222 §5.6 — [[uninit]] on unions',
        'clang_doc': 'ProfilesFramework.rst — union_marker',
    },
    'static_marker': {
        'p4222': 'P4222 §4.2 — [[uninit]] on static / thread storage',
        'clang_doc': 'ProfilesFramework.rst — static_marker',
    },
}


def classify( normalised_message ):
    """Map a normalised ``std::init`` diagnostic message to a rule id."""
    for pattern, rule_id in _RULE_CLASSIFIERS:
        if pattern.match( normalised_message ):
            return rule_id
    return UNCLASSIFIED_RULE_ID
