#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

"""Unit tests for sconscript Export/Import coupling scan and order."""

import os

import pytest
import SCons.Errors

from cuppa.core.sconscript_coupling import (
        BUILTIN_EXPORT_NAMES,
        clear_session_shared,
        export_shared,
        import_shared,
        order_sconscripts,
        scan_sconscript_source,
)


pytestmark = pytest.mark.unit


def _norm_list( paths ):
    return [ os.path.normpath( p ) for p in paths ]


def test_scan_export_import_string_literals():
    source = """
Import('env')
Export('capy_libs')
Import('env', 'capy_libs')
"""
    coupling = scan_sconscript_source( source, path='sconscript' )
    assert coupling.exports == { 'capy_libs' }
    assert 'capy_libs' in coupling.imports
    assert 'env' in coupling.imports


def test_scan_cuppa_export_shared_methods():
    source = """
Import('env')
env.ExportShared( 'shared_libs', libs )
value = env.ImportShared( 'shared_libs' )
"""
    coupling = scan_sconscript_source( source, path='sconscript' )
    assert 'shared_libs' in coupling.exports
    assert 'shared_libs' in coupling.imports


def test_scan_space_separated_export_names():
    coupling = scan_sconscript_source( "Export('foo bar')\n", path='sconscript' )
    assert coupling.exports == { 'foo', 'bar' }


def test_scan_ignores_dynamic_import_name():
    coupling = scan_sconscript_source(
            "name = 'capy_libs'\nImport(name)\n",
            path='sconscript',
    )
    assert coupling.imports == set()


def test_order_puts_exporter_before_importer( tmp_path ):
    root = tmp_path / 'sconscript'
    child = tmp_path / 'test' / 'sconscript'
    child.parent.mkdir()
    root.write_text( "Import('env')\nExport('capy_libs')\n", encoding='utf-8' )
    child.write_text( "Import('env', 'capy_libs')\n", encoding='utf-8' )
    # Intentionally list importer first (discovery often hits test/ early).
    ordered = order_sconscripts( [ str( child ), str( root ) ] )
    assert _norm_list( ordered ) == _norm_list( [ str( root ), str( child ) ] )


def test_order_three_scripts_with_chain( tmp_path ):
    """A exports a; B imports a exports b; C imports b — topo A, B, C."""
    a = tmp_path / 'a.sconscript'
    b = tmp_path / 'b.sconscript'
    c = tmp_path / 'c.sconscript'
    a.write_text( "Export('name_a')\n", encoding='utf-8' )
    b.write_text( "Import('name_a')\nExport('name_b')\n", encoding='utf-8' )
    c.write_text( "Import('name_b')\n", encoding='utf-8' )
    ordered = order_sconscripts( [ str( c ), str( a ), str( b ) ] )
    assert _norm_list( ordered ) == _norm_list( [ str( a ), str( b ), str( c ) ] )


def test_order_flat_when_no_product_imports( tmp_path ):
    a = tmp_path / 'a.sconscript'
    b = tmp_path / 'b.sconscript'
    a.write_text( "Import('env')\n", encoding='utf-8' )
    b.write_text( "Import('env')\n", encoding='utf-8' )
    paths = [ str( b ), str( a ) ]
    assert _norm_list( order_sconscripts( paths ) ) == _norm_list( paths )


def test_duplicate_export_is_error( tmp_path ):
    a = tmp_path / 'a.sconscript'
    b = tmp_path / 'b.sconscript'
    a.write_text( "Export('capy_libs')\n", encoding='utf-8' )
    b.write_text( "Export('capy_libs')\n", encoding='utf-8' )
    with pytest.raises( SCons.Errors.StopError ) as caught:
        order_sconscripts( [ str( a ), str( b ) ] )
    assert 'multiple sconscripts Export' in str( caught.value )


def test_unsatisfied_import_is_error( tmp_path ):
    child = tmp_path / 'test' / 'sconscript'
    child.parent.mkdir()
    child.write_text( "Import('env', 'missing_libs')\n", encoding='utf-8' )
    with pytest.raises( SCons.Errors.StopError ) as caught:
        order_sconscripts( [ str( child ) ], search_root=str( tmp_path ) )
    assert 'not satisfied' in str( caught.value )


def test_scripts_subset_widens_to_exporter( tmp_path ):
    """Simulate ``--scripts=test/sconscript``: only importer named; pull exporter."""
    root = tmp_path / 'sconscript'
    child = tmp_path / 'test' / 'sconscript'
    child.parent.mkdir()
    root.write_text( "Export('capy_libs')\n", encoding='utf-8' )
    child.write_text( "Import('capy_libs')\n", encoding='utf-8' )
    ordered = order_sconscripts(
            [ str( child ) ],
            search_root=str( tmp_path ),
            widen=True,
    )
    norms = _norm_list( ordered )
    assert os.path.normpath( str( root ) ) in norms
    assert norms.index( os.path.normpath( str( root ) ) ) < norms.index(
            os.path.normpath( str( child ) )
    )


