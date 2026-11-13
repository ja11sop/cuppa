#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   Options Error trees + short StopError for surprising refusals
#-------------------------------------------------------------------------------

"""Operator-facing option / precondition refusals.

Surprising flag combinations print an **Options Error** tree on stdout
(unprefixed so tree glyphs survive), then raise a short ``StopError`` so the
critical logger line stays a one-line summary. See
``design/archive/console-stop-error-reporting.md``.
"""

import SCons.Errors

from cuppa.colourise import (
        as_emphasised,
        as_error,
        as_error_label,
        as_info,
        as_subdued,
)
from cuppa.utility import storage
from cuppa.utility.console_report import write_report_lines


def remedy_colour( text ):
    """Emphasised info for positive next-step flags on a remedy branch."""
    return as_emphasised( as_info( text ) )


def raise_options_error(
        headline,
        reasons,
        short_message,
        encoding=None,
        out=None,
        title="Options Error",
):
    """Print an Options Error tree on stdout, then raise a short ``StopError``.

    ``headline`` is the title after the chip. ``reasons`` is a list of
    ``(prose, colour)`` branches — typically a why branch coloured with
    ``as_error`` and a remedy branch coloured with :func:`remedy_colour` so
    the positive next flags stand out. Bare ``--flags`` and ``[bracketed]``
    values take that branch's colour via ``highlight_values``.

    ``title`` defaults to ``Options Error`` (operator flag mistakes). Keep
    that for configure-time flag refusals; do not invent phase titles until
    a second vocabulary is needed.
    """
    tee, elbow, pipe, gap = storage.glyphs( encoding )
    stub = pipe.rstrip()
    lines = [
            "",
            "{}: {}".format(
                    as_error_label( as_emphasised( title ) ),
                    storage.highlight_values( headline, as_error ),
            ),
    ]
    total = len( reasons )
    for index, ( reason, colour ) in enumerate( reasons ):
        last = index == total - 1
        lines.append( as_subdued( stub ) )
        first = elbow if last else tee
        carried = gap if last else pipe
        wrap_width = max( storage.WIDEST_PROSE - len( first ), storage.NARROWEST_PROSE )
        branch = first
        for piece in storage.wrapped( reason, wrap_width ):
            lines.append(
                    as_subdued( branch ) + storage.highlight_values( piece, colour )
            )
            branch = carried
    lines.append( "" )
    write_report_lines( lines, out=out )
    raise SCons.Errors.StopError( short_message )
