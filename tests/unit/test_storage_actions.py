import io
import json
import re

import pytest

from cuppa.core import storage_actions
from cuppa.utility import storage
from tests.helpers.fakes import FakeEnv


pytestmark = pytest.mark.unit


class FakeToolchain( object ):
    def __init__( self, name ):
        self._name = name

    def name( self ):
        return self._name


class FakeConstruct( object ):
    def __init__( self, selections ):
        # selections: list of (toolchain_name, variant, arch, abi)
        self.selections = selections

    def create_build_envs( self, toolchain, cuppa_env ):
        return [
            {
                'variant': variant,
                'target_arch': arch,
                'abi': abi,
            }
            for name, variant, arch, abi in self.selections
            if name == toolchain.name()
        ]


def env_for( tmp_path, **options ):
    build = tmp_path / '_build'
    build.mkdir()
    env = FakeEnv( options )
    env['build_root'] = '_build'
    env['abs_build_root'] = str( build )
    env['sconstruct_dir'] = str( tmp_path )
    env['list_format'] = options.get( 'list_format', 'text' )
    env['active_toolchains'] = [ FakeToolchain( 'gcc15' ) ]
    return env, build


def plant_variant( build_root, *parts, content=b'hello' ):
    path = build_root.joinpath( *parts )
    working = path / 'working'
    working.mkdir( parents=True )
    ( working / 'obj.o' ).write_bytes( content )
    return path


def test_list_builds_marks_selected_variants_and_totals( tmp_path ):
    env, build = env_for( tmp_path, list_builds=True )
    plant_variant( build, 'test', 'gcc15', 'dbg', 'x86_64', 'cxx2c', content=b'1234' )
    plant_variant( build, 'test', 'gcc15', 'rel', 'x86_64', 'cxx2c', content=b'12345678' )

    construct = FakeConstruct( [
        ( 'gcc15', 'dbg', 'x86_64', 'cxx2c' ),
    ] )
    out = io.StringIO()
    status = storage_actions.list_builds( construct, env, out=out )
    text = out.getvalue()

    assert status == 0
    assert 'BUILD FOLDER' in text
    assert 'BY TOOLCHAIN VARIANT' in text
    assert 'BY SCONSCRIPT' in text
    assert 'SELECTED' in text
    assert re.search( r'(──|\+--|`--)\s*selected \(1 of 2 entries\)', text )
    assert re.search( r'(──|\+--|`--)\s*(-[✓*]-|[✓*]{3}|---)\s*gcc15\b', text )
    assert 'dbg/x86_64/cxx2c' in text
    assert 'rel/x86_64/cxx2c' in text
    # Mixed toolchain selection: parent partial; selected leaf full; other leaf none.
    assert re.search( r'(-[✓*]-)\s*gcc15\b', text )
    assert re.search( r'([✓*]{3})\s*dbg/x86_64/cxx2c', text )
    assert re.search( r'(---)\s*rel/x86_64/cxx2c', text )
    # Sconscript rollups are partial; the selected leaf keeps a single check.
    assert re.search( r'(-[✓*]-).*(──|\+--|`--)\s*test\b', text )
    assert re.search( r'(-[✓*]-).*(──|\+--|`--)\s*gcc15\b', text )
    assert re.search( r'[✓*].*(──|\+--|`--)\s*dbg/x86_64/cxx2c', text )
    assert 'Selected ' in text
    assert 'Explicit command for the selected builds:' in text
    assert 'cuppa -D' in text
    assert '--dbg' in text
    assert '--toolchains=' in text
    assert '--remove-build' in text


