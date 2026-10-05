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


def write_report_lines( lines, out=None ):
    """Emit report lines unprefixed — tree glyphs do not survive log labels.

    When the quiet heartbeat is diverting and ``out`` is the default stdout
    pipe, clear+write via ``heartbeat.write_report`` so a later status paint
    cannot leave the banner glued to ``working …``. Interactive launchers
    keep the banner on the progress TTY; piped launchers (CI, redirects)
    also forward it on stdout. Explicit ``out`` streams keep the simple
    clear+write path.
    """
    text = "".join( line + "\n" for line in lines )
    if out is None:
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
