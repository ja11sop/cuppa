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
    build_vcs_provenance,
    default_report_directory,
    display_path,
    enrich_scope_view,
    rule_doc_href,
    rule_link_tooltip,
    source_href,
    variant_display_from_dir,
    write_profiles_reports,
)
from cuppa.cpp.profiles_report.source_pages import sanitized_source_filename

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


def test_rule_link_tooltip_includes_rule_name_and_message():
    tooltip = rule_link_tooltip(
        'std::init',
        'ref_to_uninit',
        "pointer to uninitialized memory must be marked '…'",
    )
    assert tooltip.startswith( 'std::init::ref_to_uninit — ' )
    assert 'uninitialized memory' in tooltip


def test_rule_doc_href_for_std_init():
    assert rule_doc_href( 'std::init', 'uninit_decl' ).endswith(
        '/cxx-profiles/std-init/uninit-decl.html',
    )
    assert rule_doc_href( 'std::future', 'uninit_decl' ) is None


def test_overview_doc_hrefs():
    from cuppa.cpp.profiles_report.report_html import overview_doc_href, overview_doc_hrefs

    assert overview_doc_href().endswith( '/cxx-profiles/report-overview.html' )
    assert overview_doc_href( 'violation-totals' ).endswith( '#violation-totals' )
    hrefs = overview_doc_hrefs()
    assert hrefs[ 'codebase_reach' ].endswith( '#codebase-reach-tier-1' )
    assert hrefs[ 'violation_density' ].endswith( '#violation-density-tier-2' )
    assert hrefs[ 'rule_concentration' ].endswith( '#rule-concentration' )
    assert hrefs[ 'profile_matrices' ].endswith( '#profile-matrices' )
    assert hrefs[ 'build_breakdown' ].endswith( '#build-breakdown' )


def test_report_model_includes_rollup_views():
    model = _sample_inventory().as_report_model()
    assert model[ 'rollup' ][ 'rules' ]
    assert model[ 'rollup' ][ 'files' ]
    assert model[ 'rollup' ][ 'files' ][ 0 ][ 'unique_line_count' ] == 1
    assert model[ 'rollup' ][ 'files' ][ 0 ][ 'unique_rule_count' ] == 1
    rollup_rule = model[ 'rollup' ][ 'rules' ][ 0 ]
    assert rollup_rule[ 'unique_line_count' ] == 1
    assert rollup_rule[ 'files' ][ 0 ][ 'unique_line_count' ] == 1
    assert rollup_rule[ 'files' ][ 0 ][ 'total_references' ] == 1
    scope_rule = model[ 'scopes' ][ 0 ][ 'profiles' ][ 0 ][ 'rules' ][ 0 ]
    assert scope_rule[ 'unique_line_count' ] == 1
    assert scope_rule[ 'files' ][ 0 ][ 'unique_line_count' ] == 1
    scope_file = model[ 'scopes' ][ 0 ][ 'profiles' ][ 0 ][ 'files' ][ 0 ]
    assert scope_file[ 'unique_line_count' ] == 1
    assert scope_file[ 'unique_rule_count' ] == 1
    assert scope_file[ 'variant_counts' ][ 0 ][ 'variant_label' ] == 'dbg'
    assert scope_file[ 'profile' ] == 'std::init'
    assert model[ 'scopes' ][ 0 ][ 'report_stem' ].startswith( 'cxx-profiles--' )
    assert model[ 'scopes' ][ 0 ][ 'total_references' ] == 1
    assert model[ 'scopes' ][ 0 ][ 'unique_line_count' ] == 1
    assert model[ 'scopes' ][ 0 ][ 'unique_rule_count' ] == 1
    assert model[ 'rollup' ][ 'unique_violation_count' ] == 1
    assert model[ 'rollup' ][ 'variant_count' ] == 1


