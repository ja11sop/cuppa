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


@pytest.mark.parametrize(
    'rule_id',
    [
        'uninit_decl',
        'static_runtime_init',
        'ctor_uninit_member',
        'ref_to_uninit',
    ],
)
def test_std_init_golden_lines_classify( rule_id ):
    golden = json.loads( _GOLDEN.read_text( encoding='utf-8' ) )
    line = golden[ rule_id ]
    diagnostic = parse_profiles_diagnostic( line )
    assert diagnostic is not None
    assert diagnostic.profile == std_init.PROFILE_NAME
    assert diagnostic.rule_id == rule_id


def test_std_init_golden_base_class_line():
    golden = json.loads( _GOLDEN.read_text( encoding='utf-8' ) )
    diagnostic = parse_profiles_diagnostic( golden[ 'ctor_uninit_member_base' ] )
    assert diagnostic is not None
    assert diagnostic.rule_id == 'ctor_uninit_member'


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


def test_std_init_documents_rules_awaiting_golden_capture():
    assert 'uninit_read' in std_init.DOCUMENTED_RULE_IDS
    assert 'uninit_decl' in std_init.RULE_DOC_REFERENCES
