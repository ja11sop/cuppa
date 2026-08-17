#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

import os

import pytest

from cuppa.cpp.profiles_report.source_pages import (
    BY_SOURCE_DIR,
    build_source_page_title,
    build_source_view_lines,
    collect_file_violations,
    compute_gutter_width_ch,
    display_path_for_report,
    display_path_on_disk,
    format_rule_label_html,
    format_violation_message_html,
    sanitized_source_filename,
    source_page_relpath,
    write_source_pages,
)
from cuppa.cpp.cxx_profiles_report import (
    ProfilesInventory,
    ProfilesScope,
    parse_profiles_diagnostic,
)

pytestmark = pytest.mark.unit

_SAMPLE_SCOPE = ProfilesScope(
    sconscript='./widget/sconscript',
    variant_dir='_build/widget/clang24_profiles/dbg/x86_64/cxx2c',
    toolchain='clang24_profiles',
    variant_label='dbg',
)


def _record_line( inventory, path, line=10, column=12 ):
    diagnostic = parse_profiles_diagnostic(
        "{}:{}:{}: error: pointer to uninitialized memory must be marked "
        "'[[ref_to_uninit]]' under profile 'std::init'".format( path, line, column )
    )
    inventory.record( _SAMPLE_SCOPE, diagnostic )


def test_sanitized_source_filename():
    assert sanitized_source_filename( '/a/b/c.cpp' ) == '--a--b--c.cpp.html'
    assert source_page_relpath( '/a/b/c.cpp' ) == os.path.join(
        BY_SOURCE_DIR, '--a--b--c.cpp.html',
    )


def test_sanitized_source_filename_hashes_overlong_paths():
    long_path = '/home/user/' + 'very-long-segment/' * 40 + 'file.hpp'
    name = sanitized_source_filename( long_path )
    assert len( name ) <= 240
    assert name.endswith( '.html' )
    assert '--' in name


def test_display_path_rebases_project_source( tmp_path ):
    source = tmp_path / 'src' / 'widget.cpp'
    source.parent.mkdir()
    source.write_text( 'int x;\n', encoding='utf-8' )
    env = {
        'sconstruct_dir': str( tmp_path ),
        'cxx_profiles_report_root': str( tmp_path ),
    }
    assert display_path_for_report( str( source ), env ) == 'src/widget.cpp'


def test_display_path_shortens_dependency_download_tree( tmp_path, monkeypatch ):
    deps_root = tmp_path / '_download'
    folder = 'git_ssh_git@git.example.com__org_widget@master'
    dep_root = deps_root / folder
    dep_root.mkdir( parents=True )
    ( dep_root / '.git' ).mkdir()
    include_dir = dep_root / 'include' / 'widget'
    include_dir.mkdir( parents=True )
    source = include_dir / 'widget.hpp'
    source.write_text( 'struct Widget {};\n', encoding='utf-8' )

    monkeypatch.setattr(
        'cuppa.core.dependency_identity.short_name_from_git_tree',
        lambda path: ( 'git.example.com/org/widget', 'ssh://git@git.example.com/org/widget' ),
    )

    env = {
        'sconstruct_dir': str( tmp_path ),
        'downloads_root': str( deps_root ),
    }
    display = display_path_for_report( str( source ), env )
    assert display == (
        'git.example.com/org/widget@master/include/widget/widget.hpp'
    )


def test_collect_file_violations_aggregates_rules_and_lines():
    inventory = ProfilesInventory()
    path = '/tmp/widget.cpp'
    _record_line( inventory, path, line=4, column=8 )
    _record_line( inventory, path, line=4, column=8 )
    _record_line( inventory, path, line=9, column=3 )

    files = collect_file_violations( inventory )
    assert len( files ) == 1
    entry = files[ path ]
    assert entry[ 'total_references' ] == 3
    assert entry[ 'lines' ][ 4 ][ 0 ][ 'references' ] == 2
    assert len( entry[ 'rule_summary' ] ) == 1
    assert entry[ 'rule_summary' ][ 0 ][ 'label' ] == 'std::init::ref_to_uninit'
    assert entry[ 'rule_summary' ][ 0 ][ 'line_count' ] == 2
    assert entry[ 'rule_summary' ][ 0 ][ 'count' ] == 3
    assert '[[ref_to_uninit]]' in entry[ 'rule_summary' ][ 0 ][ 'violation_message_html' ]
    assert entry[ 'unique_line_count' ] == 2