def test_unique_violation_count_dedupes_across_variants():
    inventory = ProfilesInventory()
    diagnostic = parse_profiles_diagnostic( _LINE )
    dbg_scope = ProfilesScope(
        sconscript='./widget/sconscript',
        variant_dir='_build/widget/clang24_profiles/dbg/x86_64/cxx2c',
        toolchain='clang24_profiles',
        variant_label='dbg',
    )
    rel_scope = ProfilesScope(
        sconscript='./widget/sconscript',
        variant_dir='_build/widget/clang24_profiles/rel/x86_64/cxx2c',
        toolchain='clang24_profiles',
        variant_label='rel',
    )
    inventory.record( dbg_scope, diagnostic )
    inventory.record( rel_scope, diagnostic )
    model = inventory.as_report_model()
    assert model[ 'rollup' ][ 'total_references' ] == 1
    assert model[ 'rollup' ][ 'raw_total_references' ] == 2
    assert model[ 'rollup' ][ 'unique_violation_count' ] == 1
    assert model[ 'rollup' ][ 'unique_rule_count' ] == 1
    assert model[ 'rollup' ][ 'variant_count' ] == 2
    rollup_rule = model[ 'rollup' ][ 'rules' ][ 0 ]
    assert rollup_rule[ 'variant_counts' ][ 0 ][ 'variant_label' ] == 'dbg'
    assert rollup_rule[ 'variant_counts' ][ 0 ][ 'file_count' ] == 1
    assert rollup_rule[ 'variant_counts' ][ 0 ][ 'files' ][ 0 ][ 'unique_line_count' ] == 1
    assert rollup_rule[ 'variant_counts' ][ 1 ][ 'variant_label' ] == 'rel'
    assert rollup_rule[ 'variant_counts' ][ 1 ][ 'file_count' ] == 1
    assert rollup_rule[ 'variant_counts' ][ 0 ][ 'build_key' ][ 0 ] == 'dbg'
    assert rollup_rule[ 'variant_counts' ][ 1 ][ 'build_key' ][ 0 ] == 'rel'


def test_rollup_variant_display_uses_common_plus_delta():
    from cuppa.cpp.profiles_report.report_html import enrich_model_for_html

    inventory = ProfilesInventory()
    diagnostic = parse_profiles_diagnostic( _LINE )
    dbg_scope = ProfilesScope(
        sconscript='./widget/sconscript',
        variant_dir='_build/widget/clang24_profiles/dbg/x86_64/cxx2c',
        toolchain='clang24_profiles',
        variant_label='dbg',
    )
    rel_scope = ProfilesScope(
        sconscript='./widget/sconscript',
        variant_dir='_build/widget/clang24_profiles/rel/x86_64/cxx2c',
        toolchain='clang24_profiles',
        variant_label='rel',
    )
    inventory.record( dbg_scope, diagnostic )
    inventory.record( rel_scope, diagnostic )
    model = inventory.as_report_model()
    enrich_model_for_html(
        model,
        {},
        'raw',
        '',
        '/tmp/project',
        '/tmp/project',
    )
    rollup_rule = model[ 'rollup' ][ 'rules' ][ 0 ]
    display = rollup_rule[ 'variant_display' ]
    assert display[ 'multi_build' ] is True
    assert display[ 'common' ][ 'violations' ] == 1
    assert display[ 'common' ][ 'refs' ] == 1
    assert display[ 'common' ][ 'peak_refs' ] == 1
    assert display[ 'totals' ][ 'violations' ] == 1
    assert display[ 'totals' ][ 'refs' ] == 1
    assert display[ 'totals' ][ 'peak_refs' ] == 1
    assert display[ 'deltas' ] == []
    assert rollup_rule[ 'peak_refs_display' ] is display
    rollup_file = rollup_rule[ 'files' ][ 0 ]
    assert rollup_file[ 'build_refs_display' ][ 'multi_build' ] is True
    assert rollup_file[ 'build_refs_display' ][ 'common' ][ 'refs' ] == 1


def test_build_vcs_provenance_location_dependency_style():
    provenance = build_vcs_provenance(
        'git@git.example.com:org/widget.git',
        'master',
        'release-1.2-3-gb39732e',
    )
    assert provenance[ 'location_label' ] == 'git.example.com:org/widget@master'
    assert provenance[ 'repo_href' ] == 'https://git.example.com/org/widget'
    assert provenance[ 'tag' ] == 'release-1.2'
    assert provenance[ 'commit' ] == 'b39732e'
    assert provenance[ 'tag_href' ] == 'https://git.example.com/org/widget/-/tags/release-1.2'
    assert provenance[ 'commit_href' ] == 'https://git.example.com/org/widget/-/commit/b39732e'


