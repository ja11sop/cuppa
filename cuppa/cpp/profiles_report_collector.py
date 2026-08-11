#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   In-process Profiles violation collector (prof-report-collector)
#-------------------------------------------------------------------------------

import threading

from cuppa.colourise import as_notice
from cuppa.cpp.cxx_profiles_report import (
    ProfilesInventory,
    format_capture_summary,
    parse_profiles_diagnostic,
)
from cuppa.log import logger
from cuppa.progress import NotifyProgress, VariantCompletionTracker


class ProfilesReportSession(object):
    """Thread-safe session store and Progress scope bookkeeping."""

    def __init__( self ):
        self._lock = threading.Lock()
        self._inventory = ProfilesInventory()
        self._variant_completion = VariantCompletionTracker()

    @property
    def inventory( self ):
        return self._inventory

    def record( self, scope, diagnostic ):
        with self._lock:
            self._inventory.record( scope, diagnostic )

    def on_progress( self, progress, sconscript, variant, env, target, source ):
        self._variant_completion.note_progress( progress, variant )
        if progress == 'sconstruct_end':
            self._emit_session_summary()

    def _emit_session_summary( self ):
        with self._lock:
            if self._inventory.total_references() == 0:
                logger.info(
                    "C++ Profiles report: no violations captured "
                    "(see --cxx-profiles-report; HTML output lands in a later slice)"
                )
                return
            incomplete = self._variant_completion.incomplete_variants()
            if incomplete:
                logger.warn(
                    "C++ Profiles report: incomplete scope(s) [{}]".format(
                        as_notice( ', '.join( sorted( incomplete ) ) )
                    )
                )
            logger.info(
                "C++ Profiles report capture summary:\n{}".format(
                    format_capture_summary( self._inventory )
                )
            )


class ProfilesDiagnosticCollector(object):
    """Process-wide collector activated by ``--cxx-profiles-report``."""

    _session = None
    _register_lock = threading.Lock()
    _spawn_hook_registered = False

    @classmethod
    def activate( cls ):
        with cls._register_lock:
            if cls._session is None:
                cls._session = ProfilesReportSession()
                NotifyProgress.register_callback( None, cls._session.on_progress )
                cls._register_spawn_processor_hook()
            return cls._session

    @classmethod
    def _register_spawn_processor_hook( cls ):
        if cls._spawn_hook_registered:
            return
        NotifyProgress.register_sconscript_env_hook( cls._rebind_spawn_processor )
        cls._spawn_hook_registered = True

    @classmethod
    def _rebind_spawn_processor( cls, env ):
        if hasattr( env, 'get_option' ) and env.get_option( 'raw_output' ):
            return
        import cuppa.output_processor
        cuppa.output_processor.Processor.install( env )

    @classmethod
    def active( cls ):
        return cls._session

    @classmethod
    def record_line( cls, scope, line ):
        session = cls._session
        if session is None or not line:
            return
        diagnostic = parse_profiles_diagnostic( line )
        if diagnostic is not None:
            session.record( scope, diagnostic )

    @classmethod
    def reset( cls ):
        """Clear the active session (unit tests only)."""
        cls._session = None
