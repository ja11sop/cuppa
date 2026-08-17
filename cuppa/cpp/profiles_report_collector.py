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
    profiles_scope_from_construction_env,
)
from cuppa.cpp.profiles_report.context_summary import (
    normalize_report_path,
    parse_include_stack_line,
)
from cuppa.log import logger
from cuppa.progress import NotifyProgress, VariantCompletionTracker


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

    @property
    def inventory( self ):
        return self._inventory

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
            logger.info(
                "C++ Profiles report capture summary:\n{}".format(
                    format_capture_summary( self._inventory )
                )
            )
            parsed_files = frozenset( self._parsed_files )
            translation_units = frozenset( self._translation_units )
        result = write_profiles_reports(
            self._inventory,
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

    @classmethod
    def activate( cls, report_env=None ):
        with cls._register_lock:
            if report_env is not None:
                cls._report_env = report_env
            if cls._session is None:
                cls._session = ProfilesReportSession()
                NotifyProgress.register_callback( None, cls._session.on_progress )
                cls._register_spawn_processor_hook()
            return cls._session

    @classmethod
    def finalize_inventory_session( cls ):
        """Fallback flush and selective exit after the build DAG completes."""
        if not NotifyProgress.inventory_report_mode():
            return
        cls.flush_pending()
        exit_status = cls.inventory_process_exit_status()
        if exit_status:
            import SCons.Script
            SCons.Script.Exit( exit_status )

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
        if hasattr( env, 'get_option' ) and env.get_option( 'raw_output' ):
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
