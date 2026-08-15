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

    def on_progress( self, progress, sconscript, variant, env, target, source ):
        self._variant_completion.note_progress( progress, variant )
        if progress == 'sconstruct_end':
            self._emit_session_summary( env )

    def _emit_session_summary( self, env ):
        from cuppa.cpp.profiles_report.report_html import write_profiles_reports
        from cuppa.reports.manifest import append_cxx_profiles_entry

        with self._lock:
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
            logger.info(
                "C++ Profiles report capture summary:\n{}".format(
                    format_capture_summary( self._inventory )
                )
            )
            parsed_files = frozenset( self._parsed_files )
            translation_units = frozenset( self._translation_units )
        result = write_profiles_reports(
            self._inventory,
            env,
            incomplete_scopes=incomplete,
            parsed_files=parsed_files,
            translation_units=translation_units,
        )
        if result:
            append_cxx_profiles_entry(
                env,
                result[ 'model' ],
                result[ 'session_paths' ],
                result[ 'scope_paths' ],
                incomplete_scopes=incomplete,
                partial=bool( incomplete ),
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
