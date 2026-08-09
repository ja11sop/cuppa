import os

import pytest

from cuppa.utility import storage


pytestmark = pytest.mark.unit


def test_human_size_uses_binary_units():
    assert storage.human_size( 0 ) == '0B'
    assert storage.human_size( 512 ) == '512B'
    assert storage.human_size( 1024 ) == '1K'
    assert storage.human_size( int( 1.5 * 1024 * 1024 ) ) == '1.5M'


def test_relative_age_uses_readable_buckets():
    now = 1_700_000_000
    assert storage.relative_age( None ) == '-'
    assert storage.relative_age( now - 3600, now=now ) == 'today'
    assert storage.relative_age( now - 86400, now=now ) == 'yesterday'
    assert storage.relative_age( now - 3 * 86400, now=now ) == '3 days ago'
    assert storage.relative_age( now - 20 * 86400, now=now ) == '2 weeks ago'
    assert storage.relative_age( now - 90 * 86400, now=now ) == '3 months ago'
    assert storage.relative_age( now - 800 * 86400, now=now ) == '2 years ago'


def test_directory_size_sums_files_without_following_symlinks( tmp_path ):
    tree = tmp_path / 'tree'
    tree.mkdir()
    ( tree / 'a.txt' ).write_bytes( b'12345' )
    nested = tree / 'nested'
    nested.mkdir()
    ( nested / 'b.txt' ).write_bytes( b'abcdef' )

    outside = tmp_path / 'outside'
    outside.mkdir()
    ( outside / 'c.txt' ).write_bytes( b'xxxxx' )
    ( tree / 'link' ).symlink_to( outside )

    assert storage.directory_size( str( tree ) ) == 5 + 6
    stats = storage.directory_stats( str( tree ) )
    assert stats.bytes == 5 + 6
    assert stats.mtime is not None


def test_display_path_uses_tilde_for_home( tmp_path, monkeypatch ):
    home = tmp_path / 'home'
    home.mkdir()
    monkeypatch.setenv( 'HOME', str( home ) )
    nested = home / 'project' / '_build'
    nested.mkdir( parents=True )
    assert storage.display_path( str( nested ) ) == '~/project/_build'


def test_selected_mark_falls_back_to_ascii():
    assert storage.selected_mark( encoding='utf-8' ) == '✓'
    assert storage.selected_mark( encoding='ascii' ) == '*'
    assert storage.selection_triple( 'full', encoding='utf-8' ) == '✓✓✓'
    assert storage.selection_triple( 'partial', encoding='utf-8' ) == '-✓-'
    assert storage.selection_triple( 'none', encoding='ascii' ) == '---'
    assert storage.selection_triple( 'partial', encoding='ascii' ) == '-*-'


def test_is_contained_requires_a_path_inside_the_root( tmp_path ):
    root = tmp_path / 'root'
    inside = root / 'child'
    outside = tmp_path / 'elsewhere'
    inside.mkdir( parents=True )
    outside.mkdir()

    assert storage.is_contained( str( inside ), str( root ) ) is True
    assert storage.is_contained( str( root ), str( root ) ) is True
    assert storage.is_contained( str( outside ), str( root ) ) is False


def test_is_suspicious_root_rejects_home_and_filesystem_root( tmp_path, monkeypatch ):
    home = tmp_path / 'home'
    home.mkdir()
    monkeypatch.setenv( 'HOME', str( home ) )
    monkeypatch.setenv( 'USERPROFILE', str( home ) )

    assert storage.is_suspicious_root( str( home ) ) is True
    assert storage.is_suspicious_root( os.sep ) is True
    assert storage.is_suspicious_root( str( tmp_path / 'build' ) ) is False


def test_remove_path_and_prune_empty_parents( tmp_path ):
    root = tmp_path / 'build'
    leaf = root / 'a' / 'b' / 'c'
    leaf.mkdir( parents=True )
    ( leaf / 'file' ).write_text( 'x' )

    assert storage.remove_path( str( leaf ) ) is True
    storage.prune_empty_parents( str( leaf ), str( root ) )
    assert root.exists()
    assert not ( root / 'a' ).exists()


def test_remove_path_dry_run_leaves_the_tree( tmp_path ):
    path = tmp_path / 'keep'
    path.mkdir()
    ( path / 'file' ).write_text( 'x' )
    assert storage.remove_path( str( path ), dry_run=True ) is True
    assert path.exists()


def test_render_table_pads_columns():
    columns = ( ( 'size', 'SIZE' ), ( 'name', 'NAME' ) )
    rows = [ { 'size': '1K', 'name': 'short' }, { 'size': '10M', 'name': 'longer_name' } ]
    lines = storage.render_table( columns, rows )
    assert lines[0].startswith( 'SIZE' )
    assert 'longer_name' in lines[2]
    # Header NAME and values share a common left edge after SIZE padding.
    name_col = lines[0].index( 'NAME' )
    assert lines[1][name_col:].startswith( 'short' )
    assert lines[2][name_col:].startswith( 'longer_name' )


def test_render_json_payload_uses_allman_four_space_indent():
    import json

    text = storage.render_json_payload( {
        'wipe_applies_to': 'registered',
        'sections': [ { 'name': 'discovered', 'families': [] } ],
        'empty': [],
    } )
    assert '"sections":\n    [' in text
    assert '"families": []' in text
    assert '    "name": "discovered"' in text
    # Round-trip: formatting is presentation only.
    assert json.loads( text )['wipe_applies_to'] == 'registered'