def test_list_builds_summary_omits_variants_absent_from_the_build_root( tmp_path ):
    env, build = env_for( tmp_path, list_builds=True )
    plant_variant( build, 'test', 'gcc15', 'dbg', 'x86_64', 'cxx2c', content=b'1234' )
    # Active selection includes rel, but no rel tree exists on disk.
    construct = FakeConstruct( [
        ( 'gcc15', 'dbg', 'x86_64', 'cxx2c' ),
        ( 'gcc15', 'rel', 'x86_64', 'cxx2c' ),
    ] )
    out = io.StringIO()
    storage_actions.list_builds( construct, env, out=out )
    text = out.getvalue()
    assert '--dbg' in text
    assert '--rel' not in text
    payload = io.StringIO()
    env['list_format'] = 'json'
    storage_actions.list_builds( construct, env, out=payload )
    settings = json.loads( payload.getvalue() )['summary']['settings']
    assert settings.get( 'dbg' ) is True
    assert 'rel' not in settings


def test_list_builds_rolls_up_selected_when_every_leaf_matches( tmp_path ):
    env, build = env_for( tmp_path, list_builds=True )
    plant_variant( build, 'test', 'gcc15', 'dbg', 'x86_64', 'cxx2c', content=b'1234' )
    plant_variant( build, 'test', 'gcc15', 'rel', 'x86_64', 'cxx2c', content=b'12345678' )
    construct = FakeConstruct( [
        ( 'gcc15', 'dbg', 'x86_64', 'cxx2c' ),
        ( 'gcc15', 'rel', 'x86_64', 'cxx2c' ),
    ] )
    out = io.StringIO()
    storage_actions.list_builds( construct, env, out=out )
    text = out.getvalue()
    assert re.search( r'([✓*]{3})\s*gcc15\b', text )
    assert re.search( r'([✓*]{3})\s*dbg/x86_64/cxx2c', text )
    assert re.search( r'([✓*]{3})\s*rel/x86_64/cxx2c', text )
    assert re.search( r'([✓*]{3}).*(──|\+--|`--)\s*test\b', text )
    assert re.search( r'(──|\+--|`--)\s*all 2 entries selected', text )


def test_list_builds_marks_sconscript_name_above_toolchains( tmp_path ):
    env, build = env_for( tmp_path, list_builds=True )
    plant_variant( build, 'test', 'algorithms', 'gcc15', 'dbg', 'x86_64', 'cxx2c' )
    construct = FakeConstruct( [ ( 'gcc15', 'dbg', 'x86_64', 'cxx2c' ) ] )
    payload_out = io.StringIO()
    env['list_format'] = 'json'
    storage_actions.list_builds( construct, env, out=payload_out )
    tree = json.loads( payload_out.getvalue() )['by_sconscript']
    assert tree[0]['name'] == 'test'
    assert tree[0]['sconscript_name'] is False
    assert tree[0]['children'][0]['name'] == 'algorithms'
    assert tree[0]['children'][0]['sconscript_name'] is True


def test_list_builds_lists_toolchains_before_sibling_folders( tmp_path ):
    env, build = env_for( tmp_path, list_builds=True )
    plant_variant( build, 'test', 'gcc15', 'dbg', 'x86_64', 'cxx2c', content=b'1234' )
    plant_variant( build, 'test', 'algorithms', 'gcc15', 'dbg', 'x86_64', 'cxx2c', content=b'123456' )
    plant_variant( build, 'test', 'clang211', 'dbg', 'x86_64', 'cxx2c', content=b'12' )
    construct = FakeConstruct( [ ( 'gcc15', 'dbg', 'x86_64', 'cxx2c' ) ] )
    env['list_format'] = 'json'
    out = io.StringIO()
    storage_actions.list_builds( construct, env, out=out )
    children = json.loads( out.getvalue() )['by_sconscript'][0]['children']
    names = [ child['name'] for child in children ]
    assert names == [ 'clang211', 'gcc15', 'algorithms' ]
    assert children[0]['toolchain'] is True
    assert children[1]['toolchain'] is True
    assert children[2]['sconscript_name'] is True


