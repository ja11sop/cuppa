#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   entry_points — pkg_resources-free entry point iteration
#-------------------------------------------------------------------------------
#
# setuptools >= 82 removed pkg_resources. Prefer importlib.metadata.


def iter_entry_points( group, name=None ):
    """Yield entry points for ``group``, optionally filtered by ``name``.

    Compatible with ``pkg_resources.iter_entry_points(group=..., name=...)``.
    Each yielded object supports ``.load()`` like setuptools entry points.
    """
    try:
        from importlib.metadata import entry_points
    except ImportError:  # pragma: no cover - Python < 3.8
        try:
            from importlib_metadata import entry_points
        except ImportError:
            from pkg_resources import iter_entry_points as _legacy_iter
            for entry_point in _legacy_iter( group=group, name=name ):
                yield entry_point
            return

    try:
        selected = entry_points( group=group )
    except TypeError:
        # Python 3.8 / 3.9: entry_points() returns a dict-like SelectableGroups
        selected = entry_points().get( group, [] )

    for entry_point in selected:
        if name is None or entry_point.name == name:
            yield entry_point
