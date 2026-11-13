#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

"""``--deep-clean`` modifier on ``-c`` / ``--clean``.

Expands out-of-tree / native product clean for the current selection. Does not
delete dependency extracts. See ``design/archive/deep-clean.md``.
"""

from __future__ import annotations


def _env_mapping_get( env, key ):
    getter = getattr( env, 'get', None )
    if callable( getter ):
        try:
            return getter( key )
        except Exception:
            return None
    return None


def deep_clean_requested( env ) -> bool:
    """True when the ``--deep-clean`` option is set (before the clean gate)."""
    if env is None:
        return False
    if _env_mapping_get( env, 'deep_clean' ):
        return True
    getter = getattr( env, 'get_option', None )
    if callable( getter ):
        try:
            return bool( getter( 'deep-clean' ) )
        except Exception:
            return False
    return False


def deep_clean_enabled( env ) -> bool:
    """True when builders should expand clean under ``-c --deep-clean``.

    False unless clean mode is active **and** ``--deep-clean`` was accepted
    (the refusal gate rejects ``--deep-clean`` alone).
    """
    if not deep_clean_requested( env ):
        return False
    if _env_mapping_get( env, 'clean' ):
        return True
    getter = getattr( env, 'get_option', None )
    if callable( getter ):
        try:
            return bool( getter( 'clean' ) )
        except Exception:
            return False
    return False


def add_deep_clean_option( add_option ):
    add_option(
            '--deep-clean',
            dest='deep-clean',
            action='store_true',
            help=(
                    "With -c / --clean, also clean out-of-tree products for the "
                    "current selection (cooperative Boost.Build b2 --clean; "
                    "CMake cmake --build --target clean). Requires -c; does "
                    "not delete dependency extracts (use "
                    "--remove-dependencies / purge / wipe)"
            ),
    )


def check_deep_clean_options( env ):
    """Refuse ``--deep-clean`` without ``-c`` / ``--clean``."""
    if not deep_clean_requested( env ):
        return
    cleaning = bool( env.get( 'clean' ) )
    if not cleaning:
        getter = getattr( env, 'get_option', None )
        if callable( getter ):
            try:
                cleaning = bool( getter( 'clean' ) )
            except Exception:
                cleaning = False
    if cleaning:
        return

    from cuppa.colourise import as_error
    from cuppa.utility.console_errors import raise_options_error, remedy_colour

    raise_options_error(
            "--deep-clean requires -c / --clean",
            [
                    (
                            "--deep-clean is a modifier on clean; alone there "
                            "is nothing to deepen",
                            as_error,
                    ),
                    (
                            "Pass -c --deep-clean (or --clean --deep-clean)",
                            remedy_colour,
                    ),
            ],
            "Invalid option (--deep-clean without -c / --clean)",
    )
