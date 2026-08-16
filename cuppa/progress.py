
#          Copyright Jamie Allsop 2013-2015
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   Progress
#-------------------------------------------------------------------------------

import logging
import os.path
import threading

from cuppa.colourise import as_notice, as_info
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

        if cls.inventory_report_mode():
            file_deps = [ '#' + env['sconscript_file'], '#' + env['sconstruct_file'] ]
            finished = env.Depends( cls._finished[variant], file_deps )
            env.Requires( cls._finished[variant], target )
        else:
            finished = env.Depends(
                    cls._finished[variant],
                    [ target, '#' + env['sconscript_file'], '#' + env['sconstruct_file'] ]
            )

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
    return env.Command( label, [], progress_action( label, event, sconscript, variant, env ) )


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




