#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

"""Integration: discovered sconscripts honour ExportShared before ImportShared."""

from pathlib import Path

import pytest

from tests.helpers.cuppa_runner import assert_success, run_cuppa
from tests.helpers.project import copy_dummy_project, write_sconstruct


pytestmark = pytest.mark.integration


def test_export_shared_orders_importer_after_exporter( tmp_path ):
    project = copy_dummy_project( tmp_path )
    write_sconstruct( project, default_variants=['dbg'] )

    # Root exports a marker string; test/ imports it. List importer-first via
    # filesystem layout (test/ often discovered before or after root — either way
    # Cuppa must run the exporter first).
    ( project / 'sconscript' ).write_text(
            "Import('env')\n"
            "env.ExportShared( 'shared_marker', 'from-root' )\n",
            encoding='utf-8',
    )
    test_dir = project / 'test'
    test_dir.mkdir()
    marker = project / 'imported_marker.txt'
    ( test_dir / 'sconscript' ).write_text(
            "Import('env')\n"
            "value = env.ImportShared( 'shared_marker' )\n"
            "open( r'{}', 'w', encoding='utf-8' ).write( value )\n".format(
                    str( marker ).replace( '\\', '\\\\' )
            ),
            encoding='utf-8',
    )

    result = run_cuppa( project, '--dbg' )
    assert_success( result )
    assert marker.exists(), result.stdout + result.stderr
    assert marker.read_text( encoding='utf-8' ) == 'from-root'
