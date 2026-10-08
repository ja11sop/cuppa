#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   Build children and Ctrl-C
#-------------------------------------------------------------------------------

"""Stop in-flight build children cleanly when the build is interrupted.

The terminal delivers SIGINT to every process in the foreground group. Build
children are started in their own session so that broadcast does not rip
through every compiler at once. Instead Cuppa owns the stop:

* **First Ctrl-C** — SCons stops scheduling new tasks, and Cuppa sends
  ``SIGINT`` to remembered children (native tools and **delegates** such as
  ``cmake --build`` / ninja / nested ``cuppa``). The current SCons action
  then waits for that child to exit cleanly — so a delegate that would
  otherwise keep building thousands of targets is told to stop, then
  drained, rather than left running until a second interrupt.
* **Second Ctrl-C** — ``SIGTERM`` the remaining process trees (harder stop).
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


def stop_count():
    """How many Ctrl-C signals this build has seen."""
    with _lock:
        return _stops


def terminate_process_tree( pid, sig=None ):
    """Signal ``pid`` and every descendant (cascade nested cmake orphans).

    Build tools use ``start_new_session``, so ``killpg`` on a nested ``cuppa``
    alone leaves ninja/cmake writing to ``/dev/tty`` after the tip has exited.
    Prefer ``psutil`` recursive children; fall back to ``killpg``.
    """
    if not pid or os.name == "nt":
        return
    if sig is None:
        sig = signal.SIGTERM
    try:
        import psutil
    except ImportError:
        psutil = None
    if psutil is not None:
        try:
            root = psutil.Process( pid )
        except ( psutil.Error, ValueError ):
            root = None
        if root is not None:
            descendants = []
            try:
                descendants = root.children( recursive=True )
            except ( psutil.Error, ValueError ):
                descendants = []
            # Children first so session leaders are not reaping before signal.
            for child in reversed( descendants ):
                try:
                    child.send_signal( sig )
                except ( psutil.Error, ValueError, OSError ):
                    pass
            try:
                root.send_signal( sig )
            except ( psutil.Error, ValueError, OSError ):
                pass
    try:
        os.killpg( pid, sig )
    except ( ProcessLookupError, PermissionError, OSError ):
        pass
    try:
        os.kill( pid, sig )
    except ( ProcessLookupError, PermissionError, OSError ):
        pass


def interrupt_build_children():
    """Ask children to stop on the first Ctrl-C (``SIGINT``), then wait.

    Delegates such as ninja treat ``SIGINT`` as a cooperative stop
    (``build stopped: interrupted by user``). Cuppa does not reap them here —
    the spawning SCons action's ``wait`` is the drain.
    """
    with _lock:
        sessions = list( _sessions )
    for pid in sessions:
        terminate_process_tree( pid, signal.SIGINT )


def terminate_build_children():
    """Hard-stop children that ignored the first interrupt (second Ctrl-C)."""
    with _lock:
        sessions = list( _sessions )
    for pid in sessions:
        terminate_process_tree( pid, signal.SIGTERM )


def note_stop_request():
    """Count Ctrl-C: first signals children; second ``SIGTERM`` stubborn ones.

    Cascade nested waits also watch :func:`stop_count` so a tip interrupt is
    visible inside ``_run_nested_cuppa`` even if signal delivery races.
    """
    global _stops
    with _lock:
        _stops += 1
        stop = _stops
    if stop == 1:
        interrupt_build_children()
    elif stop >= 2:
        terminate_build_children()
    return stop


def reset_stop_requests():
    """A new build starts again at the first Ctrl-C."""
    global _stops
    with _lock:
        _stops = 0


def install_graceful_interrupt():
    """Wrap SCons's SIGINT handler for cooperative then hard child stops.

    Children are not in the terminal's process group, so the terminal SIGINT
    does not reach them — :func:`note_stop_request` forwards stop instead.
    The terse close is printed when ``Jobs.run`` returns. ``-Q`` never writes
    ``scons: Build interrupted.``, so that line cannot be the cue.
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
