
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
import sys
import threading

from cuppa.colourise import as_colour, as_emphasised, as_info, as_notice, as_subdued
from cuppa.log import logger

from SCons.Script import Action


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


# --terse-output. Flip this to compare the two transcripts. Not a CLI flag.
# False keeps SCons Progress(...) lines: the sconscript and variant structure
# is useful, though parallel builds interleave it. True hides those lines.
# -Q already omits them, because progress_action only builds the description
# when the logger is at info.
TERSE_SUPPRESS_PROGRESS_LINES = False

_terse_command = threading.local()
_pending_lock = threading.Lock()
# Commands stashed by a job thread and not yet consumed by a spawn. A Python
# action prints before it runs and never spawns, so the next print on that
# thread (or process exit) writes the line back out.
_pending_commands = {}


def terse_counts_prefix():
    """Leading counts segment reserved for Phase 2. Empty until then."""
    return ""


def _is_progress_command( cmd ):
    return bool( cmd ) and cmd.lstrip().startswith( "Progress(" )


def _variant_label( env ):
    if not env:
        return ""
    variant = env.get( "variant" ) if hasattr( env, "get" ) else None
    if variant is None:
        return ""
    name = variant.name() if hasattr( variant, "name" ) else variant
    return str( name )


def _target_label( target ):
    if not target:
        return ""
    if not isinstance( target, ( list, tuple ) ):
        target = [ target ]
    text = str( target[0] )
    return os.path.basename( text ) or text


def format_terse_success( target, env ):
    """One success line. The counts prefix is empty until Phase 2."""
    parts = []
    prefix = terse_counts_prefix()
    if prefix:
        parts.append( prefix )
    parts.append( as_colour( "success", "[ok]" ) )
    variant = _variant_label( env )
    if variant:
        parts.append( as_subdued( variant ) )
    name = _target_label( target )
    if name:
        parts.append( as_emphasised( name ) )
    return " ".join( parts )


def stash_terse_command( cmd, target, source, env ):
    _terse_command.cmd = cmd
    _terse_command.target = target
    _terse_command.source = source
    _terse_command.env = env
    with _pending_lock:
        _pending_commands[ threading.get_ident() ] = ( cmd, target, source, env )


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


def flush_terse_commands():
    """Reprint commands still stashed when the process exits."""
    with _pending_lock:
        leftover = list( _pending_commands.values() )
        _pending_commands.clear()
    for cmd, _target, _source, _env in leftover:
        _write_command( cmd )


def terse_print_cmd_line( cmd, target, source, env ):
    """SCons ``PRINT_CMD_LINE_FUNC`` for ``--terse-output``.

    Progress lines are printed or dropped here. Tool commands are stashed
    and printed later, only when that run warns or fails. Show and execute
    run on the same SCons job thread, so a per-thread stash pairs them
    under ``-j``. A command that never reaches a spawn is written back on
    the next print, or at process exit.
    """
    flush_unconsumed_terse_command()
    if _is_progress_command( cmd ):
        if not TERSE_SUPPRESS_PROGRESS_LINES:
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


def render_terse_spawn( returncode, errors, warnings, buffered_lines, command, target, env, summary ):
    """Lines to print after a terse tool run.

    A clean exit with no warnings is one success line. Anything else reprints
    the command, then the processed output, then the summary.
    """
    if not returncode and not errors and not warnings:
        return [ format_terse_success( target, env ) ]
    lines = []
    if command:
        lines.append( command )
    for chunk in buffered_lines or []:
        lines.extend( _chunk_lines( chunk ) )
    lines.extend( _chunk_lines( summary ) )
    return lines




