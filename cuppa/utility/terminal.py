
#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   Terminal — console width, fit, controlling TTY, progress stream
#-------------------------------------------------------------------------------

"""Shared interactive-console primitives.

Cuppa often paints on the **controlling terminal** while durable transcript
travels a launcher **stdout pipe**. Helpers here prefer ``/dev/tty`` /
``CONOUT$`` (and inherited progress fds) so width and progress streams are not
clamped to a pipe's fake 80 columns.

Used by heartbeat status lines, transfer ``ProgressReporter``, terse ``Run``
command cells, and cascade nest ``pass_fds`` / env forwarding.
"""

import os
import re
import sys

from cuppa.utility.preprocess import AnsiEscape


# --- display width (ANSI-aware) ------------------------------------------------

_ANSI_ESCAPE_RE = AnsiEscape.ansi_escape_re
# HtmlColouriser placeholders (cuppa/colourise_html.py); keep in sync with that token.
_HTML_COLOUR_TOKEN_RE = re.compile( r'\x00cuppa-html-\d+\x00' )

ELLIPSIS = '\u2026'


def visible_len( text ):
    """Display width of ``text`` with ANSI and HTML colouriser tokens removed."""
    text = _ANSI_ESCAPE_RE.sub( '', str( text ) )
    return len( _HTML_COLOUR_TOKEN_RE.sub( '', text ) )


def pad_visible( text, width ):
    """Left-justify ``text`` to a visible width of ``width`` columns."""
    text = str( text )
    pad = width - visible_len( text )
    if pad <= 0:
        return text
    return text + ( ' ' * pad )


# --- console columns / fit -----------------------------------------------------

_columns_override = None  # tests / heartbeat.configure


def set_columns_override( columns ):
    """Pin ``terminal_columns()`` (``None`` restores TTY probe)."""
    global _columns_override
    _columns_override = columns


def terminal_columns():
    """Columns of the interactive console (not the launcher stdout pipe).

    Order: override → progress-stream fileno → ``/dev/tty`` / ``CONOUT$`` →
    ``shutil.get_terminal_size`` on stdout → 80.
    """
    if _columns_override is not None:
        return max( 1, int( _columns_override ) )
    if _progress_tty_stream is not None:
        try:
            return max( 1, os.get_terminal_size( _progress_tty_stream.fileno() ).columns )
        except Exception:
            pass
    if _progress_tty_fd is not None:
        try:
            return max( 1, os.get_terminal_size( _progress_tty_fd ).columns )
        except Exception:
            pass
    for path in controlling_tty_paths():
        fd = None
        try:
            fd = os.open( path, os.O_RDONLY )
            return max( 1, os.get_terminal_size( fd ).columns )
        except Exception:
            pass
        finally:
            if fd is not None:
                try:
                    os.close( fd )
                except Exception:
                    pass
    try:
        import shutil
        return max( 1, shutil.get_terminal_size( fallback=( 80, 24 ) ).columns )
    except Exception:
        return 80


def fit_plain( plain, cols ):
    """Truncate plain text to ``cols`` visible columns with an ellipsis."""
    text = plain or ''
    if cols < 1:
        cols = 1
    if len( text ) <= cols:
        return text
    if cols == 1:
        return ELLIPSIS
    return text[ : cols - 1 ] + ELLIPSIS


# --- launcher vs human console -------------------------------------------------

STDOUT_IS_TTY_ENV = "CUPPA_STDOUT_IS_TTY"


def resolve_cuppa_stdout_is_tty( environ=None, stdout_is_tty=None ):
    """Env value for :data:`STDOUT_IS_TTY_ENV` passed to the SCons child.

    Preserve an outermost interactive flag through nested ``python -m cuppa``
    (cascade). Only probe ``stdout.isatty()`` when the flag is unset.
    """
    env = os.environ if environ is None else environ
    inherited = env.get( STDOUT_IS_TTY_ENV )
    if inherited is not None and str( inherited ).strip() != '':
        return str( inherited ).strip()
    if stdout_is_tty is None:
        try:
            stdout_is_tty = bool( sys.stdout.isatty() )
        except Exception:
            stdout_is_tty = False
    return '1' if stdout_is_tty else '0'


def outer_stdout_is_tty():
    """Whether the ultimate human console is a TTY.

    The outermost ``cuppa`` launcher sets :data:`STDOUT_IS_TTY_ENV` because the
    SCons child's stdout is always a pipe. Nested cascade must **preserve**
    that flag. Unset (direct SCons) means "assume interactive".
    """
    flag = os.environ.get( STDOUT_IS_TTY_ENV )
    if flag is None:
        return True
    return flag.strip() not in ( '0', 'false', 'False', 'no', 'NO' )


# --- controlling TTY / progress stream ----------------------------------------

PROGRESS_TTY_ENV = "CUPPA_PROGRESS_TTY"
PROGRESS_FD_ENV = "CUPPA_PROGRESS_FD"

_progress_tty_stream = None
_progress_tty_fd = None


def controlling_tty_paths():
    """Device paths to try for the interactive console (platform order)."""
    if sys.platform == 'win32' or os.name == 'nt':
        return ( 'CONOUT$', )
    return ( '/dev/tty', )


def progress_fd_inheritance_supported():
    """``pass_fds`` + inherited fileno only works on POSIX."""
    return not ( sys.platform == 'win32' or os.name == 'nt' )


def stream_writable( stream ):
    """True when a tiny write/flush succeeds (GitHub Actions ``CONOUT$`` lies)."""
    try:
        stream.write( '' )
        stream.flush()
        return True
    except Exception:
        return False


