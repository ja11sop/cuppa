#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   C++ LTO policy (--cxx-disable-lto)
#-------------------------------------------------------------------------------

import SCons.Script

from cuppa.colourise import as_info
from cuppa.log import logger

_disable_lto_logged = False


def is_lto_disabled():
    """True when ``--cxx-disable-lto`` was passed on the Cuppa/SCons command line.

    Safe to call during toolchain initialise and from unit tests that never
    registered the option (returns False).
    """
    try:
        return bool( SCons.Script.GetOption( 'cxx_disable_lto' ) )
    except Exception:
        return False


def note_lto_disabled_once():
    global _disable_lto_logged
    if _disable_lto_logged:
        return
    _disable_lto_logged = True
    logger.info(
        "LTO disabled by [{}]: --rel compile/link omit -flto* / -ffat-lto-objects "
        "and LTO-specific archivers (gcc-ar / llvm-ar)".format( as_info( '--cxx-disable-lto' ) )
    )


class CxxDisableLtoMethod:

    @classmethod
    def add_options( cls, add_option ):
        add_option(
            '--cxx-disable-lto',
            dest='cxx_disable_lto',
            action='store_true',
            help="Omit release LTO flags (-flto / -flto=auto / -ffat-lto-objects) from "
                 "compile and link, and do not switch to gcc-ar / llvm-ar. Useful for "
                 "diagnosing --rel incremental rebuilds; --rel still uses -O3 -DNDEBUG",
        )

    @classmethod
    def add_to_env( cls, cuppa_env ):
        # Option-only surface; no env.* method required.
        pass
