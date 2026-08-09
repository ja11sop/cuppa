#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

import io
import json
import os

import pytest

from cuppa.core.toolchain_actions import (
        SECTION_DISCOVERED,
        SECTION_REGISTERED,
        collect_toolchain_rows,
        list_toolchains,
        row_from_toolchain,
)


pytestmark = pytest.mark.unit


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


def test_row_from_toolchain_classifies_discovered_vs_registered( tmp_path ):
    discovered = FakeToolchain(
            'gcc15', 'gcc', '15.2.0', '/usr/bin/g++',
    )
    registered = FakeToolchain(
            'gcc15_local_abcd1234', 'gcc', '15.2.0',
            str( tmp_path / 'bin' / 'g++' ),
            storage_path=str( tmp_path / 'toolchains' / 'gcc' / 'local_abcd1234' ),
            cxx_path=str( tmp_path / 'bin' ),
    )
    d_row = row_from_toolchain( 'gcc15', discovered )
    r_row = row_from_toolchain( 'gcc15_local_abcd1234', registered )
    assert d_row['section'] == SECTION_DISCOVERED
    assert d_row['storage_path'] is None
    assert r_row['section'] == SECTION_REGISTERED
    assert r_row['storage_path'] == str( tmp_path / 'toolchains' / 'gcc' / 'local_abcd1234' )


def test_collect_keeps_both_path_and_managed_names( tmp_path ):
    env = {
        'toolchains': {
            'gcc15_local_abcd': FakeToolchain(
                    'gcc15_local_abcd', 'gcc', '15.0.0',
                    str( tmp_path / 'g++' ),
                    storage_path=str( tmp_path / 'reg' ),
            ),
            'gcc15': FakeToolchain( 'gcc15', 'gcc', '15.0.0', '/usr/bin/g++' ),
            'clang18': FakeToolchain( 'clang18', 'clang', '18.1.0', '/usr/bin/clang++' ),
        }
    }
    sections = collect_toolchain_rows( env )
    assert [ r['name'] for r in sections[SECTION_DISCOVERED] ] == [ 'clang18', 'gcc15' ]
    assert [ r['name'] for r in sections[SECTION_REGISTERED] ] == [ 'gcc15_local_abcd' ]


def test_list_toolchains_json_payload( tmp_path ):
    env = {
        'list_format': 'json',
        'toolchains': {
            'gcc15': FakeToolchain( 'gcc15', 'gcc', '15.0.0', '/usr/bin/g++' ),
            'gcc15_snap': FakeToolchain(
                    'gcc15_snap', 'gcc', '15.0.0',
                    str( tmp_path / 'g++' ),
                    storage_path=str( tmp_path / 'owned' ),
            ),
        },
    }
    out = io.StringIO()
    assert list_toolchains( env, out=out ) == 0
    payload = json.loads( out.getvalue() )
    assert payload['wipe_applies_to'] == SECTION_REGISTERED
    assert payload['sections'][0]['name'] == SECTION_DISCOVERED
    assert payload['sections'][1]['name'] == SECTION_REGISTERED
    assert payload['sections'][0]['toolchains'][0]['name'] == 'gcc15'
    assert payload['sections'][1]['toolchains'][0]['storage_path'] == str( tmp_path / 'owned' )


def test_list_toolchains_text_mentions_wipe_only_for_registered():
    env = {
        'list_format': 'text',
        'toolchains': {
            'gcc15': FakeToolchain( 'gcc15', 'gcc', '15.0.0', '/usr/bin/g++' ),
        },
    }
    out = io.StringIO()
    assert list_toolchains( env, out=out ) == 0
    text = out.getvalue()
    assert SECTION_DISCOVERED in text
    assert SECTION_REGISTERED in text
    assert '(none)' in text
    assert 'Force-wipe' in text
    assert 'Registered' in text
