#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   C++ modules enablement (--cxx-modules) and C++20 floor
#-------------------------------------------------------------------------------

from cuppa.colourise import as_info, as_notice, as_warning
from cuppa.log import logger


_MODULES_DEPRECATED_CLI = (
        '[{}] is deprecated; use [{}] (removed in cuppa 2.0)'
)
_MODULES_DEPRECATED_METHOD = (
        'env.{}() is deprecated; use env.{}() (removed in cuppa 2.0)'
)


# Ordinal dialect ranks: a later standard always ranks higher. Aliases share a
# rank. Pre-C++11 standards share the lowest rank; the distinction between them
# never matters for a modules floor.
_DIALECT_RANK = {
    'c++98': 3,
    'c++03': 3,
    'c++0x': 11,
    'c++11': 11,
    'c++1y': 14,
    'c++14': 14,
    'c++1z': 17,
    'c++17': 17,
    'c++2a': 20,
    'c++20': 20,
    'c++2b': 23,
    'c++23': 23,
    'c++2c': 26,
    'c++26': 26,
    'c++latest': 26,
}


MODULE_SOURCE_SUFFIXES = [ '.cppm', '.cxxm', '.ccm', '.ixx' ]


def register_module_source_suffixes( env ):
    """Teach SCons Object/SharedObject builders how to compile module interfaces."""
    import SCons.Defaults

    env.AppendUnique( CPPSUFFIXES = MODULE_SOURCE_SUFFIXES )
    static_obj = env['BUILDERS']['Object']
    shared_obj = env['BUILDERS']['SharedObject']
    for suffix in MODULE_SOURCE_SUFFIXES:
        static_obj.add_action( suffix, SCons.Defaults.CXXAction )
        shared_obj.add_action( suffix, SCons.Defaults.ShCXXAction )
        static_obj.add_emitter( suffix, SCons.Defaults.StaticObjectEmitter )
        shared_obj.add_emitter( suffix, SCons.Defaults.SharedObjectEmitter )


def dialect_rank( standard ):
    if not standard:
        return 0
    return _DIALECT_RANK.get( standard, 0 )


def dialect_from_flag( value ):
    """Dialect name from a dialect name or a dialect flag.

    Accepts `c++20`, `-std=c++2c` (GCC / Clang), and `-std:c++latest` (MSVC).
    """
    if not value:
        return None
    text = value.strip()
    for separator in ( '=', ':' ):
        if separator in text:
            text = text.split( separator, 1 )[1].strip()
            break
    return text if text in _DIALECT_RANK else None


def effective_dialect( env ):
    """The dialect this build will actually compile with.

    Returns `( dialect, requested )` where `requested` is True when the dialect
    came from `--stdcpp` / `env.StdCpp()` rather than the toolchain default.
    `env['stdcpp']` is unset unless the dialect was asked for explicitly, so the
    toolchain default has to be consulted before concluding a floor is unmet.
    """
    requested = env.get( 'stdcpp' )
    if requested:
        return requested, True

    toolchain = env.get( 'toolchain' )
    for attribute in ( 'abi', 'abi_flag' ):
        query = getattr( toolchain, attribute, None )
        if not query:
            continue
        try:
            dialect = dialect_from_flag( query( env ) )
        except Exception:
            continue
        if dialect:
            return dialect, False
    return None, False


# Each variant env applies the floor separately, so remember what has been
# reported to keep one message per toolchain and dialect change per build.
_reported_dialect_floors = set()


def _report_dialect_floor_once( toolchain, current, floor ):
    try:
        name = toolchain.name()
    except Exception:
        name = str( toolchain )
    key = ( name, current, floor )
    if key in _reported_dialect_floors:
        return False
    _reported_dialect_floors.add( key )
    return True


def ensure_modules_dialect_floor( env, floor='c++20' ):
    """When modules are enabled, require at least the given dialect floor.

    The toolchain default counts towards the floor: a toolchain that already
    defaults to the floor or later is left alone, so ``--cxx-modules`` never lowers
    the dialect a build would otherwise have used.
    """
    current, requested = effective_dialect( env )
    floor_rank = dialect_rank( floor )
    if dialect_rank( current ) >= floor_rank:
        logger.debug(
            "C++ modules dialect floor {} already met by {}"
            .format( as_info( floor ), as_notice( current ) )
        )
        return current

    toolchain = env['toolchain']
    if _report_dialect_floor_once( toolchain, current, floor ):
        if requested:
            logger.warn(
                "C++ modules require {}+; raising the requested dialect from {} to {}. "
                "Pass --stdcpp={} or later so build paths name the dialect actually used"
                .format( as_info( floor ), as_warning( current ), as_info( floor ), floor )
            )
        else:
            logger.info(
                "C++ modules require {}; setting dialect to it{}"
                .format(
                    as_info( floor ),
                    " (toolchain default is {})".format( as_notice( current ) ) if current else "",
                )
            )
    env['stdcpp'] = floor
    flag = toolchain.stdcpp_flag_for( floor )
    env.ReplaceFlags( [ flag ] )
    return floor