def test_format_rule_label_html_splits_profile_weight():
    html = format_rule_label_html( 'std::init', 'ref_to_uninit' )
    assert 'prof-rule-profile' in html
    assert 'prof-rule-id' in html
    assert 'std::init::' in html
    assert 'ref_to_uninit' in html


def test_format_violation_message_html_replaces_placeholder():
    html = format_violation_message_html(
        "pointer to uninitialized memory must be marked '…'",
        profile='std::init',
        rule_id='ref_to_uninit',
    )
    assert '[[ref_to_uninit]]' in html
    assert 'prof-attr-literal' in html
    assert "'…'" not in html
    assert 'prof-emphasis' not in html
    assert "''" not in html


def test_format_violation_message_html_uninit_decl_shows_attribute_literal():
    html = format_violation_message_html(
        "variable '…' must be initialized or marked '…'",
        profile='std::init',
        rule_id='uninit_decl',
    )
    assert '[[uninit]]' in html
    assert 'prof-attr-literal' in html
    assert html.count( 'prof-message-name' ) == 1
    assert '&lt;name&gt;' in html
    assert "''" not in html
    assert 'variable &#x27;<span class="prof-message-name">&lt;name&gt;</span>&#x27; must be initialized' in html


def test_build_source_view_lines_marks_violation_column( tmp_path ):
    source = tmp_path / 'widget.cpp'
    source.write_text(
        'int good;\n'
        'int* bad;\n',
        encoding='utf-8',
    )
    file_entry = {
        'lines': {
            2: [
                {
                    'line': 2,
                    'column': 6,
                    'profile': 'std::init',
                    'rule_id': 'ref_to_uninit',
                    'message': 'example',
                    'references': 1,
                },
            ],
        },
    }
    lines = build_source_view_lines( str( source ), file_entry )
    assert len( lines ) == 2
    assert lines[ 0 ][ 'kind' ] == 'plain'
    assert lines[ 1 ][ 'kind' ] == 'violation'
    assert lines[ 1 ][ 'column' ] == 6
    assert lines[ 1 ][ 'gutter' ] == 'ref_to_uninit (1)'


def test_compute_gutter_width_ch_fits_longest_label():
    file_entry = {
        'lines': {
            1: [
                { 'rule_id': 'ref_to_uninit', 'references': 1 },
            ],
            2: [
                { 'rule_id': 'uninit_with_initializer', 'references': 12 },
            ],
        },
    }
    width = compute_gutter_width_ch( file_entry )
    assert width >= len( 'uninit_with_initializer (12)' )


def test_build_source_page_title_splits_dependency_paths( tmp_path, monkeypatch ):
    deps_root = tmp_path / '_download'
    folder = 'git_ssh_git@git.example.com__org_widget@master'
    dep_root = deps_root / folder
    dep_root.mkdir( parents=True )
    ( dep_root / '.git' ).mkdir()
    source = dep_root / 'include' / 'widget' / 'widget.hpp'
    source.parent.mkdir( parents=True )
    source.write_text( 'struct Widget {};\n', encoding='utf-8' )

    monkeypatch.setattr(
        'cuppa.core.dependency_identity.short_name_from_git_tree',
        lambda path: ( 'git.example.com/org/widget', 'ssh://git@git.example.com/org/widget' ),
    )

    env = { 'downloads_root': str( deps_root ) }
    display = display_path_for_report( str( source ), env )
    title = build_source_page_title( display, str( source ), env )
    assert title[ 'title_split' ] is True
    assert title[ 'title_prefix' ] == 'git.example.com/org/widget@master'
    assert title[ 'title_suffix' ] == 'include/widget/widget.hpp'
    assert title[ 'title_include_split' ] is True
    assert title[ 'title_include_prefix' ] == 'include/'
    assert title[ 'title_include_path' ] == 'widget/widget.hpp'


