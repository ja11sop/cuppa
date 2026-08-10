#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   C++ Profiles enablement (--cxx-profiles / --cxx-profiles-enforce)
#-------------------------------------------------------------------------------

from cuppa.colourise import as_error, as_notice
from cuppa.log import logger


def _parse_enforce_list( raw ):
    if not raw:
        return []
    if isinstance( raw, ( list, tuple ) ):
        values = []
        for item in raw:
            values.extend( _parse_enforce_list( item ) )
        return values
    return [ part.strip() for part in str( raw ).split( ',' ) if part.strip() ]


def activate_profiles_for_env( env ):
    """Enable C++ Profiles for ``env`` or raise StopError when unsupported."""
    toolchain = env['toolchain']
    supported = False
    if hasattr( toolchain, 'profiles_supported' ):
        supported = bool( toolchain.profiles_supported( env ) )
    if not supported:
        import SCons.Errors
        message = (
            "--cxx-profiles requested but toolchain [{}] does not support C++ Profiles "
            "(use a Profiles-capable Clang archive via --toolchain-archive= / "
            "--clang-root=; see design/plans/cxx-profiles.md)"
            .format( toolchain.name() )
        )
        logger.error(
            "--cxx-profiles requested but toolchain [{}] does not support C++ Profiles "
            "(use a Profiles-capable Clang archive via --toolchain-archive= / "
            "--clang-root=)"
            .format( as_error( toolchain.name() ) )
        )
        env['cxx_profiles'] = False
        raise SCons.Errors.StopError( message )

    env['cxx_profiles'] = True
    if hasattr( toolchain, 'profiles_enable_flags' ):
        env.AppendUnique( CXXFLAGS = toolchain.profiles_enable_flags( env ) )

    names = list( env.get( 'cxx_profiles_enforce' ) or [] )
    if names:
        native = []
        if hasattr( toolchain, 'profiles_enforce_flags' ):
            native = list( toolchain.profiles_enforce_flags( env, names ) or [] )
        if native:
            env.AppendUnique( CXXFLAGS = native )
            env['_cuppa_profiles_enforce_header'] = None
        else:
            from cuppa.cpp.cxx_profiles import ensure_enforce_header
            header = ensure_enforce_header( env, names )
            env['_cuppa_profiles_enforce_header'] = header

    logger.debug(
        "C++ Profiles active for toolchain [{}]"
        .format( as_notice( toolchain.name() ) )
    )
    return True


class CxxProfilesMethod:
    """Opt-in C++ Profiles framework and optional TU-wide enforce injection."""

    @classmethod
    def add_options( cls, add_option ):
        add_option(
            '--cxx-profiles',
            dest='cxx_profiles',
            action='store_true',
            help='Enable the C++ Profiles framework (-fprofiles) when the '
                 'toolchain supports it (Profiles-capable Clang archives)',
        )
        add_option(
            '--cxx-profiles-enforce',
            dest='cxx_profiles_enforce',
            type='string',
            nargs=1,
            action='store',
            help='Comma-separated profile designators to enforce on every C++ '
                 'translation unit (implies --cxx-profiles). Example: '
                 '--cxx-profiles-enforce=std::init',
        )

    @classmethod
    def get_options( cls, env ):
        env['cxx_profiles'] = bool( env.get_option( 'cxx_profiles' ) )
        env['cxx_profiles_enforce'] = _parse_enforce_list(
            env.get_option( 'cxx_profiles_enforce' )
        )
        if env['cxx_profiles_enforce']:
            env['cxx_profiles'] = True

    def __call__( self, env, enabled=True ):
        env['cxx_profiles'] = bool( enabled )
        if enabled:
            activate_profiles_for_env( env )
        return None

    def enforce( self, env, *names ):
        """Set enforce designators for this env and activate Profiles."""
        parsed = []
        for name in names:
            parsed.extend( _parse_enforce_list( name ) )
        env['cxx_profiles_enforce'] = parsed
        if parsed:
            env['cxx_profiles'] = True
            activate_profiles_for_env( env )
        return None

    @classmethod
    def add_to_env( cls, cuppa_env ):
        method = cls()
        cuppa_env.add_method( 'CxxProfiles', method )
        cuppa_env.add_method( 'CxxProfilesEnforce', method.enforce )

    @classmethod
    def init_env_for_variant( cls, sconscript_exports ):
        env = sconscript_exports['env']
        if env.get( 'cxx_profiles' ):
            activate_profiles_for_env( env )
