import io
import json
import os
import re

import pytest

from cuppa.colourise import as_emphasised, as_info
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
    assert re.search( r'(──|\+--|`--)\s*(-[✓✔*]-|[✓✔*]{3}|---)\s*gcc15\b', text )
    assert 'dbg/x86_64/cxx2c' in text
    assert 'rel/x86_64/cxx2c' in text
    # Mixed toolchain selection: parent partial; selected leaf full; other leaf none.
    assert re.search( r'(-[✓✔*]-)\s*gcc15\b', text )
    assert re.search( r'([✓✔*]{3})\s*dbg/x86_64/cxx2c', text )
    assert re.search( r'(---)\s*rel/x86_64/cxx2c', text )
    # Sconscript rollups are partial; the selected leaf keeps a single check.
    assert re.search( r'(-[✓✔*]-).*(──|\+--|`--)\s*test\b', text )
    assert re.search( r'(-[✓✔*]-).*(──|\+--|`--)\s*gcc15\b', text )
    assert re.search( r'[✓✔*].*(──|\+--|`--)\s*dbg/x86_64/cxx2c', text )
    assert 'Selected ' in text
    assert 'Explicit command for the selected builds:' in text
    assert 'cuppa -D' in text
    assert '--dbg' in text
    assert '--toolchains=' in text
    assert '--remove-builds' in text


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
    assert re.search( r'([✓✔*]{3})\s*gcc15\b', text )
    assert re.search( r'([✓✔*]{3})\s*dbg/x86_64/cxx2c', text )
    assert re.search( r'([✓✔*]{3})\s*rel/x86_64/cxx2c', text )
    assert re.search( r'([✓✔*]{3}).*(──|\+--|`--)\s*test\b', text )
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


def test_remove_builds_removes_only_the_selected_suffix( tmp_path ):
    env, build = env_for( tmp_path, remove_builds=True )
    keep = plant_variant( build, 'lib', 'gcc15', 'rel', 'x86_64', 'cxx2c' )
    remove = plant_variant( build, 'lib', 'gcc15', 'dbg', 'x86_64', 'cxx2c' )
    construct = FakeConstruct( [ ( 'gcc15', 'dbg', 'x86_64', 'cxx2c' ) ] )

    out = io.StringIO()
    status = storage_actions.remove_builds( construct, env, out=out )
    text = out.getvalue()

    assert status == 0
    assert not remove.exists()
    assert keep.exists()
    assert 'Removing' in text
    assert text.index( 'Removing' ) < text.index( 'BUILD FOLDER' )
    assert '_build' in text.split( 'BUILD FOLDER' )[0]
    assert 'BUILD FOLDER' in text
    assert 'BY TOOLCHAIN VARIANT' in text
    assert 'BY SCONSCRIPT' in text
    assert 'REMOVED' in text
    assert re.search( r'removed \(1 of 2 entries\)', text )
    assert re.search( r'[✓✔*].*(──|\+--|`--)\s*dbg/x86_64/cxx2c', text )
    assert re.search( r'(──|\+--|`--)\s*rel/x86_64/cxx2c', text )
    assert 'Removed 1 entry freeing up' in text
    assert 'Verify the removal' in text
    assert '--list-builds' in text


def test_remove_builds_dry_run_removes_nothing( tmp_path, monkeypatch ):
    env, build = env_for( tmp_path, remove_builds=True )
    path = plant_variant( build, 'gcc15', 'dbg', 'x86_64', 'cxx2c' )
    construct = FakeConstruct( [ ( 'gcc15', 'dbg', 'x86_64', 'cxx2c' ) ] )
    monkeypatch.setattr( storage_actions, 'dry_run', lambda cuppa_env: True )

    out = io.StringIO()
    status = storage_actions.remove_builds( construct, env, out=out )
    text = out.getvalue()

    assert status == 0
    assert path.exists()
    assert 'Would remove' in text
    assert text.index( 'Would remove' ) < text.index( 'BUILD FOLDER' )
    assert 'REMOVED' in text
    assert 'Would remove 1 entry freeing up' in text
    assert 'dry run' in text
    assert 'Verify the removal' in text
    assert '--list-builds' in text


