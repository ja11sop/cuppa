
#          Copyright Jamie Allsop 2013-2015
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   Progress
#-------------------------------------------------------------------------------

import atexit
import os.path
import signal
import sys
import threading

from cuppa.colourise import (
        as_badge, as_colour, as_emphasised, as_emphasised_plain, as_info, as_notice, as_subdued,
)

from SCons.Script import Action


def _write_terse_stdout( text ):
    """Write a terse transcript fragment; serialize under ``-j`` / ``--parallel``.

    Clears the quiet heartbeat first when diverting. A process-wide transcript
    lock prevents interleaved lines such as ``format.ovariant``.
    """
    try:
        from cuppa.utility.heartbeat import write_transcript
        write_transcript( text )
        return
    except Exception:
        pass
    sys.stdout.write( text )
    try:
        sys.stdout.flush()
    except Exception:
        pass


_interrupt_announced = False
_abort_announced = False
_interrupt_finished = False
_interrupt_lock = threading.Lock()
_terse_activity_seen = False
_terse_activity_lock = threading.Lock()
_summary_enabled = False


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
    _write_terse_stdout( as_subdued( "finished in-flight actions" ) + "\n" )
    summary = ""
    if _summary_enabled:
        summary = _progress_ledger.interrupt_summary()
    line = as_notice( "[interrupted]" )
    if summary:
        line += " " + summary
    _write_terse_stdout( line + "\n" )
    sys.stdout.flush()


def write_terse_build_completion( env ):
    """Finish a successful terse build, including a no-op build under ``-Q``."""
    if not _env_get( env, "terse_output" ) or _interrupt_announced:
        return
    outcome = "succeeded" if terse_build_had_activity() else "up to date"
    suffix = ""
    if _summary_enabled:
        suffix = _progress_ledger.completion_clause( outcome == "up to date" )
    _write_terse_stdout( as_colour( "success", "[completed]" ) + " build " + outcome + suffix + "\n" )
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
        write_terse_progress_checkpoint( self._event, self._file, self._variant, self._env )
        if self._event == "sconstruct_end":
            write_terse_build_completion( self._env )
        return None