def test_build_source_page_title_splits_include_prefix_from_nested_path(
    tmp_path, monkeypatch,
):
    deps_root = tmp_path / '_download'
    folder = 'git_ssh_git@gitlab.example__org_common_types@master'
    dep_root = deps_root / folder
    dep_root.mkdir( parents=True )
    ( dep_root / '.git' ).mkdir()
    source = dep_root / 'include' / 'widget' / 'common_types' / 'number.hpp'
    source.parent.mkdir( parents=True )
    source.write_text( 'struct number {};\n', encoding='utf-8' )

    monkeypatch.setattr(
        'cuppa.core.dependency_identity.short_name_from_git_tree',
        lambda path: (
            'gitlab.example/org/common_types',
            'ssh://git@gitlab.example/org/common_types',
        ),
    )

    env = { 'downloads_root': str( deps_root ) }
    title = build_source_page_title( '', str( source ), env )
    assert title[ 'title_include_prefix' ] == 'include/'
    assert title[ 'title_include_path' ] == 'widget/common_types/number.hpp'


def test_build_source_page_title_splits_local_include_path( tmp_path ):
    project = tmp_path / 'project'
    source = project / 'include' / 'widget' / 'engine' / 'engine.hpp'
    source.parent.mkdir( parents=True )
    source.write_text( 'struct engine {};\n', encoding='utf-8' )

    env = { 'sconstruct_dir': str( project ) }
    title = build_source_page_title(
        'include/widget/engine/engine.hpp',
        str( source ),
        env,
    )
    assert title[ 'title_split' ] is True
    assert title[ 'title_prefix' ] == ''
    assert title[ 'title_include_split' ] is True
    assert title[ 'title_include_prefix' ] == 'include/'
    assert title[ 'title_include_path' ] == 'widget/engine/engine.hpp'


def test_build_source_page_title_splits_build_working_path( tmp_path ):
    project = tmp_path / 'project'
    source = (
        project
        / '_build'
        / 'widget'
        / 'clang24_profiles_2026_08_07_27'
        / 'dbg'
        / 'x86_64'
        / 'cxx2c'
        / 'working'
        / 'widget'
        / 'version.cpp'
    )
    source.parent.mkdir( parents=True )
    source.write_text( 'const char* version = "1";\n', encoding='utf-8' )

    env = { 'sconstruct_dir': str( project ) }
    title = build_source_page_title(
        '_build/widget/clang24_profiles_2026_08_07_27/dbg/x86_64/cxx2c/working/widget/version.cpp',
        str( source ),
        env,
    )
    assert title[ 'title_split' ] is True
    assert title[ 'title_prefix' ] == (
        '_build/widget/clang24_profiles_2026_08_07_27/dbg/x86_64/cxx2c/working/'
    )
    assert title[ 'title_suffix' ] == 'widget/version.cpp'
    assert title[ 'title_include_split' ] is False
    assert title[ 'title_suffix_only' ] is False


def test_build_source_page_title_bolds_plain_local_path( tmp_path ):
    project = tmp_path / 'project'
    source = project / 'test' / 'instruments' / 'management.cpp'
    source.parent.mkdir( parents=True )
    source.write_text( 'void manage() {}\n', encoding='utf-8' )

    env = { 'sconstruct_dir': str( project ) }
    title = build_source_page_title(
        'test/instruments/management.cpp',
        str( source ),
        env,
    )
    assert title[ 'title_split' ] is True
    assert title[ 'title_suffix_only' ] is True
    assert title[ 'title_suffix' ] == 'test/instruments/management.cpp'


