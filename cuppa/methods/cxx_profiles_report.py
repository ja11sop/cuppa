#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   C++ Profiles violation report (--cxx-profiles-report)
#-------------------------------------------------------------------------------

from cuppa.colourise import as_error
from cuppa.cpp.profiles_report_collector import ProfilesDiagnosticCollector
from cuppa.log import logger


class CxxProfilesReportMethod:
    """Opt-in capture of Profiles diagnostics during builds."""

    @classmethod
    def add_options( cls, add_option ):
        add_option(
            '--cxx-profiles-report',
            dest='cxx_profiles_report',
            action='store_true',
            help='Capture Profiles diagnostics during the build for a violation '
                 'report (requires --cxx-profiles or --cxx-profiles-enforce=; '
                 'HTML output is a follow-on slice)',
        )

    @classmethod
    def get_options( cls, env ):
        enabled = bool( env.get_option( 'cxx_profiles_report' ) )
        env[ 'cxx_profiles_report' ] = enabled
        if not enabled:
            return

        profiles_active = bool( env.get( 'cxx_profiles' ) ) or bool(
            env.get( 'cxx_profiles_enforce' )
        )
        if not profiles_active:
            import SCons.Errors
            message = (
                "--cxx-profiles-report requires C++ Profiles to be active "
                "(use --cxx-profiles or --cxx-profiles-enforce=)"
            )
            logger.error(
                "--cxx-profiles-report requires C++ Profiles to be active "
                "(use {} or {} )".format(
                    as_error( '--cxx-profiles' ),
                    as_error( '--cxx-profiles-enforce=' ),
                )
            )
            raise SCons.Errors.StopError( message )

        ProfilesDiagnosticCollector.activate()
        logger.debug( "C++ Profiles violation capture enabled" )

    @classmethod
    def add_to_env( cls, cuppa_env ):
        pass
