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
    """Emit report lines unprefixed — tree glyphs do not survive log labels."""
    stream = out if out is not None else sys.stdout
    for line in lines:
        stream.write( line + "\n" )
    stream.flush()


def report_mode_banner( line, out=None ):
    """Print one mode chip on the console-report channel.

    ``line`` may already include colour (``as_info_label`` plus plain suffix).
    A later TTY heartbeat must clear its status line before calling this.
    """
    write_report_lines( [ line ], out=out )