def progress_action( label, event, sconscript, variant, env ):

    progress = Progress( event, sconscript, variant, env )

    description = None

    # Terse checkpoints are printed by ``Progress`` itself, including under
    # ``-Q``. The description would also print ``Progress(...)`` at info.
    # Quiet console keeps the info description off (heartbeat is separate).
    from cuppa.utility.heartbeat import multi_line_progress_allowed
    if not _env_get( env, "terse_output" ) and multi_line_progress_allowed():
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
_terse_launch = threading.local()
_pending_lock = threading.Lock()
# Commands stashed by a job thread and not yet consumed by a spawn. A Python
# action prints before it runs and never spawns, so the next print on that
# thread (or process exit) writes the line back out.
_pending_commands = {}
_terse_locations = []
_terse_locations_lock = threading.Lock()
_terse_prepare_written = False
_terse_ready_written = False
_written_sconstruct_maps = set()


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
        self._percent_digits = 3
        self._up_to_date = 0
        self._nested = 0
        self._test_cases = 0
        self._lookahead_done = False

    def reset( self ):
        with self._lock:
            self._nodes = {}
            self._executors = {}
            self._cells = {}
            self._done = 0
            self._total = 0
            self._narrowed = False
            self._action_digits = 3
            self._percent_digits = 3
            self._up_to_date = 0
            self._nested = 0
            self._test_cases = 0
            self._lookahead_done = False

    def register( self, env, nodes ):
        cell = _progress_cell( env )
        with self._lock:
            for node in _iter_nodes( nodes ):
                slots, executor_id = _action_slots( node )
                if slots <= 0 or executor_id is None:
                    continue
                existing = self._executors.get( executor_id )
                if existing is not None:
                    existing[ "nodes" ].append( node )
                    self._nodes[ id( node ) ] = existing
                    continue
                entry = {
                        "slots": slots,
                        "remaining": slots,
                        "cell": cell,
                        "nodes": [ node ],
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

    def credit_currently_up_to_date( self ):
        """Count actions SCons already considers current. Once per build.

        ``is_up_to_date`` is not free, and nothing outside ``--terse-output``
        shows this tally, so the caller is the terse sconstruct begin line.
        A later ``make_ready`` visit credits the same node again and finds
        nothing left. A file that looks current can still be rebuilt when this
        build regenerates an input it uses. That run does not move the tally
        a second time.
        """
        with self._lock:
            if self._lookahead_done:
                return
            self._lookahead_done = True
            pending = []
            seen = set()
            for entry in self._nodes.values():
                if id( entry ) in seen or entry[ "remaining" ] <= 0:
                    continue
                seen.add( id( entry ) )
                live = [
                        node for node in entry[ "nodes" ]
                        if self._nodes.get( id( node ) ) is entry
                ]
                pending.append( ( entry, live ) )
        for entry, live in pending:
            if live and all( _node_is_currently_up_to_date( node ) for node in live ):
                self._credit_live_entry( entry )

    def _credit_live_entry( self, entry ):
        with self._lock:
            if entry[ "remaining" ] <= 0:
                return False
            if not any( candidate is entry for candidate in self._nodes.values() ):
                return False
            take = entry[ "remaining" ]
            if not self._credit_entry( entry, take ):
                return False
            self._up_to_date += take
            return True

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
        counts = self.checkpoint_counts( None, None )
        return _plan_sentence( counts[ "scripts" ], counts[ "variants" ], counts[ "total" ] )

    def checkpoint_counts( self, script, variant ):
        """Tallies for one progress checkpoint. Does not credit an action."""
        with self._lock:
            scripts = set()
            variants = set()
            script_variants = set()
            script_done = 0
            script_total = 0
            cell_done = 0
            cell_total = 0
            for cell, bucket in self._cells.items():
                entry_script, entry_variant = cell
                if entry_script:
                    scripts.add( entry_script )
                if entry_variant:
                    variants.add( entry_variant )
                if script is not None and entry_script == script:
                    script_done += bucket[ "done" ]
                    script_total += bucket[ "total" ]
                    if entry_variant:
                        script_variants.add( entry_variant )
                if cell == ( script, variant ):
                    cell_done = bucket[ "done" ]
                    cell_total = bucket[ "total" ]
            total = self._total
            done = self._done
            if total:
                percent = int( ( 100 * done + total // 2 ) / total )
            else:
                percent = 0
            _action_digits, percent_digits = self._prefix_widths( percent )
        return {
                "percent": percent,
                "percent_digits": percent_digits,
                "scripts": len( scripts ),
                "variants": len( variants ),
                "done": done,
                "total": total,
                "script_variants": len( script_variants ),
                "script_done": script_done,
                "script_total": script_total,
                "cell_done": cell_done,
                "cell_total": cell_total,
        }

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

    def action_line_indent( self ):
        """Spaces that put ``[ok]`` in the same column as ``[progress]``.

        The scope word is ten columns and the cell tally reserves three
        digits, which is one space short. Past 999 the tally is wider, so
        the progress line takes the extra columns instead.
        """
        with self._lock:
            digits = self._action_digits
        gap = _SCOPE_WIDTH - ( 2 * digits ) - 3
        return max( gap, 0 )

    def progress_line_indent( self ):
        with self._lock:
            digits = self._action_digits
        gap = _SCOPE_WIDTH - ( 2 * digits ) - 3
        return max( -gap, 0 )

    def _prefix_widths( self, percent ):
        """Reserve three digits for the tally and three for the percent.

        Percent needs three from the start so ``100%`` does not nudge ``[ok]``
        one column past earlier `` 13%`` lines. Grow past 999 actions or 100%.
        """
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
    global _progress_narrowed, _summary_enabled
    global _terse_prepare_written, _terse_ready_written
    _progress_ledger.reset()
    _current_action_target.value = None
    _terse_action_accounted.done = False
    _summary_enabled = False
    _terse_prepare_written = False
    _terse_ready_written = False
    with _progress_narrow_lock:
        _progress_narrowed = False
    with _terse_locations_lock:
        _terse_locations[:] = []
        _written_sconstruct_maps.clear()


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


def _node_is_currently_up_to_date( node ):
    """True when SCons would skip this node given the tree as it is now."""
    has_builder = getattr( node, "has_builder", None )
    if not callable( has_builder ):
        return False
    try:
        if not has_builder() or getattr( node, "always_build", False ):
            return False
        current = getattr( node, "is_up_to_date", None )
        if not callable( current ):
            return False
        return bool( current() )
    except Exception:
        return False


def credit_terse_up_to_date_lookahead():
    """Count up-to-date actions before the first terse begin line."""
    _progress_ledger.credit_currently_up_to_date()


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
    """`` 19/182 ·  10%`` for this sconscript and variant, then the whole build.

    Counts reserve three digits and the percent three (so ``100%`` does not
    shift the status column), and grow past 999. Empty when nothing has been
    registered. The fraction is not a position in the sconscript list.
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


_SHARED_ACROSS_VARIANTS = "shared_across_variants"


def label_terse_action( nodes, action, paths=None, summary=None, shared=None ):
    """Remember ``action`` on each product node. A later status line reads it.

    Do not label a node that has more than one tool action. A static library is
    both ``archive`` and ``index``; the toolchain tells those apart from the
    command. One label would hide that.

    ``paths="transfer"`` prints ``source → dest`` even when the action word is
    shared with a single-file action (``run`` is both a program and a redirect).

    ``summary`` replaces the file cell (delegated builders: ``-B …`` instead of
    a stamp basename such as ``cmake.build.complete``).

    ``paths="product"`` prints the located target path (token + leaf), for a
    delegated close whose news is the artefact, not a stamp name.

    ``shared`` replaces the variant cell when the author knows the tool is
    build-wide (e.g. Boost bootstrap ``build-b2``). ``True`` means
    ``shared_across_variants``. Not inferred from the Depends graph.
    """
    if not action and not summary and shared is None and not paths:
        return nodes
    if shared is True:
        shared = _SHARED_ACROSS_VARIANTS
    for node in _iter_nodes( nodes ):
        attributes = getattr( node, "attributes", None )
        if attributes is None:
            continue
        try:
            if action:
                attributes.cuppa_terse_action = action
            if paths:
                attributes.cuppa_terse_paths = paths
            if summary:
                attributes.cuppa_terse_summary = summary
            if shared is not None:
                attributes.cuppa_terse_shared = str( shared )
        except Exception:
            continue
    return nodes


def location_source_kind( location ):
    """``archive`` or ``repository`` from a resolved ``Location``."""
    kind_fn = getattr( location, "source_kind", None )
    if callable( kind_fn ):
        kind = str( kind_fn() or "" ).strip()
        if kind:
            return kind
    return "repository"


def label_terse_location( env, name, path, scope="sconscript", build_folder=None, kind="" ):
    """Register a named root for terse file cells and begin-line maps.

    Built-in tokens (``working``, ``final``, ``artefacts``, ``variant``) come
    from the env on variant begin. Authors and Cuppa add extras such as
    ``fmt`` or ``boost``. ``scope`` is ``sconstruct``, ``sconscript``, or
    ``variant``. Sconstruct-scoped maps print under ``[prepare]``,
    not on sconstruct begin. ``<packages>`` is variant-scoped: the extract
    dir follows the package tool variant. ``build_folder`` is the first
    segment under ``abs_build_root`` for this tree (usually
    ``Location.local_folder()``). ``kind`` is ``root``, ``repository``,
    ``archive``, or ``package`` on read-phase maps. Not inferred from
    ``_download`` folder names.
    """
    token = str( name or "" ).strip().strip( "<>" )
    if not token or not path:
        return
    abs_path = _to_abs( path, env )
    if _is_project_root( abs_path, env ):
        return
    scope = str( scope or "sconscript" )
    script = "" if scope == "sconstruct" else _sconscript_label( env )
    cell = _variant_cell( env ) if scope == "variant" else ""
    folder = str( build_folder or "" ).replace( "\\", "/" ).strip( "/" )
    kind = str( kind or "" ).strip()
    entry = ( scope, script, cell, token, abs_path, folder, kind )
    with _terse_locations_lock:
        kept = [
                item for item in _terse_locations
                if not (
                        item[0] == entry[0]
                        and item[1] == entry[1]
                        and item[3] == entry[3]
                        and ( entry[0] != "variant" or item[2] == entry[2] )
                )
        ]
        kept.append( entry )
        _terse_locations[:] = kept
    if (
            scope == "sconstruct"
            and token != "packages"
            and _env_get( env, "terse_output" )
            and not _env_get( env, "clean" )
            and _terse_prepare_written
    ):
        _emit_sconstruct_location_map( token, abs_path, env, kind=kind )


def _author_locations():
    with _terse_locations_lock:
        return list( _terse_locations )


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


def _explicit_terse_summary( target ):
    """Method-supplied file-cell summary, from whichever target carries it."""
    for node in _iter_nodes( target ):
        attributes = getattr( node, "attributes", None )
        if attributes is None:
            continue
        summary = str( getattr( attributes, "cuppa_terse_summary", "" ) or "" )
        if summary:
            return summary
    return ""


def _explicit_terse_shared( target ):
    """Author-supplied shared-build label for the variant slot, or empty."""
    for node in _iter_nodes( target ):
        attributes = getattr( node, "attributes", None )
        if attributes is None:
            continue
        shared = str( getattr( attributes, "cuppa_terse_shared", "" ) or "" )
        if shared:
            return shared
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


def _coloured_shared_label( text ):
    """``shared`` plain; a suffix such as ``_across_variants`` subdued."""
    text = str( text or "" )
    if not text:
        return ""
    if text.startswith( "shared" ) and len( text ) > len( "shared" ):
        return "shared" + as_subdued( text[ len( "shared" ): ] )
    return text


def _coloured_build_cell( env, target=None ):
    """Variant cell, or an author-supplied shared label when present on ``target``."""
    shared = _explicit_terse_shared( target )
    if shared:
        return _coloured_shared_label( shared )
    return _coloured_variant_cell( env )


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
    text = str( raw or "" )
    if text.startswith( "~" ):
        return os.path.normpath( os.path.expanduser( text ) )
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
    """Source location: project path, nested tokens, or ``~/...``."""
    node = _first_node( source )
    raw = _origin_path( node, env ) if node is not None else ""
    token, relative = _locate( raw, env, allow_variant_roots=False )
    if token:
        relative = str( relative or "" ).replace( "\\", "/" ).strip( "/" )
        prefix = "<" + token + ">"
        shown = prefix + ( "/" + relative if relative else "" )
    else:
        shown = relative or _display_source_path( raw, env )
    if not shown:
        return "", ""
    shown = str( shown ).replace( "\\", "/" )
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


def _unpack_location( item ):
    if len( item ) >= 7:
        return item[0], item[1], item[2], item[3], item[4], item[5], item[6]
    if len( item ) >= 6:
        return item[0], item[1], item[2], item[3], item[4], item[5], ""
    return item[0], item[1], item[2], item[3], item[4], "", ""


def _with_variant_token( relative, env ):
    """Replace this env's ``tool_variant_dir`` segments with ``<variant>``."""
    relative = str( relative or "" ).replace( "\\", "/" )
    tool = _slash( _env_get( env, "tool_variant_dir", "" ) or "" ).strip( "/" )
    if not relative or not tool:
        return relative
    parts = [ part for part in relative.split( "/" ) if part != "" ]
    tool_parts = [ part for part in tool.split( "/" ) if part != "" ]
    width = len( tool_parts )
    if not width or len( parts ) < width:
        return relative
    folded = [ os.path.normcase( part ) for part in parts ]
    needle = [ os.path.normcase( part ) for part in tool_parts ]
    out = []
    index = 0
    while index < len( parts ):
        if folded[ index:index + width ] == needle:
            out.append( "<variant>" )
            index += width
        else:
            out.append( parts[ index ] )
            index += 1
    prefix = "/" if relative.startswith( "/" ) else ""
    return prefix + "/".join( out )


def _is_project_root( path, env ):
    """True when ``path`` is the sconstruct directory or project ``base_path``."""
    if not path:
        return False
    path = os.path.normcase( os.path.normpath( path ) )
    for key in ( "sconstruct_dir", "base_path" ):
        root = _env_get( env, key, "" ) or ""
        if not root:
            continue
        other = os.path.normcase( _to_abs( root, env ) )
        if path == other:
            return True
    return False


_CATEGORY_LOCATION_TOKENS = frozenset( ( "dependencies", "packages" ) )


def _nested_author_match( abs_path, env ):
    """Distinct nested tokens from a category root to the innermost.

    ``dependencies`` and ``packages`` are category roots. A package extract
    under the download root is ``<packages>/<boost_package>``, not
    ``<dependencies>/<packages>/<boost_package>``.
    """
    by_root = {}
    for item in _author_locations():
        _scope, _script, _cell, token, root, _folder, _kind = _unpack_location( item )
        if _is_project_root( root, env ):
            continue
        relative = _rel_inside( abs_path, root )
        if relative is None:
            continue
        key = os.path.normcase( os.path.normpath( root ) )
        length = len( os.path.normpath( root ) )
        existing = by_root.get( key )
        if existing is None:
            by_root[ key ] = ( length, token, relative, key )
    if not by_root:
        return None
    ranked = sorted( by_root.values(), key=lambda item: item[0] )
    _length, inner_token, inner_relative, inner_key = ranked[ -1 ]
    tokens = []
    for _length, token, _relative, key in reversed( ranked ):
        contained = (
                inner_key == key
                or inner_key.startswith( key + os.sep )
                or inner_key.startswith( key + "/" )
        )
        if not contained:
            continue
        if token not in tokens:
            tokens.append( token )
        if token in _CATEGORY_LOCATION_TOKENS:
            break
    if not tokens:
        tokens = [ inner_token ]
    tokens.reverse()
    return ">/<" .join( tokens ), inner_relative


def _token_for_build_folder( folder ):
    folder = str( folder or "" ).replace( "\\", "/" ).strip( "/" )
    if not folder:
        return ""
    for item in _author_locations():
        _scope, _script, _cell, token, root, mapped, _kind = _unpack_location( item )
        mapped = mapped or os.path.basename( str( root ).rstrip( "\\/" ) )
        if os.path.normcase( mapped ) == os.path.normcase( folder ):
            return token
    return ""


def _locate( raw, env, allow_variant_roots=True ):
    """``(root, relative)`` for a path on a status line.

    ``root`` is ``working`` or ``final`` for this variant's build,
    ``artefacts`` for this variant's folder under the artefacts root, or a
    nested token key such as ``dependencies>/<fmt``. A path under
    ``abs_build_root`` whose first folder is a registered ``build_folder``
    is rewritten with that name and ``<variant>``. Otherwise ``relative`` is
    the project path, ``~/...``, or an absolute path.
    """
    if not raw:
        return "", ""
    abs_path = _to_abs( raw, env )
    if allow_variant_roots:
        roots = (
                ( "final", "abs_final_dir" ),
                ( "working", "abs_build_dir" ),
                ( "artefacts", "abs_artefacts_root" ),
        )
        for token, key in roots:
            root = _env_get( env, key, "" ) or ""
            if token == "artefacts" and not root:
                root = _env_get( env, "abs_artifacts_root", "" ) or ""
            if not root:
                continue
            root_abs = root if os.path.isabs( root ) else _to_abs( root, env )
            relative = _rel_inside( abs_path, root_abs )
            if relative is None:
                continue
            if token == "artefacts":
                variant_relative = _strip_artifact_folder( relative, env )
                if variant_relative == relative:
                    continue
                return token, variant_relative
            return token, relative
    build_root = _env_get( env, "abs_build_root", "" ) or ""
    if build_root:
        root_abs = build_root if os.path.isabs( build_root ) else _to_abs( build_root, env )
        relative = _rel_inside( abs_path, root_abs )
        if relative is not None:
            first, _sep, rest = relative.partition( "/" )
            token = _token_for_build_folder( first )
            if token:
                shown_root = _project_display( root_abs, env ) or "_build"
                if not shown_root or shown_root in ( ".", "/" ):
                    shown_root = "_build"
                body = shown_root + "/<" + token + ">"
                if rest:
                    body += "/" + _with_variant_token( rest, env )
                return "", body
    matches = _nested_author_match( abs_path, env )
    if matches:
        return matches
    return "", _display_source_path( raw, env )


def _coloured_transfer_end( token, relative, dest ):
    """One side of ``source → dest``.

    The source is entirely subdued. The destination directory is subdued and
    its filename is info-coloured and bold, not the info highlight.
    ``<working>``, ``<final>``, ``<artefacts>``, and nested tokens such as
    ``<dependencies>/<fmt>`` mark build locations so they are not read as
    project paths.
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
_TRANSFORM_ACTIONS = ( "markdown", "asciidoc" )
_RUN_FILE_ACTIONS = ( "run", "test", "benchmark" )


def _is_transform_action( action ):
    text = str( action or "" )
    return text == "compile" or text.startswith( "compile-" ) or text in _TRANSFORM_ACTIONS


def _transform_field( target, source, env ):
    """``source → product`` for compile and other one-input rewrites."""
    directory, filename = _compile_file_parts( source, env )
    source_text = _coloured_file( directory, filename ) if filename else ""
    dest_token, dest_path = _locate( _node_path( _first_node( target ) ), env )
    dest_text = _coloured_transfer_end( dest_token, dest_path, dest=True )
    if not dest_text:
        dest_text = _coloured_file( "", _node_basename( target ) )
    if source_text and dest_text:
        return source_text + " " + as_subdued( "→" ) + " " + dest_text
    return source_text or dest_text


def _mapped_product_path( token, relative ):
    """True when dest locate hit a token or a ``_build/<name>/…`` rewrite."""
    if token:
        return True
    return "<" in str( relative or "" )


def located_program_parts( path, env ):
    """``('<final>/', 'management')`` or ``('', basename)`` when unmapped."""
    raw = str( path or "" ).replace( "\\", "/" )
    token, relative = _locate( raw, env )
    leaf = os.path.basename( raw ) or raw
    if not _mapped_product_path( token, relative ):
        return "", leaf
    relative = str( relative or "" ).replace( "\\", "/" ).strip( "/" )
    directory, filename = os.path.split( relative ) if relative else ( "", "" )
    if directory in ( "", "." ):
        directory = ""
    prefix = ( "<" + token + ">/" if token else "" ) + ( directory + "/" if directory else "" )
    return prefix, filename or leaf


def _located_product_field( target, env, require_map=True ):
    """Product cell with dest colouring, or the leaf when the path is unmapped."""
    raw = _node_path( _first_node( target ) )
    token, relative = _locate( raw, env )
    if require_map and not _mapped_product_path( token, relative ):
        return _coloured_file( "", _node_basename( target ) )
    shown = _coloured_transfer_end( token, relative, dest=True )
    return shown or _coloured_file( "", _node_basename( target ) )


def _file_field( action, target, source, env ):
    if _paths_style( target ) == "product" and action not in _TRANSFER_ACTIONS:
        return _located_product_field( target, env, require_map=False )
    summary = _explicit_terse_summary( target )
    if summary:
        if _paths_style( target ) == "file":
            shown = str( summary ).replace( "\\", "/" )
            directory, filename = os.path.split( shown )
            if directory in ( "", "." ):
                directory = ""
            return _coloured_file( directory, filename or shown )
        return as_subdued( summary )
    if action in _TRANSFER_ACTIONS or _paths_style( target ) == "transfer":
        return _transfer_field( target, source, env )
    if action in _PATH_ACTIONS:
        return _path_action_field( _node_path( _first_node( target ) ), env )
    if _is_transform_action( action ):
        return _transform_field( target, source, env )
    if action in _RUN_FILE_ACTIONS:
        program = source if _first_node( source ) is not None else target
        return _located_product_field( program, env )
    return _located_product_field( target, env )

_STATUS_WIDTH = 6


def _action_label( action ):
    """Bold in the plain ink. On a dark console that is bold white, not info."""
    return as_emphasised_plain( str( action ) )


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
    elif status == "done":
        # Clean close of a delegated ``[launch]`` span. Same column width as ``[ok]``.
        text = "[done]"
        painted = as_colour( "success", text )
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
    """Indent ``→`` so a nested status lines up with ``[ok]`` / ``[progress]``.

    When a cell tally exists, the gap is that prefix minus one column for the
    arrow. Nested copies and test-cases with an empty ledger stay flush.
    """
    _credited, plain = _progress_ledger.credit_and_prefix( None, None, env, False )
    arrow = as_subdued( "→" )
    if not plain:
        return arrow + " " + marker
    indent = _progress_ledger.action_line_indent()
    return ( " " * ( indent + len( plain ) - 1 ) ) + arrow + " " + marker


def _location_map_prefix( env, badge=None ):
    """Indent ``→ [location]`` (or a retrieve status badge) to the checkpoint column."""
    if badge is None:
        badge = _location_badge()
    _credited, plain = _progress_ledger.credit_and_prefix( None, None, env, False )
    if plain:
        return _uncounted_prefix( env, badge )
    counts = _progress_ledger.checkpoint_counts( None, None )
    percent_width = counts[ "percent_digits" ] + 1
    column = (
            _progress_ledger.progress_line_indent()
            + _SCOPE_WIDTH + 1 + percent_width + 1
    )
    indent = max( column - 2, 0 )
    return ( " " * indent ) + as_subdued( "→" ) + " " + badge


def _coloured_location_value( shown, env, kind="" ):
    """Path on a location map. Same roles as the parent checkpoint path.

    ``_build/`` (and other prefixes) subdued; sconscript leaf info; ``dbg`` /
    ``rel`` / ``cov`` plain; remaining layout dirs subdued; last component
    info+bold. Root and package maps are vocabulary: every path segment
    and the slashes between them are info+bold
    (``~/_cuppa/_download``, ``abseil-cpp/20250814.2``). A nested parent
    token on the value (``<dependencies>/gcc16_rel_...``) stays subdued;
    only the identity this map defines is vocabulary.
    """
    shown = str( shown or "" ).replace( "\\", "/" )
    if not shown:
        return ""
    vocabulary = str( kind or "" ) in ( "root", "package" )
    parent = ""
    identity = shown
    if vocabulary:
        while identity.startswith( "<" ) and ">/" in identity:
            token, rest = identity.split( ">/", 1 )
            parent += token + ">/"
            identity = rest
    parts = [ part for part in identity.split( "/" ) if part ]
    if identity.startswith( "/" ):
        parts = [ "" ] + parts
    if not parts:
        return as_subdued( parent ) if parent else ""
    script_parts = [
            part for part in _sconscript_label( env ).replace( "\\", "/" ).split( "/" ) if part
    ]
    script_leaf = script_parts[ -1 ] if script_parts else ""
    name = _variant_name( env )
    painted = []
    last = len( parts ) - 1
    for index, part in enumerate( parts ):
        if vocabulary and part:
            painted.append( as_emphasised( as_info( part ) ) )
        elif index == last and part:
            painted.append( as_emphasised( as_info( part ) ) )
        elif name and part == name:
            painted.append( part )
        elif script_leaf and part == script_leaf:
            painted.append( as_info( part ) )
        else:
            painted.append( as_subdued( part ) )
    slash = as_emphasised( as_info( "/" ) ) if vocabulary else as_subdued( "/" )
    value = slash.join( painted )
    if parent:
        return as_subdued( parent ) + value
    return value


def _location_badge():
    """Bold muted grey ``[location]``. Vocabulary chrome, not action ink."""
    return as_emphasised( as_subdued( "[location]" ) )


def _location_map_rhs( token, path, env ):
    """Map value: nested under a parent token when contained, else display path."""
    if str( token ) == "variant":
        return _slash( path ).strip( "/" )
    abs_path = _to_abs( path, env )
    if str( token ) not in ( "working", "final", "artefacts" ):
        parents = []
        for item in _author_locations():
            _scope, _script, _cell, other, root, _folder, _kind = _unpack_location( item )
            if other == token or _is_project_root( root, env ):
                continue
            relative = _rel_inside( abs_path, root )
            if relative is not None:
                parents.append( ( len( os.path.normpath( root ) ), relative, other ) )
        if parents:
            parents.sort( reverse=True )
            for _length, relative, other in parents:
                if str( token ) == "packages" and other == "dependencies" and relative:
                    return "<dependencies>/" + relative
                if relative:
                    return relative
    shown = _project_display( abs_path, env ) or _home_display( abs_path )
    return _with_variant_token( shown, env )


def _declared_dependency_names( env ):
    """``default_dependencies`` names, as strings."""
    return [ str( name ) for name in ( _env_get( env, "default_dependencies" ) or [] ) ]


def _location_is_transitive( token, env ):
    """True when a mapped dependency is outside ``default_dependencies``.

    Roots are never transitive. With no declared list, nothing is marked.
    """
    if str( token ) in _CATEGORY_LOCATION_TOKENS:
        return False
    declared = _declared_dependency_names( env )
    if not declared:
        return False
    return str( token ) not in set( declared )


def format_terse_location_line( token, path, env, scope="variant", kind="" ):
    """``→ [location] [sconscript ·] [variant ·] <token> = path [· kind] [· transitive]``.

    Identity fields let a map reattach when ``-j`` splits it from its
    ``[progress]`` begin. Sconscript-scoped maps omit the variant cell.
    Sconstruct-scoped maps omit both identity cells (the ``[prepare]``
    bookend already names the sconstruct). Read-phase kinds are ``root``,
    ``repository``, ``archive``, and     ``package``. ``transitive`` is info-coloured (declared maps stay unmarked).
    """
    shown = _location_map_rhs( token, path, env )
    fields = []
    if scope != "sconstruct":
        script = _sconscript_label( env )
        if script:
            fields.append( _coloured_sconscript( script ) )
    if scope == "variant":
        cell = _coloured_variant_cell( env )
        if cell:
            fields.append( cell )
    value = (
            "<" + str( token ) + ">"
            + as_subdued( " = " )
            + _coloured_location_value( shown, env, kind=kind )
    )
    fields.append( value )
    if kind and scope == "sconstruct":
        fields.append( as_subdued( kind ) )
        if _location_is_transitive( token, env ):
            fields.append( as_info( "transitive" ) )
    lead = _location_map_prefix( env )
    return lead + " " + ( " " + as_subdued( "·" ) + " " ).join( fields )


def _builtin_location_maps( env ):
    maps = []
    tool = _slash( _env_get( env, "tool_variant_dir", "" ) or "" ).strip( "/" )
    if tool:
        maps.append( ( "variant", tool ) )
    for token, key in (
            ( "working", "abs_build_dir" ),
            ( "final", "abs_final_dir" ),
            ( "artefacts", "abs_artefacts_root" ),
    ):
        path = _env_get( env, key, "" ) or ""
        if token == "artefacts" and not path:
            path = _env_get( env, "abs_artifacts_root", "" ) or ""
        if path:
            maps.append( ( token, path ) )
    return maps


def format_terse_location_maps( scope, env ):
    """Location-map lines for one checkpoint begin. Empty on end events."""
    lines = []
    if scope == "sconstruct":
        script = ""
        cell = ""
    else:
        script = _sconscript_label( env )
        cell = _variant_cell( env )

    def _matches( item_scope, item_script, item_cell ):
        if item_scope != scope:
            return False
        if item_script and script and item_script != script:
            return False
        if scope == "variant" and item_cell and cell and item_cell != cell:
            return False
        return True

    if scope == "variant":
        for item in _author_locations():
            item_scope, item_script, item_cell, token, path, _folder, kind = _unpack_location( item )
            if token != "packages" or not _matches( item_scope, item_script, item_cell ):
                continue
            lines.append( format_terse_location_line(
                    token, path, env, scope=scope, kind=kind,
            ) )
        for token, path in _builtin_location_maps( env ):
            lines.append( format_terse_location_line( token, path, env, scope=scope ) )
    for item in _author_locations():
        item_scope, item_script, item_cell, token, path, _folder, kind = _unpack_location( item )
        if token == "packages":
            continue
        if not _matches( item_scope, item_script, item_cell ):
            continue
        lines.append( format_terse_location_line(
                token, path, env, scope=item_scope, kind=kind,
        ) )
    return lines


def write_terse_nested_copy( source, dest, env, target=None ):
    """Uncounted ``copy`` after a delegated product is staged. Does not close the parent."""
    if not _env_get( env, "terse_output" ):
        return
    dest_nodes = [ dest ]
    shared = _explicit_terse_shared( target )
    if shared:
        attributes = type( "A", (), {} )()
        attributes.cuppa_terse_shared = shared
        holder = type( "T", (), {} )()
        holder.path = dest
        holder.attributes = attributes
        dest_nodes = [ holder ]
    line = format_terse_line(
            "ok",
            'Copy("{}", "{}")'.format( dest, source ),
            dest_nodes,
            [ source ],
            env,
            count=False,
    )
    _write_terse_stdout( line + "\n" )
    sys.stdout.flush()
    note_terse_nested_action()


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
    fields.append( _action_label( action ) )
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
        parts.append( ( " " * _progress_ledger.action_line_indent() ) + prefix )
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
        parts.append( ( " " * _progress_ledger.action_line_indent() ) + prefix )
    marker = _status_marker( status )
    if not count:
        marker = _uncounted_prefix( env, marker )
    parts.append( marker )

    fields = []
    script = _sconscript_label( env )
    if script:
        fields.append( _coloured_sconscript( script ) )
    cell = _coloured_build_cell( env, target )
    if cell:
        fields.append( cell )
    action = spell_terse_action( command, target, env )
    fields.append( _action_label( action ) )
    file_text = _file_field( action, target, source, env )
    if file_text:
        fields.append( file_text )
    if fields:
        parts.append( ( " " + as_subdued( "·" ) + " " ).join( fields ) )
    line = " ".join( parts )
    if command and _env_get( env, "terse_output_show_actions" ):
        line += " " + as_subdued( str( command ) )
    return line


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


def take_terse_launch():
    """Return and clear a delegated launch noted on this job thread.

    Returns ``(emitted, command)``. ``command`` is the argv to reprint on
    failure when the launch bookend hid it on the clean path.
    """
    emitted = bool( getattr( _terse_launch, "emitted", False ) )
    command = getattr( _terse_launch, "command", None )
    _terse_launch.emitted = False
    _terse_launch.command = None
    _terse_launch.target = None
    _terse_launch.source = None
    _terse_launch.env = None
    return emitted, command


def format_terse_launch( action, summary, env, target=None ):
    """``delegate P% [launch] [sconscript ·] variant · action · summary``.

    Chrome matches a progress checkpoint; fields after the badge mirror the
    counted close line so a long muted child wall can be reattached. Not in
    the action total. ``target`` may carry a ``shared`` label for the cell.
    """
    script = _sconscript_label( env )
    cell = _variant_cell( env )
    counts = _progress_ledger.checkpoint_counts( script, cell )
    percent = "{:>{}}%".format( counts[ "percent" ], counts[ "percent_digits" ] )
    lead = " " * _progress_ledger.progress_line_indent()
    parts = [
            lead + as_subdued( "{:<{}}".format( "delegate", _SCOPE_WIDTH ) ),
            percent,
            as_emphasised( as_info( "[launch]" ) ),
    ]
    fields = []
    if script:
        fields.append( _coloured_sconscript( script ) )
    painted_cell = _coloured_build_cell( env, target )
    if painted_cell:
        fields.append( painted_cell )
    if action:
        fields.append( _action_label( action ) )
    file_text = ""
    if summary:
        if target is not None and _paths_style( target ) == "file":
            shown = str( summary ).replace( "\\", "/" )
            directory, filename = os.path.split( shown )
            if directory in ( "", "." ):
                directory = ""
            file_text = _coloured_file( directory, filename or shown )
        else:
            file_text = as_subdued( str( summary ) )
    elif target is not None:
        file_text = _file_field( action, target, None, env )
    if file_text:
        fields.append( file_text )
    line = " ".join( parts )
    if fields:
        line += " " + ( " " + as_subdued( "·" ) + " " ).join( fields )
    return line


def write_terse_launch( action, summary, env, command=None, target=None ):
    """Print a delegated launch bookend. No effect unless ``--terse-output``."""
    if not _env_get( env, "terse_output" ):
        return
    _terse_launch.emitted = True
    if command:
        _terse_launch.command = command
    line = format_terse_launch( action, summary, env, target=target )
    note_terse_build_activity()
    _write_terse_stdout( line + "\n" )
    sys.stdout.flush()


def format_terse_muted_child( text, env ):
    """One foreign child line: indented ``→`` and subdued body, no Cuppa badge."""
    body = str( text or "" ).rstrip( "\n" )
    return _uncounted_prefix( env, as_subdued( body ) )


def write_terse_muted_child( text, env ):
    """Stream one muted delegated child line. No effect unless ``--terse-output``."""
    if not _env_get( env, "terse_output" ):
        return
    _write_terse_stdout( format_terse_muted_child( text, env ) + "\n" )
    sys.stdout.flush()


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
        _write_terse_stdout( cmd + "\n" )


def flush_unconsumed_terse_command():
    """Reprint a command whose action did not spawn on this thread.

    A delegated launch bookend already announced the job, so do not dump the
    stashed argv on the clean path. Keep the command for a later failure line.
    """
    cmd, target, source, env = take_terse_command()
    if getattr( _terse_launch, "emitted", False ):
        if cmd and not getattr( _terse_launch, "command", None ):
            _terse_launch.command = cmd
            _terse_launch.target = target
            _terse_launch.source = source
            _terse_launch.env = env
        return
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
    _write_terse_stdout(
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


_CHECKPOINT_PHASE = {
        "sconstruct_begin": ( "sconstruct", "begin" ),
        "sconstruct_end": ( "sconstruct", "end" ),
        "begin": ( "sconscript", "begin" ),
        "end": ( "sconscript", "end" ),
        "started": ( "variant", "begin" ),
        "finished": ( "variant", "end" ),
}
_SCOPE_WIDTH = len( "sconstruct" )


def _counted_phrase( count, singular, plural ):
    """A plain number and a subdued word. ``1 variant``, ``40 sconscripts``."""
    word = singular if count == 1 else plural
    return str( count ) + as_subdued( " " + word )


def _fraction_phrase( done, total ):
    word = "action" if total == 1 else "actions"
    return "{}/{}".format( done, total ) + as_subdued( " " + word )


def _join_subdued( parts ):
    return as_subdued( " · " ).join( parts )


def _coloured_named_path( shown, leaf=None ):
    """Mute the path. The leaf and the directory before it are info.

    ``leaf`` replaces the info colour on the last part. A variant cell uses
    that so ``dbg`` stays plain, as it does on an action line.
    """
    if not shown:
        return ""
    parts = [ part for part in shown.split( "/" ) if part != "" ]
    if not parts:
        return ""
    paint = leaf if leaf is not None else as_info( parts[ -1 ] )
    if len( parts ) == 1:
        return paint
    parent = as_info( parts[ -2 ] + "/" )
    if len( parts ) == 2:
        return parent + paint
    return as_subdued( "/".join( parts[ :-2 ] ) + "/" ) + parent + paint


def _sconscript_file_display( env ):
    path = str( _env_get( env, "sconscript_file", "" ) or "" ).replace( "\\", "/" )
    if path.startswith( "./" ):
        path = path[ 2: ]
    return path


def _sconstruct_display( env ):
    filename = str( _env_get( env, "sconstruct_file", "" ) or "sconstruct" ).replace( "\\", "/" )
    directory = str( _env_get( env, "sconstruct_dir", "" ) or "" )
    if os.path.isabs( filename ) or not directory:
        raw = filename
    else:
        raw = os.path.join( directory, filename )
    shown = _home_display( _to_abs( raw, env ) )
    return shown or _slash( filename )


def _checkpoint_path( scope, env ):
    if scope == "sconstruct":
        return _coloured_named_path( _sconstruct_display( env ) )
    if scope == "sconscript":
        return _coloured_named_path( _sconscript_file_display( env ) )
    script = _sconscript_label( env )
    cell = _variant_cell( env )
    shown = script + "/" + cell if script and cell else ( cell or script )
    painted = _coloured_variant_cell( env ) or None
    return _coloured_named_path( shown, leaf=painted )


def _checkpoint_summary( scope, counts ):
    if scope == "sconstruct":
        if not counts[ "total" ] and not counts[ "scripts" ]:
            return ""
        return _join_subdued( [
                _counted_phrase( counts[ "scripts" ], "sconscript", "sconscripts" ),
                _counted_phrase( counts[ "variants" ], "variant", "variants" ),
                _fraction_phrase( counts[ "done" ], counts[ "total" ] ),
        ] )
    if scope == "sconscript":
        if not counts[ "script_total" ] and not counts[ "script_variants" ]:
            return ""
        return _join_subdued( [
                _counted_phrase( counts[ "script_variants" ], "variant", "variants" ),
                _fraction_phrase( counts[ "script_done" ], counts[ "script_total" ] ),
        ] )
    if not counts[ "cell_total" ]:
        return ""
    return _fraction_phrase( counts[ "cell_done" ], counts[ "cell_total" ] )


def format_terse_progress_checkpoint( event, _sconscript, _variant, env ):
    """One ``[progress]`` checkpoint. ``None`` when this event is not a scope edge.

    The percent is the whole build. The fraction follows the scope word:
    the whole build, every variant of this sconscript, or this cell. Reading
    the ledger does not credit the checkpoint.
    """
    phase = _CHECKPOINT_PHASE.get( event )
    if phase is None:
        return None
    scope, edge = phase
    script = _sconscript_label( env )
    cell = _variant_cell( env )
    counts = _progress_ledger.checkpoint_counts( script, cell )
    percent = "{:>{}}%".format( counts[ "percent" ], counts[ "percent_digits" ] )
    lead = " " * _progress_ledger.progress_line_indent()
    parts = [
            lead + as_subdued( "{:<{}}".format( scope, _SCOPE_WIDTH ) ),
            percent,
            as_emphasised( as_info( "[progress]" ) ),
            _checkpoint_path( scope, env ),
    ]
    line = " ".join( parts ) + as_subdued( " · " ) + _action_label( edge )
    summary = _checkpoint_summary( scope, counts )
    if summary:
        line += as_subdued( " · " ) + summary
    return line


def write_terse_progress_checkpoint( event, sconscript, variant, env ):
    """Print a terse checkpoint. No effect unless ``--terse-output`` is set.

    The first begin line counts actions SCons already considers up to date,
    so the percent includes that work before the scope's own actions run.
    """
    if not _env_get( env, "terse_output" ):
        return
    if event in ( "sconstruct_begin", "begin", "started" ):
        credit_terse_up_to_date_lookahead()
    line = format_terse_progress_checkpoint( event, sconscript, variant, env )
    if not line:
        return
    _write_terse_stdout( line + "\n" )
    phase = _CHECKPOINT_PHASE.get( event )
    if phase and phase[1] == "begin" and phase[0] != "sconstruct":
        for map_line in format_terse_location_maps( phase[0], env ):
            _write_terse_stdout( map_line + "\n" )
    sys.stdout.flush()


def _factory_owner( factory ):
    """Class a ``cls.create`` classmethod is bound to, else ``None``."""
    owner = getattr( factory, "__self__", None )
    if isinstance( owner, type ):
        return owner
    return None


def _dependency_kind_from_factory( factory ):
    """Map a ``env['dependencies']`` factory to a read-checkpoint kind.

    Factories are stored as ``cls.create``, so attributes live on the class,
    not the callable. ``package`` is a GitLab/Conan package; ``archive`` is a
    source tarball (Boost, URL zip/tar); ``repository`` is an SCM or path
    location. ``None`` means no map kind (system Qt).
    """
    owner = _factory_owner( factory )
    targets = []
    if factory is not None:
        targets.append( factory )
    if owner is not None:
        targets.append( owner )
    if not targets:
        return "repository"
    for target in targets:
        if getattr( target, "_package_manager", None ) or getattr( target, "_package", None ):
            return "package"
        if getattr( target, "_conanfile", None ) is not None or getattr( target, "_requires", None ) is not None:
            return "package"
    for target in targets:
        name = getattr( target, "_name", None )
        if name in ( "qt4", "qt5" ):
            return None
        if name == "boost":
            return "archive"
        spec = getattr( target, "_default_location", None )
        if spec:
            from cuppa.location import Location
            return Location.source_kind_for( spec )
        if callable( getattr( target, "location_option", None ) ):
            return "repository"
    return "repository"


def _sconstruct_dependency_maps():
    """Sconstruct location entries that are dependencies, not category roots."""
    seen = set()
    entries = []
    for item in _author_locations():
        scope, _script, _cell, token, _path, _folder, kind = _unpack_location( item )
        if scope != "sconstruct":
            continue
        if token in _CATEGORY_LOCATION_TOKENS or kind == "root":
            continue
        if token in seen:
            continue
        seen.add( token )
        entries.append( ( token, kind ) )
    return entries


def _declared_transitive_suffix( declared_n, transitive_n ):
    """`` (35 declared, 7 transitive)`` bound to the preceding count."""
    return (
            as_subdued( " (" )
            + str( declared_n )
            + as_subdued( " declared, " )
            + str( transitive_n )
            + as_subdued( " transitive)" )
    )


def _read_checkpoint_summary( env ):
    """Resolved graph first; declared/transitive hang off that total.

    ``41 dependencies (35 declared, 6 transitive) · 33 repositories · 8 packages``
    when traveling-manifest packages join the maps. Without extras, just
    ``35 dependencies · 33 repositories · 2 packages``. Kind counts stay
    unqualified; map lines mark ``transitive`` only.
    """
    declared = _declared_dependency_names( env )
    mapped = _sconstruct_dependency_maps()
    mapped_names = [ token for token, _kind in mapped ]
    ordered = []
    seen = set()
    for name in declared + mapped_names:
        if name in seen:
            continue
        seen.add( name )
        ordered.append( name )
    if not ordered:
        return ""
    factories = _env_get( env, "dependencies" ) or {}
    kinds = { token: kind for token, kind in mapped if kind }
    counts = {}
    for name in ordered:
        kind = kinds.get( name )
        if not kind and isinstance( factories, dict ):
            kind = _dependency_kind_from_factory( factories.get( name ) )
        if not kind or kind == "root":
            continue
        counts[ kind ] = counts.get( kind, 0 ) + 1
    extra = [ name for name in mapped_names if name not in set( declared ) ]
    dep_phrase = _counted_phrase( len( ordered ), "dependency", "dependencies" )
    if extra:
        dep_phrase += _declared_transitive_suffix( len( declared ), len( extra ) )
    parts = [ dep_phrase ]
    for kind, singular, plural in (
            ( "repository", "repository", "repositories" ),
            ( "package", "package", "packages" ),
            ( "archive", "archive", "archives" ),
    ):
        n = counts.get( kind, 0 )
        if n:
            parts.append( _counted_phrase( n, singular, plural ) )
    return _join_subdued( parts )


def _format_resolve_bookend( env, badge, summary ):
    """``sconstruct 0% [prepare|ready] path · resolve · summary``."""
    counts = _progress_ledger.checkpoint_counts( None, None )
    percent = "{:>{}}%".format( 0, counts[ "percent_digits" ] )
    lead = " " * _progress_ledger.progress_line_indent()
    parts = [
            lead + as_subdued( "{:<{}}".format( "sconstruct", _SCOPE_WIDTH ) ),
            percent,
            as_emphasised( as_info( badge ) ),
            _checkpoint_path( "sconstruct", env ),
    ]
    line = " ".join( parts ) + as_subdued( " · " ) + _action_label( "resolve" )
    if summary:
        line += as_subdued( " · " ) + summary
    return line


def write_terse_resolve_prepare( env ):
    """Open the resolve span. Location maps and retrieve children follow live."""
    global _terse_prepare_written, _terse_ready_written
    if not _env_get( env, "terse_output" ):
        return
    if _env_get( env, "clean" ):
        _terse_prepare_written = True
        _terse_ready_written = True
        return
    if _terse_prepare_written:
        return
    _terse_prepare_written = True
    declared = _declared_dependency_names( env )
    summary = ""
    if declared:
        summary = _counted_phrase(
                len( declared ), "declared dependency", "declared dependencies",
        )
    _write_terse_stdout( _format_resolve_bookend( env, "[prepare]", summary ) + "\n" )
    sys.stdout.flush()


def write_terse_resolve_ready( env ):
    """Close the resolve span with resolved totals. Does not reprint maps."""
    global _terse_ready_written
    if not _env_get( env, "terse_output" ):
        return
    if _env_get( env, "clean" ):
        _terse_ready_written = True
        return
    if _terse_ready_written:
        return
    if not _terse_prepare_written:
        write_terse_resolve_prepare( env )
    _terse_ready_written = True
    _write_terse_stdout(
            _format_resolve_bookend( env, "[ready]", _read_checkpoint_summary( env ) )
            + "\n"
    )
    sys.stdout.flush()


def write_terse_read_checkpoint( env ):
    """Alias for ``write_terse_resolve_ready`` (older call sites)."""
    write_terse_resolve_ready( env )


_RESOLVE_CHILD_WIDTH = len( "[location]" )


def _resolve_child_badge( badge, status="ok" ):
    """Ten columns so ``[update]`` lines up with ``[location]``.

    Success uses the same success colour as ``[ok]``. Pad sits outside the
    colour. ``[download]`` is already ten characters.
    """
    text = "[" + str( badge ) + "]"
    if status in ( "error", "fail" ):
        painted = as_colour( "error", text )
    elif status == "warn":
        painted = as_colour( "warning", text )
    else:
        painted = as_colour( "success", text )
    short = _RESOLVE_CHILD_WIDTH - len( text )
    if short <= 0:
        return painted
    return painted + ( " " * short )


def terse_resolve_child_enabled( env, token ):
    """Whether a retrieve child would print (do not pre-colour as success)."""
    if not token:
        return False
    if not _env_get( env, "terse_output" ) or _env_get( env, "clean" ):
        return False
    return bool( _terse_prepare_written )


def format_terse_resolve_child( env, badge, token, *fields, status="ok", remark="" ):
    """``→ [update]   <fmt> · master · 9197f515 · update failed, using available extract``."""
    lead = _location_map_prefix( env, _resolve_child_badge( badge, status ) )
    parts = [ "<" + str( token ) + ">" ]
    for field in fields:
        text = str( field or "" ).strip()
        if text:
            parts.append( text )
    line = lead + " " + ( " " + as_subdued( "·" ) + " " ).join( parts )
    text = str( remark or "" ).strip()
    if text:
        if status in ( "error", "fail" ):
            painted = as_colour( "error", text )
        elif status == "warn":
            painted = as_colour( "warning", text )
        else:
            painted = as_colour( "success", text )
        line += as_subdued( " · " ) + painted
    return line


def write_terse_resolve_child( env, badge, token, *fields, status="ok", remark="" ):
    """Print a retrieve child after the work. True when emitted."""
    if not terse_resolve_child_enabled( env, token ):
        return False
    _write_terse_stdout(
            format_terse_resolve_child(
                    env, badge, token, *fields, status=status, remark=remark,
            ) + "\n"
    )
    sys.stdout.flush()
    return True


def _emit_sconstruct_location_map( token, path, env, kind="" ):
    if token == "packages" or token in _written_sconstruct_maps:
        return
    _written_sconstruct_maps.add( token )
    _write_terse_stdout(
            format_terse_location_line(
                    token, path, env, scope="sconstruct", kind=kind,
            ) + "\n"
    )
    sys.stdout.flush()


def heartbeat_print_cmd_line( cmd, target, source, env ):
    """SCons ``PRINT_CMD_LINE_FUNC`` when the quiet+TTY heartbeat is diverting.

    Must clear ``working`` *before* writing the command to the stdout pipe.
    ``posix_spawn`` uses ``suppress_output=True``, so ``Popen2`` never prints
    the command itself — SCons prints here first, then SPAWN runs. Clearing
    only inside ``Popen2`` leaves the launcher free to append the command to
    the status row. Uses the shared transcript lock under ``-j``.
    """
    try:
        from cuppa.utility.heartbeat import write_transcript
        write_transcript( cmd + "\n" )
        return
    except Exception:
        pass
    sys.stdout.write( cmd + "\n" )
    try:
        sys.stdout.flush()
    except Exception:
        pass


def terse_print_cmd_line( cmd, target, source, env ):
    """SCons ``PRINT_CMD_LINE_FUNC`` for ``--terse-output``.

    A ``Progress(...)`` description is dropped. The checkpoint is printed
    from the progress action, including under ``-Q``. Tool commands are
    stashed and printed later, only when that run warns or fails. Show and
    execute run on the same SCons job thread, so a per-thread stash pairs
    them under ``-j``. A command that never reaches a spawn is written back
    on the next print, or at process exit.
    """
    flush_unconsumed_terse_command()
    if _is_progress_command( cmd ):
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
            take_terse_launch()
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
    Otherwise the SCons description is used. A delegated launch that already
    streamed muted children only reprints argv on failure.
    """
    command, stashed_target, stashed_source, stashed_env = take_terse_command()
    children = take_terse_children()
    launched, launch_command = take_terse_launch()
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
    if launched and severity == "ok":
        severity = "done"
    spell_command = command or launch_command or ""
    if children and not _explicit_terse_action( use_target ):
        spell_command = children[0][0]
    status_line = format_terse_line(
            severity,
            spell_command,
            use_target,
            use_source,
            use_env,
    )
    if severity not in ( "ok", "done" ):
        if launched and launch_command:
            _write_command( launch_command )
        elif children:
            for child_command, lines, _child_failed in children:
                _write_command( child_command )
                for line in lines:
                    _write_command( line )
        elif command and not _is_python_action_dump( command ):
            _write_command( command )
    note_terse_build_activity()
    _write_terse_stdout( status_line + "\n" )
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