def test_build_vcs_provenance_github_links():
    provenance = build_vcs_provenance(
        'https://github.com/org/widget.git',
        'main',
        'abc1234567890',
    )
    assert provenance[ 'location_label' ] == 'github.com/org/widget@main'
    assert provenance[ 'repo_href' ] == 'https://github.com/org/widget'
    assert provenance[ 'tag' ] is None
    assert provenance[ 'commit' ] == 'abc123456789'
    assert provenance[ 'commit_href' ] == 'https://github.com/org/widget/commit/abc123456789'


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
            'unique_line_count': 78,
            'rules': [
                {
                    'rule_id': 'uninit_decl',
                    'total_references': 45,
                    'unique_line_count': 45,
                },
                {
                    'rule_id': 'destroy_uninit',
                    'total_references': 33,
                    'unique_line_count': 33,
                },
            ],
        },
    ]
    scope[ 'variant_dir' ] = '_build/test/clang24_profiles/dbg/x86_64/cxx2c'
    enrich_scope_view( scope )
    assert scope[ 'variant_display' ] == 'dbg/x86_64/cxx2c'
    assert scope[ 'profiles_summary_items' ] == [ ( 'std::init', 78 ) ]
    assert scope[ 'rules_summary_items' ][ 0 ][ 'rule_id' ] == 'uninit_decl'
    assert scope[ 'rules_summary_items' ][ 0 ][ 'count' ] == 45
    assert scope[ 'rules_summary_items' ][ 1 ][ 'rule_id' ] == 'destroy_uninit'
    assert 'prof-rule-profile' in scope[ 'rules_summary_items' ][ 0 ][ 'label_html' ]
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
        'artefacts_root': 'out/artefacts',
        'abs_artefacts_root': str( tmp_path / 'out' / 'artefacts' ),
        'artifacts_root': 'out/artefacts',
        'abs_artifacts_root': str( tmp_path / 'out' / 'artefacts' ),
    }
    assert default_report_directory( env ) == str(
        tmp_path / 'out' / 'artefacts' / 'cxx-profiles'
    )


