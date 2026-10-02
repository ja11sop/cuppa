
#          Copyright Jamie Allsop 2013-2015
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   Progress
#-------------------------------------------------------------------------------

import atexit
import logging
import os.path
import signal
import sys
import threading

from cuppa.colourise import as_badge, as_colour, as_emphasised, as_info, as_notice, as_subdued
from cuppa.log import logger

from SCons.Script import Action


_interrupt_announced = False
_abort_announced = False
_interrupt_finished = False
_interrupt_lock = threading.Lock()
_terse_activity_seen = False
_terse_activity_lock = threading.Lock()
_summary_enabled = False
_plan_written = False


def reset_terse_build_activity():
    """Start a build with no tool or Python action reported yet."""
    global _terse_activity_seen
    with _terse_activity_lock:
        _terse_activity_seen = False


def note_terse_build_activity():
    """Remember that this build emitted at least one terse action line."""
    global _terse_activity_seen
    with _terse_activity_lock:
        _terse_activity_seen = True


def terse_build_had_activity():
    with _terse_activity_lock:
        return _terse_activity_seen


def _plural( count, singular, plural ):
    return "{} {}".format( count, singular if count == 1 else plural )


def _plan_sentence( scripts, variants, total ):
    parts = []
    if scripts:
        parts.append( _plural( scripts, "sconscript", "sconscripts" ) )
    if variants:
        parts.append( _plural( variants, "variant", "variants" ) )
    if total:
        parts.append( _plural( total, "action", "actions" ) )
    return " · ".join( parts )


def enable_terse_build_summary():
    """Print the opening plan and the closing counts for this build."""
    global _summary_enabled
    _summary_enabled = True


def write_terse_build_plan():
    """One subdued line before the first action, once the totals are known."""
    global _plan_written
    if not _summary_enabled or _plan_written or _interrupt_announced:
        return
    _plan_written = True
    text = _progress_ledger.plan_line()
    if not text:
        return
    sys.stdout.write( as_subdued( text ) + "\n" )
    sys.stdout.flush()


def write_terse_interrupt_finish():
    """Close a graceful Ctrl-C once the actions already running have finished.

    An ``aborted`` build has no closing line. The counts are the same ones a
    successful build would report.
    """
    global _interrupt_finished
    with _interrupt_lock:
        if _abort_announced or _interrupt_finished or not _interrupt_announced:
            return
        _interrupt_finished = True
    sys.stdout.write( as_subdued( "finished in-flight actions" ) + "\n" )
    summary = ""
    if _summary_enabled:
        summary = _progress_ledger.interrupt_summary()
    line = as_notice( "[interrupted]" )
    if summary:
        line += " " + summary
    sys.stdout.write( line + "\n" )
    sys.stdout.flush()


def write_terse_build_completion( env ):
    """Finish a successful terse build, including a no-op build under ``-Q``."""
    if not _env_get( env, "terse_output" ) or _interrupt_announced:
        return
    outcome = "succeeded" if terse_build_had_activity() else "up to date"
    suffix = ""
    if _summary_enabled:
        suffix = _progress_ledger.completion_clause( outcome == "up to date" )
    sys.stdout.write( as_colour( "success", "[done]" ) + " build " + outcome + suffix + "\n" )
    sys.stdout.flush()


def reset_build_interrupted():
    """Allow another build in this process to report Ctrl-C once."""
    global _interrupt_announced, _abort_announced, _interrupt_finished
    with _interrupt_lock:
        _interrupt_announced = False
        _abort_announced = False
        _interrupt_finished = False


def is_interrupt_returncode( returncode ):
    """True when a child died from Ctrl-C (SIGINT), not from its own failure."""
    try:
        code = int( returncode )
    except ( TypeError, ValueError ):
        return False
    interrupted = signal.SIGINT
    return code in ( -interrupted, 128 + interrupted )


def _interrupt_stream():
    """The real stderr, under the filter that hides SCons's Ctrl-C list."""
    stream = sys.stderr
    while isinstance( stream, _TerseInterruptStream ):
        stream = stream._real
    return stream


def _write_interrupt_word( word ):
    """Put ``word`` on its own line, even when the transcript stopped mid-line."""
    try:
        sys.stdout.flush()
    except Exception:
        pass
    stream = _interrupt_stream()
    stream.write( "\n" + as_subdued( word ) + "\n" )
    stream.flush()


def note_build_interrupted():
    """Print one ``interrupted`` line. Further calls in this build do nothing."""
    global _interrupt_announced
    with _interrupt_lock:
        if _interrupt_announced:
            return
        _interrupt_announced = True
    _write_interrupt_word( "interrupted — finishing in-flight actions..." )


def note_build_aborted():
    """Print one ``aborted`` line when a second Ctrl-C stops running work."""
    global _abort_announced
    with _interrupt_lock:
        if _abort_announced:
            return
        _abort_announced = True
    _write_interrupt_word( "aborted" )


def _is_interrupt_noise( text ):
    """Per-target SCons lines for a Ctrl-C, and the error summary that follows."""
    line = str( text or "" ).strip()
    if not line:
        return False
    if line == "scons: Build interrupted.":
        return True
    if line.startswith( "scons: *** [" ):
        errstr = line.rsplit( "] ", 1 )[-1]
        if errstr in ( "Build interrupted.", "Error {}".format( -signal.SIGINT ), "Error {}".format( 128 + signal.SIGINT ) ):
            return True
    if _interrupt_announced and line in (
            "scons: building terminated because of errors.",
            "scons: cleaning terminated because of errors.",
    ):
        return True
    return False


class _TerseInterruptStream:
    """Drop the per-job ``Error -2`` lines Ctrl-C produces under ``-j``."""

    def __init__( self, real ):
        self._real = real

    def write( self, text ):
        if _is_interrupt_noise( text ):
            note_build_interrupted()
            # SCons prints this after the jobs already running have returned.
            if "Build interrupted." in str( text or "" ):
                write_terse_interrupt_finish()
            return
        return self._real.write( text )

    def flush( self ):
        return self._real.flush()

    def __getattr__( self, name ):
        return getattr( self._real, name )


def terse_interrupt_installed():
    """True once ``--terse-output`` is hiding the per-job Ctrl-C list."""
    return isinstance( sys.stderr, _TerseInterruptStream ) or isinstance( sys.stdout, _TerseInterruptStream )


def install_terse_interrupt_filter():
    """Hide the Ctrl-C job list. One ``interrupted`` line remains."""
    reset_build_interrupted()
    reset_terse_build_activity()
    if not isinstance( sys.stderr, _TerseInterruptStream ):
        sys.stderr = _TerseInterruptStream( sys.stderr )
    if not isinstance( sys.stdout, _TerseInterruptStream ):
        sys.stdout = _TerseInterruptStream( sys.stdout )


