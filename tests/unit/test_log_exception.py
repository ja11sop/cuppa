#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

"""StopError / UserError critical lines highlight values; other exceptions stay info."""

import logging

import SCons.Errors
import pytest

from cuppa.colourise import as_error, as_info, colouriser
from cuppa.utility.storage import highlight_values

pytestmark = pytest.mark.unit


@pytest.fixture
def colour_on():
    was = colouriser.use_colour
    colouriser.enable()
    yield
    colouriser.use_colour = was


def test_stop_error_critical_line_highlights_values( colour_on, caplog ):
    from cuppa import log_exception

    message = (
            "cascade will not publish: [grpc 1.84.0 (grpc)] at "
            "[~/.cuppa/publishers/grpc] has uncommitted changes. "
            "Pass --publish-modified to publish anyway."
    )
    with caplog.at_level( logging.CRITICAL ):
        log_exception( SCons.Errors.StopError( message ), "stack", suppress=False )

    text = caplog.records[0].getMessage()
    assert as_error( "StopError" ) in text
    assert highlight_values( message, as_error ) in text
    assert as_info( message ) not in text


def test_build_error_critical_line_stays_info( colour_on, caplog ):
    from cuppa import log_exception

    message = "build failed for [widget]"
    with caplog.at_level( logging.CRITICAL ):
        log_exception( SCons.Errors.BuildError( errstr=message ), "stack", suppress=False )

    text = caplog.records[0].getMessage()
    assert as_info( "BuildError" ) in text
    assert as_info( message ) in text


def test_mask_and_colour_operator_error_does_not_paint_csi_reset_as_value( colour_on ):
    """Pre-coloured args must not leave a literal ``0m`` on the SCons re-raise line."""
    from cuppa import _mask_and_colour_operator_error

    precoloured = "Package [{}]: missing [{}]".format(
            as_error( "pkg/1.0/rel" ),
            as_error( "pkg_libs.pc" ),
    )
    error = SCons.Errors.StopError( precoloured )
    _mask_and_colour_operator_error( error )
    text = error.args[0]
    assert "0m" not in text.replace( "\x1b[0m", "" )
    assert as_error( "pkg/1.0/rel" ) in text
    assert as_error( "pkg_libs.pc" ) in text
