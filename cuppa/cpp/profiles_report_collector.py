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
    filter_inventory_for_index,
    format_capture_summary,
    normalize_sconscript_path,
    parse_profiles_diagnostic,
    profiles_scope_from_construction_env,
)
from cuppa.cpp.profiles_report.context_summary import (
    normalize_report_path,
    parse_include_stack_line,
)
from cuppa.log import logger
from cuppa.progress import NotifyProgress, VariantCompletionTracker


_UNSET = object()


class ProfilesReportSession(object):
    """Thread-safe session store and Progress scope bookkeeping."""

    def __init__( self ):
        self._lock = threading.Lock()
        self._inventory = ProfilesInventory()
        self._variant_completion = VariantCompletionTracker()
        self._parsed_files = set()
        self._translation_units = set()
        self._written = False
        self._non_profile_errors = 0
        self._profile_display_error_count = 0
        self.activation_via_cli = False
        self._declaring_sconscripts = set()
        self._locked_destination = _UNSET
        self._locked_link_style = _UNSET

    @property
    def inventory( self ):
        return self._inventory

    def declaring_sconscripts( self ):
        with self._lock:
            return frozenset( self._declaring_sconscripts )

    def register_declaring_sconscript( self, path ):
        normalized = normalize_sconscript_path( path )
        if not normalized:
            return
        with self._lock:
            self._declaring_sconscripts.add( normalized )

    def note_index_options( self, destination=None, link_style=None ):
        """First explicit ``destination`` / ``link_style`` wins; later mismatches warn."""
        if destination is not None:
            if destination is True:
                if self._locked_destination is _UNSET:
                    self._locked_destination = True
            elif self._locked_destination is _UNSET:
                self._locked_destination = destination
            elif self._locked_destination is True:
                logger.warn(
                    "C++ Profiles report: ignoring later CollateCxxProfilesIndex "
                    "destination [{}]; first declaration wins".format(
                        as_notice( str( destination ) ),
                    )
                )
            elif destination != self._locked_destination:
                logger.warn(
                    "C++ Profiles report: ignoring later CollateCxxProfilesIndex "
                    "destination [{}]; first declaration [{}] wins".format(
                        as_notice( str( destination ) ),
                        as_notice( str( self._locked_destination ) ),
                    )
                )
        if link_style:
            if self._locked_link_style is _UNSET:
                self._locked_link_style = link_style
            elif link_style != self._locked_link_style:
                logger.warn(
                    "C++ Profiles report: ignoring later CollateCxxProfilesIndex "
                    "link_style [{}]; first declaration [{}] wins".format(
                        as_notice( str( link_style ) ),
                        as_notice( str( self._locked_link_style ) ),
                    )
                )

    def index_inventory( self ):
        """Inventory used for the session index (filtered when method-only).

        Snapshots locations under the session lock so ``--parallel`` compiles
        can still ``record()`` while the index is built.
        """
        with self._lock:
            snapshot = self._inventory.snapshot()
            declaring = frozenset( self._declaring_sconscripts )
            via_cli = self.activation_via_cli
        if via_cli or not declaring:
            return snapshot, None
        filtered, omitted = filter_inventory_for_index( snapshot, declaring )
        metadata = {
            'active': True,
            'declaring_sconscripts': sorted( declaring ),
            'omitted_scope_count': omitted,
        }
        return filtered, metadata

    def record( self, scope, diagnostic ):
        with self._lock:
            self._inventory.record( scope, diagnostic )

    def record_parsed_file( self, scope, path ):
        """Record one path seen via ``-H`` (or compile hook); idempotent."""
        del scope
        normalized = normalize_report_path( path )
        if not normalized:
            return
        with self._lock:
            self._parsed_files.add( normalized )

    def record_translation_unit( self, scope, path ):
        """Record a compiled primary source path and include it in parsed files."""
        del scope
        normalized = normalize_report_path( path )
        if not normalized:
            return
        with self._lock:
            self._translation_units.add( normalized )
            self._parsed_files.add( normalized )

    def parsed_files( self ):
        with self._lock:
            return frozenset( self._parsed_files )

    def translation_units( self ):
        with self._lock:
            return frozenset( self._translation_units )

    def non_profile_error_count( self ):
        with self._lock:
            return self._non_profile_errors

    def record_non_profile_error( self ):
        with self._lock:
            self._non_profile_errors += 1

    def next_profile_display_error_id( self ):
        """Monotonic Error N label for profile violations shown in inventory mode."""
        with self._lock:
            self._profile_display_error_count += 1
            return self._profile_display_error_count

    def on_progress( self, progress, sconscript, variant, env, target, source ):
        self._variant_completion.note_progress( progress, variant )
        if progress == 'sconstruct_end':
            self._emit_session_summary( env )
            # Exit after the DAG, not from cuppa.run() during SConstruct parse.
            ProfilesDiagnosticCollector.maybe_exit_for_non_profile_errors()

    def flush_pending( self, env, fallback_flush=False ):
        """Write the session index when capture is non-empty and not yet emitted."""
        with self._lock:
            if self._written:
                return False
            if self._inventory.total_references() == 0:
                return False
        self._emit_session_summary( env, fallback_flush=fallback_flush )
        return True

    def _write_env( self, progress_env ):
        """Prefer the cuppa env captured at activate time over Progress ``empty_env``."""
        report_env = ProfilesDiagnosticCollector._report_env
        return report_env if report_env is not None else progress_env

    def _emit_session_summary( self, env, fallback_flush=False ):
        from cuppa.cpp.profiles_report.report_html import write_profiles_reports
        from cuppa.reports.manifest import append_cxx_profiles_entry

        write_env = self._write_env( env )
        with self._lock:
            if self._written:
                return
            if self._inventory.total_references() == 0:
                logger.info(
                    "C++ Profiles report: no violations captured"
                )
                return
            incomplete = self._variant_completion.incomplete_variants()
            if incomplete:
                logger.warn(
                    "C++ Profiles report: incomplete scope(s) [{}]".format(
                        as_notice( ', '.join( sorted( incomplete ) ) )
                    )
                )
            if fallback_flush:
                logger.warn(
                    "C++ Profiles report: flushing session index after early build abort"
                )
        index_inventory, scope_filter = self.index_inventory()
        if scope_filter and scope_filter.get( 'omitted_scope_count' ):
            omitted = scope_filter[ 'omitted_scope_count' ]
            logger.warn(
                "C++ Profiles report: omitted {} captured scope(s) from the session "
                "index (only sconscripts that called CollateCxxProfilesIndex() are "
                "listed). Pass {} for the full session inventory.".format(
                    as_notice( str( omitted ) ),
                    as_notice( '--cxx-profiles-report' ),
                )
            )
        if index_inventory.total_references() == 0:
            if scope_filter:
                logger.info(
                    "C++ Profiles report: no violations remain after applying "
                    "the sconscript scope filter"
                )
            else:
                logger.info(
                    "C++ Profiles report: no violations captured"
                )
            return
        logger.info(
            "C++ Profiles report capture summary:\n{}".format(
                format_capture_summary( index_inventory )
            )
        )
        with self._lock:
            parsed_files = frozenset( self._parsed_files )
            translation_units = frozenset( self._translation_units )
        if scope_filter:
            write_env[ '_cxx_profiles_scope_filter' ] = scope_filter
        result = write_profiles_reports(
            index_inventory,
            write_env,
            incomplete_scopes=incomplete,
            parsed_files=parsed_files,
            translation_units=translation_units,
        )
        if result:
            append_cxx_profiles_entry(
                write_env,
                result[ 'model' ],
                result[ 'session_paths' ],
                result[ 'scope_paths' ],
                incomplete_scopes=incomplete,
                partial=bool( incomplete ) or fallback_flush,
            )
            with self._lock:
                self._written = True


