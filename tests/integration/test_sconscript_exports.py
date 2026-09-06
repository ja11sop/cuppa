#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

"""Integration: ExportShared ordering, --scripts widen, and strict exports."""

import pytest

from tests.helpers.cuppa_runner import (
        assert_failure,
        assert_success,
        find_final_binaries,
        find_under_build,
        run_cuppa,
)
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


def test_clean_with_scripts_widen_removes_exporter_artefacts( tmp_path ):
    """``--scripts=test/sconscript --clean`` must clean root outputs after widen.

    Widened exporter paths must match discovery (``./sconscript``), otherwise
    clean registers a different ``_build`` layout and leaves artefacts behind.
    """
    project = copy_dummy_project( tmp_path )
    write_sconstruct( project, default_variants=['dbg'] )

    ( project / 'sconscript' ).write_text(
            "Import('env')\n"
            "env.AppendUnique(CPPPATH=['#/include'])\n"
            "env.Build( 'widget', ['#/apps/main.cpp'] )\n"
            "env.ExportShared( 'shared_marker', 'from-root' )\n",
            encoding='utf-8',
    )
    test_dir = project / 'test'
    test_dir.mkdir()
    ( test_dir / 'sconscript' ).write_text(
            "Import('env')\n"
            "env.ImportShared( 'shared_marker' )\n"
            "env.AppendUnique(CPPPATH=['#/include'])\n"
            "env.Build( 'app', ['#/apps/main.cpp'] )\n",
            encoding='utf-8',
    )

    assert_success( run_cuppa( project, '--dbg' ) )
    build = project / '_build'
    assert any( p.is_file() for p in build.rglob( '*' ) )

    assert_success( run_cuppa( project, '--dbg', '--clean' ) )
    assert not any( p.is_file() for p in build.rglob( '*' ) )

    assert_success( run_cuppa( project, '--dbg' ) )
    assert_success( run_cuppa( project, '--dbg', '--scripts=test/sconscript', '--clean' ) )
    left = [ p for p in build.rglob( '*' ) if p.is_file() ]
    assert not left, left


def test_export_shared_dbg_and_rel_are_distinct( tmp_path ):
    """Same ExportShared name must resolve to the active variant under --dbg --rel."""
    project = copy_dummy_project( tmp_path )
    write_sconstruct( project, default_variants=['dbg', 'rel'] )

    ( project / 'sconscript' ).write_text(
            "Import('env')\n"
            "env.ExportShared( 'shared_variant', env['variant'].name() )\n",
            encoding='utf-8',
    )
    test_dir = project / 'test'
    test_dir.mkdir()
    marker_dbg = project / 'marker_dbg.txt'
    marker_rel = project / 'marker_rel.txt'
    ( test_dir / 'sconscript' ).write_text(
            "Import('env')\n"
            "value = env.ImportShared( 'shared_variant' )\n"
            "assert value == env['variant'].name(), (value, env['variant'].name())\n"
            "path = r'{dbg}' if env['variant'].name() == 'dbg' else r'{rel}'\n"
            "open( path, 'w', encoding='utf-8' ).write( value )\n".format(
                    dbg=str( marker_dbg ).replace( '\\', '\\\\' ),
                    rel=str( marker_rel ).replace( '\\', '\\\\' ),
            ),
            encoding='utf-8',
    )

    result = run_cuppa( project, '--dbg', '--rel' )
    assert_success( result )
    assert marker_dbg.read_text( encoding='utf-8' ) == 'dbg'
    assert marker_rel.read_text( encoding='utf-8' ) == 'rel'


def test_export_shared_static_lib_builds_under_parallel( tmp_path ):
    """Imported BuildStaticLib nodes must link correctly under ``--parallel`` (-j).

    Configure still runs sconscripts serially; this checks the build DAG when the
    consumer links nodes published via ExportShared.
    """
    project = copy_dummy_project( tmp_path )
    write_sconstruct( project, default_variants=['dbg'] )

    ( project / 'lib' ).mkdir()
    ( project / 'lib' / 'answer.cpp' ).write_text(
            "int answer()\n"
            "{\n"
            "    return 42;\n"
            "}\n",
            encoding='utf-8',
    )
    ( project / 'apps' / 'use_answer.cpp' ).write_text(
            "int answer();\n"
            "int main()\n"
            "{\n"
            "    return answer() == 42 ? 0 : 1;\n"
            "}\n",
            encoding='utf-8',
    )

    ( project / 'sconscript' ).write_text(
            "Import('env')\n"
            "lib = env.BuildStaticLib( 'answer', 'lib/answer.cpp' )\n"
            "env.ExportShared( 'answer_lib', lib )\n",
            encoding='utf-8',
    )
    test_dir = project / 'test'
    test_dir.mkdir()
    ( test_dir / 'sconscript' ).write_text(
            "Import('env')\n"
            "lib = env.ImportShared( 'answer_lib' )\n"
            "env.AppendUnique( LIBPATH=[ env['abs_final_dir'] ] )\n"
            "app = env.Build( 'use_answer', ['#/apps/use_answer.cpp'], LIBS=[ lib ] )\n"
            "env.Depends( app, lib )\n",
            encoding='utf-8',
    )

    result = run_cuppa( project, '--dbg', '--parallel' )
    assert_success( result )
    assert find_final_binaries( project, 'use_answer' )
    archives = [
            path for path in find_under_build( project )
            if path.is_file() and path.suffix in ( '.a', '.lib' ) and 'answer' in path.name
    ]
    assert archives, 'expected BuildStaticLib archive under _build'
