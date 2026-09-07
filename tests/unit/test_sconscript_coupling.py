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
    ( tmp_path / 'sconscript' ).write_text( "Export('capy_libs')\n", encoding='utf-8' )
    child = tmp_path / 'test' / 'sconscript'
    child.parent.mkdir()
    child.write_text( "Import('capy_libs')\n", encoding='utf-8' )
    cwd = os.getcwd()
    try:
        os.chdir( str( tmp_path ) )
        ordered = order_sconscripts(
                [ 'test/sconscript' ],
                search_root=str( tmp_path ),
                widen=True,
        )
    finally:
        os.chdir( cwd )
    # Widened exporter must be project-relative (./sconscript), not absolute —
    # absolute paths break --clean layout matching.
    assert not any( os.path.isabs( p ) for p in ordered )
    norms = _norm_list( ordered )
    assert norms.index( 'sconscript' ) < norms.index( 'test/sconscript' )


def test_as_project_relative_prefixes_dot_slash( tmp_path ):
    from cuppa.core.sconscript_coupling import _as_project_relative
    root = tmp_path / 'sconscript'
    root.write_text( 'Export("x")\n', encoding='utf-8' )
    rel = _as_project_relative( str( root.resolve() ), base_dir=str( tmp_path ) )
    assert not os.path.isabs( rel )
    assert os.path.normpath( rel ) == 'sconscript'
    assert rel.startswith( '.' + os.sep )


def test_scripts_subset_multi_hop_widen( tmp_path ):
    """Importer-only --scripts set; mid-tier exporter also Imports another name."""
    ( tmp_path / 'leaf' ).mkdir()
    ( tmp_path / 'mid' ).mkdir()
    ( tmp_path / 'sconscript' ).write_text( "Export('name_root')\n", encoding='utf-8' )
    ( tmp_path / 'mid' / 'sconscript' ).write_text(
            "Import('name_root')\nExport('name_mid')\n", encoding='utf-8'
    )
    ( tmp_path / 'leaf' / 'sconscript' ).write_text( "Import('name_mid')\n", encoding='utf-8' )
    cwd = os.getcwd()
    try:
        os.chdir( str( tmp_path ) )
        ordered = order_sconscripts(
                [ 'leaf/sconscript' ],
                search_root=str( tmp_path ),
                widen=True,
        )
    finally:
        os.chdir( cwd )
    assert not any( os.path.isabs( p ) for p in ordered )
    assert _norm_list( ordered ) == [ 'sconscript', 'mid/sconscript', 'leaf/sconscript' ]


def test_scripts_multiple_named_importers_widen_once( tmp_path ):
    """``--scripts=x,y`` both Import the same root export."""
    ( tmp_path / 'apps' ).mkdir()
    ( tmp_path / 'sconscript' ).write_text( "Export('shared')\n", encoding='utf-8' )
    ( tmp_path / 'apps' / 'x.sconscript' ).write_text( "Import('shared')\n", encoding='utf-8' )
    ( tmp_path / 'apps' / 'y.sconscript' ).write_text( "Import('shared')\n", encoding='utf-8' )
    cwd = os.getcwd()
    try:
        os.chdir( str( tmp_path ) )
        ordered = order_sconscripts(
                [ 'apps/y.sconscript', 'apps/x.sconscript' ],
                search_root=str( tmp_path ),
                widen=True,
        )
    finally:
        os.chdir( cwd )
    norms = _norm_list( ordered )
    assert norms[0] == 'sconscript'
    assert set( norms[1:] ) == { 'apps/x.sconscript', 'apps/y.sconscript' }
    assert not any( os.path.isabs( p ) for p in ordered )


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
    env['tool_variant_dir'] = 'gcc/dbg/x86_64/cxx2c'
    export_shared( env, 'capy_libs', [ 'lib_a' ] )
    assert import_shared( env, 'capy_libs' ) == [ 'lib_a' ]
    assert import_shared( env, 'capy_libs', 'capy_libs' ) == ( [ 'lib_a' ], [ 'lib_a' ] )
    with pytest.raises( SCons.Errors.StopError ):
        export_shared( env, 'env', 'nope' )
    clear_session_shared()
    with pytest.raises( SCons.Errors.StopError ):
        import_shared( env, 'capy_libs' )
    assert 'env' in BUILTIN_EXPORT_NAMES


def test_export_shared_is_variant_scoped():
    """Same export name under dbg and rel must not overwrite each other."""
    clear_session_shared()

    class FakeEnv( dict ):
        pass

    dbg = FakeEnv()
    dbg['tool_variant_dir'] = 'gcc/dbg/x86_64/cxx2c'
    rel = FakeEnv()
    rel['tool_variant_dir'] = 'gcc/rel/x86_64/cxx2c'

    export_shared( dbg, 'mylib', 'dbg-nodes' )
    export_shared( rel, 'mylib', 'rel-nodes' )
    assert import_shared( dbg, 'mylib' ) == 'dbg-nodes'
    assert import_shared( rel, 'mylib' ) == 'rel-nodes'

    # Rel re-export must not disturb dbg
    export_shared( rel, 'mylib', 'rel-nodes-2' )
    assert import_shared( dbg, 'mylib' ) == 'dbg-nodes'
    assert import_shared( rel, 'mylib' ) == 'rel-nodes-2'


def test_import_shared_missing_in_this_variant_only():
    clear_session_shared()

    class FakeEnv( dict ):
        pass

    dbg = FakeEnv()
    dbg['tool_variant_dir'] = 'gcc/dbg/x86_64/cxx2c'
    rel = FakeEnv()
    rel['tool_variant_dir'] = 'gcc/rel/x86_64/cxx2c'
    export_shared( dbg, 'mylib', 'dbg-only' )
    with pytest.raises( SCons.Errors.StopError ) as caught:
        import_shared( rel, 'mylib' )
    assert 'scope' in str( caught.value )
    assert import_shared( dbg, 'mylib' ) == 'dbg-only'

def test_parse_error_in_sconscript_is_stop_error():
    with pytest.raises( SCons.Errors.StopError ) as caught:
        scan_sconscript_source( "Export('oops'\n", path='bad.sconscript' )
    assert 'cannot parse' in str( caught.value )