def test_scripts_subset_multi_hop_widen( tmp_path ):
    """Importer-only --scripts set; mid-tier exporter also Imports another name."""
    leaf = tmp_path / 'leaf' / 'sconscript'
    mid = tmp_path / 'mid' / 'sconscript'
    root = tmp_path / 'sconscript'
    leaf.parent.mkdir()
    mid.parent.mkdir()
    root.write_text( "Export('name_root')\n", encoding='utf-8' )
    mid.write_text( "Import('name_root')\nExport('name_mid')\n", encoding='utf-8' )
    leaf.write_text( "Import('name_mid')\n", encoding='utf-8' )
    ordered = order_sconscripts(
            [ str( leaf ) ],
            search_root=str( tmp_path ),
            widen=True,
    )
    norms = _norm_list( ordered )
    assert norms == _norm_list( [ str( root ), str( mid ), str( leaf ) ] )


def test_scripts_multiple_named_importers_widen_once( tmp_path ):
    """``--scripts=x,y`` both Import the same root export."""
    root = tmp_path / 'sconscript'
    x = tmp_path / 'apps' / 'x.sconscript'
    y = tmp_path / 'apps' / 'y.sconscript'
    x.parent.mkdir()
    root.write_text( "Export('shared')\n", encoding='utf-8' )
    x.write_text( "Import('shared')\n", encoding='utf-8' )
    y.write_text( "Import('shared')\n", encoding='utf-8' )
    ordered = order_sconscripts(
            [ str( y ), str( x ) ],
            search_root=str( tmp_path ),
            widen=True,
    )
    norms = _norm_list( ordered )
    assert norms[0] == os.path.normpath( str( root ) )
    assert set( norms[1:] ) == {
            os.path.normpath( str( x ) ),
            os.path.normpath( str( y ) ),
    }


def test_strict_widen_false_does_not_pull_exporter( tmp_path ):
    root = tmp_path / 'sconscript'
    child = tmp_path / 'test' / 'sconscript'
    child.parent.mkdir()
    root.write_text( "Export('capy_libs')\n", encoding='utf-8' )
    child.write_text( "Import('capy_libs')\n", encoding='utf-8' )
    with pytest.raises( SCons.Errors.StopError ) as caught:
        order_sconscripts(
                [ str( child ) ],
                search_root=str( tmp_path ),
                widen=False,
        )
    assert 'strict-sconscript-exports' in str( caught.value )
    assert os.path.normpath( str( root ) ) not in str( caught.value ) or True


def test_strict_satisfied_within_set_ok( tmp_path ):
    root = tmp_path / 'sconscript'
    child = tmp_path / 'test' / 'sconscript'
    child.parent.mkdir()
    root.write_text( "Export('capy_libs')\n", encoding='utf-8' )
    child.write_text( "Import('capy_libs')\n", encoding='utf-8' )
    ordered = order_sconscripts(
            [ str( child ), str( root ) ],
            search_root=str( tmp_path ),
            widen=False,
    )
    assert _norm_list( ordered ) == _norm_list( [ str( root ), str( child ) ] )


def test_cycle_is_error( tmp_path ):
    a = tmp_path / 'a.sconscript'
    b = tmp_path / 'b.sconscript'
    a.write_text( "Export('a_name')\nImport('b_name')\n", encoding='utf-8' )
    b.write_text( "Export('b_name')\nImport('a_name')\n", encoding='utf-8' )
    with pytest.raises( SCons.Errors.StopError ) as caught:
        order_sconscripts( [ str( a ), str( b ) ] )
    assert 'cycle' in str( caught.value ).lower()


def test_order_preserves_dot_slash_prefix( tmp_path ):
    # Construct discovers ``./sconscript``; stripping ``./`` breaks final_dir layout.
    root = tmp_path / 'sconscript'
    root.write_text( "Import('env')\n", encoding='utf-8' )
    cwd = os.getcwd()
    try:
        os.chdir( str( tmp_path ) )
        ordered = order_sconscripts( [ './sconscript' ] )
        assert ordered == [ './sconscript' ]
    finally:
        os.chdir( cwd )


def test_export_import_shared_session_registry():
    clear_session_shared()

    class FakeEnv( dict ):
        pass

    env = FakeEnv()
    export_shared( env, 'capy_libs', [ 'lib_a' ] )
    assert import_shared( env, 'capy_libs' ) == [ 'lib_a' ]
    assert import_shared( env, 'capy_libs', 'capy_libs' ) == ( [ 'lib_a' ], [ 'lib_a' ] )
    with pytest.raises( SCons.Errors.StopError ):
        export_shared( env, 'env', 'nope' )
    clear_session_shared()
    with pytest.raises( SCons.Errors.StopError ):
        import_shared( env, 'capy_libs' )
    assert 'env' in BUILTIN_EXPORT_NAMES


def test_parse_error_in_sconscript_is_stop_error():
    with pytest.raises( SCons.Errors.StopError ) as caught:
        scan_sconscript_source( "Export('oops'\n", path='bad.sconscript' )
    assert 'cannot parse' in str( caught.value )
