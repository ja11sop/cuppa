#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   C++ diagnostic error limit (--cxx-error-limit, --cxx-disable-error-limit, …)
#-------------------------------------------------------------------------------

from cuppa.colourise import as_emphasised, as_notice
from cuppa.log import logger

_inventory_error_limit_logged = False

_BARE_ERROR_LIMIT_FLAGS = frozenset( ( '-ferror-limit', '-fmax-errors' ) )

_ERROR_LIMIT_POLICY_KEYS = (
    'cxx_error_limit',
    'cxx_default_error_limit',
    'cxx_disable_error_limit',
)


def _clear_error_limit_policy_keys( env ):
    """Remove explicit error-limit policy keys so a new choice starts clean."""
    env.pop( 'cxx_error_limit', None )
    env[ 'cxx_default_error_limit' ] = False
    env[ 'cxx_disable_error_limit' ] = False


def _profiles_inventory_active( env ):
    return bool( env.get( 'cxx_profiles_report' ) )


def resolve_effective_error_limit( env ):
    """Return ``None`` (compiler default), ``0`` (unlimited), or a positive cap."""
    if env is None:
        return None
    if env.get( 'cxx_error_limit' ) is not None:
        return int( env[ 'cxx_error_limit' ] )
    if env.get( 'cxx_default_error_limit' ):
        return None
    if env.get( 'cxx_disable_error_limit' ):
        return 0
    if _profiles_inventory_active( env ):
        return 0
    return None


def resolve_effective_error_limit_source( env ):
    """Return ``(limit, source)`` where *source* explains why the limit was chosen."""
    if env is None:
        return None, None
    if env.get( 'cxx_error_limit' ) is not None:
        return int( env[ 'cxx_error_limit' ] ), 'explicit'
    if env.get( 'cxx_default_error_limit' ):
        return None, 'default'
    if env.get( 'cxx_disable_error_limit' ):
        return 0, 'disable'
    if _profiles_inventory_active( env ):
        return 0, 'inventory'
    return None, None


def _toolchain_error_limit_flags( toolchain, env, limit ):
    if hasattr( toolchain, 'error_limit_flags' ):
        return list( toolchain.error_limit_flags( env, limit ) or [] )
    if limit == 0 and hasattr( toolchain, 'disable_error_limit_flags' ):
        return list( toolchain.disable_error_limit_flags( env ) or [] )
    return []


def _error_limit_flag_family( flag ):
    text = str( flag )
    if text.startswith( '-ferror-limit' ):
        return '-ferror-limit'
    if text.startswith( '-fmax-errors' ):
        return '-fmax-errors'
    return None


def _remove_error_limit_from_flags( flags ):
    remove = frozenset( ( '-ferror-limit', '-fmax-errors' ) )
    cleaned = []
    index = 0
    while index < len( flags ):
        flag = flags[ index ]
        family = _error_limit_flag_family( flag )
        if family in remove:
            if str( flag ) in _BARE_ERROR_LIMIT_FLAGS:
                index += 2
            else:
                index += 1
            continue
        cleaned.append( flag )
        index += 1
    return cleaned


def _strip_error_limit_flags( env ):
    """Remove existing ``-ferror-limit`` / ``-fmax-errors`` flags from compile flag lists."""
    for key in ( 'CXXFLAGS', 'CCFLAGS' ):
        if key not in env:
            continue
        env.Replace( **{
            key: _remove_error_limit_from_flags( list( env.get( key ) or [] ) ),
        } )


def apply_error_limit_for_env( env ):
    """Set toolchain CXXFLAGS for the resolved diagnostic error limit."""
    global _inventory_error_limit_logged

    limit, source = resolve_effective_error_limit_source( env )
    if source == 'default':
        _strip_error_limit_flags( env )
        logger.debug(
            'C++ error limit restored to toolchain default (removed cuppa/project '
            'error-limit flags from CXXFLAGS/CCFLAGS)'
        )
        return True

    if limit is None:
        return False

    toolchain = env[ 'toolchain' ]
    flags = _toolchain_error_limit_flags( toolchain, env, limit )
    if not flags:
        logger.warn(
            'C++ error limit {} requested for toolchain [{}] but this toolchain '
            'does not support a diagnostic cap flag'.format(
                limit,
                as_notice( toolchain.name() ),
            ),
        )
        return False

    _strip_error_limit_flags( env )
    env.AppendUnique( CXXFLAGS = flags )
    if source == 'inventory' and not _inventory_error_limit_logged:
        _inventory_error_limit_logged = True
        logger.info(
            'C++ Profiles inventory: unlimited per-TU diagnostic cap implied '
            '(pass {} to keep the compiler default cap)'.format(
                as_emphasised( '--cxx-default-error-limit' ),
            ),
        )
    elif source == 'disable':
        logger.debug(
            "C++ error limit disabled for toolchain [{}]"
            .format( as_notice( toolchain.name() ) )
        )
    elif source == 'explicit':
        logger.debug(
            "C++ error limit set to {} for toolchain [{}]"
            .format( limit, as_notice( toolchain.name() ) )
        )
    return True


