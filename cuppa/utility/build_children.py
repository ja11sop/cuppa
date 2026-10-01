#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   Build children and Ctrl-C
#-------------------------------------------------------------------------------

"""Let work that has already started finish when the build is interrupted.

The terminal delivers SIGINT to every process in the foreground group. A
compiler or test killed at that moment can leave a binary half-written and
not executable, and another task then fails with permission denied. Build
children are started in their own session, so the first Ctrl-C reaches SCons
only. SCons already refuses new tasks. The ones already running finish and
leave their outputs complete. A second Ctrl-C stops those children.
"""

import os
import signal
import threading


_lock = threading.Lock()
_sessions = set()
_stops = 0
_handler_installed = False


def child_popen_kwargs():
    """Extra ``Popen`` arguments that keep a child off the terminal's SIGINT."""
    if os.name == "nt":
        return {}
    return { "start_new_session": True }


def remember_child( process ):
    pid = getattr( process, "pid", None )
    if not pid or os.name == "nt":
        return
    with _lock:
        _sessions.add( pid )


def forget_child( process ):
    pid = getattr( process, "pid", None )
    if not pid:
        return
    with _lock:
        _sessions.discard( pid )


def terminate_build_children():
    """Stop children that were left running after a second Ctrl-C."""
    with _lock:
        sessions = list( _sessions )
    for pid in sessions:
        try:
            os.killpg( pid, signal.SIGTERM )
        except ( ProcessLookupError, PermissionError, OSError ):
            pass


def note_stop_request():
    """Count Ctrl-C. The second one stops children that are still running."""
    global _stops
    with _lock:
        _stops += 1
        stop = _stops
    if stop >= 2:
        terminate_build_children()
    return stop


def reset_stop_requests():
    """A new build starts again at the first Ctrl-C."""
    global _stops
    with _lock:
        _stops = 0


def install_graceful_interrupt():
    """Wrap SCons's SIGINT handler so the second Ctrl-C stops children.

    The first signal still goes to SCons, which stops scheduling new tasks.
    Children are not in the terminal's process group, so that signal does not
    kill them. The terse close is printed when ``Jobs.run`` returns. ``-Q``
    never writes ``scons: Build interrupted.``, so that line cannot be the cue.
    """
    global _handler_installed
    if _handler_installed:
        return
    import SCons.Taskmaster.Job as jobs
    original = jobs.Jobs._setup_sig_handler
    original_run = jobs.Jobs.run

    def setup( self ):
        reset_stop_requests()
        original( self )
        previous = signal.getsignal( signal.SIGINT )

        def handler( signum, frame, previous=previous ):
            stop = note_stop_request()
            if stop == 1:
                _announce_interrupted()
            elif stop == 2:
                _announce_aborted()
            if callable( previous ):
                return previous( signum, frame )
            return None

        try:
            signal.signal( signal.SIGINT, handler )
        except ValueError:
            # Only the main thread may install a signal handler.
            pass

    def run( self, postfunc=lambda: None ):
        try:
            return original_run( self, postfunc )
        finally:
            _finish_interrupted_build()

    jobs.Jobs._setup_sig_handler = setup
    jobs.Jobs.run = run
    _handler_installed = True


def _announce_interrupted():
    """The terse ``interrupted`` line, as soon as Ctrl-C arrives."""
    try:
        from cuppa.progress import note_build_interrupted, terse_interrupt_installed
    except Exception:
        return
    if not terse_interrupt_installed():
        return
    try:
        note_build_interrupted()
    except Exception:
        pass


def _finish_interrupted_build():
    """Print the terse close once the jobs already running have returned.

    SCons writes ``scons: Build interrupted.`` only when progress output is
    on. ``-Q`` and ``--silent`` skip it, and the drain would otherwise end
    with no summary.
    """
    try:
        from cuppa.progress import terse_interrupt_installed, write_terse_interrupt_finish
    except Exception:
        return
    if not terse_interrupt_installed():
        return
    try:
        write_terse_interrupt_finish()
    except Exception:
        pass


def _announce_aborted():
    """The terse ``aborted`` line when a second Ctrl-C stops the drain."""
    try:
        from cuppa.progress import note_build_aborted, terse_interrupt_installed
    except Exception:
        return
    if not terse_interrupt_installed():
        return
    try:
        note_build_aborted()
    except Exception:
        pass