def test_removal_announce_line_emphasises_count_size_and_short_path( tmp_path ):
    line = storage_actions._removal_announce_line(
        False, 13, 1024 * 210, str( tmp_path / '_build' ),
        project_dir=str( tmp_path ),
    )
    assert 'Removing' in line
    assert '13' in line
    assert '_build' in line
    assert str( tmp_path ) not in line
    # Emphasised / info spans are present (ANSI or plain depending on colouriser).
    assert as_emphasised( '13' ) in line or '13' in line
    assert as_info( '_build' ) in line or line.endswith( '_build' ) or '_build' in line


def test_remove_builds_reports_failures_with_ballot( tmp_path, monkeypatch ):
    env, build = env_for( tmp_path, remove_builds=True )
    path = plant_variant( build, 'lib', 'gcc15', 'dbg', 'x86_64', 'cxx2c' )
    construct = FakeConstruct( [ ( 'gcc15', 'dbg', 'x86_64', 'cxx2c' ) ] )

    def boom( target, dry_run=False ):
        raise OSError( 13, "Permission denied", os.path.join( target, 'working' ) )

    monkeypatch.setattr( storage, 'remove_path', boom )

    out = io.StringIO()
    status = storage_actions.remove_builds( construct, env, out=out )
    text = out.getvalue()

    assert status == 1
    assert path.exists()
    assert re.search( r'[✗✘x]{3}', text )
    assert 'Permission denied' in text
    assert 'Not all requested build entries could be removed' in text
    assert '[1 error]' in text
    assert '[0 warnings]' in text
    assert '[0 notes]' in text
    assert '1 error' in text
    assert 'lib/gcc15/dbg/x86_64/cxx2c' in text
    assert '[Errno 13]' in text or 'Errno 13' in text
    assert '_build/' in text
    assert 'Removed 0 entries freeing up' in text
    assert 'Verify the removal' in text


def test_removal_reason_highlights_only_bracketed_values():
    reason = storage_actions._format_removal_reason(
        OSError( 13, "Permission denied", "/tmp/project/_build/lib/working" ),
        project_dir="/tmp/project",
    )
    assert reason.startswith( '[Errno 13]' )
    assert '[_build/' in reason or '[lib/' in reason
    coloured = storage.highlight_values( reason, lambda text: 'X' + text + 'X' )
    assert 'Permission denied' in coloured
    assert 'XErrno 13X' in coloured or coloured.count( 'X' ) >= 2


def test_judgement_tree_lines_wrap_long_reasons():
    long_path = '_build/' + '/'.join( [ 'seg' ] * 40 )
    failures = [ {
        'label': 'lib/gcc15/dbg/x86_64/cxx2c',
        'reason': "[Errno 13] Permission denied: [{}]".format( long_path ),
        'path': '/tmp/x',
        'severity': 'error',
    } ]
    lines = storage_actions._judgement_tree_lines( failures, width=60 )
    # Stem carried across wrapped reason lines.
    reason_lines = [ line for line in lines if 'Permission denied' in line or 'seg/' in line ]
    assert len( reason_lines ) >= 2


