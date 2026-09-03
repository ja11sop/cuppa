#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

import json

import pytest

from pathlib import Path

from cuppa.cpp.profiles_report import (
    UNCLASSIFIED_RULE_ID,
    classify_rule,
    parse_profiles_diagnostic,
)
from cuppa.cpp.profiles_report.profiles import std_init

pytestmark = pytest.mark.unit

_GOLDEN = (
    Path( __file__ ).resolve().parents[ 1 ]
    / 'fixtures'
    / 'profiles_capture'
    / 'std_init_golden.json'
)

_ALL_RULE_IDS = (
    'uninit_decl',
    'uninit_read',
    'uninit_write',
    'ref_to_uninit',
    'double_destroy',
    'destroy_uninit',
    'ctor_uninit_member',
    'static_runtime_init',
    'uninit_with_initializer',
    'pointer_marker',
    'union_marker',
    'static_marker',
)


@pytest.mark.parametrize( 'rule_id', _ALL_RULE_IDS )
def test_std_init_golden_primary_lines_classify( rule_id ):
    golden = json.loads( _GOLDEN.read_text( encoding='utf-8' ) )
    line = golden[ rule_id ]
    diagnostic = parse_profiles_diagnostic( line )
    assert diagnostic is not None
    assert diagnostic.profile == std_init.PROFILE_NAME
    assert diagnostic.rule_id == rule_id


@pytest.mark.parametrize(
    'fixture_key, rule_id',
    [
        ( 'uninit_decl_union', 'uninit_decl' ),
        ( 'uninit_read_member', 'uninit_read' ),
        ( 'uninit_read_through_ref', 'uninit_read' ),
        ( 'ref_to_uninit_marked_direction', 'ref_to_uninit' ),
        ( 'ctor_uninit_member_base', 'ctor_uninit_member' ),
    ],
)
def test_std_init_golden_alternate_lines_classify( fixture_key, rule_id ):
    golden = json.loads( _GOLDEN.read_text( encoding='utf-8' ) )
    diagnostic = parse_profiles_diagnostic( golden[ fixture_key ] )
    assert diagnostic is not None
    assert diagnostic.rule_id == rule_id


def test_classify_rule_is_profile_keyed():
    message = "variable '…' must be initialized or marked '…'"
    assert classify_rule( 'std::init', message ) == 'uninit_decl'
    assert classify_rule( 'std::type', message ) == UNCLASSIFIED_RULE_ID
    assert classify_rule( 'std::future', message ) == UNCLASSIFIED_RULE_ID


def test_unknown_compiler_returns_none():
    line = (
        "/tmp/x.cpp:1:1: error: example under profile 'std::init'"
    )
    assert parse_profiles_diagnostic( line, compiler='gcc' ) is None


def test_destroy_rules_documented_before_live_capture():
    assert 'destroy_uninit' in std_init.DOCUMENTED_RULE_IDS_AWAITING_LIVE_CAPTURE
    assert 'double_destroy' in std_init.DOCUMENTED_RULE_IDS_AWAITING_LIVE_CAPTURE
    assert 'uninit_decl' in std_init.RULE_DOC_REFERENCES


@pytest.mark.parametrize( 'rule_id, page_slug', sorted( std_init.RULE_DOC_PAGES.items() ) )
def test_std_init_rule_doc_hrefs( rule_id, page_slug ):
    href = std_init.rule_doc_href( rule_id )
    assert href == (
        'https://ja11sop.github.io/cuppa/cuppa/latest/cxx-profiles/std-init/{}.html'.format(
            page_slug,
        )
    )
    assert rule_id in std_init.RULE_DOC_REFERENCES


def test_std_init_rule_doc_href_unknown():
    assert std_init.rule_doc_href( '_unclassified' ) is None


def test_std_init_doc_pages_exist_in_antora_tree():
    pages = (
        Path( __file__ ).resolve().parents[2]
        / 'docs' / 'modules' / 'ROOT' / 'pages' / 'cxx-profiles' / 'std-init'
    )
    for slug in set( std_init.RULE_DOC_PAGES.values() ):
        assert ( pages / '{}.adoc'.format( slug ) ).is_file(), slug
