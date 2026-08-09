#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

import io
import json
import re

import pytest

from cuppa.core.dependency_tree import _flat_variant_children
from cuppa.core.toolchain_actions import (
        SECTION_DISCOVERED,
        SECTION_REGISTERED,
        attach_toolchain_session_names,
        build_toolchain_sections,
        build_toolchain_tree,
        collect_toolchain_rows,
        list_toolchains,
        row_from_toolchain,
)


pytestmark = pytest.mark.unit


_ANSI_RE = re.compile( r'\x1b\[[0-9;]*m' )


def _strip_ansi( text ):
    return _ANSI_RE.sub( '', text )


class FakePlatform( object ):
    def default_toolchain( self ):
        return 'gcc'


class FakeToolchain( object ):
    def __init__(
            self,
            name,
            family,
            version,
            binary,
            storage_path=None,
            cxx_path=None,
    ):
        self._name = name
        self._family = family
        self._version = version
        self.values = { 'CXX': binary }
        self._cxx_path = cxx_path
        if storage_path:
            self._toolchain_dep_root = storage_path

    def name( self ):
        return self._name

    def family( self ):
        return self._family

    def version( self ):
        return self._version

    def binary( self ):
        return self.values['CXX']


def test_size_cells_can_be_muted():
    from cuppa.colourise import colouriser
    from cuppa.core.toolchain_actions import _size_cell
    was = colouriser.use_colour
    colouriser.enable()
    try:
        muted = _size_cell( 1024, muted=True )
        plain = _size_cell( 1024, muted=False )
        assert muted != plain
        assert _strip_ansi( muted ).strip() == _strip_ansi( plain ).strip()
    finally:
        colouriser.use_colour = was


def test_row_from_toolchain_classifies_discovered_vs_registered( tmp_path ):
    discovered = FakeToolchain( 'gcc15', 'gcc', '15.2.0', '/usr/bin/g++' )
    registered = FakeToolchain(
            'gcc15_local_abcd1234', 'gcc', '15.2.0',
            str( tmp_path / 'bin' / 'g++' ),
            storage_path=str( tmp_path / 'toolchains' / 'gcc' / 'local_abcd1234' ),
            cxx_path=str( tmp_path / 'bin' ),
    )
    ( tmp_path / 'toolchains' / 'gcc' / 'local_abcd1234' ).mkdir( parents=True )
    d_row = row_from_toolchain( 'gcc15', discovered )
    r_row = row_from_toolchain( 'gcc15_local_abcd1234', registered )
    assert d_row['section'] == SECTION_DISCOVERED
    assert d_row['storage_path'] is None
    assert r_row['section'] == SECTION_REGISTERED
    assert r_row['storage_path'] == str( tmp_path / 'toolchains' / 'gcc' / 'local_abcd1234' )
    assert r_row['size_bytes'] is not None or r_row['last_used_epoch'] is not None


def test_family_default_name_is_bare_family_token():
    rows = [
        {
            'name': 'clang', 'family': 'clang', 'version': '21.1',
            'driver_path': '/usr/bin/clang++-21', 'is_default': True,
            'size_bytes': None, 'last_used_epoch': None,
        },
        {
            'name': 'clang21', 'family': 'clang', 'version': '21.1',
            'driver_path': '/usr/bin/clang++-21', 'is_default': False,
            'size_bytes': None, 'last_used_epoch': None,
        },
        {
            'name': 'gcc', 'family': 'gcc', 'version': '15.3',
            'driver_path': '/usr/bin/g++-15', 'is_default': True,
            'size_bytes': None, 'last_used_epoch': None,
        },
    ]
    tree = build_toolchain_tree( rows, platform_default_name='gcc' )
    families = { node['family']: node for node in tree['families'] }
    assert families['gcc']['is_platform_default'] is True
    assert families['clang']['is_platform_default'] is False
    clang_21 = families['clang']['versions'][0]
    assert clang_21['owns_default'] is True
    assert clang_21['drivers'][0]['names'][-1]['name'] == 'clang'


def test_platform_default_family_requires_default_name_child():
    # Registered-only gcc snapshot: same family as platform default, but no bare ``gcc``.
    rows = [
        {
            'name': 'gcc17_gcc_snapshot_x', 'family': 'gcc', 'version': '17.0',
            'driver_path': '/tmp/g++', 'is_default': False,
            'size_bytes': 100, 'last_used_epoch': None,
        },
    ]
    tree = build_toolchain_tree( rows, platform_default_name='gcc' )
    assert tree['families'][0]['is_platform_default'] is False


