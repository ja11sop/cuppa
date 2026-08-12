#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

import json
import os

import pytest

from cuppa.cpp.cxx_profiles_report import (
    ProfilesInventory,
    ProfilesScope,
    parse_profiles_diagnostic,
)
from cuppa.cpp.profiles_report.report_html import (
    INDEX_BASENAME,
    JSON_BASENAME,
    build_sconscript_groups,
    default_report_directory,
    display_path,
    enrich_scope_view,
    source_href,
    variant_display_from_dir,
    write_profiles_reports,
)

pytestmark = pytest.mark.unit

_SAMPLE_SCOPE = ProfilesScope(
    sconscript='./widget/sconscript',
    variant_dir='_build/widget/clang24_profiles/dbg/x86_64/cxx2c',
    toolchain='clang24_profiles',
    variant_label='dbg',
)

_LINE = (
    "/home/user/project/src/widget.cpp:10:12: error: pointer to uninitialized "
    "memory must be marked '[[ref_to_uninit]]' under profile 'std::init'"
)


def _sample_inventory():
    inventory = ProfilesInventory()
    inventory.record( _SAMPLE_SCOPE, parse_profiles_diagnostic( _LINE ) )
    return inventory


def test_report_model_includes_rollup_views():
    model = _sample_inventory().as_report_model()
    assert model[ 'rollup' ][ 'rules' ]
    assert model[ 'rollup' ][ 'files' ]
    assert model[ 'scopes' ][ 0 ][ 'report_stem' ].startswith( 'cxx-profiles--' )
    assert model[ 'scopes' ][ 0 ][ 'total_references' ] == 1


def test_display_path_rebases_under_sconstruct_dir():
    path = '/home/user/project/src/widget.cpp'
    assert display_path( path, '/home/user/project', '/home/user/project' ) == (
        'src/widget.cpp'
    )


def test_source_href_gitlab_blob():
    base = 'https://gitlab.example.com/org/widget/-/blob/main'
    href = source_href(
        '/home/user/project/src/widget.cpp',
        10,
        'gitlab',
        base,
        'src/widget.cpp',
    )
    assert href == 'https://gitlab.example.com/org/widget/-/blob/main/src/widget.cpp#L10'


def test_variant_display_from_dir():
    assert variant_display_from_dir(
        '_build/widget/clang24_profiles/dbg/x86_64/cxx2c',
    ) == 'dbg/x86_64/cxx2c'


def test_scope_summaries_and_sconscript_groups():
    model = _sample_inventory().as_report_model()
    scope = model[ 'scopes' ][ 0 ]
    scope[ 'profiles' ] = [
        {
            'profile': 'std::init',
            'rules': [
                { 'rule_id': 'uninit_decl', 'total_references': 45 },
                { 'rule_id': 'destroy_uninit', 'total_references': 33 },
            ],
        },
    ]
    scope[ 'variant_dir' ] = '_build/test/clang24_profiles/dbg/x86_64/cxx2c'
    enrich_scope_view( scope )
    assert scope[ 'variant_display' ] == 'dbg/x86_64/cxx2c'
    assert 'std::init (78)' in scope[ 'profiles_summary' ]
    assert 'std::init::uninit_decl (45)' in scope[ 'rules_summary' ]

    pages = [
        {
            'html': 'a.html',
            'scope': scope,
        },
    ]
    groups = build_sconscript_groups( pages )
    assert len( groups ) == 1
    assert groups[ 0 ][ 'sconscript' ] == scope[ 'sconscript' ]


def test_default_report_directory_uses_artifacts_root( tmp_path ):
    env = {
        'sconstruct_dir': str( tmp_path ),
        'artifacts_root': 'out/artefacts',
        'abs_artifacts_root': str( tmp_path / 'out' / 'artefacts' ),
    }
    assert default_report_directory( env ) == str(
        tmp_path / 'out' / 'artefacts' / 'cxx-profiles'
    )


def test_write_profiles_reports_emits_html_and_json( tmp_path ):
    inventory = _sample_inventory()
    env = {
        'sconstruct_dir': str( tmp_path ),
        'artifacts_root': '_artifacts',
        'abs_artifacts_root': str( tmp_path / '_artifacts' ),
        'cxx_profiles_report': True,
        'cxx_profiles_report_link_style': 'local',
        'cxx_profiles_report_root': str( tmp_path ),
    }
    result = write_profiles_reports( inventory, env )
    report_dir = default_report_directory( env )
    assert result[ 'index_path' ] == os.path.join( report_dir, INDEX_BASENAME )
    assert os.path.isfile( os.path.join( report_dir, INDEX_BASENAME ) )
    assert os.path.isfile( os.path.join( report_dir, JSON_BASENAME ) )
    scope_stem = inventory.as_report_model()[ 'scopes' ][ 0 ][ 'report_stem' ]
    assert os.path.isfile( os.path.join( report_dir, '{}.html'.format( scope_stem ) ) )

    payload = json.loads(
        open( os.path.join( report_dir, JSON_BASENAME ), encoding='utf-8' ).read()
    )
    assert payload[ 'rollup' ][ 'total_references' ] == 1
