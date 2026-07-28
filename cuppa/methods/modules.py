#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   C++ modules enablement (--modules) and C++20 floor
#-------------------------------------------------------------------------------

from cuppa.colourise import as_info, as_notice, as_warning
from cuppa.log import logger


# Relative dialect ranks; aliases share a rank.
_DIALECT_RANK = {
    'c++98': 98,
    'c++03': 98,
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


def ensure_modules_dialect_floor( env, floor='c++20' ):
    """When modules are enabled, require at least the given dialect floor."""
    current = env.get( 'stdcpp' )
    floor_rank = dialect_rank( floor )
    if dialect_rank( current ) >= floor_rank:
        return current

    toolchain = env['toolchain']
    if not current:
        logger.info(
            "C++ modules enabled; setting dialect to {}"
            .format( as_info( floor ) )
        )
    else:
        logger.warn(
            "C++ modules require {}+; raising dialect from {} to {}"
            .format( as_info( floor ), as_warning( current ), as_info( floor ) )
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
            "--modules requested but toolchain [{}] does not support C++ modules "
            "(Linux/macOS GCC 14+ / Clang 16+, or Windows MSVC toolset 14.2+ "
            "[--toolchains=vc142 / vc143 / vc145 / …] in this cuppa release)"
            .format( toolchain.name() )
        )
        logger.error(
            "--modules requested but toolchain [{}] does not support C++ modules "
            "(Linux/macOS GCC 14+ / Clang 16+, or Windows MSVC toolset 14.2+ "
            "[--toolchains=vc142 / vc143 / vc145 / …] in this cuppa release)"
            .format( as_error( toolchain.name() ) )
        )
        env['modules'] = False
        raise SCons.Errors.StopError( message )

    env['modules'] = True
    ensure_modules_dialect_floor( env )
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


class ModulesMethod:
    """Optional explicit env.Modules() toggle; primarily driven by --modules."""

    @classmethod
    def add_options( cls, add_option ):
        add_option(
            '--modules',
            dest='modules',
            action='store_true',
            help='Enable experimental C++20 named modules and header units '
                 '(GCC 14+ / Clang 16+ on Linux)',
        )

    @classmethod
    def get_options( cls, env ):
        env['modules'] = bool( env.get_option( 'modules' ) )

    def __call__( self, env, enabled=True ):
        env['modules'] = bool( enabled )
        if enabled:
            activate_modules_for_env( env )
        return None

    @classmethod
    def add_to_env( cls, cuppa_env ):
        cuppa_env.add_method( 'Modules', cls() )

    @classmethod
    def init_env_for_variant( cls, sconscript_exports ):
        env = sconscript_exports['env']
        if env.get( 'modules' ):
            activate_modules_for_env( env )