def test_display_path_on_disk_uses_home_tilde( tmp_path, monkeypatch ):
    home = tmp_path / 'home'
    home.mkdir()
    monkeypatch.setenv( 'HOME', str( home ) )
    source = home / 'project' / 'src' / 'widget.cpp'
    source.parent.mkdir( parents=True )
    source.write_text( 'int x;\n', encoding='utf-8' )
    assert display_path_on_disk( str( source ) ) == '~/project/src/widget.cpp'


def test_line_gutter_aggregates_duplicate_rules_on_one_line():
    inventory = ProfilesInventory()
    path = '/tmp/widget.cpp'
    _record_line( inventory, path, line=4, column=8 )
    _record_line( inventory, path, line=4, column=8 )
    files = collect_file_violations( inventory )
    lines = build_source_view_lines( path, files[ path ] )
    violation = next( line for line in lines if line[ 'kind' ] == 'violation' )
    assert violation[ 'gutter' ] == 'ref_to_uninit (2)'


def test_write_source_pages_emits_markup( tmp_path ):
    source = tmp_path / 'src' / 'widget.cpp'
    source.parent.mkdir()
    source.write_text( 'int* p;\n', encoding='utf-8' )

    inventory = ProfilesInventory()
    _record_line( inventory, str( source ), line=1, column=6 )

    env = {
        'sconstruct_dir': str( tmp_path ),
        'cxx_profiles_report_link_style': 'local',
    }
    destination = tmp_path / 'report'
    page_map, written = write_source_pages(
        inventory,
        str( destination ),
        env,
        'local',
        None,
        'cxx-profiles-index.html',
        lambda: __import__( 'jinja2' ).Environment(
            loader=__import__( 'jinja2' ).PackageLoader( 'cuppa', 'cpp/templates' ),
            autoescape=__import__( 'jinja2' ).select_autoescape( [ 'html', 'xml' ] ),
        ).get_template( 'cxx_profiles_source_file.html' ),
    )
    assert len( written ) == 1
    assert page_map[ str( source ) ] == source_page_relpath( str( source ) )
    html = open( written[ 0 ], encoding='utf-8' ).read()
    assert 'prof-violation' in html
    assert 'prof-rule-id' in html
    assert 'ref_to_uninit' in html
    assert 'prof-summary-table' in html
    assert 'Violation Message' in html
    assert '>Violations</th>' in html
    assert 'Distinct/Unique' not in html
    assert 'violation of' in html
    assert 'distinct rule' in html
    assert 'violation detected through' not in html
    assert 'violations detected through' not in html
    assert 'Source code' in html
    assert 'breadcrumb' in html
    assert 'By source' in html
    assert 'prof-stat-value--alert' in html


def test_write_source_pages_github_source_link( tmp_path, monkeypatch ):
    source = tmp_path / 'include' / 'widget.hpp'
    source.parent.mkdir( parents=True )
    source.write_text( 'int* p;\n', encoding='utf-8' )

    inventory = ProfilesInventory()
    _record_line( inventory, str( source ), line=1, column=6 )

    monkeypatch.setattr(
        'cuppa.test_report.html_report.vcs_info_from_location',
        lambda *args: (
            'git@github.com:cppalliance/capy.git',
            'https://github.com/cppalliance/capy',
            'develop',
            'origin',
            'abc123',
        ),
    )

    env = {
        'sconstruct_dir': str( tmp_path ),
        'reports_link_style': 'github',
        'current_branch': 'develop',
    }
    destination = tmp_path / 'report'
    page_map, written = write_source_pages(
        inventory,
        str( destination ),
        env,
        'github',
        'https://github.com/cppalliance/capy/blob/develop',
        'cxx-profiles-index.html',
        lambda: __import__( 'jinja2' ).Environment(
            loader=__import__( 'jinja2' ).PackageLoader( 'cuppa', 'cpp/templates' ),
            autoescape=__import__( 'jinja2' ).select_autoescape( [ 'html', 'xml' ] ),
        ).get_template( 'cxx_profiles_source_file.html' ),
    )
    html = open( written[ 0 ], encoding='utf-8' ).read()
    assert 'https://github.com/cppalliance/capy/blob/develop/include/widget.hpp' in html
    assert 'file://' not in html