def activate_disable_error_limit_for_env( env ):
    """Backward-compatible helper: unlimited diagnostics (``limit=0``)."""
    _clear_error_limit_policy_keys( env )
    env[ 'cxx_disable_error_limit' ] = True
    return apply_error_limit_for_env( env )


def reset_error_limit_state_for_tests():
    """Reset module globals (unit tests only)."""
    global _inventory_error_limit_logged, _options_registered
    _inventory_error_limit_logged = False
    _options_registered = False


_options_registered = False


class CxxErrorLimitMethod:
    """C++ compiler diagnostic cap control (``-ferror-limit``, ``-fmax-errors``, …)."""

    @classmethod
    def add_options( cls, add_option ):
        global _options_registered
        if _options_registered:
            return
        _options_registered = True
        add_option(
            '--cxx-error-limit',
            dest='cxx_error_limit',
            default=None,
            help='Set the C++ compiler diagnostic cap (0 = unlimited; Clang -ferror-limit=N, '
                 'GCC -fmax-errors=N). Overrides Profiles inventory implication and '
                 '--cxx-disable-error-limit',
        )
        add_option(
            '--cxx-default-error-limit',
            dest='cxx_default_error_limit',
            action='store_true',
            help='Use the toolchain default diagnostic cap (no cuppa error-limit flag). '
                 'Overrides unlimited implied by --cxx-profiles-report / '
                 'CollateCxxProfilesIndex()',
        )
        add_option(
            '--cxx-disable-error-limit',
            dest='cxx_disable_error_limit',
            action='store_true',
            help='Disable the C++ compiler diagnostic cap so every error is reported '
                 '(Clang -ferror-limit=0, GCC -fmax-errors=0; shorthand for '
                 '--cxx-error-limit=0 outside Profiles inventory runs)',
        )

    @classmethod
    def get_options( cls, env ):
        raw_limit = env.get_option( 'cxx_error_limit' )
        if raw_limit is not None and raw_limit is not False:
            env[ 'cxx_error_limit' ] = int( raw_limit )
        env[ 'cxx_default_error_limit' ] = bool(
            env.get_option( 'cxx_default_error_limit' )
        )
        env[ 'cxx_disable_error_limit' ] = bool(
            env.get_option( 'cxx_disable_error_limit' )
        )

    def __call__( self, env, limit ):
        """Set an explicit diagnostic cap (``0`` = unlimited)."""
        _clear_error_limit_policy_keys( env )
        env[ 'cxx_error_limit' ] = int( limit )
        apply_error_limit_for_env( env )
        return None

    def default_limit( self, env ):
        """Restore the toolchain default diagnostic cap (strip project flags only)."""
        _clear_error_limit_policy_keys( env )
        env[ 'cxx_default_error_limit' ] = True
        apply_error_limit_for_env( env )
        return None

    def disable_limit( self, env, enabled=True ):
        """Disable the diagnostic cap so every error is reported."""
        if enabled:
            _clear_error_limit_policy_keys( env )
            env[ 'cxx_disable_error_limit' ] = True
            apply_error_limit_for_env( env )
        else:
            env[ 'cxx_disable_error_limit' ] = False
            apply_error_limit_for_env( env )
        return None

    @classmethod
    def add_to_env( cls, cuppa_env ):
        method = cls()
        cuppa_env.add_method( 'CxxErrorLimit', method )
        cuppa_env.add_method( 'CxxDefaultErrorLimit', method.default_limit )
        cuppa_env.add_method( 'CxxDisableErrorLimit', method.disable_limit )

    @classmethod
    def init_env_for_variant( cls, sconscript_exports ):
        apply_error_limit_for_env( sconscript_exports[ 'env' ] )


# Backward-compatible import alias (same class; add_options is idempotent).
CxxDisableErrorLimitMethod = CxxErrorLimitMethod
