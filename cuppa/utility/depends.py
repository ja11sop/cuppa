#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

"""Helpers for run/test dependency (Depends) node lists."""

from SCons.Script import Flatten


def with_depends( source, *depends_groups ):
    """
    Flatten ``source`` with any non-empty depends groups.

    Used when methods accept both a preferred name and a legacy alias
    (for example ``depends_on`` and ``data``); all non-empty groups merge.
    """
    extras = [ group for group in depends_groups if group ]
    if not extras:
        return source
    if source is None or source == []:
        return Flatten( extras )
    return Flatten( [ source ] + extras )


def merge_depends( *depends_groups ):
    """Merge non-empty depends groups into one list, or ``None`` if none given."""
    return with_depends( None, *depends_groups )