def test_write_profiles_reports_emits_html_and_json( tmp_path ):
    source = tmp_path / 'src' / 'widget.cpp'
    source.parent.mkdir()
    source.write_text( 'int* p;\n', encoding='utf-8' )

    inventory = ProfilesInventory()
    diagnostic = parse_profiles_diagnostic(
        "{}:10:12: error: pointer to uninitialized memory must be marked "
        "'[[ref_to_uninit]]' under profile 'std::init'".format( source )
    )
    inventory.record( _SAMPLE_SCOPE, diagnostic )

    env = {
        'sconstruct_dir': str( tmp_path ),
        'artefacts_root': '_artefacts',
        'abs_artefacts_root': str( tmp_path / '_artefacts' ),
        'artifacts_root': '_artefacts',
        'abs_artifacts_root': str( tmp_path / '_artefacts' ),
        'cxx_profiles_report': True,
        'cxx_profiles_report_link_style': 'local',
        'cxx_profiles_report_root': str( tmp_path ),
        'cxx_profiles_enforce': [ 'std::init' ],
    }
    result = write_profiles_reports( inventory, env )
    report_dir = default_report_directory( env )
    assert result[ 'index_path' ] == os.path.join( report_dir, INDEX_BASENAME )
    assert os.path.isfile( os.path.join( report_dir, INDEX_BASENAME ) )
    assert os.path.isfile( os.path.join( report_dir, JSON_BASENAME ) )
    scope_stem = inventory.as_report_model()[ 'scopes' ][ 0 ][ 'report_stem' ]
    scope_path = os.path.join( report_dir, '{}.html'.format( scope_stem ) )
    assert os.path.isfile( scope_path )
    scope_html = open( scope_path, encoding='utf-8' ).read()
    assert 'breadcrumb' in scope_html
    assert 'Profiles report' in scope_html

    source_page = os.path.join(
        report_dir,
        'by-source',
        sanitized_source_filename( str( source ) ),
    )
    assert os.path.isfile( source_page )
    assert len( result[ 'source_paths' ] ) == 1

    payload = json.loads(
        open( os.path.join( report_dir, JSON_BASENAME ), encoding='utf-8' ).read()
    )
    assert payload[ 'schema_version' ] == 1
    assert payload[ 'summary' ][ 'total_references' ] == 1
    assert payload[ 'locations' ]
    assert payload[ 'metadata' ][ 'report_project' ]
    report = payload[ 'report' ]
    assert report[ 'rollup' ][ 'total_references' ] == 1
    rollup_file = report[ 'rollup' ][ 'files' ][ 0 ]
    assert rollup_file[ 'display_path' ] == 'src/widget.cpp'
    assert rollup_file[ 'href' ].startswith( 'by-source/' )
    assert rollup_file[ 'unique_line_count' ] == 1
    rollup_rule = report[ 'rollup' ][ 'rules' ][ 0 ]
    assert rollup_rule[ 'files' ][ 0 ][ 'display_path' ] == 'src/widget.cpp'
    assert rollup_rule[ 'files' ][ 0 ][ 'unique_line_count' ] == 1

    index_html = open( os.path.join( report_dir, INDEX_BASENAME ), encoding='utf-8' ).read()
    assert 'prof-files-table' in index_html
    assert 'prof-rules-table' in index_html
    assert 'fa-eye' in index_html
    assert index_html.index( 'prof-summary-col-detail' ) < index_html.index( 'Profile</th>' )
    assert index_html.index( 'Violations By-Rule' ) < index_html.index( 'Violations By-File' )
    assert index_html.index( 'Violations By-File' ) < index_html.index( 'Violations By-Build' )
    assert index_html.index( 'Violations By-Build' ) < index_html.index( 'Violations By-Sconscript' )
    assert 'id="builds"' in index_html
    assert 'buildViewsTabs' in index_html
    assert 'prof-build-tabs' in index_html
    assert 'prof-build-views' in index_html
    assert 'prof-build-views-picker' in index_html
    builds_tab_start = index_html.index( 'id="builds"' )
    builds_tab_end = index_html.index( 'id="scopes"', builds_tab_start )
    builds_html = index_html[ builds_tab_start:builds_tab_end ]
    assert 'Build inventory load' in builds_html
    assert 'prof-overview-builds-table' in builds_html
    assert 'prof-profile-scope-name' not in builds_html
    assert 'Overview' in index_html
    assert 'id="overview"' in index_html
    assert 'Profile matrix — std::init' not in index_html
    assert 'Profile matrices' in index_html
    assert 'Rule concentration — All profiles' in index_html
    assert 'profile-matrix-pane-1' in index_html
    assert 'profileMatrixTabs' in index_html
    assert 'prof-overview-primary-metric' in index_html
    assert 'prof-overview-profile-prefix' in index_html
    assert 'prof-overview-rule-id' in index_html
    assert 'prof-profile-matrix-tab-name' in index_html
    assert 'data-profile="std::init"' in index_html
    assert 'prof-rule-concentration' in index_html
    concentration_start = index_html.index( 'prof-rule-concentration' )
    concentration_end = index_html.index( 'Profile matrices', concentration_start )
    concentration_html = index_html[ concentration_start:concentration_end ]
    assert 'Union Refs</th>' in concentration_html
    assert 'Peak Refs</th>' in concentration_html
    assert 'prof-stat-value--warn' in index_html
    assert 'prof-stat-value--neutral' in index_html
    assert 'prof-warn-accent' in index_html
    assert 'Violation totals' in index_html
    assert 'distinct violation' in index_html or 'distinct violations' in index_html
    assert 'union reference' in index_html or 'union references' in index_html
    assert '(Union Refs)' in index_html
    assert '(Violations)' in index_html
    assert '(Rules)' in index_html
    assert 'Unique Violations' not in index_html
    assert 'report-overview.html#violation-totals' in index_html
    assert 'report-overview.html#codebase-reach-tier-1' in index_html
    assert 'report-overview.html#violation-density-tier-2' in index_html
    assert 'report-overview.html#rule-concentration' in index_html
    assert 'report-overview.html#profile-matrices' in index_html
    assert 'file impacted' in index_html or 'files impacted' in index_html or 'files out of' in index_html
    assert 'Files (of' in index_html
    assert 'prof-stat-value--hot-files' in index_html
    assert 'prof-overview-matrix-footnote' in index_html
    assert 'prof-overview-violation-active' in index_html
    assert 'Violation Hits' in index_html
    assert 'Rule Hits' in index_html
    assert index_html.index( 'Build inventory load' ) < index_html.index( 'Profile matrices' )
    assert 'prof-overview-builds-table' in index_html
    assert 'Build Refs</th>' in index_html
    assert 'File Hits' in index_html
    assert 'prof-overview-builds-id-col' in index_html
    assert '>dbg1<' in index_html or '>dbg1</' in index_html
    assert 'Session total (union)' in index_html
    assert 'report-overview.html#build-breakdown' in index_html
    assert 'std::init::' in index_html
    assert 'Copyright Jamie Allsop' not in index_html
    assert payload[ 'context' ][ 'profiles' ]
    rules_tab = index_html.index( 'id="rollup-rules"')
    assert index_html.index( 'prof-rules-table', rules_tab ) < index_html.index( 'Rule</th>', rules_tab )
    assert index_html.index( 'Violations</th>', rules_tab ) < index_html.index( 'Union Refs</th>', rules_tab )
    assert index_html.index( 'Union Refs</th>', rules_tab ) < index_html.index( 'Peak Refs</th>', rules_tab )
    assert index_html.index( 'Peak Refs</th>', rules_tab ) < index_html.index( 'Violating Files</th>', rules_tab )
    assert 'violation of' in index_html
    assert 'prof-stat-value--hot-files' in index_html
    summary_start = index_html.index( '<h6 class="prof-session-summary' )
    summary_end = index_html.index( '</h6>', summary_start )
    summary_html = index_html[ summary_start:summary_end ]
    assert 'prof-stat-value--hot-files' in summary_html
    assert 'file through' in summary_html.replace( '\n', ' ' )
    assert 'distinct rule' in index_html
    assert 'through' in index_html
    assert 'Peak Refs</th>' in index_html
    assert 'build variant' not in index_html
    assert 'prof-index-project' in index_html
    assert 'prof-report-project-name' not in index_html
    assert 'C++ Profiles Reports for</h3>' in index_html
    assert 'Sconscript / Variant' in index_html
    assert 'Rule Violations' in index_html
    assert 'prof-scopes-table' in index_html
    assert 'prof-violation-count' in index_html
    assert 'prof-scopes-group-row' in index_html
    assert 'prof-scopes-variant-row' in index_html
    assert 'font-weight-bold">dbg</span><span class="prof-variant-tail">/x86_64/cxx2c</span>' in index_html

    assert 'prof-files-table' in scope_html
    assert 'prof-rules-table' in scope_html
    assert 'prof-rule-detail-table' in scope_html
    assert 'prof-violating-file-link' in scope_html
    assert 'prof-violating-file-count' in scope_html
    assert 'Violating Files</th>' in scope_html
    assert 'Build Refs</th>' in scope_html
    assert 'Peak Refs</th>' not in scope_html
    assert 'prof-violation-count' in scope_html
    assert '>Rules</th>' in scope_html
    assert '>Violations</th>' in scope_html
    assert 'Distinct/Unique' not in scope_html
    assert 'Violated Rules</th>' in scope_html
    assert 'prof-violated-rule-link' in scope_html
    assert 'cxx-profiles/std-init/ref-to-uninit.html' in scope_html
    assert 'std::init::ref_to_uninit' in scope_html
    assert 'prof-file-detail-table' in scope_html
    assert 'Violation Message</th>' in scope_html
    assert 'prof-summary-col-index' in scope_html
    assert '[[ref_to_uninit]]' in scope_html
    assert 'prof-attr-literal' in scope_html
    assert 'prof-violation-message' in scope_html
    assert 'prof-file-include-prefix' in scope_html
    assert 'Violations By-Rule' in scope_html
    assert 'Violations By-File' in scope_html
    assert 'prof-report-project-name' in scope_html
    assert 'prof-session-summary' in scope_html
    assert 'prof-stat-value--warn' in scope_html
    assert 'prof-stat-value--neutral' in scope_html
    assert '<span class="prof-profile-scope-name">' not in scope_html
    assert scope_html.count( 'Violations By-Rule' ) == 1
    assert scope_html.count( 'Violations By-File' ) == 1
    assert 'id="scope-rules"' in scope_html
    rules_table_start = scope_html.index( 'id="scope-rules"' )
    assert scope_html.index( '>Profile</th>', rules_table_start ) < scope_html.index( '>Rule</th>', rules_table_start )
    assert '>File</th>' in scope_html
    assert 'fa-eye' in scope_html

    source_html = open( source_page, encoding='utf-8' ).read()
    assert 'violation of' in source_html
    assert 'distinct rule' in source_html
    assert 'Union Refs</th>' in source_html
    assert 'violation detected through' not in source_html
    assert 'violations detected through' not in source_html


