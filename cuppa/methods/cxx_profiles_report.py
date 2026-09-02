#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   C++ Profiles violation report (--cxx-profiles-report, env.CollateCxxProfilesIndex)
#-------------------------------------------------------------------------------

from cuppa.colourise import as_error, as_notice
from cuppa.cpp.profiles_report_collector import ProfilesDiagnosticCollector
from cuppa.log import logger
from cuppa.reports.link_style import REPORT_LINK_STYLES

_inventory_ignore_errors_set = False


def _profiles_report_active( env ):
    return bool( env.get( 'cxx_profiles' ) ) or bool( env.get( 'cxx_profiles_enforce' ) )


def _require_profiles_for_report( env ):
    if _profiles_report_active( env ):
        return
    if env.get( 'clean' ) or env.get( 'remove_builds' ):
        return
    import SCons.Errors
    message = (
        "C++ Profiles report requires Profiles to be active "
        "(use --cxx-profiles or --cxx-profiles-enforce=)"
    )
    logger.error(
        "C++ Profiles report requires Profiles to be active "
        "(use {} or {} )".format(
            as_error( '--cxx-profiles' ),
            as_error( '--cxx-profiles-enforce=' ),
        )
    )
    raise SCons.Errors.StopError( message )


def _enable_inventory_report_mode():
    """Enable Progress collation hooks for Profiles inventory runs."""
    from cuppa.progress import NotifyProgress
    if NotifyProgress.inventory_report_mode():
        return
    NotifyProgress.set_inventory_report_mode( True )


def _enable_inventory_keep_going():
    """Record inventory keep-going (``-i`` is injected by the cuppa CLI when needed)."""
    global _inventory_ignore_errors_set
    if _inventory_ignore_errors_set:
        return
    import SCons.Script
    _inventory_ignore_errors_set = True
    if SCons.Script.GetOption( 'ignore_errors' ):
        return
    logger.warn(
        "C++ Profiles report: keep-going ({}) was not set; inventory may stop at the first "
        "failed compile. Pass {} explicitly or use {} on the cuppa command line.".format(
            as_notice( '-i' ),
            as_notice( '-i' ),
            as_notice( '--cxx-profiles-report' ),
        )
    )


def activate_cxx_profiles_report(
        env,
        destination=None,
        link_style=None,
        via_cli=False,
        declaring=False,
):
    """Enable Profiles capture for this env (CLI flag or ``env.CollateCxxProfilesIndex()``)."""
    if destination is not None:
        env[ 'cxx_profiles_report' ] = destination
    elif not env.get( 'cxx_profiles_report' ):
        env[ 'cxx_profiles_report' ] = True
    if link_style:
        env[ 'cxx_profiles_report_link_style' ] = link_style
    from cuppa.reports.manifest import maybe_remove_cxx_profiles_on_clean
    maybe_remove_cxx_profiles_on_clean( env )
    _require_profiles_for_report( env )
    if not env.get( 'cxx_profiles_report' ):
        return
    _enable_inventory_report_mode()
    _enable_inventory_keep_going()
    session = ProfilesDiagnosticCollector.activate( report_env=env, via_cli=via_cli )
    if declaring:
        session.register_declaring_sconscript( env.get( 'sconscript_file' ) )
    session.note_index_options(
        destination=env.get( 'cxx_profiles_report' ),
        link_style=link_style or env.get( 'cxx_profiles_report_link_style' ),
    )
    logger.debug( "C++ Profiles violation capture enabled" )


def reset_inventory_report_state_for_tests():
    """Reset module globals (unit tests only)."""
    global _inventory_ignore_errors_set
    _inventory_ignore_errors_set = False
    from cuppa.progress import NotifyProgress
    NotifyProgress.set_inventory_report_mode( False )


class CollateCxxProfilesIndexCallable(object):
    """SCons method: declare Profiles session index (HTML + JSON) for this sconscript tree."""

    def __call__( self, env, destination=None, link_style=None ):
        activate_cxx_profiles_report(
            env,
            destination=destination if destination is not None else True,
            link_style=link_style,
            declaring=True,
        )
        return env.get( 'cxx_profiles_report' )


class CollateCxxProfilesIndexMethod:
    """Opt-in capture of Profiles diagnostics; session index at ``sconstruct_end``."""

    @classmethod
    def add_options( cls, add_option ):
        add_option(
            '--cxx-profiles-report',
            dest='cxx_profiles_report',
            nargs='?',
            const=True,
            default=False,
            help='Capture Profiles diagnostics and emit HTML + JSON under '
                 '<artefacts-root>/cxx-profiles/ (default _artefacts/cxx-profiles/; '
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
            choices=list( REPORT_LINK_STYLES ),
            help='Profiles-only source link override (overrides --reports-link-style for '
                 'Profiles HTML; default: --reports-link-style or local)',
        )
        add_option(
            '--cxx-profiles-report-context',
            dest='cxx_profiles_report_context',
            default='full',
            choices=[ 'full', 'rules-only', 'off' ],
            help='Overview context in Profiles JSON/HTML: full (default), rules-only '
                 '(matrix and concentration without tier metrics), or off',
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
        context_mode = env.get_option( 'cxx_profiles_report_context' )
        if context_mode:
            env[ 'cxx_profiles_report_context' ] = context_mode
        if not enabled:
            # Register before sconscript env_ready so method-only
            # CollateCxxProfilesIndex() still gets a scoped SpawnedProcessor.
            ProfilesDiagnosticCollector._register_spawn_processor_hook()
            return
        activate_cxx_profiles_report( env, via_cli=True )

    @classmethod
    def add_to_env( cls, cuppa_env ):
        cuppa_env.add_method( 'CollateCxxProfilesIndex', CollateCxxProfilesIndexCallable() )