def test_judgement_tree_lines_summary_brackets_and_notes():
    from cuppa.colourise import as_error, as_info, as_subdued, as_warning

    failures = [
            {
                'severity': 'error',
                'label': 'broken',
                'reason': 'could not remove [broken]',
            },
            {
                'severity': 'warning',
                'label': 'stale',
                'reason': 'already deleted [stale]',
            },
            {
                'severity': 'note',
                'label': 'hint',
                'reason': 'left [hint] in place',
            },
    ]
    intro = 'Wiping ' + storage.emphasised_count_phrase( 3, 'tree' )
    lines = storage_actions._judgement_tree_lines( failures, intro=intro, width=110 )
    assert lines[1].startswith( 'Wiping ' )
    assert storage.emphasised_count_phrase( 3, 'tree' ) in lines[1]
    assert as_error( '[1 error]' ) in lines[1]
    assert as_warning( '[1 warning]' ) in lines[1]
    assert as_info( '[1 note]' ) in lines[1]

    zeroed = storage_actions._judgement_tree_lines(
            [ failures[1] ],
            intro='Wiping ' + storage.emphasised_count_phrase( 1, 'tree' ),
            width=110,
    )
    assert as_subdued( '[0 errors]' ) in zeroed[1]
    assert as_warning( '[1 warning]' ) in zeroed[1]
    assert as_subdued( '[0 notes]' ) in zeroed[1]
    assert any( '1 warning' in line for line in zeroed )
    assert any( 'stale' in line for line in zeroed )


def test_remove_builds_already_deleted_is_a_note( tmp_path, monkeypatch ):
    env, build = env_for( tmp_path, remove_builds=True )
    path = plant_variant( build, 'lib', 'gcc15', 'dbg', 'x86_64', 'cxx2c' )
    construct = FakeConstruct( [ ( 'gcc15', 'dbg', 'x86_64', 'cxx2c' ) ] )
    real_lexists = os.path.lexists

    def fake_lexists( target ):
        if os.path.realpath( str( target ) ) == os.path.realpath( str( path ) ):
            return False
        return real_lexists( target )

    monkeypatch.setattr( os.path, 'lexists', fake_lexists )

    out = io.StringIO()
    status = storage_actions.remove_builds( construct, env, out=out )
    text = out.getvalue()

    assert status == 0
    assert '1 note' in text
    assert '[1 note]' in text
    assert '[0 warnings]' in text
    assert 'was already gone' in text
    assert 'Not all requested build entries could be removed' in text


def test_already_gone_helpers_are_past_tense_notes():
    err = storage.StorageError( "not found (possibly already deleted)" )
    assert storage_actions._is_already_gone_error( err )
    reason = storage_actions._already_gone_note_reason( '/tmp/project/_build/lib', project_dir='/tmp/project' )
    assert reason.startswith( 'was already gone: [' )
    assert '_build/' in reason or 'lib' in reason


def test_outcome_triple_marks_mixed_as_check_dash_ballot():
    assert storage.outcome_triple( 'full', 'failed' ) in ( '✗✗✗', 'xxx' )
    mixed = storage.outcome_triple( 'full', 'mixed' )
    assert mixed[0] in ( '✓', '*' )
    assert mixed[1] == '-'
    assert mixed[2] in ( '✗', 'x' )


def test_outcome_binary_is_single_slot():
    assert storage.outcome_binary( 'none' ) == '-'
    assert storage.outcome_binary( 'removed' ) in ( '✓', '*' )
    assert storage.outcome_binary( 'failed' ) in ( '✗', 'x' )


def test_with_heavy_marks_upgrades_light_check_and_ballot():
    light = storage.selected_mark() * 3
    heavy = storage.with_heavy_marks( light )
    if light.startswith( '*' ):
        assert heavy == light
    else:
        assert heavy == storage.HEAVY_SELECTED_MARK * 3
    mixed = storage.selected_mark() + '-' + storage.failed_mark()
    upgraded = storage.with_heavy_marks( mixed )
    if mixed[0] == '*':
        assert upgraded == mixed
    else:
        assert upgraded == storage.HEAVY_SELECTED_MARK + '-' + storage.HEAVY_FAILED_MARK


