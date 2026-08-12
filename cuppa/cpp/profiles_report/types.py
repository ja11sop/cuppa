#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

from collections import namedtuple

ProfilesScope = namedtuple(
    'ProfilesScope',
    [ 'sconscript', 'variant_dir', 'toolchain', 'variant_label' ],
)

ProfilesDiagnostic = namedtuple(
    'ProfilesDiagnostic',
    [
        'path',
        'line',
        'column',
        'message',
        'profile',
        'normalised_message',
        'rule_id',
    ],
)

ProfilesLocation = namedtuple(
    'ProfilesLocation',
    [
        'scope',
        'path',
        'line',
        'column',
        'profile',
        'normalised_message',
        'rule_id',
        'reference_count',
        'raw_message',
    ],
)

_UNSCOPED = ProfilesScope(
    sconscript='_unscoped',
    variant_dir='_unscoped',
    toolchain='_unscoped',
    variant_label='_unscoped',
)


def unscoped_profiles_scope():
    """Return the fallback scope when spawn or Progress attribution is unknown."""
    return _UNSCOPED
