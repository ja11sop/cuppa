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


def test_order_puts_exporter_before_importer( tmp_path ):
    root = tmp_path / 'sconscript'
    child = tmp_path / 'test' / 'sconscript'
    child.parent.mkdir()
    root.write_text( "Import('env')\nExport('capy_libs')\n", encoding='utf-8' )
    child.write_text( "Import('env', 'capy_libs')\n", encoding='utf-8' )
    # Intentionally list importer first (discovery often hits test/ early).
    ordered = order_sconscripts( [ str( child ), str( root ) ] )
    assert ordered == [ str( root ), str( child ) ] or (
            os.path.normpath( ordered[0] ) == os.path.normpath( str( root ) )
            and os.path.normpath( ordered[1] ) == os.path.normpath( str( child ) )
    )


def test_order_flat_when_no_product_imports( tmp_path ):
    a = tmp_path / 'a.sconscript'
    b = tmp_path / 'b.sconscript'
    a.write_text( "Import('env')\n", encoding='utf-8' )
    b.write_text( "Import('env')\n", encoding='utf-8' )
    paths = [ str( b ), str( a ) ]
    assert [ os.path.normpath( p ) for p in order_sconscripts( paths ) ] == [
            os.path.normpath( p ) for p in paths
    ]


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


def test_widen_finds_exporter_outside_initial_list( tmp_path ):
    root = tmp_path / 'sconscript'
    child = tmp_path / 'test' / 'sconscript'
    child.parent.mkdir()
    root.write_text( "Export('capy_libs')\n", encoding='utf-8' )
    child.write_text( "Import('capy_libs')\n", encoding='utf-8' )
    ordered = order_sconscripts( [ str( child ) ], search_root=str( tmp_path ) )
    norms = [ os.path.normpath( p ) for p in ordered ]
    assert os.path.normpath( str( root ) ) in norms
    assert norms.index( os.path.normpath( str( root ) ) ) < norms.index(
            os.path.normpath( str( child ) )
    )


def test_cycle_is_error( tmp_path ):
    a = tmp_path / 'a.sconscript'
    b = tmp_path / 'b.sconscript'
    a.write_text( "Export('a_name')\nImport('b_name')\n", encoding='utf-8' )
    b.write_text( "Export('b_name')\nImport('a_name')\n", encoding='utf-8' )
    with pytest.raises( SCons.Errors.StopError ) as caught:
        order_sconscripts( [ str( a ), str( b ) ] )
    assert 'cycle' in str( caught.value ).lower()


def test_export_import_shared_session_registry():
    clear_session_shared()
    class FakeEnv( dict ):
        pass
    env = FakeEnv()
    export_shared( env, 'capy_libs', [ 'lib_a' ] )
    assert import_shared( env, 'capy_libs' ) == [ 'lib_a' ]
    with pytest.raises( SCons.Errors.StopError ):
        export_shared( env, 'env', 'nope' )
    assert 'env' in BUILTIN_EXPORT_NAMES
