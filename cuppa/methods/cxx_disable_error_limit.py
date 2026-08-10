#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   C++ diagnostic error-limit disable (--cxx-disable-error-limit)
#-------------------------------------------------------------------------------

from cuppa.colourise import as_notice
from cuppa.log import logger


def activate_disable_error_limit_for_env( env ):
    """Append toolchain flags to report all diagnostics (no early cap)."""
    toolchain = env['toolchain']
    flags = []
    if hasattr( toolchain, 'disable_error_limit_flags' ):
        flags = list( toolchain.disable_error_limit_flags( env ) or [] )
    if flags:
        env.AppendUnique( CXXFLAGS = flags )
        logger.debug(
            "C++ error limit disabled for toolchain [{}]"
            .format( as_notice( toolchain.name() ) )
        )
    return bool( flags )


class CxxDisableErrorLimitMethod:
    """Opt-in removal of the compiler diagnostic cap (``-ferror-limit=0``, etc.)."""

    @classmethod
    def add_options( cls, add_option ):
        add_option(
            '--cxx-disable-error-limit',
            dest='cxx_disable_error_limit',
            action='store_true',
            help='Disable the C++ compiler diagnostic cap so every error is reported '
                 '(Clang -ferror-limit=0, GCC -fmax-errors=0)',
        )

    @classmethod
    def get_options( cls, env ):
        env['cxx_disable_error_limit'] = bool(
                env.get_option( 'cxx_disable_error_limit' )
        )

    def __call__( self, env, enabled=True ):
        env['cxx_disable_error_limit'] = bool( enabled )
        if enabled:
            activate_disable_error_limit_for_env( env )
        return None

    @classmethod
    def add_to_env( cls, cuppa_env ):
        cuppa_env.add_method( 'CxxDisableErrorLimit', cls() )

    @classmethod
    def init_env_for_variant( cls, sconscript_exports ):
        env = sconscript_exports['env']
        if env.get( 'cxx_disable_error_limit' ):
            activate_disable_error_limit_for_env( env )
