#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   Console reports — stdout product, not the logger
#-------------------------------------------------------------------------------

"""Stdout lines the operator asked Cuppa to show.

Console reports (list trees, judgement trees, mode banners) are not logs.
``-Q`` raises the logger to warn and ``-s`` / ``--quiet`` raises it to error,
so ``logger.info`` cannot carry them. See ``design/plans/console-channels.md``.
"""

import sys


class _HeartbeatReportStream( object ):
    """File-like writer that clears the quiet status line before each chunk.

    Under ``-Q`` the heartbeat paints on the progress TTY with ``\\r`` while
    SCons/Cuppa report bodies historically wrote the stdout *pipe*. The
    ``cuppa`` launcher then echoed pipe text onto the same physical row as
    the status caption (``…downloadsRemoving 1 dependency…``). Route those
    writes through ``heartbeat.write_report`` instead.
    """

    def write( self, data ):
        if not data:
            return 0
        from cuppa.utility.heartbeat import write_report
        write_report( data )
        return len( data )

    def flush( self ):
        pass


def _is_default_stdout( out ):
    return out is None or out is sys.stdout


def ensure_report_stream( out=None ):
    """Return a stream safe for console reports under quiet heartbeat diversion.

    Explicit capture streams (tests, ``StringIO``) are unchanged. Default /
    ``sys.stdout`` while diverting goes through ``write_report`` so list/purge
    tables cannot glue onto ``|---+--|  …``.
    """
    if not _is_default_stdout( out ):
        return out
    try:
        from cuppa.utility.heartbeat import diverting
        if diverting():
            return _HeartbeatReportStream()
    except Exception:
        pass
    return sys.stdout if out is None else out


def write_report_lines( lines, out=None ):
    """Emit report lines unprefixed — tree glyphs do not survive log labels.

    When the quiet heartbeat is diverting and ``out`` is the default stdout
    pipe, clear+write via ``heartbeat.write_report`` so a later status paint
    cannot leave the banner glued to ``working …``. Interactive launchers
    keep the banner on the progress TTY; piped launchers (CI, redirects)
    also forward it on stdout. Explicit capture streams keep the simple
    write path (after an immediate status clear).
    """
    text = "".join( line + "\n" for line in lines )
    if _is_default_stdout( out ):
        try:
            from cuppa.utility.heartbeat import diverting, write_report
            if diverting():
                write_report( text )
                return
        except Exception:
            pass
        try:
            from cuppa.utility.heartbeat import clear as clear_heartbeat
            clear_heartbeat()
        except Exception:
            pass
        sys.stdout.write( text )
        sys.stdout.flush()
        return
    try:
        from cuppa.utility.heartbeat import clear as clear_heartbeat
        clear_heartbeat()
    except Exception:
        pass
    for line in lines:
        out.write( line + "\n" )
    out.flush()


def report_mode_banner( line, out=None ):
    """Print one mode chip on the console-report channel.

    ``line`` may already include colour (``as_info_label`` plus plain suffix).
    A later TTY heartbeat must clear its status line before calling this.
    """
    write_report_lines( [ line ], out=out )