class ProfilesDiagnosticCollector(object):
    """Process-wide collector activated by ``--cxx-profiles-report``."""

    _session = None
    _report_env = None
    _register_lock = threading.Lock()
    _spawn_hook_registered = False
    _activation_via_cli = False

    @classmethod
    def activate( cls, report_env=None, via_cli=False ):
        with cls._register_lock:
            if via_cli:
                cls._activation_via_cli = True
            if report_env is not None and cls._report_env is None:
                cls._report_env = report_env
            if cls._session is None:
                cls._session = ProfilesReportSession()
                NotifyProgress.register_callback( None, cls._session.on_progress )
                cls._register_spawn_processor_hook()
            if cls._activation_via_cli:
                cls._session.activation_via_cli = True
        # Method-only Collate runs during SConscript, after env_ready. Rebind
        # this env so SpawnedProcessor sees sconscript_file (not _unscoped).
        if report_env is not None:
            cls._rebind_spawn_processor( report_env )
        return cls._session

    @classmethod
    def maybe_exit_for_non_profile_errors( cls ):
        """Terminate the SCons process when inventory captured ordinary errors.

        Inventory keep-going (``-i``) makes SCons treat ``Script.Exit`` and
        ``SystemExit`` from ``sconstruct_end`` as a failed action and continue.
        ``os._exit`` ends the process after the session index is written.
        """
        exit_status = cls.inventory_process_exit_status()
        if exit_status:
            import logging
            import os
            import sys
            logging.shutdown()
            sys.stdout.flush()
            sys.stderr.flush()
            os._exit( exit_status )

    @classmethod
    def finalize_inventory_session( cls ):
        """Fallback flush after SConstruct parse; exit is deferred to sconstruct_end."""
        if not NotifyProgress.inventory_report_mode():
            return
        cls.flush_pending()
        cls.maybe_exit_for_non_profile_errors()

    @classmethod
    def inventory_process_exit_status( cls ):
        """Return forced process exit code for inventory mode, or ``None`` to keep SCons status."""
        if not NotifyProgress.inventory_report_mode():
            return None
        session = cls._session
        if session is None:
            return None
        count = session.non_profile_error_count()
        if count <= 0:
            return None
        logger.warn(
            "C++ Profiles report: {} non-profile compile error(s); exiting non-zero".format(
                as_notice( str( count ) ),
            )
        )
        return 1

    @classmethod
    def record_non_profile_error( cls ):
        session = cls._session
        if session is not None:
            session.record_non_profile_error()

    @classmethod
    def next_profile_display_error_id( cls ):
        session = cls._session
        if session is None:
            return 0
        return session.next_profile_display_error_id()

    @classmethod
    def flush_pending( cls ):
        """Fallback session index write when ``sconstruct_end`` did not run."""
        session = cls._session
        env = cls._report_env
        if session is None or env is None:
            return False
        return session.flush_pending( env, fallback_flush=True )

    @classmethod
    def _register_spawn_processor_hook( cls ):
        if cls._spawn_hook_registered:
            return
        NotifyProgress.register_sconscript_env_hook( cls._rebind_spawn_processor )
        cls._spawn_hook_registered = True

    @classmethod
    def _wrap_compile_method( cls, env, method_name ):
        original = getattr( env, method_name, None )
        if original is None or getattr( original, '_profiles_report_wrapped', False ):
            return

        def wrapped( call_env, source, **kwargs ):
            session = cls._session
            if session is not None:
                from SCons.Script import Flatten
                scope = profiles_scope_from_construction_env( call_env )
                for item in Flatten( [ source ] ):
                    path = item.path if hasattr( item, 'path' ) else str( item )
                    session.record_translation_unit( scope, path )
            return original( source, **kwargs )

        wrapped._profiles_report_wrapped = True
        env.AddMethod( wrapped, method_name )

    @classmethod
    def _install_report_build_hooks( cls, env ):
        if not env.get( 'cxx_profiles_report' ):
            return
        env.AppendUnique( CXXFLAGS = [ '-H' ] )
        for method_name in ( 'Compile', 'CompileStatic', 'CompileShared' ):
            cls._wrap_compile_method( env, method_name )

    @classmethod
    def _rebind_spawn_processor( cls, env ):
        if not hasattr( env, 'get' ):
            return
        if hasattr( env, 'get_option' ) and env.get_option( 'raw_output' ):
            return
        # Construction envs always have SPAWN/PSPAWN; unit-test dicts do not.
        if env.get( 'SPAWN' ) is None and env.get( 'PSPAWN' ) is None:
            return
        # Scoped SPAWN is needed whenever Profiles may capture, including
        # method-only Collate (report flag is not set yet at env_ready).
        if not (
                env.get( 'cxx_profiles' )
                or env.get( 'cxx_profiles_enforce' )
                or env.get( 'cxx_profiles_report' )
        ):
            return
        import cuppa.output_processor
        cuppa.output_processor.Processor.install( env )
        cls._install_report_build_hooks( env )

    @classmethod
    def active( cls ):
        return cls._session

    @classmethod
    def record_line( cls, scope, line ):
        """Record one compiler stderr line.

        Returns ``True`` when the line was consumed for report capture only and
        should not be echoed to the console (for example ``-H`` include-stack rows).
        """
        session = cls._session
        if session is None or not line:
            return False
        include_path = parse_include_stack_line( line )
        if include_path is not None:
            session.record_parsed_file( scope, include_path )
            return True
        diagnostic = parse_profiles_diagnostic( line )
        if diagnostic is not None:
            session.record( scope, diagnostic )
        return False

    @classmethod
    def reset( cls ):
        """Clear the active session (unit tests only)."""
        cls._session = None
        cls._report_env = None
        cls._spawn_hook_registered = False
        cls._flush_registered = False
        cls._activation_via_cli = False