def ensure_import_std_dialect_floor( env ):
    """import std / std.compat require C++23."""
    return ensure_modules_dialect_floor( env, floor='c++23' )


def activate_modules_for_env( env ):
    toolchain = env['toolchain']
    if not toolchain.supports_modules( env ):
        from cuppa.colourise import as_error
        import SCons.Errors
        message = (
            "--cxx-modules requested but toolchain [{}] does not support C++ modules "
            "(Linux/macOS GCC 14+ / Clang 16+, or Windows MSVC toolset 14.2+ "
            "[--toolchains=vc142 / vc143 / vc145 / …] in this cuppa release)"
            .format( toolchain.name() )
        )
        logger.error(
            "--cxx-modules requested but toolchain [{}] does not support C++ modules "
            "(Linux/macOS GCC 14+ / Clang 16+, or Windows MSVC toolset 14.2+ "
            "[--toolchains=vc142 / vc143 / vc145 / …] in this cuppa release)"
            .format( as_error( toolchain.name() ) )
        )
        env['modules'] = False
        raise SCons.Errors.StopError( message )

    env['modules'] = True
    # The dialect floor belongs to the compile that actually builds or consumes a
    # module (see cuppa.cpp.cxx_modules), not to enabling modules for the env.
    register_module_source_suffixes( env )

    from cuppa.cpp.cxx_modules import get_registry, modules_dir
    modules_dir( env )
    get_registry( env )

    if hasattr( toolchain, 'modules_enable_flags' ):
        env.AppendUnique( CXXFLAGS = toolchain.modules_enable_flags( env ) )

    logger.debug(
        "C++ modules active for toolchain [{}]"
        .format( as_notice( toolchain.name() ) )
    )
    return True


class _CxxModulesCallable:
    """Primary ``env.CxxModules()`` toggle."""

    def __call__( self, env, enabled=True ):
        env['modules'] = bool( enabled )
        if enabled:
            activate_modules_for_env( env )
        return None


class _ModulesDeprecatedCallable:
    """Deprecated alias for ``env.Modules()``."""

    def __call__( self, env, enabled=True ):
        logger.warn(
                _MODULES_DEPRECATED_METHOD.format( 'Modules', 'CxxModules' )
        )
        return _CxxModulesCallable()( env, enabled )


class ModulesMethod:
    """Opt-in C++ modules; primarily driven by ``--cxx-modules``."""

    @classmethod
    def add_options( cls, add_option ):
        add_option(
            '--cxx-modules',
            dest='cxx_modules',
            action='store_true',
            help='Enable C++20 named modules, header units, and import std '
                 'when the toolchain supports them '
                 '(GCC 14+ / LLVM Clang 16+ / MSVC toolset 14.2+)',
        )
        add_option(
            '--modules',
            dest='modules_legacy',
            action='store_true',
            help='(deprecated) same as --cxx-modules; removed in cuppa 2.0',
        )

    @classmethod
    def get_options( cls, env ):
        canonical = bool( env.get_option( 'cxx_modules' ) )
        legacy = bool( env.get_option( 'modules_legacy' ) )
        if legacy:
            from cuppa.colourise import as_info as _as_info
            logger.warn(
                    _MODULES_DEPRECATED_CLI.format(
                            _as_info( '--modules' ),
                            _as_info( '--cxx-modules' ),
                    )
            )
        env['modules'] = canonical or legacy

    @classmethod
    def add_to_env( cls, cuppa_env ):
        cuppa_env.add_method( 'CxxModules', _CxxModulesCallable() )
        cuppa_env.add_method( 'Modules', _ModulesDeprecatedCallable() )

    @classmethod
    def init_env_for_variant( cls, sconscript_exports ):
        env = sconscript_exports['env']
        if env.get( 'modules' ):
            activate_modules_for_env( env )
