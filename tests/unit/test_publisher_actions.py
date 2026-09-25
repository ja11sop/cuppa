#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

"""Unit tests for ``--list-publishers`` / ``--remove-publishers``."""

from __future__ import annotations

import io
import json
import os
from pathlib import Path
import pytest

from cuppa.core import publisher_actions
from cuppa.package_managers import package_cascade


pytestmark = pytest.mark.unit


def _env( storage_root, publisher_root=None, **extra ):
    env = {
            'storage_root': str( storage_root ),
            'list_format': 'text',
            'no_exec': False,
    }
    if publisher_root is not None:
        env['publisher-root'] = str( publisher_root )
    env.update( extra )
    return env


def _plant_tree( root: Path, name: str, with_git=True ):
    tree = root / name
    tree.mkdir( parents=True )
    if with_git:
        ( tree / '.git' ).mkdir()
    ( tree / 'sconstruct' ).write_text( '# test\n', encoding='utf-8' )
    ( tree / 'readme' ).write_text( 'payload\n', encoding='utf-8' )
    return tree


def test_collect_lists_git_trees_under_default_publishers_root( tmp_path, monkeypatch ):
    storage = tmp_path / 'cuppa'
    forest = storage / 'publishers'
    _plant_tree( forest, 'capy' )
    _plant_tree( forest, 'corosio' )
    ( forest / 'noise.txt' ).write_text( 'skip\n', encoding='utf-8' )

    monkeypatch.setattr(
            publisher_actions, '_develop_realpaths', lambda _env: set()
    )
    data = publisher_actions.collect_publisher_rows( _env( storage ) )
    assert data['publishers_root'] == str( forest )
    names = [ row['name'] for row in data['rows'] ]
    assert names == [ 'capy', 'corosio' ]
    assert data['tree_count'] == 2


def test_collect_honours_explicit_publisher_root( tmp_path, monkeypatch ):
    storage = tmp_path / 'cuppa'
    custom = tmp_path / 'forest'
    _plant_tree( custom, 'widget' )
    monkeypatch.setattr(
            publisher_actions, '_develop_realpaths', lambda _env: set()
    )
    data = publisher_actions.collect_publisher_rows(
            _env( storage, publisher_root=custom )
    )
    assert data['publishers_root'] == str( custom )
    assert [ row['name'] for row in data['rows'] ] == [ 'widget' ]


def test_list_publishers_json_and_text( tmp_path, monkeypatch ):
    storage = tmp_path / 'cuppa'
    forest = storage / 'publishers'
    _plant_tree( forest, 'capy' )
    monkeypatch.setattr(
            publisher_actions, '_develop_realpaths', lambda _env: set()
    )
    env = _env( storage, list_format='json' )
    out = io.StringIO()
    assert publisher_actions.list_publishers( None, env, out=out ) == 0
    payload = json.loads( out.getvalue() )
    assert payload['tree_count'] == 1
    assert payload['entries'][0]['name'] == 'capy'
    assert payload['entries'][0]['status'] == 'warn'
    assert 'notes' in payload['entries'][0]

    env['list_format'] = 'text'
    out = io.StringIO()
    assert publisher_actions.list_publishers( None, env, out=out ) == 0
    text = out.getvalue()
    assert 'Publishers in' in text
    assert 'STATUS' in text
    assert 'SIZE' in text
    assert 'UPSTREAM' in text
    assert 'capy' in text
    assert '1 publisher tree' in text
    assert 'not a working copy' in text
    assert 'Ahead and behind are relative to your last fetch' in text


def test_remove_publishers_skips_develop_linked( tmp_path, monkeypatch ):
    storage = tmp_path / 'cuppa'
    forest = storage / 'publishers'
    capy = _plant_tree( forest, 'capy' )
    other = _plant_tree( forest, 'corosio' )
    monkeypatch.setattr(
            publisher_actions, '_develop_realpaths',
            lambda _env: { os.path.realpath( str( capy ) ) },
    )
    env = _env( storage, remove_all_publishers=True )
    out = io.StringIO()
    assert publisher_actions.remove_publishers( None, env, out=out ) == 0
    text = out.getvalue()
    assert 'skipping [capy]' in text
    assert capy.is_dir()
    assert not other.exists()


def test_remove_publishers_dry_run_leaves_trees( tmp_path, monkeypatch ):
    storage = tmp_path / 'cuppa'
    forest = storage / 'publishers'
    tree = _plant_tree( forest, 'capy' )
    monkeypatch.setattr(
            publisher_actions, '_develop_realpaths', lambda _env: set()
    )
    env = _env( storage, remove_publishers='capy', no_exec=True )
    out = io.StringIO()
    assert publisher_actions.remove_publishers( None, env, out=out ) == 0
    assert 'Would remove' in out.getvalue()
    assert tree.is_dir()


def test_remove_publishers_unknown_name_errors( tmp_path, monkeypatch ):
    storage = tmp_path / 'cuppa'
    ( storage / 'publishers' ).mkdir( parents=True )
    monkeypatch.setattr(
            publisher_actions, '_develop_realpaths', lambda _env: set()
    )
    env = _env( storage, remove_publishers='missing' )
    out = io.StringIO()
    assert publisher_actions.remove_publishers( None, env, out=out ) == 1
    assert 'no publisher tree named [missing]' in out.getvalue()


def test_publisher_root_option_round_trip( tmp_path ):
    """``publisher_lookup_root`` matches clone root defaults used by collect."""
    storage = tmp_path / 'cuppa'

    class Env( dict ):
        def get( self, key, default=None ):
            return dict.get( self, key, default )

    env = Env( storage_root=str( storage ) )
    assert package_cascade.publisher_lookup_root( env ).endswith(
            os.path.join( 'publishers' )
    )
    custom = tmp_path / 'custom'
    env['publisher-root'] = str( custom )
    assert package_cascade.publisher_lookup_root( env ) == str( custom )