def test_tree_groups_shared_driver_under_one_node():
    rows = [
        {
            'name': 'gcc153', 'family': 'gcc', 'version': '15.3',
            'driver_path': '/usr/bin/g++-15', 'is_default': False,
            'size_bytes': None, 'last_used_epoch': None,
        },
        {
            'name': 'gcc15', 'family': 'gcc', 'version': '15.3',
            'driver_path': '/usr/bin/g++-15', 'is_default': False,
            'size_bytes': None, 'last_used_epoch': None,
        },
        {
            'name': 'gcc', 'family': 'gcc', 'version': '15.3',
            'driver_path': '/usr/bin/g++-15', 'is_default': True,
            'size_bytes': None, 'last_used_epoch': None,
        },
        {
            'name': 'clang21', 'family': 'clang', 'version': '21.1',
            'driver_path': '/usr/bin/clang++-21', 'is_default': False,
            'size_bytes': None, 'last_used_epoch': None,
        },
    ]
    tree = build_toolchain_tree( rows, platform_default_name='gcc' )
    families = { node['family']: node for node in tree['families'] }
    assert set( families ) == { 'clang', 'gcc' }
    gcc_version = families['gcc']['versions'][0]
    assert gcc_version['version'] == '15.3'
    assert gcc_version['owns_default'] is True
    assert len( gcc_version['drivers'] ) == 1
    names = [ entry['name'] for entry in gcc_version['drivers'][0]['names'] ]
    assert names == [ 'gcc15', 'gcc153', 'gcc' ]
    assert gcc_version['drivers'][0]['names'][-1]['is_default'] is True


def test_collect_marks_bare_family_names_as_default():
    env = {
        'platform': FakePlatform(),
        'toolchains': {
            'gcc': FakeToolchain( 'gcc', 'gcc', '15.3', '/usr/bin/g++-15' ),
            'gcc15': FakeToolchain( 'gcc15', 'gcc', '15.3', '/usr/bin/g++-15' ),
            'clang': FakeToolchain( 'clang', 'clang', '21.1', '/usr/bin/clang++-21' ),
            'clang21': FakeToolchain( 'clang21', 'clang', '21.1', '/usr/bin/clang++-21' ),
        },
    }
    rows = collect_toolchain_rows( env )
    by_name = { row['name']: row for row in rows[SECTION_DISCOVERED] }
    assert by_name['gcc']['is_default'] is True
    assert by_name['gcc15']['is_default'] is False
    assert by_name['clang']['is_default'] is True
    assert by_name['clang21']['is_default'] is False


def test_list_toolchains_json_is_nested( tmp_path ):
    owned = tmp_path / 'owned'
    owned.mkdir()
    env = {
        'list_format': 'json',
        'platform': FakePlatform(),
        'toolchains': {
            'gcc': FakeToolchain( 'gcc', 'gcc', '15.3', '/usr/bin/g++-15' ),
            'gcc15': FakeToolchain( 'gcc15', 'gcc', '15.3', '/usr/bin/g++-15' ),
            'gcc15_snap': FakeToolchain(
                    'gcc15_snap', 'gcc', '15.0.0',
                    str( tmp_path / 'g++' ),
                    storage_path=str( owned ),
            ),
        },
    }
    out = io.StringIO()
    assert list_toolchains( env, out=out ) == 0
    payload = json.loads( out.getvalue() )
    assert payload['wipe_applies_to'] == SECTION_REGISTERED
    discovered = payload['sections'][0]
    registered = payload['sections'][1]
    assert discovered['name'] == SECTION_DISCOVERED
    assert registered['name'] == SECTION_REGISTERED
    gcc = next( f for f in discovered['families'] if f['family'] == 'gcc' )
    assert gcc['is_platform_default'] is True
    assert gcc['versions'][0]['owns_default'] is True
    assert registered['families'][0]['versions'][0]['drivers'][0]['names'][0]['name'] == \
        'gcc15_snap'
    assert registered['families'][0]['versions'][0]['drivers'][0]['names'][0]['size_bytes'] \
        is not None


