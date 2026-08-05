"""Unit tests for the dependency inventory."""

import json
import os

import pytest

from cuppa.core import dependency_inventory
from cuppa.utility import storage


pytestmark = pytest.mark.unit


def test_entry_key_is_stable( tmp_path ):
    path = tmp_path / 'dependencies' / 'widget@master'
    path.mkdir( parents=True )
    key1 = dependency_inventory.entry_key_for_path( str( path ) )
    key2 = dependency_inventory.entry_key_for_path( str( path ) )
    assert key1 == key2
    assert key1.endswith( key1[-16:] )


def test_touch_and_load_entry( tmp_path ):
    dependencies_root = tmp_path / 'dependencies'
    tree = dependencies_root / 'widget@master'
    tree.mkdir( parents=True )
    ( tree / 'readme' ).write_text( 'hello', encoding='utf-8' )

    entry = dependency_inventory.touch_entry(
            str( dependencies_root ),
            str( tree ),
            storage_type='location',
            dependency='widget',
            qualifier='@master',
            tool_variant=None,
            sconstruct_dir=str( tmp_path / 'project' ),
            exact_sizes=True,
    )
    assert entry['dependency'] == 'widget'
    assert entry['qualifier'] == '@master'
    assert entry['type'] == 'location'
    assert entry['kind'] == 'location'
    assert entry['size']['method'] == 'exact'
    assert entry['size']['bytes'] >= 5
    assert str( tmp_path / 'project' ) in entry['used_by'] or storage.real_path(
            str( tmp_path / 'project' )
    ) in entry['used_by']

    loaded = dependency_inventory.load_all_entries( str( dependencies_root ) )
    assert len( loaded ) == 1
    assert loaded[0]['dependency'] == 'widget'

    on_disk = dependencies_root / dependency_inventory.INVENTORY_DIR_NAME
    assert on_disk.is_dir()
    files = list( on_disk.glob( '*.json' ) )
    assert len( files ) == 1
    payload = json.loads( files[0].read_text( encoding='utf-8' ) )
    assert payload['type'] == 'location'
    assert payload['kind'] == 'location'


def test_write_entry_refuses_path_outside_root( tmp_path ):
    dependencies_root = tmp_path / 'dependencies'
    dependencies_root.mkdir()
    outside = tmp_path / 'elsewhere'
    outside.mkdir()
    with pytest.raises( storage.StorageError ):
        dependency_inventory.write_entry( str( dependencies_root ), {
            'path': str( outside ),
            'dependency': 'x',
            'kind': 'location',
        } )


def test_corrupt_entry_is_skipped( tmp_path ):
    dependencies_root = tmp_path / 'dependencies'
    inv = dependencies_root / dependency_inventory.INVENTORY_DIR_NAME
    inv.mkdir( parents=True )
    bad = inv / 'broken.json'
    bad.write_text( '{not json', encoding='utf-8' )
    assert dependency_inventory.load_all_entries( str( dependencies_root ) ) == []


def test_format_size_cell_marks_sampled():
    assert dependency_inventory.format_size_cell( {
        'bytes': 1024, 'method': 'sampled'
    } ).startswith( '~' )
    assert not dependency_inventory.format_size_cell( {
        'bytes': 1024, 'method': 'exact'
    } ).startswith( '~' )


def test_size_should_upgrade_to_exact():
    assert dependency_inventory.size_should_upgrade_to_exact( {} )
    assert dependency_inventory.size_should_upgrade_to_exact( { 'size': None } )
    assert dependency_inventory.size_should_upgrade_to_exact( {
        'size': { 'bytes': 10, 'method': 'sampled' },
    } )
    assert not dependency_inventory.size_should_upgrade_to_exact( {
        'size': { 'bytes': 10, 'method': 'exact' },
    } )


def test_touch_entry_without_last_used_leaves_used_by_empty( tmp_path ):
    dependencies_root = tmp_path / 'dependencies'
    tree = dependencies_root / 'widget@master'
    tree.mkdir( parents=True )
    ( tree / 'readme' ).write_text( 'hello', encoding='utf-8' )

    entry = dependency_inventory.touch_entry(
            str( dependencies_root ),
            str( tree ),
            storage_type='location',
            dependency='widget',
            qualifier='@master',
            sconstruct_dir=str( tmp_path / 'project' ),
            refresh_size=False,
            update_last_used=False,
    )
    assert entry.get( 'used_by' ) == {}
    assert entry.get( 'last_used_source' ) != 'resolve'
    assert 'last_used' not in entry or entry.get( 'last_used_source' ) != 'resolve'


def test_touch_entry_refresh_size_false_skips_measure( tmp_path ):
    dependencies_root = tmp_path / 'dependencies'
    tree = dependencies_root / 'widget@master'
    tree.mkdir( parents=True )
    ( tree / 'readme' ).write_text( 'hello', encoding='utf-8' )

    entry = dependency_inventory.touch_entry(
            str( dependencies_root ),
            str( tree ),
            storage_type='location',
            dependency='widget',
            qualifier='@master',
            refresh_size=False,
            update_last_used=False,
    )
    assert 'size' not in entry

    loaded = dependency_inventory.load_entry(
            str( dependencies_root ),
            dependency_inventory.entry_key_for_path( str( tree ) ),
    )
    assert loaded is not None
    assert 'size' not in loaded


def test_delete_entry_for_path( tmp_path ):
    dependencies_root = tmp_path / 'dependencies'
    tree = dependencies_root / 'gadget'
    tree.mkdir( parents=True )
    dependency_inventory.touch_entry(
            str( dependencies_root ),
            str( tree ),
            storage_type='gitlab',
            dependency='gadget',
            exact_sizes=True,
            refresh_size=True,
    )
    assert dependency_inventory.load_all_entries( str( dependencies_root ) )
    dependency_inventory.delete_entry_for_path( str( dependencies_root ), str( tree ) )
    assert dependency_inventory.load_all_entries( str( dependencies_root ) ) == []