def test_list_builds_json_is_scriptable( tmp_path ):
    env, build = env_for( tmp_path, list_builds=True, list_format='json' )
    plant_variant( build, 'gcc15', 'dbg', 'x86_64', 'cxx2c' )
    construct = FakeConstruct( [ ( 'gcc15', 'dbg', 'x86_64', 'cxx2c' ) ] )
    out = io.StringIO()
    storage_actions.list_builds( construct, env, out=out )
    payload = json.loads( out.getvalue() )
    assert payload['entries'][0]['selected'] is True
    assert 'size_bytes' in payload['entries'][0]
    assert payload['total_bytes'] >= 5
    assert payload['folder']['selected_entries'] == 1
    assert payload['by_toolchain_variant'][0]['name'] == 'gcc15'
    assert payload['by_toolchain_variant'][0]['selection'] == 'full'
    assert payload['by_toolchain_variant'][0]['children'][0]['name'] == 'dbg/x86_64/cxx2c'
    assert payload['by_sconscript'][0]['selected'] is True
    assert payload['summary']['equivalent_command'].startswith( 'cuppa -D' )
    assert 'dbg' in payload['summary']['settings']
    assert payload['summary']['settings']['toolchains'] == [ 'gcc15' ]


def test_remove_build_removes_only_the_selected_suffix( tmp_path ):
    env, build = env_for( tmp_path, remove_build=True )
    keep = plant_variant( build, 'lib', 'gcc15', 'rel', 'x86_64', 'cxx2c' )
    remove = plant_variant( build, 'lib', 'gcc15', 'dbg', 'x86_64', 'cxx2c' )
    construct = FakeConstruct( [ ( 'gcc15', 'dbg', 'x86_64', 'cxx2c' ) ] )

    out = io.StringIO()
    status = storage_actions.remove_build( construct, env, out=out )

    assert status == 0
    assert not remove.exists()
    assert keep.exists()
    assert 'removed' in out.getvalue()


def test_remove_build_dry_run_removes_nothing( tmp_path, monkeypatch ):
    env, build = env_for( tmp_path, remove_build=True )
    path = plant_variant( build, 'gcc15', 'dbg', 'x86_64', 'cxx2c' )
    construct = FakeConstruct( [ ( 'gcc15', 'dbg', 'x86_64', 'cxx2c' ) ] )
    monkeypatch.setattr( storage_actions, 'dry_run', lambda cuppa_env: True )

    out = io.StringIO()
    status = storage_actions.remove_build( construct, env, out=out )

    assert status == 0
    assert path.exists()
    assert 'Would remove' in out.getvalue()
    assert 'dry run' in out.getvalue()


def test_remove_build_refuses_a_symlink( tmp_path ):
    env, build = env_for( tmp_path, remove_build=True )
    real = tmp_path / 'elsewhere' / 'gcc15' / 'dbg' / 'x86_64' / 'cxx2c'
    real.mkdir( parents=True )
    link = build / 'gcc15' / 'dbg' / 'x86_64' / 'cxx2c'
    link.parent.mkdir( parents=True )
    link.symlink_to( real )
    construct = FakeConstruct( [ ( 'gcc15', 'dbg', 'x86_64', 'cxx2c' ) ] )

    out = io.StringIO()
    with pytest.raises( storage.StorageError, match='symlink' ):
        storage_actions.remove_build( construct, env, out=out )


def test_remove_all_builds_removes_the_build_root( tmp_path ):
    env, build = env_for( tmp_path, remove_all_builds=True )
    plant_variant( build, 'gcc15', 'dbg', 'x86_64', 'cxx2c' )

    out = io.StringIO()
    status = storage_actions.remove_all_builds( env, out=out )

    assert status == 0
    assert not build.exists()


def test_remove_all_builds_refuses_the_sconstruct_directory( tmp_path ):
    env, build = env_for( tmp_path, remove_all_builds=True )
    env['abs_build_root'] = str( tmp_path )
    out = io.StringIO()
    with pytest.raises( storage.StorageError, match='sconstruct' ):
        storage_actions.remove_all_builds( env, out=out )


def test_remove_build_reports_nothing_to_remove( tmp_path ):
    env, build = env_for( tmp_path, remove_build=True )
    construct = FakeConstruct( [ ( 'gcc15', 'dbg', 'x86_64', 'cxx2c' ) ] )
    out = io.StringIO()
    status = storage_actions.remove_build( construct, env, out=out )
    assert status == 0
    assert 'nothing to remove' in out.getvalue()