def test_list_toolchains_text_tree_shape():
    env = {
        'list_format': 'text',
        'platform': FakePlatform(),
        'toolchains': {
            'gcc': FakeToolchain( 'gcc', 'gcc', '15.3', '/usr/bin/g++-15' ),
            'gcc15': FakeToolchain( 'gcc15', 'gcc', '15.3', '/usr/bin/g++-15' ),
            'clang': FakeToolchain( 'clang', 'clang', '21.1', '/usr/bin/clang++-21' ),
        },
    }
    out = io.StringIO()
    assert list_toolchains( env, out=out ) == 0
    text = _strip_ansi( out.getvalue() )
    assert 'discovered' in text
    assert 'registered' in text
    assert 'gcc (default)' in text  # platform default family and/or name
    assert 'clang (default)' in text  # family-default name
    assert 'family-version-driver-name(s)' in text
    assert 'TOOLCHAIN' in text
    assert 'toolchains,' in text
    assert 'Force-wipe removal of toolchains' in text
    assert '-n --force-wipe-dependencies=[toolchain]*' in text
    # No blank line between section body and the following rule
    assert '\n\n  ---' not in text.replace( '\r', '' )


def test_attach_toolchain_session_names( tmp_path ):
    extract = tmp_path / 'toolchains' / 'clang' / 'profiles_2026_08_07_27'
    extract.mkdir( parents=True )
    env = {
        'toolchains': {
            'clang24_profiles_2026_08_07_27': FakeToolchain(
                    'clang24_profiles_2026_08_07_27', 'clang', '24.0',
                    str( extract / 'bin' / 'clang++' ),
                    storage_path=str( extract ),
            ),
        },
    }
    rows = [
        {
            'type': 'toolchain',
            'path': str( extract ),
            'qualifier': 'profiles_2026_08_07_27',
            'dependency': 'clang',
        },
    ]
    attach_toolchain_session_names( rows, env )
    assert rows[0]['toolchain_session_name'] == 'clang24_profiles_2026_08_07_27'


def test_flat_variant_children_prefers_session_name():
    leaves = [
        {
            'type': 'toolchain',
            'qualifier': 'profiles_2026_08_07_27',
            'toolchain_session_name': 'clang24_profiles_2026_08_07_27',
            'path': '/tmp/toolchains/clang/profiles_2026_08_07_27',
            'state': 'referenced',
            'size_bytes': 10,
        },
    ]
    children = _flat_variant_children( leaves, label_key='qualifier' )
    assert children[0]['label'] == 'clang24_profiles_2026_08_07_27'


def test_build_toolchain_sections_orders_discovered_then_registered( tmp_path ):
    reg = tmp_path / 'reg'
    reg.mkdir()
    env = {
        'platform': FakePlatform(),
        'toolchains': {
            'gcc': FakeToolchain( 'gcc', 'gcc', '15.3', '/usr/bin/g++-15' ),
            'gcc_snap': FakeToolchain(
                    'gcc_snap', 'gcc', '17.0',
                    str( tmp_path / 'g++' ),
                    storage_path=str( reg ),
            ),
        },
    }
    sections = build_toolchain_sections( env )
    assert [ section['name'] for section in sections ] == [
            SECTION_DISCOVERED, SECTION_REGISTERED,
    ]
    assert sections[0]['families'][0]['family'] == 'gcc'
    assert sections[1]['families'][0]['versions'][0]['version'] == '17.0'


def test_registered_stats_prefer_inventory( tmp_path, monkeypatch ):
    extract = tmp_path / 'deps' / 'toolchains' / 'clang' / 'profiles_x'
    extract.mkdir( parents=True )
    ( extract / 'marker' ).write_text( 'x', encoding='utf-8' )

    env = {
        'dependencies_root': str( tmp_path / 'deps' ),
        'platform': FakePlatform(),
        'toolchains': {
            'clang24_profiles_x': FakeToolchain(
                    'clang24_profiles_x', 'clang', '24.0',
                    str( extract / 'bin' / 'clang++' ),
                    storage_path=str( extract ),
            ),
        },
    }

    fake_entry = {
        'path': str( extract ),
        'size': { 'bytes': 1234567, 'method': 'exact' },
        'last_used': '2026-08-01T12:00:00Z',
        'last_used_source': 'resolve',
    }

    monkeypatch.setattr(
            'cuppa.core.dependency_inventory.load_all_entries',
            lambda _root: [ fake_entry ],
    )
    rows = collect_toolchain_rows( env )
    row = rows[SECTION_REGISTERED][0]
    assert row['size_bytes'] == 1234567
    assert row['last_used_epoch'] is not None
