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
            nargs='?',
            const=True,
            default=False,
            help='Capture Profiles diagnostics and emit HTML + JSON under '
                 '<artifacts-root>/cxx-profiles/ (default _artifacts/cxx-profiles/; '
                 'requires --cxx-profiles or --cxx-profiles-enforce=; optional '
                 'directory path after =)',
        )
        add_option(
            '--cxx-profiles-report-root',
            dest='cxx_profiles_report_root',
            default=None,
            help='Rebase project-owned source paths in Profiles reports '
                 '(default: sconstruct directory)',
        )
        add_option(
            '--cxx-profiles-report-link-style',
            dest='cxx_profiles_report_link_style',
            default=None,
            choices=[ 'local', 'gitlab', 'github' ],
            help='Profiles-only source link override (overrides --reports-link-style for '
                 'Profiles HTML; default: --reports-link-style or local)',
        )

    @classmethod
    def get_options( cls, env ):
        raw = env.get_option( 'cxx_profiles_report' )
        enabled = False if raw in ( None, False ) else raw
        env[ 'cxx_profiles_report' ] = enabled
        env[ 'cxx_profiles_report_root' ] = env.get_option( 'cxx_profiles_report_root' )
        link_style = env.get_option( 'cxx_profiles_report_link_style' )
        if link_style:
            env[ 'cxx_profiles_report_link_style' ] = link_style
        if not enabled:
            return

        from cuppa.reports.manifest import maybe_remove_cxx_profiles_on_clean
        maybe_remove_cxx_profiles_on_clean( env )

        profiles_active = bool( env.get( 'cxx_profiles' ) ) or bool(
            env.get( 'cxx_profiles_enforce' )
        )
        if not profiles_active:
            if env.get( 'clean' ) or env.get( 'remove_builds' ):
                return
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