def reset_progress_tty_state():
    """Clear cached progress tty stream/fd (unit tests)."""
    global _progress_tty_stream, _progress_tty_fd
    _progress_tty_stream = None
    _progress_tty_fd = None


def _publish_progress_tty_env( stream ):
    """Record path + fd env for cascade nests / launcher children."""
    global _progress_tty_stream, _progress_tty_fd
    try:
        fd = stream.fileno()
    except Exception:
        return
    _progress_tty_stream = stream
    _progress_tty_fd = fd
    if progress_fd_inheritance_supported():
        try:
            os.environ[PROGRESS_FD_ENV] = str( fd )
        except Exception:
            pass
    else:
        try:
            os.environ.pop( PROGRESS_FD_ENV, None )
        except Exception:
            pass
    try:
        path = os.ttyname( fd )
    except Exception:
        path = None
    if not path and ( sys.platform == 'win32' or os.name == 'nt' ):
        path = 'CONOUT$'
    if path:
        try:
            os.environ[PROGRESS_TTY_ENV] = path
        except Exception:
            pass


def resolve_progress_tty_path():
    """Absolute tty device path for rewriting progress, or ``None``."""
    existing = os.environ.get( PROGRESS_TTY_ENV )
    if existing and ( existing == 'CONOUT$' or os.path.exists( existing ) ):
        return existing
    fd = ensure_progress_tty_fd()
    if fd is None:
        return None
    try:
        return os.ttyname( fd )
    except Exception:
        return os.environ.get( PROGRESS_TTY_ENV )


def ensure_progress_tty_fd():
    """Return a live fileno for interactive progress, or ``None``.

    Cascade nests use ``start_new_session`` and lose ``/dev/tty``. The tip keeps
    an open progress fd and forwards it with ``pass_fds`` + :data:`PROGRESS_FD_ENV`
    on POSIX. Windows nests reopen ``CONOUT$`` / :data:`PROGRESS_TTY_ENV`.
    """
    global _progress_tty_stream, _progress_tty_fd

    if _progress_tty_fd is not None:
        try:
            if os.isatty( _progress_tty_fd ):
                return _progress_tty_fd
        except Exception:
            _progress_tty_fd = None
            _progress_tty_stream = None

    if progress_fd_inheritance_supported():
        inherited = os.environ.get( PROGRESS_FD_ENV )
        if inherited:
            try:
                fd = int( inherited )
                if os.isatty( fd ):
                    _progress_tty_fd = fd
                    return fd
            except Exception:
                pass

    candidates = list( controlling_tty_paths() )
    env_tty = os.environ.get( PROGRESS_TTY_ENV )
    if env_tty and env_tty not in candidates:
        candidates.append( env_tty )

    for path in candidates:
        try:
            stream = open( path, 'w' )
        except ( OSError, IOError ):
            continue
        try:
            if stream.isatty() and stream_writable( stream ):
                _publish_progress_tty_env( stream )
                return _progress_tty_fd
        except Exception:
            pass
        try:
            stream.close()
        except Exception:
            pass
    return None


def progress_tty_popen_kwargs( env=None ):
    """``pass_fds`` / env updates so a child keeps the tip progress tty.

    Returns ``(kwargs, env)``. Omits ``pass_fds`` on Windows; strips
    :data:`PROGRESS_FD_ENV` there so a stale numeric fd cannot leak.
    """
    if env is None:
        env = os.environ.copy()
    else:
        env = dict( env )
    fd = ensure_progress_tty_fd()
    if fd is None:
        env.pop( PROGRESS_FD_ENV, None )
        return {}, env
    path = None
    try:
        path = os.ttyname( fd )
    except Exception:
        path = os.environ.get( PROGRESS_TTY_ENV )
    if not progress_fd_inheritance_supported():
        env.pop( PROGRESS_FD_ENV, None )
        if not path:
            path = 'CONOUT$'
        env[PROGRESS_TTY_ENV] = path
        return {}, env
    env[PROGRESS_FD_ENV] = str( fd )
    if path:
        env[PROGRESS_TTY_ENV] = path
    return { "pass_fds": ( fd, ) }, env


def open_progress_stream():
    """Return ``(stream, is_tty, owns_stream)`` for progress / status output.

    Prefer inherited :data:`PROGRESS_FD_ENV` on POSIX, then controlling tty /
    :data:`PROGRESS_TTY_ENV`. Fall back to ``sys.stderr`` when there is no tty.
    """
    if progress_fd_inheritance_supported():
        inherited = os.environ.get( PROGRESS_FD_ENV )
        if inherited:
            try:
                fd = int( inherited )
                if os.isatty( fd ):
                    stream = os.fdopen( fd, 'w', closefd=False )
                    if stream_writable( stream ):
                        _publish_progress_tty_env( stream )
                        return stream, True, False
            except Exception:
                pass

    fd = ensure_progress_tty_fd()
    if fd is not None and _progress_tty_stream is not None:
        return _progress_tty_stream, True, False
    if fd is not None:
        try:
            stream = os.fdopen( fd, 'w', closefd=False )
            return stream, True, False
        except Exception:
            pass

    stream = sys.stderr
    is_tty = False
    try:
        is_tty = bool( stream.isatty() )
    except Exception:
        is_tty = False
    if not is_tty:
        try:
            is_tty = os.isatty( 2 )
        except Exception:
            is_tty = False
    return stream, is_tty, False