class NotifyProgress(object):

    _callbacks = set()
    _sconscript_env_hooks = set()

    _sconstruct_begin = None
    _sconstruct_end   = None
    _begin    = {}
    _end      = {}
    _started  = {}
    _finished = {}
    _inventory_report_mode = False

    @classmethod
    def set_inventory_report_mode( cls, enabled ):
        cls._inventory_report_mode = bool( enabled )

    @classmethod
    def inventory_report_mode( cls ):
        return cls._inventory_report_mode

    @classmethod
    def register_callback( cls, env, callback ):
        if env:
            if not 'cuppa_progress_callbacks' in env:
                env['cuppa_progress_callbacks'] = set()
            env['cuppa_progress_callbacks'].add( callback )
        else:
            cls._callbacks.add( callback )


    @classmethod
    def register_sconscript_env_hook( cls, hook ):
        """Register a callback invoked once each sconscript env is ready to build.

        Hooks receive the cloned sconscript construction ``env`` (after
        ``build_dir`` / ``sconscript_file`` are set). Intended for rebinding
        per-sconscript services such as ``SPAWN`` without coupling ``construct``
        to individual features.
        """
        cls._sconscript_env_hooks.add( hook )


    @classmethod
    def notify_sconscript_env_ready( cls, env ):
        """Invoke registered sconscript-env hooks; errors propagate to the build."""
        for hook in cls._sconscript_env_hooks:
            hook( env )


    @classmethod
    def call_callbacks( cls, event, sconscript, variant, env, target, source ):
        if 'cuppa_progress_callbacks' in env:
            for callback in env['cuppa_progress_callbacks']:
                callback( event, sconscript, variant, env, target, source )
        for callback in cls._callbacks:
            callback( event, sconscript, variant, env, target, source )


    @classmethod
    def variant( cls, env ):
        return os.path.split(env['build_dir'])[0]


    @classmethod
    def scope_from_env( cls, env ):
        """Return ``(sconscript, variant_dir)`` for a construction env, or ``None``."""
        try:
            if not env.get( 'build_dir' ) or not env.get( 'sconscript_file' ):
                return None
            return ( cls.sconscript( env ), cls.variant( env ) )
        except ( AttributeError, KeyError, TypeError ):
            return None


    @classmethod
    def toolchain_name( cls, env ):
        try:
            return env[ 'toolchain' ].name()
        except ( AttributeError, KeyError, TypeError ):
            return None


    @classmethod
    def sconscript( cls, env ):
        return env['sconscript_file']


    @classmethod
    def key( cls, env ):
        return cls.sconscript( env ) + "/" + cls.variant( env )


    @classmethod
    def add( cls, env, target ):

        if '_pre_sconscript_phase_' in env and env['_pre_sconscript_phase_']:
            return

        empty_env       = env['empty_env']
        sconscript_env  = env['sconscript_env']

        sconscript    = cls.sconscript( sconscript_env )
        variant       = cls.variant( env )

        if not cls._sconstruct_begin:
            cls._sconstruct_begin = progress( '#SconstructBegin', 'sconstruct_begin', None, None, empty_env )

        if not sconscript in cls._begin:
            cls._begin[sconscript] = progress( 'Begin', 'begin', sconscript, None, sconscript_env )

        begin = cls._begin[sconscript]

        env.Requires( begin, cls._sconstruct_begin )

        if variant not in cls._started:
            cls._started[variant] = progress( 'Starting', 'started', sconscript, variant, env )

        env.Requires( target, cls._started[variant] )
        env.Requires( cls._started[variant], begin )

        if variant not in cls._finished:
            cls._finished[variant] = progress( 'Finished', 'finished', sconscript, variant, env )

        file_deps = [ '#' + env['sconscript_file'], '#' + env['sconstruct_file'] ]
        # Depends enforces build order. Requires alone does not — inventory mode previously
        # let Finished run before long Run/Test actions completed ([#215]).
        env.Depends( cls._finished[variant], file_deps )
        env.Depends( cls._finished[variant], target )
        finished = cls._finished[variant]

        if not sconscript in cls._end:
            cls._end[sconscript] = progress( 'End', 'end', sconscript, None, sconscript_env )

        end = env.Requires( cls._end[sconscript], finished )

        if not cls._sconstruct_end:
            cls._sconstruct_end = progress( '#SconstructEnd', 'sconstruct_end', None, None, empty_env )

        env.Requires( cls._sconstruct_end, end )
        if _env_get( env, "terse_output" ):
            register_terse_actions( env, target )


class VariantCompletionTracker(object):
    """Track Progress variant paths that started but have not yet finished."""

    def __init__( self ):
        self._lock = threading.Lock()
        self._open_variants = set()
        self._complete_variants = set()

    def note_progress( self, event, variant ):
        if event == 'started' and variant:
            with self._lock:
                self._open_variants.add( variant )
                self._complete_variants.discard( variant )
        elif event == 'finished' and variant:
            with self._lock:
                self._open_variants.discard( variant )
                self._complete_variants.add( variant )

    def incomplete_variants( self ):
        with self._lock:
            return self._open_variants - self._complete_variants


def progress( label, event, sconscript, variant, env ):
    # Use the unwrapped builder when Cuppa has wrapped Command with
    # MethodWithProgress — otherwise NotifyProgress.add → Command →
    # NotifyProgress.add recurses forever (Command returns a NodeList).
    command = getattr( env, '_Command', None ) or env.Command
    return command( label, [], progress_action( label, event, sconscript, variant, env ) )


class Progress(object):

    def __init__( self, event, sconscript, variant, env ):
        self._event   = event
        self._file    = sconscript
        self._variant = variant
        self._env     = env

    def __call__( self, target, source, env ):
        NotifyProgress.call_callbacks( self._event, self._file, self._variant, self._env, target, source )
        if self._event == "sconstruct_end":
            write_terse_build_completion( self._env )
        return None


def progress_action( label, event, sconscript, variant, env ):

    progress = Progress( event, sconscript, variant, env )

    description = None

    if logger.isEnabledFor( logging.INFO ):
        stage = ""
        name  = ""
        if label.startswith("#"):
            stage = as_notice( label[1:] )
        elif not variant:
            stage = as_notice(label) + " sconscript: ["
            name = as_notice( sconscript ) + "]"
        else:
            stage = as_notice(label) + " variant: ["
            name = as_info( variant ) + "]"

        description = "Progress( {}{} )".format( stage, name )

    return Action( progress, description )


_terse_command = threading.local()
_terse_children = threading.local()
_pending_lock = threading.Lock()
# Commands stashed by a job thread and not yet consumed by a spawn. A Python
# action prints before it runs and never spawns, so the next print on that
# thread (or process exit) writes the line back out.
_pending_commands = {}


