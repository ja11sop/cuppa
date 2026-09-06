#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

"""Integration: ExportShared ordering, --scripts widen, and strict exports."""

import pytest

from tests.helpers.cuppa_runner import assert_failure, assert_success, run_cuppa
from tests.helpers.project import copy_dummy_project, write_sconstruct


pytestmark = pytest.mark.integration


def _write_export_tree( project ):
    """Root exports; mid imports root and exports; leaf imports mid."""
    ( project / 'sconscript' ).write_text(
            "Import('env')\n"
            "env.ExportShared( 'name_root', 'from-root' )\n",
            encoding='utf-8',
    )
    mid = project / 'mid'
    mid.mkdir()
    ( mid / 'sconscript' ).write_text(
            "Import('env')\n"
            "root = env.ImportShared( 'name_root' )\n"
            "env.ExportShared( 'name_mid', root + '-mid' )\n",
            encoding='utf-8',
    )
    leaf = project / 'leaf'
    leaf.mkdir()
    marker = project / 'imported_marker.txt'
    ( leaf / 'sconscript' ).write_text(
            "Import('env')\n"
            "value = env.ImportShared( 'name_mid' )\n"
            "open( r'{}', 'w', encoding='utf-8' ).write( value )\n".format(
                    str( marker ).replace( '\\', '\\\\' )
            ),
            encoding='utf-8',
    )
    return marker


def test_export_shared_orders_importer_after_exporter( tmp_path ):
    project = copy_dummy_project( tmp_path )
    write_sconstruct( project, default_variants=['dbg'] )

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


def test_scripts_single_importer_widens_chain( tmp_path ):
    """``--scripts=leaf/sconscript`` pulls mid and root exporters."""
    project = copy_dummy_project( tmp_path )
    write_sconstruct( project, default_variants=['dbg'] )
    marker = _write_export_tree( project )

    result = run_cuppa( project, '--dbg', '--scripts=leaf/sconscript' )
    assert_success( result )
    assert marker.read_text( encoding='utf-8' ) == 'from-root-mid'


def test_scripts_two_importers_share_widened_exporter( tmp_path ):
    project = copy_dummy_project( tmp_path )
    write_sconstruct( project, default_variants=['dbg'] )

    ( project / 'sconscript' ).write_text(
            "Import('env')\n"
            "env.ExportShared( 'shared', 'ok' )\n",
            encoding='utf-8',
    )
    for name in ( 'app_a', 'app_b' ):
        folder = project / name
        folder.mkdir()
        marker = project / ( name + '_marker.txt' )
        ( folder / 'sconscript' ).write_text(
                "Import('env')\n"
                "value = env.ImportShared( 'shared' )\n"
                "open( r'{}', 'w', encoding='utf-8' ).write( value )\n".format(
                        str( marker ).replace( '\\', '\\\\' )
                ),
                encoding='utf-8',
        )

    result = run_cuppa(
            project,
            '--dbg',
            '--scripts=app_a/sconscript,app_b/sconscript',
    )
    assert_success( result )
    assert ( project / 'app_a_marker.txt' ).read_text( encoding='utf-8' ) == 'ok'
    assert ( project / 'app_b_marker.txt' ).read_text( encoding='utf-8' ) == 'ok'


def test_strict_sconscript_exports_refuses_widen( tmp_path ):
    project = copy_dummy_project( tmp_path )
    write_sconstruct( project, default_variants=['dbg'] )
    _write_export_tree( project )

    result = run_cuppa(
            project,
            '--dbg',
            '--scripts=leaf/sconscript',
            '--strict-sconscript-exports',
    )
    assert_failure( result )
    assert 'not satisfied' in result.stdout
    assert 'strict-sconscript-exports' in result.stdout