def test_emphasised_name_row_mark_uses_heavy_check():
    mark = storage.selection_triple( 'full' )
    painted = storage_actions._paint_sconscript_mark(
        mark, is_sconscript_name=True, dim=False, accent='info'
    )
    if mark.startswith( '*' ):
        assert storage.selected_mark() in painted or '*' in painted
    else:
        assert storage.HEAVY_SELECTED_MARK in painted
        assert storage.SELECTED_MARK not in painted


def test_short_path_prefers_project_relative( tmp_path ):
    project = tmp_path
    nested = project / '_build' / 'lib' / 'gcc15'
    nested.mkdir( parents=True )
    assert storage.short_path( str( nested ), project_dir=str( project ) ) == os.path.join(
        '_build', 'lib', 'gcc15'
    )


def test_remove_builds_refuses_a_symlink( tmp_path ):
    env, build = env_for( tmp_path, remove_builds=True )
    real = tmp_path / 'elsewhere' / 'gcc15' / 'dbg' / 'x86_64' / 'cxx2c'
    real.mkdir( parents=True )
    link = build / 'gcc15' / 'dbg' / 'x86_64' / 'cxx2c'
    link.parent.mkdir( parents=True )
    link.symlink_to( real )
    construct = FakeConstruct( [ ( 'gcc15', 'dbg', 'x86_64', 'cxx2c' ) ] )

    out = io.StringIO()
    with pytest.raises( storage.StorageError, match='symlink' ):
        storage_actions.remove_builds( construct, env, out=out )


def test_remove_all_builds_removes_the_build_root( tmp_path ):
    env, build = env_for( tmp_path, remove_all_builds=True )
    plant_variant( build, 'gcc15', 'dbg', 'x86_64', 'cxx2c' )

    out = io.StringIO()
    status = storage_actions.remove_all_builds( env, out=out )
    text = out.getvalue()

    assert status == 0
    assert not build.exists()
    assert 'Removing' in text
    assert 'BUILD FOLDER' in text
    assert 'BY SCONSCRIPT' in text
    assert 'REMOVED' in text
    assert 'Removed build root' in text
    assert 'freeing up' in text
    assert '--list-builds' in text


def test_remove_all_builds_reports_failures_with_error_tree( tmp_path, monkeypatch ):
    env, build = env_for( tmp_path, remove_all_builds=True )
    blocked = plant_variant( build, 'lib', 'gcc15', 'dbg', 'x86_64', 'cxx2c' )
    plant_variant( build, 'app', 'gcc15', 'dbg', 'x86_64', 'cxx2c' )

    def boom( target, dry_run=False ):
        raise OSError( 13, "Permission denied", str( blocked / 'working' ) )

    monkeypatch.setattr( storage, 'remove_path', boom )

    out = io.StringIO()
    status = storage_actions.remove_all_builds( env, out=out )
    text = out.getvalue()

    assert status == 1
    assert build.exists()
    assert 'BUILD FOLDER' in text
    assert 'REMOVED' in text
    assert 'The build root could not be removed' in text
    assert '1 error' in text
    assert 'Permission denied' in text
    assert 'lib/gcc15/dbg/x86_64/cxx2c' in text or 'working' in text
    assert 'Build root was not removed.' in text
    assert re.search( r'[✗✘x]', text )


def test_remove_all_builds_refuses_the_sconstruct_directory( tmp_path ):
    env, build = env_for( tmp_path, remove_all_builds=True )
    env['abs_build_root'] = str( tmp_path )
    out = io.StringIO()
    with pytest.raises( storage.StorageError, match='sconstruct' ):
        storage_actions.remove_all_builds( env, out=out )


def test_remove_builds_reports_nothing_to_remove( tmp_path ):
    env, build = env_for( tmp_path, remove_builds=True )
    construct = FakeConstruct( [ ( 'gcc15', 'dbg', 'x86_64', 'cxx2c' ) ] )
    out = io.StringIO()
    status = storage_actions.remove_builds( construct, env, out=out )
    assert status == 0
    assert 'nothing to remove' in out.getvalue()