class _ProgressLedger(object):
    """Actions that will print a status line, by sconscript and variant.

    One executor is one tally, however many targets it writes. A static
    library's archive and index are two slots on that executor. A test
    binary's log files share one. Up-to-date work is already done.
    """

    def __init__( self ):
        self._lock = threading.Lock()
        self._nodes = {}
        self._executors = {}
        self._cells = {}
        self._done = 0
        self._total = 0
        self._narrowed = False
        self._action_digits = 3
        self._percent_digits = 2
        self._up_to_date = 0
        self._nested = 0
        self._test_cases = 0

    def reset( self ):
        with self._lock:
            self._nodes = {}
            self._executors = {}
            self._cells = {}
            self._done = 0
            self._total = 0
            self._narrowed = False
            self._action_digits = 3
            self._percent_digits = 2
            self._up_to_date = 0
            self._nested = 0
            self._test_cases = 0

    def register( self, env, nodes ):
        cell = _progress_cell( env )
        with self._lock:
            for node in _iter_nodes( nodes ):
                slots, executor_id = _action_slots( node )
                if slots <= 0 or executor_id is None:
                    continue
                existing = self._executors.get( executor_id )
                if existing is not None:
                    self._nodes[ id( node ) ] = existing
                    continue
                entry = {
                        "slots": slots,
                        "remaining": slots,
                        "cell": cell,
                }
                self._executors[ executor_id ] = entry
                self._nodes[ id( node ) ] = entry
                bucket = self._cells.setdefault( cell, { "done": 0, "total": 0 } )
                bucket[ "total" ] += slots
                self._total += slots

    def keep_reachable( self, roots ):
        """Drop actions that are not under the targets about to be built.

        An empty walk leaves the full set in place. A failed lookup must not
        turn the tally into zero.
        """
        with self._lock:
            if self._narrowed:
                return
            known = set( self._nodes )
        found = _reachable_ids( roots, known )
        with self._lock:
            if self._narrowed:
                return
            self._narrowed = True
            if not found:
                return
            entry_ids = set()
            for ident in found:
                entry = self._nodes.get( ident )
                if entry is not None:
                    entry_ids.add( id( entry ) )
            if not entry_ids:
                return
            self._nodes = {
                    ident: entry
                    for ident, entry in self._nodes.items()
                    if id( entry ) in entry_ids
            }
            self._rebuild_totals()

    def credit_and_prefix( self, target, current, env, count ):
        with self._lock:
            credited = False
            if count:
                credited = self._credit_unlocked( target, current, 1 )
            return credited, self._prefix_unlocked( _progress_cell( env ) )

    def credit_all_remaining( self, node ):
        with self._lock:
            entry = self._nodes.get( id( node ) )
            if entry is None:
                return False
            take = entry[ "remaining" ]
            if not self._credit_entry( entry, take ):
                return False
            self._up_to_date += take
            return True

    def note_nested( self ):
        with self._lock:
            self._nested += 1

    def note_test_cases( self, count ):
        try:
            count = int( count )
        except ( TypeError, ValueError ):
            return
        if count <= 0:
            return
        with self._lock:
            self._test_cases += count

    def plan_line( self ):
        """``3 sconscripts · 1 variant · 13465 actions``, or empty."""
        with self._lock:
            scripts = set()
            variants = set()
            seen = set()
            for entry in self._nodes.values():
                if id( entry ) in seen:
                    continue
                seen.add( id( entry ) )
                script, variant = entry[ "cell" ]
                if script:
                    scripts.add( script )
                if variant:
                    variants.add( variant )
            total = self._total
        return _plan_sentence( len( scripts ), len( variants ), total )

    def completion_clause( self, up_to_date_outcome ):
        """The counts that follow ``build succeeded`` or ``build up to date``."""
        with self._lock:
            total = self._total
            ran = self._done - self._up_to_date
            skipped = self._up_to_date
            cases = self._test_cases
            nested = self._nested
        if ran < 0:
            ran = 0
        if up_to_date_outcome:
            if not total:
                return ""
            return " · " + _plural( total, "action", "actions" )
        parts = []
        if ran and skipped:
            parts.append( "{} ran".format( ran ) )
            parts.append( "{} up to date".format( skipped ) )
        elif ran:
            parts.append( "{} ran".format( ran ) )
        elif skipped:
            parts.append( "{} up to date".format( skipped ) )
        if cases:
            parts.append( _plural( cases, "test case", "test cases" ) )
        if nested:
            parts.append( "{} nested".format( nested ) )
        if not parts:
            return ""
        return " · " + " · ".join( parts )

    def interrupt_summary( self ):
        """How far the whole build got, not only the actions still running.

        ``reached 57%: 1280/2245 · 80 ran · 1200 up to date``. The fraction is
        actions completed against the actions that were going to run. Completed
        counts both ``ran`` and ``up to date``.
        """
        with self._lock:
            total = self._total
            done = self._done
            ran = done - self._up_to_date
            skipped = self._up_to_date
            cases = self._test_cases
            nested = self._nested
        if ran < 0:
            ran = 0
        if done < 0:
            done = 0
        parts = []
        if total:
            percent = int( ( 100 * done + total // 2 ) / total )
            parts.append( "reached {}%: {}/{}".format( percent, done, total ) )
        if ran:
            parts.append( "{} ran".format( ran ) )
        if skipped:
            parts.append( "{} up to date".format( skipped ) )
        if cases:
            parts.append( _plural( cases, "test case", "test cases" ) )
        if nested:
            parts.append( "{} nested".format( nested ) )
        return " · ".join( parts )

    def _credit_unlocked( self, target, current, count ):
        for node in _iter_nodes( target ):
            entry = self._nodes.get( id( node ) )
            if entry is not None and entry[ "remaining" ] > 0:
                return self._credit_entry( entry, count )
        for node in _iter_nodes( current ):
            entry = self._nodes.get( id( node ) )
            if entry is not None and entry[ "remaining" ] > 0:
                return self._credit_entry( entry, count )
        return False

    def _credit_entry( self, entry, count ):
        take = entry[ "remaining" ] if count is None else min( int( count ), entry[ "remaining" ] )
        if take <= 0:
            return False
        entry[ "remaining" ] -= take
        bucket = self._cells.get( entry[ "cell" ] )
        if bucket is not None:
            bucket[ "done" ] += take
        self._done += take
        return True

    def _prefix_unlocked( self, cell ):
        bucket = self._cells.get( cell )
        if not bucket or not bucket[ "total" ] or not self._total:
            return ""
        percent = int( ( 100 * self._done + self._total // 2 ) / self._total )
        action_digits, percent_digits = self._prefix_widths( percent )
        return "{:>{}}/{:>{}} · {:>{}}%".format(
                bucket[ "done" ], action_digits,
                bucket[ "total" ], action_digits,
                percent, percent_digits,
        )

    def _prefix_widths( self, percent ):
        """Reserve three digits and two for the percent. Grow past 999 or 99."""
        widest = 0
        for bucket in self._cells.values():
            widest = max( widest, bucket[ "total" ], bucket[ "done" ] )
        if widest:
            self._action_digits = max( self._action_digits, len( str( widest ) ) )
        self._percent_digits = max( self._percent_digits, len( str( percent ) ) )
        return self._action_digits, self._percent_digits

    def _rebuild_totals( self ):
        self._cells = {}
        self._done = 0
        self._total = 0
        seen = set()
        for entry in self._nodes.values():
            if id( entry ) in seen:
                continue
            seen.add( id( entry ) )
            done = entry[ "slots" ] - entry[ "remaining" ]
            bucket = self._cells.setdefault( entry[ "cell" ], { "done": 0, "total": 0 } )
            bucket[ "total" ] += entry[ "slots" ]
            bucket[ "done" ] += done
            self._total += entry[ "slots" ]
            self._done += done


_progress_ledger = _ProgressLedger()
_current_action_target = threading.local()
_terse_action_accounted = threading.local()
_progress_narrowed = False
_progress_narrow_lock = threading.Lock()


def reset_progress_ledger():
    """Drop registered actions. The next build counts from empty."""
    global _progress_narrowed, _summary_enabled, _plan_written
    _progress_ledger.reset()
    _current_action_target.value = None
    _terse_action_accounted.done = False
    _summary_enabled = False
    _plan_written = False
    with _progress_narrow_lock:
        _progress_narrowed = False


def register_terse_actions( env, nodes ):
    """Count executors that will get a status line. No effect unless terse."""
    if not _env_get( env, "terse_output" ):
        return
    _progress_ledger.register( env, nodes )


def remember_terse_action_target( target ):
    """The Python action now running. Its roll-up credits this target."""
    _current_action_target.value = target


def forget_terse_action_target():
    _current_action_target.value = None


def _current_action_nodes():
    return getattr( _current_action_target, "value", None )


def note_terse_action_accounted():
    """This action already moved the tally. Do not count it again."""
    _terse_action_accounted.done = True


def take_terse_action_accounted():
    done = bool( getattr( _terse_action_accounted, "done", False ) )
    _terse_action_accounted.done = False
    return done


def note_up_to_date_action( node ):
    """SCons will not run this action. It is already done."""
    _progress_ledger.credit_all_remaining( node )


def note_terse_nested_action():
    """A nested ``Execute`` printed a status line. It is not an action."""
    _progress_ledger.note_nested()


def note_terse_test_cases( count ):
    """Case total from a test roll-up, including cases that were not printed."""
    _progress_ledger.note_test_cases( count )


def _action_slots( node ):
    """Status lines one executor will print, and an id for that executor.

    ``(0, None)`` is not an action. Several targets that share an executor
    count once.
    """
    has_builder = getattr( node, "has_builder", None )
    if not callable( has_builder ):
        return 0, None
    try:
        if not has_builder():
            return 0, None
    except Exception:
        return 0, None
    try:
        executor = node.get_executor()
    except Exception:
        return 1, id( node )
    if executor is None:
        return 1, id( node )
    try:
        actions = executor.get_action_list()
    except Exception:
        return 1, id( executor )
    slots = _slots_in( actions or [] )
    if slots <= 0:
        slots = 1
    return slots, id( executor )


def _slots_in( actions ):
    total = 0
    for action in actions:
        children = getattr( action, "list", None )
        if children:
            total += _slots_in( children )
        else:
            total += 1
    return total


def _progress_cell( env ):
    return ( _sconscript_label( env ), _variant_cell( env ) )


def _reachable_ids( roots, nodes ):
    found = set()
    seen = set()
    stack = [ node for node in roots or [] if node is not None ]
    while stack:
        node = stack.pop()
        if isinstance( node, ( str, bytes ) ):
            continue
        ident = id( node )
        if ident in seen:
            continue
        seen.add( ident )
        if ident in nodes:
            found.add( ident )
        for child in _graph_children( node ):
            stack.append( child )
    return found


def _graph_children( node ):
    kids = []
    children = getattr( node, "children", None )
    if callable( children ):
        try:
            kids.extend( children( scan=False ) )
        except Exception:
            pass
    prerequisites = getattr( node, "prerequisites", None )
    if prerequisites:
        try:
            kids.extend( prerequisites )
        except Exception:
            pass
    return kids


def _build_root_nodes():
    try:
        import SCons.Script as script
    except Exception:
        return []
    names = list( getattr( script, "BUILD_TARGETS", None ) or [] )
    if not names:
        defaults = list( getattr( script, "DEFAULT_TARGETS", None ) or [] )
        nodes = [ node for node in defaults if not isinstance( node, ( str, bytes ) ) ]
        if nodes and not names:
            return nodes
        names = [ node for node in defaults if isinstance( node, ( str, bytes ) ) ]
    if not names:
        return []
    try:
        env = script.DefaultEnvironment()
    except Exception:
        return [ node for node in names if not isinstance( node, ( str, bytes ) ) ]
    roots = []
    for name in names:
        if not isinstance( name, ( str, bytes ) ):
            roots.append( name )
            continue
        try:
            roots.extend( env.arg2nodes( [ name ] ) )
        except Exception:
            continue
    return roots


def narrow_progress_ledger( roots ):
    _progress_ledger.keep_reachable( roots )


def narrow_progress_ledger_once():
    """Keep the tally to the targets of this build. Once, on the first task."""
    global _progress_narrowed
    with _progress_narrow_lock:
        if _progress_narrowed:
            return
        _progress_narrowed = True
    narrow_progress_ledger( _build_root_nodes() )


def _credit_up_to_date_targets( targets ):
    try:
        import SCons.Node as node_module
        up_to_date = node_module.up_to_date
    except Exception:
        return
    for target in _iter_nodes( targets ):
        try:
            state = target.get_state()
        except Exception:
            continue
        if state == up_to_date:
            note_up_to_date_action( target )


def install_terse_progress_hooks():
    """Count up-to-date nodes, and ignore actions outside this build."""
    import SCons.Script.Main as main
    current = main.BuildTask.make_ready
    if getattr( current, "_cuppa_terse_ledger", False ):
        return

    def make_ready( self ):
        narrow_progress_ledger_once()
        write_terse_build_plan()
        current( self )
        _credit_up_to_date_targets( self.targets )

    make_ready._cuppa_terse_ledger = True
    main.BuildTask.make_ready = make_ready


def _account_and_prefix( target, env, count, mark=False ):
    credited, text = _progress_ledger.credit_and_prefix(
            target, _current_action_nodes(), env, count,
    )
    if credited and mark:
        note_terse_action_accounted()
    if not count or not text:
        return ""
    return _colour_counts_prefix( text )


def _colour_counts_prefix( text ):
    """Subdue the cell tally and separator, but leave the percent plain."""
    tally, separator, percent = text.partition( " · " )
    if not separator:
        return as_subdued( text )
    return as_subdued( tally + separator ) + percent


def terse_counts_prefix( env=None ):
    """`` 19/182 · 10%`` for this sconscript and variant, then the whole build.

    Counts reserve three digits and the percent two, and grow past 999 or
    99. Empty when nothing has been registered. The fraction is not a
    position in the sconscript list.
    """
    if env is None:
        return ""
    _credited, text = _progress_ledger.credit_and_prefix( None, None, env, False )
    if not text:
        return ""
    return _colour_counts_prefix( text )


def _is_progress_command( cmd ):
    return bool( cmd ) and cmd.lstrip().startswith( "Progress(" )


def _env_get( env, key, default=None ):
    if not env or not hasattr( env, "get" ):
        return default
    return env.get( key, default )


def _first_node( nodes ):
    if not nodes:
        return None
    if isinstance( nodes, ( list, tuple ) ):
        return nodes[0] if nodes else None
    return nodes


def _node_path( node ):
    if node is None:
        return ""
    path = getattr( node, "path", None )
    if path:
        return str( path )
    return str( node )


def _node_basename( nodes ):
    text = _node_path( _first_node( nodes ) ).replace( "\\", "/" )
    if not text:
        return ""
    return os.path.basename( text ) or text


def _iter_nodes( nodes ):
    if nodes is None or isinstance( nodes, ( str, bytes ) ):
        return []
    if hasattr( nodes, "attributes" ):
        return [ nodes ]
    if isinstance( nodes, ( list, tuple ) ):
        return list( nodes )
    try:
        return list( nodes )
    except TypeError:
        return [ nodes ]


def label_terse_action( nodes, action, paths=None ):
    """Remember ``action`` on each product node. A later status line reads it.

    Do not label a node that has more than one tool action. A static library is
    both ``archive`` and ``index``; the toolchain tells those apart from the
    command. One label would hide that.

    ``paths="transfer"`` prints ``source → dest`` even when the action word is
    shared with a single-file action (``run`` is both a program and a redirect).
    """
    if not action:
        return nodes
    for node in _iter_nodes( nodes ):
        attributes = getattr( node, "attributes", None )
        if attributes is None:
            continue
        try:
            attributes.cuppa_terse_action = action
            if paths:
                attributes.cuppa_terse_paths = paths
        except Exception:
            continue
    return nodes


def _explicit_terse_action( target ):
    """The method label, from whichever target carries it.

    An emitter often puts an intermediate file first. The label may be on a
    later product node in the same action.
    """
    for node in _iter_nodes( target ):
        attributes = getattr( node, "attributes", None )
        if attributes is None:
            continue
        label = str( getattr( attributes, "cuppa_terse_action", "" ) or "" )
        if label:
            return label
    return ""


def spell_terse_action( command, target, env=None ):
    """Short action word for one tool run. Not the Cuppa method name.

    A method label wins, then the active toolchain, then the shared tool
    speller. Anything else is ``run``. ``link`` is only a compiler driver
    producing a program.
    """
    label = _explicit_terse_action( target )
    if label:
        return label
    toolchain = _env_get( env, "toolchain" )
    spell = getattr( toolchain, "spell_terse_action", None )
    if callable( spell ):
        # getattr's default is None, so pylint still treats this as not callable.
        word = spell( command, target )  # pylint: disable=not-callable
        if word:
            return word
    from cuppa.toolchains.terse_actions import spell_tool_command
    return spell_tool_command( command, target ) or "run"


def _coloured_sconscript( label ):
    """Mute the directory. The leaf is info, not notice, beside ``[ok]``."""
    if "/" not in label:
        return as_info( label )
    directory, leaf = label.rsplit( "/", 1 )
    return as_subdued( directory + "/" ) + as_info( leaf )


def _sconscript_label( env ):
    path = str( _env_get( env, "sconscript_file", "" ) or "" ).replace( "\\", "/" )
    if path.startswith( "./" ):
        path = path[2:]
    if path == "sconscript":
        return ""
    if path.endswith( "/sconscript" ):
        return path[: -len( "/sconscript" )]
    if path.endswith( ".sconscript" ):
        return path[: -len( ".sconscript" )]
    return path


def _variant_name( env ):
    variant = _env_get( env, "variant" )
    if variant is None:
        return ""
    name = variant.name() if hasattr( variant, "name" ) else variant
    return str( name )


def _variant_cell( env ):
    """Toolchain, variant, arch, and abi. ``dbg`` alone is ambiguous across scripts."""
    toolchain = _env_get( env, "toolchain" )
    toolchain_name = toolchain.name() if hasattr( toolchain, "name" ) else ""
    parts = [
            str( part ) for part in (
                    toolchain_name,
                    _variant_name( env ),
                    _env_get( env, "target_arch", "" ) or "",
                    _env_get( env, "abi", "" ) or "",
            ) if part
    ]
    return "_".join( parts )


def _coloured_variant_cell( env ):
    """Mute the build cell, but leave ``dbg`` / ``rel`` / ``cov`` plain."""
    cell = _variant_cell( env )
    name = _variant_name( env )
    if not cell:
        return ""
    if not name:
        return as_subdued( cell )
    if cell == name:
        return name
    token = "_" + name + "_"
    if token in cell:
        before, after = cell.split( token, 1 )
        return as_subdued( before + "_" ) + name + as_subdued( "_" + after )
    if cell.startswith( name + "_" ):
        return name + as_subdued( cell[ len( name ): ] )
    if cell.endswith( "_" + name ):
        return as_subdued( cell[ : -len( name ) ] ) + name
    return as_subdued( cell )


def _slash( path ):
    return os.path.normpath( str( path ) ).replace( "\\", "/" )


def _under( path, root ):
    """True when ``path`` is ``root`` or a file inside it. No ``..`` climb."""
    if not path or not root:
        return False
    path = os.path.normcase( os.path.normpath( path ) )
    root = os.path.normcase( os.path.normpath( root ) )
    if path == root:
        return True
    return path.startswith( root + os.sep )


def _to_abs( raw, env ):
    """Absolute path. Relative node paths are from the project root, as SCons stores them."""
    if os.path.isabs( raw ):
        return os.path.normpath( raw )
    anchor = _env_get( env, "base_path" ) or os.getcwd()
    return os.path.normpath( os.path.join( anchor, raw ) )


def _home_display( abs_path ):
    """``~/...`` with ``/`` separators on every platform. Absolute when not under home."""
    home = os.path.normpath( os.path.expanduser( "~" ) )
    path = os.path.normpath( abs_path )
    if not home or home == "~":
        return path.replace( "\\", "/" )
    if os.path.normcase( path ) == os.path.normcase( home ):
        return "~"
    prefix = home + os.sep
    if os.path.normcase( path ).startswith( os.path.normcase( prefix ) ):
        return ( "~" + path[ len( home ): ] ).replace( "\\", "/" )
    return path.replace( "\\", "/" )


def _project_display( abs_path, env ):
    base = _env_get( env, "base_path", "" ) or ""
    if not base:
        return ""
    base = os.path.normpath( base )
    path = os.path.normpath( abs_path )
    if not _under( path, base ) or os.path.normcase( path ) == os.path.normcase( base ):
        return ""
    try:
        return os.path.relpath( path, base ).replace( "\\", "/" )
    except ValueError:
        return ""


def _is_file( path, env ):
    if not path:
        return False
    candidate = path if os.path.isabs( path ) else _to_abs( path, env )
    return os.path.isfile( candidate )


def _origin_path( node, env ):
    """Source-tree path when the file exists there, not only as a variant copy."""
    raw = _node_path( node )
    srcnode = getattr( node, "srcnode", None )
    if callable( srcnode ):
        try:
            origin = srcnode()
        except Exception:
            origin = None
        if origin is not None and origin is not node:
            origin_path = _node_path( origin )
            if (
                    origin_path
                    and not _is_variant_working_path( origin_path, env )
                    and _is_file( origin_path, env )
            ):
                return origin_path
    stripped = _strip_variant_working( raw, env )
    if stripped and _is_file( stripped, env ):
        return stripped
    return raw


def _is_variant_working_path( raw, env ):
    text = _slash( raw )
    tool = _slash( _env_get( env, "tool_variant_dir", "" ) or "" ).strip( "/" )
    if tool and ( "/" + tool + "/working/" ) in ( "/" + text ):
        return True
    build_dir = _env_get( env, "build_dir", "" ) or ""
    if not build_dir:
        return False
    return _under( _to_abs( raw, env ), _to_abs( build_dir, env ) )


def _strip_variant_working( raw, env ):
    """``.../<tool>/<variant>/<arch>/<abi>/working/<file>`` → source-tree path."""
    if not raw:
        return ""
    text = _slash( raw )
    tool = _slash( _env_get( env, "tool_variant_dir", "" ) or "" ).strip( "/" )
    needle = "/" + tool + "/working/" if tool else ""
    rest = ""
    if needle and needle in ( "/" + text ):
        rest = ( "/" + text ).split( needle, 1 )[1]
    else:
        build_dir = _env_get( env, "build_dir", "" ) or ""
        if build_dir:
            abs_raw = _to_abs( raw, env )
            abs_dir = _to_abs( build_dir, env )
            if _under( abs_raw, abs_dir ):
                rest = os.path.relpath( abs_raw, abs_dir ).replace( "\\", "/" )
    if not rest or rest == ".":
        return ""
    script = _sconscript_label( env )
    if script:
        return script + "/" + rest
    return rest


def _display_source_path( raw, env ):
    """Project-relative, else ``~/...``, else absolute. Never a ``../`` climb."""
    if not raw:
        return ""
    text = str( raw ).replace( "\\", "/" )
    if text.startswith( "~/" ) or text == "~":
        return text
    climbs = text == ".." or text.startswith( "../" )
    if not os.path.isabs( raw ) and not climbs:
        shown = _slash( raw )
        return "" if shown in ( "", "." ) else shown
    abs_path = _to_abs( raw, env )
    shown = _project_display( abs_path, env ) or _home_display( abs_path )
    if shown in ( "", "." ):
        return ""
    return shown


def _compile_file_parts( source, env ):
    """Source location in the project tree, or ``~/...`` when it lives outside."""
    node = _first_node( source )
    raw = _origin_path( node, env ) if node is not None else ""
    shown = _display_source_path( raw, env )
    if not shown:
        return "", ""
    directory, filename = os.path.split( shown )
    if directory in ( "", "." ):
        directory = ""
    return directory, filename or shown


def _coloured_file( directory, filename ):
    if not filename:
        return ""
    if directory:
        return as_subdued( directory + "/" ) + as_emphasised( as_info( filename ) )
    return as_emphasised( as_info( filename ) )


def _rel_inside( abs_path, root ):
    """Path of ``abs_path`` inside ``root``, or ``None`` when it is not inside."""
    root = os.path.normpath( root )
    path = os.path.normpath( abs_path )
    if not _under( path, root ):
        return None
    if os.path.normcase( path ) == os.path.normcase( root ):
        return ""
    try:
        return os.path.relpath( path, root ).replace( "\\", "/" )
    except ValueError:
        return None


def _strip_artifact_folder( relative, env ):
    """Drop this variant's artefact directory. The line already names the sconscript.

    Install uses one flat folder, ``<sconscript>_<variant>``, as the first
    directory under the artefacts root. Reports use
    ``flat_tool_variant_dir_offset`` (``gcc16_dbg_x86_64_cxx2c/test/cycle_events``)
    nested under a prefix such as ``test/``. Either way the remainder is the
    file. A path that is neither stays unchanged.
    """
    relative = str( relative or "" ).replace( "\\", "/" ).strip( "/" )
    if not relative:
        return relative
    flat = str( _env_get( env, "flat_build_base", "" ) or "" ).replace( "\\", "/" ).strip( "/" )
    if flat:
        head, _sep, tail = relative.partition( "/" )
        if os.path.normcase( head ) == os.path.normcase( flat ):
            return tail
    offset = str( _env_get( env, "flat_tool_variant_dir_offset", "" ) or "" ).replace( "\\", "/" ).strip( "/" )
    if not offset or offset in ( ".", "/" ):
        return relative
    parts = relative.split( "/" )
    offset_parts = offset.split( "/" )
    width = len( offset_parts )
    folded = [ os.path.normcase( part ) for part in parts ]
    needle = [ os.path.normcase( part ) for part in offset_parts ]
    for index in range( 0, len( parts ) - width + 1 ):
        if folded[ index : index + width ] == needle:
            return "/".join( parts[ index + width : ] )
    return relative


def _locate( raw, env ):
    """``(root, relative)`` for a path on a status line.

    ``root`` is ``working`` or ``final`` for this variant's build, or
    ``artifacts`` for this variant's folder under the artefacts root. Any
    other path there is a normal project path. Otherwise ``relative`` is the
    project path, ``~/...``, or an absolute path.
    """
    if not raw:
        return "", ""
    text = str( raw ).replace( "\\", "/" )
    if text.startswith( "~/" ) or text == "~":
        return "", text
    abs_path = _to_abs( raw, env )
    roots = (
            ( "final", "abs_final_dir" ),
            ( "working", "abs_build_dir" ),
            ( "artifacts", "abs_artefacts_root" ),
    )
    for token, key in roots:
        root = _env_get( env, key, "" ) or ""
        if token == "artifacts" and not root:
            root = _env_get( env, "abs_artifacts_root", "" ) or ""
        if not root:
            continue
        root_abs = root if os.path.isabs( root ) else _to_abs( root, env )
        relative = _rel_inside( abs_path, root_abs )
        if relative is None:
            continue
        if token == "artifacts":
            # ``<artifacts>`` is this variant's folder, not the artefacts root.
            # ``_artifacts/documentation/...`` is a real path and stays as-is.
            variant_relative = _strip_artifact_folder( relative, env )
            if variant_relative == relative:
                continue
            return token, variant_relative
        return token, relative
    return "", _display_source_path( raw, env )


def _coloured_transfer_end( token, relative, dest ):
    """One side of ``source → dest``.

    The source is entirely subdued. The destination directory is subdued and
    its filename is info-coloured and bold, not the info highlight.
    ``<working>``, ``<final>``, and
    ``<artifacts>`` mark build locations so they are not read as project paths.
    """
    relative = str( relative or "" ).replace( "\\", "/" ).strip( "/" )
    directory, filename = os.path.split( relative ) if relative else ( "", "" )
    if directory in ( "", "." ):
        directory = ""
    prefix = ( "<" + token + ">/" ) if token else ""
    if dest:
        head = prefix + ( directory + "/" if directory else "" )
        shown = as_subdued( head ) if head else ""
        if filename:
            shown += as_emphasised( as_info( filename ) )
        elif token:
            shown = as_subdued( "<" + token + ">" )
        return shown
    if token and relative:
        return as_subdued( prefix + relative )
    if token:
        return as_subdued( "<" + token + ">" )
    return as_subdued( relative ) if relative else ""


def _transfer_field( target, source, env ):
    source_token, source_path = _locate( _node_path( _first_node( source ) ), env )
    dest_token, dest_path = _locate( _node_path( _first_node( target ) ), env )
    source_text = _coloured_transfer_end( source_token, source_path, dest=False )
    dest_text = _coloured_transfer_end( dest_token, dest_path, dest=True )
    if source_text and dest_text:
        return source_text + " " + as_subdued( "→" ) + " " + dest_text
    return source_text or dest_text


def _paths_style( nodes ):
    for node in _iter_nodes( nodes ):
        attributes = getattr( node, "attributes", None )
        if attributes is None:
            continue
        style = str( getattr( attributes, "cuppa_terse_paths", "" ) or "" )
        if style:
            return style
    return ""


_TRANSFER_ACTIONS = ( "copy", "move", "expand", "render" )
_PATH_ACTIONS = ( "delete", "mkdir", "chmod" )
_SOURCE_ACTIONS = ( "markdown", "asciidoc" )


def _file_field( action, target, source, env ):
    if action in _TRANSFER_ACTIONS or _paths_style( target ) == "transfer":
        return _transfer_field( target, source, env )
    if action in _PATH_ACTIONS:
        return _path_action_field( _node_path( _first_node( target ) ), env )
    if action == "compile" or str( action ).startswith( "compile-" ) or action in _SOURCE_ACTIONS:
        directory, filename = _compile_file_parts( source, env )
        if filename:
            return _coloured_file( directory, filename )
    # A test's targets are the logs. The program is the source.
    if action == "test":
        return _coloured_file( "", _node_basename( source ) or _node_basename( target ) )
    return _coloured_file( "", _node_basename( target ) )


_STATUS_WIDTH = 6


def _status_field( painted, text ):
    """Keep ``[ok]`` in line with ``[pass]`` and ``[warn]``.

    The token is six columns. ``[error]``, ``[xfail]``, and ``[xpass]`` are
    seven, so they run one column past the rest. The pad sits outside the
    colour, so a short badge stays tight.
    """
    short = _STATUS_WIDTH - len( text )
    if short <= 0:
        return painted
    return painted + ( " " * short )


def _status_marker( status ):
    if status == "warn":
        text = "[warn]"
        painted = as_colour( "warning", text )
    elif status == "error":
        text = "[error]"
        painted = as_colour( "error", text )
    else:
        text = "[ok]"
        painted = as_colour( "success", text )
    return _status_field( painted, text )


def _test_status_marker( status ):
    """A ``test-case`` marker. Same shape as ``[ok]``, without a highlight badge."""
    if status == "fail":
        text = "[fail]"
        painted = as_colour( "error", text )
    elif status == "skip":
        text = "[skip]"
        painted = as_subdued( text )
    elif status == "xfail":
        text = "[xfail]"
        painted = as_colour( "expected_failure", text )
    elif status == "xpass":
        text = "[xpass]"
        painted = as_colour( "unexpected_success", text )
    else:
        text = "[pass]"
        painted = as_colour( "success", text )
    return _status_field( painted, text )


def _test_status_label( status ):
    """Roll-up ``[pass]``, as a quiet badge. The text matches a case marker."""
    if status == "fail":
        meaning, text = "error", "[fail]"
    elif status == "skip":
        meaning, text = "skipped", "[skip]"
    elif status == "xfail":
        meaning, text = "expected_failure", "[xfail]"
    elif status == "xpass":
        meaning, text = "unexpected_success", "[xpass]"
    else:
        meaning, text = "success", "[pass]"
    return _status_field( as_badge( meaning, text ), text )


def format_terse_duration( nanos ):
    """A short elapsed time: ``4 ms``, ``1.2 s``, or ``12 s``."""
    try:
        nanos = int( nanos )
    except ( TypeError, ValueError ):
        return ""
    if nanos < 0:
        return ""
    if nanos < 1000000000:
        return "{} ms".format( int( round( nanos / 1000000.0 ) ) )
    seconds = nanos / 1000000000.0
    if seconds < 10:
        return "{:.1f} s".format( seconds )
    return "{:.0f} s".format( seconds )


def _uncounted_prefix( env, marker ):
    """Indent ``→`` so ``[status]`` lines up with a counted line.

    The arrow means this line is not in the action total. The gap is the
    padded tally, minus one column for the arrow itself.
    """
    _credited, plain = _progress_ledger.credit_and_prefix( None, None, env, False )
    arrow = as_subdued( "→" )
    if not plain:
        return arrow + " " + marker
    return ( " " * ( len( plain ) - 1 ) ) + arrow + " " + marker


def format_terse_result_line( status, env, action, name, duration="", detail="" ):
    """``[status] sconscript · variant · action · duration · name — detail``.

    A test roll-up draws ``[pass]`` as a quiet badge. A ``test-case`` uses the same text
    in the status colour, and leads with ``→`` because it is not in the total.
    """
    child = action == "test-case"
    prefix = "" if child else _account_and_prefix( None, env, count=True, mark=True )
    fields = []
    script = _sconscript_label( env )
    if script:
        fields.append( _coloured_sconscript( script ) )
    cell = _coloured_variant_cell( env )
    if cell:
        fields.append( cell )
    fields.append( action )
    if duration:
        fields.append( as_subdued( duration ) )
    tail = name or ""
    if detail:
        tail = ( tail + " — " + detail ).strip()
    if tail:
        fields.append( tail )
    marker = _test_status_marker( status ) if child else _test_status_label( status )
    if child:
        marker = _uncounted_prefix( env, marker )
    parts = []
    if prefix:
        parts.append( prefix )
    parts.append( marker )
    if fields:
        parts.append( ( " " + as_subdued( "·" ) + " " ).join( fields ) )
    return " ".join( parts )


_terse_status_emitted = threading.local()


def note_terse_status_emitted():
    """The action printed its own status line. Skip the generic ``[ok]``."""
    note_terse_build_activity()
    _terse_status_emitted.done = True


def take_terse_status_emitted():
    done = bool( getattr( _terse_status_emitted, "done", False ) )
    _terse_status_emitted.done = False
    return done


def format_terse_line( status, command, target, source, env, count=True ):
    """``[status] sconscript · variant · action · file``.

    ``count=False`` is a line that is not in the action total, such as a
    nested copy or move. It leads with ``→``. The caller is still the action.
    """
    parts = []
    prefix = _account_and_prefix( target, env, count=count, mark=False )
    if prefix:
        parts.append( prefix )
    marker = _status_marker( status )
    if not count:
        marker = _uncounted_prefix( env, marker )
    parts.append( marker )

    fields = []
    script = _sconscript_label( env )
    if script:
        fields.append( _coloured_sconscript( script ) )
    cell = _coloured_variant_cell( env )
    if cell:
        fields.append( cell )
    action = spell_terse_action( command, target, env )
    fields.append( action )
    file_text = _file_field( action, target, source, env )
    if file_text:
        fields.append( file_text )
    if fields:
        parts.append( ( " " + as_subdued( "·" ) + " " ).join( fields ) )
    return " ".join( parts )


def format_terse_success( command, target, source, env ):
    return format_terse_line( "ok", command, target, source, env )


def stash_terse_command( cmd, target, source, env ):
    _terse_command.cmd = cmd
    _terse_command.target = target
    _terse_command.source = source
    _terse_command.env = env
    with _pending_lock:
        _pending_commands[ threading.get_ident() ] = ( cmd, target, source, env )


def note_terse_child( command, lines, failed=False ):
    """Remember a tool this Python action started, for the status line.

    The action calls this instead of printing the command. A clean tool is
    dropped. A warning, an error line, or a non-zero exit is printed before
    the summary. Safe under ``-j`` because the note stays on this job thread.
    """
    children = getattr( _terse_children, "items", None )
    if children is None:
        children = []
        _terse_children.items = children
    children.append( ( command, list( lines or [] ), bool( failed ) ) )


def take_terse_children():
    """Return and clear child tools noted on this job thread."""
    children = list( getattr( _terse_children, "items", None ) or [] )
    _terse_children.items = []
    return children


def _output_severity( lines ):
    """``error`` if any line is an error, else ``warn``, else ``ok``.

    Asciidoctor writes ``asciidoctor: ERROR:`` and still exits 0. The status
    line should say what the tool said. The action's own return code is
    unchanged, so SCons still decides whether the build failed.
    """
    severity = "ok"
    for line in lines or []:
        folded = str( line ).lower()
        if ": error:" in folded or folded.startswith( "error:" ):
            return "error"
        if ": warning:" in folded or folded.startswith( "warning:" ):
            severity = "warn"
    return severity


def take_terse_command():
    """Return and clear the command stashed on this job thread."""
    cmd = getattr( _terse_command, "cmd", None )
    target = getattr( _terse_command, "target", None )
    source = getattr( _terse_command, "source", None )
    env = getattr( _terse_command, "env", None )
    _terse_command.cmd = None
    _terse_command.target = None
    _terse_command.source = None
    _terse_command.env = None
    with _pending_lock:
        _pending_commands.pop( threading.get_ident(), None )
    return cmd, target, source, env


def _write_command( cmd ):
    if cmd:
        sys.stdout.write( cmd + "\n" )


def flush_unconsumed_terse_command():
    """Reprint a command whose action did not spawn on this thread."""
    cmd, _target, _source, _env = take_terse_command()
    _write_command( cmd )


def _factory_args( body ):
    """Arguments of a ``Copy("dest", "src")`` style command."""
    args = []
    index = 0
    length = len( body )
    while index < length:
        while index < length and body[index] in " \t\r\n":
            index += 1
        if index >= length:
            break
        if body[index] == '"':
            end = body.find( '"', index + 1 )
            if end < 0:
                args.append( body[index + 1:] )
                break
            args.append( body[index + 1:end] )
            index = end + 1
        else:
            end = body.find( ",", index )
            token = body[index: end if end >= 0 else length].strip()
            if token:
                args.append( token )
            index = end if end >= 0 else length
            continue
        while index < length and body[index] in " \t":
            index += 1
        if index < length and body[index] == ",":
            index += 1
    return args


def _executed_paths( command, target, source ):
    """Nodes for an ``Execute`` action. ``Execute`` itself passes empty lists.

    ``Copy("dest", "src")`` and ``Move("dest", "src")`` carry the paths in the
    command text. Other commands keep the nodes SCons passed in.
    """
    text = str( command or "" ).strip()
    name, _open, body = text.partition( "(" )
    key = name.strip().lower()
    if key not in ( "copy", "move" ) or not body.endswith( ")" ):
        return target, source
    args = _factory_args( body[:-1] )
    dest = args[0] if args else ""
    src = args[1] if len( args ) > 1 else ""
    if not _node_path( _first_node( target ) ) and dest:
        target = [ dest ]
    if not _node_path( _first_node( source ) ) and src:
        source = [ src ]
    return target, source


def _quoted_args( text ):
    args = []
    body = str( text or "" )
    index = 0
    while True:
        start = body.find( '"', index )
        if start < 0:
            return args
        end = body.find( '"', start + 1 )
        if end < 0:
            return args
        args.append( body[ start + 1:end ] )
        index = end + 1


def _path_action_field( path, env ):
    """One path for ``delete``, ``mkdir``, or ``chmod``."""
    if not path:
        return ""
    token, relative = _locate( path, env )
    if token:
        return _coloured_transfer_end( token, relative, dest=True )
    shown = str( relative or path ).replace( "\\", "/" )
    directory, filename = os.path.split( shown )
    if directory in ( "", "." ):
        directory = ""
    return _coloured_file( directory, filename or shown )


def _present_executed_command( command, target, source, env, failed ):
    """Print a nested ``Execute``. Return whether that replaced the parent line.

    ``Touch`` only stamps a file the caller already reports, so it is dropped.
    Every other call is an uncounted status line. ``Copy`` and ``Move`` show
    ``source → dest``. ``Delete``, ``Mkdir``, and ``Chmod`` show the path.
    Anything else is ``run``, and its command is printed only on failure.
    """
    text = str( command or "" ).strip()
    if not text:
        return False
    key = text.split( "(", 1 )[0].strip().lower()
    if key == "touch":
        return False
    if failed:
        _write_command( text )
    if key in ( "copy", "move" ):
        use_target, use_source = _executed_paths( text, target, source )
        spell = text
    elif key in ( "delete", "mkdir", "chmod" ):
        paths = _quoted_args( text )
        use_target = [ paths[0] ] if paths else target
        use_source = []
        spell = text
    else:
        use_target, use_source = target, source
        spell = ""
    sys.stdout.write(
            format_terse_line(
                    "error" if failed else "ok",
                    spell,
                    use_target,
                    use_source,
                    env,
                    count=False,
            )
            + "\n"
    )
    sys.stdout.flush()
    note_terse_nested_action()
    note_terse_status_emitted()
    return True


def flush_terse_commands():
    """Reprint commands still stashed when the process exits."""
    with _pending_lock:
        leftover = list( _pending_commands.values() )
        _pending_commands.clear()
    for cmd, _target, _source, _env in leftover:
        _write_command( cmd )


def terse_print_cmd_line( cmd, target, source, env ):
    """SCons ``PRINT_CMD_LINE_FUNC`` for ``--terse-output``.

    ``Progress(...)`` lines are printed, as they are without this flag.
    ``-Q`` still omits them, because ``progress_action`` only builds the
    description at info. Tool commands are stashed and printed later, only
    when that run warns or fails. Show and execute run on the same SCons job
    thread, so a per-thread stash pairs them under ``-j``. A command that
    never reaches a spawn is written back on the next print, or at process exit.
    """
    flush_unconsumed_terse_command()
    if _is_progress_command( cmd ):
        sys.stdout.write( cmd + "\n" )
        return
    stash_terse_command( cmd, target, source, env )


atexit.register( flush_terse_commands )


def _chunk_lines( chunk ):
    if not chunk:
        return []
    text = chunk[:-1] if chunk.endswith( "\n" ) else chunk
    if not text:
        return []
    return text.split( "\n" )


def render_terse_spawn( returncode, errors, warnings, buffered_lines, command, target, source, env, summary ):
    """Lines to print after a terse tool run.

    A clean exit with no warnings is one success line. A warning or failure
    prints the command and the processed output first, then the status line
    as the summary.
    """
    note_terse_build_activity()
    if not returncode and not errors and not warnings:
        status = "ok"
    elif returncode or errors:
        status = "error"
    else:
        status = "warn"
    status_line = format_terse_line( status, command, target, source, env )
    if status == "ok":
        return [ status_line ]
    lines = []
    if command:
        lines.append( command )
    for chunk in buffered_lines or []:
        lines.extend( _chunk_lines( chunk ) )
    lines.extend( _chunk_lines( summary ) )
    lines.append( status_line )
    return lines


class _TersePythonCallable( object ):
    """Run a Python action, then print its terse status line.

    Installed only on environments that asked for ``--terse-output``. A shared
    builder still used without that flag calls the original and stops.
    """

    def __init__( self, original ):
        self._original = original
        name = getattr( original, "__name__", None ) or original.__class__.__name__
        self.__name__ = name
        inner = getattr( original, "strfunction", None )
        if callable( inner ):
            self.strfunction = inner

    def __call__( self, target, source, env, **ignored ):
        if not _env_get( env, "terse_output" ):
            return self._original( target=target, source=source, env=env )
        take_terse_action_accounted()
        remember_terse_action_target( target )
        try:
            try:
                result = self._original( target=target, source=source, env=env )
            except ( KeyboardInterrupt, SystemExit ):
                raise
            except Exception:
                self._finish_python_action( target, source, env, failed=True )
                raise
            self._finish_python_action( target, source, env, failed=bool( result ) )
            return result
        finally:
            forget_terse_action_target()

    def _finish_python_action( self, target, source, env, failed ):
        if take_terse_status_emitted():
            take_terse_command()
            take_terse_children()
            if not take_terse_action_accounted():
                # Nested copies printed the lines. This action still counts.
                _account_and_prefix( target, env, count=True, mark=False )
            return
        _report_python_action( target, source, env, failed=failed )


def _is_python_action_dump( command ):
    """True for SCons' default ``Name([...], [...])`` description.

    That text is the callable and the node lists, not the program that ran.
    """
    text = str( command or "" ).lstrip()
    name, sep, _rest = text.partition( "(" )
    if not sep or not name:
        return False
    return name.replace( "_", "" ).isalnum() and ( name[0].isalpha() or name[0] == "_" )


def _report_python_action( target, source, env, failed ):
    """Consume the stashed description. A clean run is one line.

    A warning or failure prints the tool command and its output first, then
    the status line. A child noted with ``note_terse_child`` is that tool.
    Otherwise the SCons description is used.
    """
    command, stashed_target, stashed_source, stashed_env = take_terse_command()
    children = take_terse_children()
    use_target = target or stashed_target
    use_source = source or stashed_source
    use_env = env or stashed_env or {}
    severity = "error" if failed else "ok"
    for _child_command, lines, child_failed in children:
        if child_failed:
            severity = "error"
            continue
        child_severity = _output_severity( lines )
        if child_severity == "error":
            severity = "error"
        elif child_severity == "warn" and severity == "ok":
            severity = "warn"
    spell_command = command or ""
    if children and not _explicit_terse_action( use_target ):
        spell_command = children[0][0]
    status_line = format_terse_line(
            severity,
            spell_command,
            use_target,
            use_source,
            use_env,
    )
    if severity != "ok":
        if children:
            for child_command, lines, _child_failed in children:
                _write_command( child_command )
                for line in lines:
                    _write_command( line )
        elif command and not _is_python_action_dump( command ):
            _write_command( command )
    note_terse_build_activity()
    sys.stdout.write( status_line + "\n" )
    sys.stdout.flush()


def _wrap_action( action ):
    """Replace a ``FunctionAction`` body without changing its build signature.

    ``FunctionAction`` stores the signature at construction. Swapping
    ``execfunction`` afterwards leaves that signature alone. Command actions
    stay on the spawn path. ``Progress`` actions stay quiet.
    """
    if action is None:
        return
    list_action = getattr( action, "list", None )
    if list_action is not None and not hasattr( action, "execfunction" ):
        for child in list_action:
            _wrap_action( child )
        return
    original = getattr( action, "execfunction", None )
    if original is None or getattr( action, "_cuppa_terse_wrapped", False ):
        return
    if isinstance( original, Progress ) or isinstance( original, _TersePythonCallable ):
        return
    action.execfunction = _TersePythonCallable( original )
    action._cuppa_terse_wrapped = True


def _wrap_builder( builder ):
    try:
        action = getattr( builder, "action", None )
    except Exception:
        return
    _wrap_action( action )


def _wrap_nodes( nodes ):
    for node in _iter_nodes( nodes ):
        executor = getattr( node, "executor", None )
        if executor is None:
            continue
        getter = getattr( executor, "get_action_list", None )
        actions = getter() if callable( getter ) else ()
        for action in actions:
            _wrap_action( action )


def _wrap_factory( env, name, after ):
    current = getattr( env, name, None )
    if current is None or getattr( current, "_cuppa_terse_factory", False ):
        return

    def factory( *args, **kwargs ):
        result = current( *args, **kwargs )
        after( result )
        return result

    factory._cuppa_terse_factory = True
    setattr( env, name, factory )


def enable_terse_python_actions( env ):
    """Give Python actions a terse status line. No effect unless ``--terse-output``."""
    if not _env_get( env, "terse_output" ):
        return
    if getattr( env, "_cuppa_terse_python_actions", False ):
        return
    try:
        env._cuppa_terse_python_actions = True
    except Exception:
        return
    builders = _env_get( env, "BUILDERS" ) or {}
    try:
        values = builders.values()
    except AttributeError:
        values = ()
    for builder in values:
        _wrap_builder( builder )
    _wrap_factory( env, "Builder", _wrap_builder )
    _wrap_factory( env, "Command", _wrap_nodes )
    # SCons keeps one process-wide install action. Wrapping ``env.Install``
    # reaches it. The printed ``Install file:`` line is then a ``copy`` status.
    for name in ( "Install", "InstallAs", "InstallVersionedLib" ):
        _wrap_factory( env, name, _wrap_nodes )
    # ``env.Execute(Copy(...))`` prints through ``PRINT_CMD_LINE_FUNC`` and
    # then returns. Nothing consumes that command, so the next print flushes
    # it raw and knocks the caller's description out of the stash.
    _wrap_execute( env )


def _wrap_execute( env ):
    current = getattr( env, "Execute", None )
    if current is None or getattr( current, "_cuppa_terse_execute", False ):
        return

    def execute( action, *args, **kwargs ):
        if not _env_get( env, "terse_output" ):
            return current( action, *args, **kwargs )
        saved = take_terse_command()
        try:
            result = current( action, *args, **kwargs )
        except ( KeyboardInterrupt, SystemExit ):
            if saved[0]:
                stash_terse_command( *saved )
            raise
        except Exception:
            take_terse_command()
            if saved[0]:
                stash_terse_command( *saved )
            raise
        nested = take_terse_command()
        visible = _present_executed_command(
                nested[0], nested[1], nested[2], env, failed=bool( result ),
        )
        if saved[0] and not visible:
            stash_terse_command( *saved )
        return result

    execute._cuppa_terse_execute = True
    try:
        env.Execute = execute
    except Exception:
        return




