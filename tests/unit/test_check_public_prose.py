#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

"""Unit tests for scripts.check_public_prose.

Fixtures use **fictional** denylist tokens only — never real private consumer
names from ``INTERNAL_PROJECTS.local.md``. Personal home examples are built from
parts so this tracked file does not itself contain a ``/home/<user>/`` literal.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from scripts import check_public_prose as prose


pytestmark = pytest.mark.unit

# Fictional soak identities — unrelated to any real private consumer names.
_TIP = 'river_orchard'
_PKG = 'kelp_bundle'
_LOCATION = 'quartz_ingress'
_ORG_TIP = 'aurora_labs/river_orchard'
_STYLE = 'Cedar style'
_HOST_PHRASE = 'Harbor private host'

# Split so the tracked source never contains a personal /home/<user>/ literal.
_HOME_ALICE = '/home/' + 'alice' + '/'
_HOME_USER = '/home/' + 'user' + '/'


def test_tokens_from_local_map_reads_real_columns( tmp_path: Path ):
    map_path = tmp_path / 'INTERNAL_PROJECTS.local.md'
    map_path.write_text(
            '# map\n'
            '\n'
            '| Label used publicly | Real project | Shape |\n'
            '|---------------------|--------------|-------|\n'
            '| **project B** | `' + _ORG_TIP + '` '
            '(`~/coding/harbor_git/' + _ORG_TIP + '`) | long |\n'
            '| **project X** | tip `' + _LOCATION + '` | locs |\n'
            '\n'
            '| Used publicly | Real name | Notes |\n'
            '|---------------|-----------|-------|\n'
            '| `widget` | `' + _PKG + '` | pkg |\n'
            '| `widget` | `google_cloud_cpp` | public OSS — allow |\n'
            '\n'
            '| Used publicly | Real value |\n'
            '|---------------|------------|\n'
            '| `gitlab.example` | ' + _HOST_PHRASE + ' |\n'
            '| `/home/user/...` | `' + _HOME_ALICE + '...` |\n'
            '\n'
            '| Used in tracked cuppa files | Private / informal name | Source |\n'
            '|-----------------------------|-------------------------|--------|\n'
            '| **Readable style** | ' + _STYLE + ' | project C |\n',
            encoding='utf-8',
    )
    tokens = prose.tokens_from_local_map( map_path )
    assert _TIP in tokens
    assert _ORG_TIP in tokens
    assert _LOCATION in tokens
    assert _PKG in tokens
    assert _STYLE in tokens
    assert _HOST_PHRASE in tokens
    assert 'google_cloud_cpp' not in tokens
    assert 'widget' not in tokens
    assert 'alice' not in tokens  # covered by /home/ rule, not denylist token


def test_find_hits_flags_private_token_and_personal_home():
    tokens = [ _TIP, _PKG ]
    assert prose.find_hits( 'soak on ' + _TIP, tokens ) == [ _TIP ]
    assert prose.find_hits( 'path ' + _HOME_ALICE + 'coding/x', tokens ) == [
            _HOME_ALICE
    ]
    assert prose.find_hits( 'path ' + _HOME_USER + 'coding/x', tokens ) == []
    assert prose.find_hits( 'uses widget fixture', tokens ) == []


def test_main_file_flag_reports_hit( tmp_path: Path, monkeypatch, capsys ):
    map_path = tmp_path / 'map.md'
    map_path.write_text(
            '| Used publicly | Real name |\n'
            '|---------------|----------|\n'
            '| `widget` | `' + _TIP + '` |\n',
            encoding='utf-8',
    )
    prose_file = tmp_path / 'pr.md'
    prose_file.write_text(
            'Verified on ' + _TIP + ' with ' + _HOME_USER + 'cuppa.\n',
            encoding='utf-8',
    )
    monkeypatch.setattr( prose, 'LOCAL_MAP', map_path )
    monkeypatch.setattr( prose, 'changed_paths', lambda **kwargs: [] )
    code = prose.main( [ '--file', str( prose_file ) ] )
    assert code == 1
    err = capsys.readouterr().err
    assert _TIP in err


def test_main_file_flag_clean_with_placeholders( tmp_path: Path, monkeypatch, capsys ):
    map_path = tmp_path / 'map.md'
    map_path.write_text(
            '| Used publicly | Real name |\n'
            '|---------------|----------|\n'
            '| `widget` | `' + _TIP + '` |\n',
            encoding='utf-8',
    )
    prose_file = tmp_path / 'pr.md'
    prose_file.write_text(
            'Verified on project B with ' + _HOME_USER + 'cuppa and widget.\n',
            encoding='utf-8',
    )
    monkeypatch.setattr( prose, 'LOCAL_MAP', map_path )
    monkeypatch.setattr( prose, 'changed_paths', lambda **kwargs: [] )
    code = prose.main( [ '--file', str( prose_file ) ] )
    assert code == 0
    assert 'check_public_prose: ok' in capsys.readouterr().out


def test_main_absent_map_still_flags_personal_home( tmp_path: Path, monkeypatch, capsys ):
    missing = tmp_path / 'missing.local.md'
    prose_file = tmp_path / 'note.md'
    prose_file.write_text( 'cloned under ' + _HOME_ALICE + 'src\n', encoding='utf-8' )
    monkeypatch.setattr( prose, 'LOCAL_MAP', missing )
    monkeypatch.setattr( prose, 'changed_paths', lambda **kwargs: [] )
    code = prose.main( [ '--file', str( prose_file ) ] )
    assert code == 1
    assert _HOME_ALICE in capsys.readouterr().err