def test_variant_index_list_partial_uses_dict_items_key():
    import jinja2

    environment = jinja2.Environment(
        loader=jinja2.PackageLoader( 'cuppa', 'cpp/templates' ),
        autoescape=jinja2.select_autoescape( [ 'html', 'xml' ] ),
    )
    template = environment.get_template( 'cxx_profiles_partial_variant_index_list.html' )
    html = template.render(
        display={
            'multi_build': True,
            'common': {
                'count': 1,
                'items': [ { 'index': 1, 'refs': 3 } ],
            },
            'deltas': [
                {
                    'build_id': 'rel1',
                    'build_label': 'rel/x86_64/cxx2c — clang24',
                    'items': [ { 'index': 2, 'refs': 5 } ],
                },
            ],
        },
    )
    flattened = html.replace( '\n', ' ' )
    assert 'prof-variant-metric-build-id text-muted">rel1</span>' in flattened
    assert 'font-weight-bold">1</span> <span class="prof-variant-metric-build-id' in flattened
    assert 'prof-file-index">1<' in flattened
    assert 'prof-violating-file-count">3<' in flattened
    assert 'prof-file-index">2<' in flattened
    assert 'prof-violating-file-count">5<' in flattened


def test_variant_index_list_uses_rule_index_colour_for_violated_rules():
    import jinja2

    environment = jinja2.Environment(
        loader=jinja2.PackageLoader( 'cuppa', 'cpp/templates' ),
        autoescape=jinja2.select_autoescape( [ 'html', 'xml' ] ),
    )
    template = environment.get_template( 'cxx_profiles_partial_variant_index_list.html' )
    html = template.render(
        display={
            'multi_build': True,
            'common': {
                'count': 0,
                'items': [],
            },
            'deltas': [
                {
                    'build_id': 'dbg1',
                    'build_label': 'dbg — clang24',
                    'items': [
                        {
                            'index': 3,
                            'refs': 9,
                            'doc_href': 'https://example.com/rule',
                            'rule_tooltip': 'rule',
                        },
                    ],
                },
            ],
        },
        index_kind='rule',
    )
    assert 'prof-rule-index">3<' in html
    assert 'prof-file-index' not in html
    assert 'prof-violated-rule-count">9<' in html


def test_variant_metric_partial_stacks_common_and_deltas():
    import jinja2

    environment = jinja2.Environment(
        loader=jinja2.PackageLoader( 'cuppa', 'cpp/templates' ),
        autoescape=jinja2.select_autoescape( [ 'html', 'xml' ] ),
    )
    template = environment.get_template( 'cxx_profiles_partial_variant_metric.html' )
    html = template.render(
        display={
            'multi_build': True,
            'common': { 'violations': 192 },
            'deltas': [
                {
                    'build_id': 'dbg1',
                    'build_label': 'dbg/x86_64/cxx2c — clang24',
                    'violations': 74,
                },
                {
                    'build_id': 'rel1',
                    'build_label': 'rel/x86_64/cxx2c — clang24',
                    'violations': 76,
                },
            ],
        },
        metric='violations',
    )
    assert 'prof-variant-metric-common font-weight-bold">192<' in html
    assert '+74 <span class="prof-variant-metric-build-id text-muted">dbg1</span>' in html
    assert '+76 <span class="prof-variant-metric-build-id text-muted">rel1</span>' in html
    assert ', +' not in html
