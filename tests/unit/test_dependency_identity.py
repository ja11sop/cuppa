"""Unit tests for dependency short-name / identity helpers."""

import pytest

from cuppa.core.dependency_identity import (
    boost_archive_from_folder,
    display_qualifier,
    gitlab_archive_name,
    short_name_from_git_url,
    unqualified_default_branch_label,
    with_vcs_qualifier,
)
from cuppa.core import dependency_tree


pytestmark = pytest.mark.unit


def test_short_name_from_ssh_url():
    assert short_name_from_git_url( 'ssh://git@git.clearpool.io/cplx_core/baa' ) == \
        'git.clearpool.io/cplx_core/baa'


def test_short_name_from_scp_style():
    assert short_name_from_git_url( 'git@git.clearpool.io:cplx_core/baa' ) == \
        'git.clearpool.io/cplx_core/baa'


def test_short_name_from_https_strips_git_suffix():
    assert short_name_from_git_url( 'https://github.com/fmtlib/fmt.git' ) == \
        'github.com/fmtlib/fmt'


def test_boost_archive_from_underscored_folder():
    name, version = boost_archive_from_folder(
            'https_boostorg.jfrog.io__artifactory_main_release_1.86.0_source_boost_1_86_0.tar.gz'
    )
    assert name == 'boost'
    assert version == '1.86.0'


def test_github_archive_from_folder():
    from cuppa.core.dependency_identity import (
        boost_remote_from_folder,
        github_archive_from_folder,
    )
    short, version, remote = github_archive_from_folder(
            'https_github.com__fmtlib_fmt_archive_refs_tags_11.1.4.zip'
    )
    assert short == 'github.com/fmtlib/fmt'
    assert version == '11.1.4'
    assert remote == 'https://github.com/fmtlib/fmt/archive/refs/tags/11.1.4.zip'

    short, version, remote = github_archive_from_folder(
            'https_github.com__fmtlib_fmt_archive_refs_tags_12.2.0.zip'
    )
    assert short == 'github.com/fmtlib/fmt'
    assert version == '12.2.0'
    assert remote == 'https://github.com/fmtlib/fmt/archive/refs/tags/12.2.0.zip'

    assert boost_remote_from_folder(
            'https_archives.boost.io__release_1.91.0_source_boost_1_91_0.tar.gz'
    ) == 'https://archives.boost.io/release/1.91.0/source/boost_1_91_0.tar.gz'
    assert boost_remote_from_folder(
            'https_boostorg.jfrog.io__artifactory_main_release_1.86.0_source_boost_1_86_0.tar.gz'
    ) == (
        'https://boostorg.jfrog.io/artifactory/main/release/'
        '1.86.0/source/boost_1_86_0.tar.gz'
    )


def test_archive_tree_groups_github_versions():
    leaves = [
        {
            'type': 'archive',
            'dependency': 'https_github.com__fmtlib_fmt_archive_refs_tags_11.1.4.zip',
            'short_name': 'github.com/fmtlib/fmt',
            'qualifier': '11.1.4',
            'tool_variant': '-',
            'state': 'unreferenced',
            'size_bytes': 100,
            'last_used_epoch': 1000.0,
            'path': '/deps/https_github.com__fmtlib_fmt_archive_refs_tags_11.1.4.zip',
            'remote_location': 'https://github.com/fmtlib/fmt/archive/refs/tags/11.1.4.zip',
            'source_url': 'https://github.com/fmtlib/fmt/archive/refs/tags/11.1.4.zip',
        },
        {
            'type': 'archive',
            'dependency': 'https_github.com__fmtlib_fmt_archive_refs_tags_12.2.0.zip',
            'short_name': 'github.com/fmtlib/fmt',
            'qualifier': '12.2.0',
            'tool_variant': '-',
            'state': 'unreferenced',
            'size_bytes': 110,
            'last_used_epoch': 1100.0,
            'path': '/deps/https_github.com__fmtlib_fmt_archive_refs_tags_12.2.0.zip',
            'remote_location': 'https://github.com/fmtlib/fmt/archive/refs/tags/12.2.0.zip',
            'source_url': 'https://github.com/fmtlib/fmt/archive/refs/tags/12.2.0.zip',
        },
    ]
    tree = dependency_tree.build_tree( leaves )
    unreferenced = next(
            section for section in tree['sections'] if section['label'] == 'unreferenced'
    )
    archive_type = next(
            child for child in unreferenced['children']
            if child.get( 'kind' ) == 'type' and 'archive' in ( child.get( 'label' ) or '' )
    )
    identities = [
            child for child in archive_type['children'] if child.get( 'kind' ) == 'identity'
    ]
    assert len( identities ) == 1
    assert identities[0]['label'] == 'github.com/fmtlib/fmt'
    assert identities[0].get( 'location' ) in ( '', None )
    versions = [
            child for child in identities[0]['children'] if child.get( 'kind' ) == 'leaf'
    ]
    assert [ child['label'] for child in versions ] == [ '11.1.4', '12.2.0' ]
    assert versions[0]['location'] == \
        'https://github.com/fmtlib/fmt/archive/refs/tags/11.1.4.zip'
    assert versions[1]['location'] == \
        'https://github.com/fmtlib/fmt/archive/refs/tags/12.2.0.zip'


def test_with_download_mark_and_find_cached_download( tmp_path ):
    from cuppa.core.dependency_identity import (
        DOWNLOAD_MARK,
        EXTRACT_MARK,
        find_cached_download,
        with_download_mark,
        with_extract_mark,
    )
    assert with_download_mark( 'https://example/a.zip', True ) == \
        '{} https://example/a.zip'.format( DOWNLOAD_MARK )
    assert with_download_mark( 'https://example/a.zip', False ) == 'https://example/a.zip'
    assert with_extract_mark( 'boost/1.91.0' ) == '{} boost/1.91.0'.format( EXTRACT_MARK )
    assert with_extract_mark( '{} already'.format( EXTRACT_MARK ) ) == '{} already'.format(
            EXTRACT_MARK
    )

    downloads = tmp_path / 'downloads'
    downloads.mkdir()
    archive_name = 'https_github.com__fmtlib_fmt_archive_refs_tags_11.1.4.zip'
    ( downloads / archive_name ).write_text( 'x' )
    found = find_cached_download(
            str( downloads ),
            storage_type='archive',
            path=str( tmp_path / 'deps' / archive_name ),
    )
    assert found == str( downloads / archive_name )

    pkg_dir = downloads / 'packages' / 'capy' / 'develop'
    pkg_dir.mkdir( parents=True )
    archive = 'capy_debian_gcc153_rel_x86_64_cxx2c.tar.gz'
    ( pkg_dir / archive ).write_text( 'y' )
    found = find_cached_download(
            str( downloads ),
            storage_type='gitlab',
            path=str( tmp_path / 'deps' / 'gcc153_rel_x86_64_cxx2c' / 'capy' / 'develop' ),
            package='capy',
            version='develop',
            tool_variant='gcc153_rel_x86_64_cxx2c',
            package_archive=archive,
    )
    assert found == str( pkg_dir / archive )

    tc_dir = downloads / 'toolchains' / 'clang' / 'profiles_2026_08_07_27'
    tc_dir.mkdir( parents=True )
    tc_archive = 'clang-profiles-linux-x86_64.tar.gz'
    ( tc_dir / tc_archive ).write_text( 'z' )
    found = find_cached_download(
            str( downloads ),
            storage_type='toolchain',
            path=str(
                tmp_path / 'deps' / 'toolchains' / 'clang' / 'profiles_2026_08_07_27'
            ),
            package='clang',
            version='profiles_2026_08_07_27',
    )
    assert found == str( tc_dir / tc_archive )


def test_archive_tree_marks_download_on_location():
    leaves = [
        {
            'type': 'archive',
            'dependency': 'https_github.com__fmtlib_fmt_archive_refs_tags_11.1.4.zip',
            'short_name': 'github.com/fmtlib/fmt',
            'qualifier': '11.1.4',
            'tool_variant': '-',
            'state': 'unreferenced',
            'size_bytes': 100,
            'last_used_epoch': 1000.0,
            'path': '/deps/https_github.com__fmtlib_fmt_archive_refs_tags_11.1.4.zip',
            'remote_location': 'https://github.com/fmtlib/fmt/archive/refs/tags/11.1.4.zip',
            'has_download': True,
        },
        {
            'type': 'archive',
            'dependency': 'https_github.com__fmtlib_fmt_archive_refs_tags_12.2.0.zip',
            'short_name': 'github.com/fmtlib/fmt',
            'qualifier': '12.2.0',
            'tool_variant': '-',
            'state': 'unreferenced',
            'size_bytes': 110,
            'last_used_epoch': 1100.0,
            'path': '/deps/https_github.com__fmtlib_fmt_archive_refs_tags_12.2.0.zip',
            'remote_location': 'https://github.com/fmtlib/fmt/archive/refs/tags/12.2.0.zip',
            'has_download': False,
        },
    ]
    tree = dependency_tree.build_tree( leaves )
    unreferenced = next(
            section for section in tree['sections'] if section['label'] == 'unreferenced'
    )
    archive_type = next(
            child for child in unreferenced['children']
            if child.get( 'kind' ) == 'type' and 'archive' in ( child.get( 'label' ) or '' )
    )
    identity = next(
            child for child in archive_type['children'] if child.get( 'kind' ) == 'identity'
    )
    versions = [
            child for child in identity['children'] if child.get( 'kind' ) == 'leaf'
    ]
    from cuppa.core.dependency_identity import DOWNLOAD_MARK
    assert versions[0]['location'].startswith( DOWNLOAD_MARK + ' ' )
    assert not versions[1]['location'].startswith( DOWNLOAD_MARK )


def test_display_qualifier_unspecified_is_at():
    assert display_qualifier( None, 'repository' ) == '@'
    assert display_qualifier( '-', 'repository' ) == '@'
    assert display_qualifier( '@master', 'repository' ) == '@master'
    assert display_qualifier( 'master', 'repository' ) == '@master'


def test_unqualified_default_branch_label():
    assert unqualified_default_branch_label(
            'git_https_example.com__org_widget.git', 'master'
    ) == '@master (unqualified)'
    assert unqualified_default_branch_label(
            'git_https_example.com__org_widget.git@master', 'master'
    ) is None
    assert unqualified_default_branch_label(
            'git_ssh_git@host__org_widget', 'master'
    ) == '@master (unqualified)'
    assert unqualified_default_branch_label(
            'git_ssh_git@host__org_widget@master', 'master'
    ) is None
    assert unqualified_default_branch_label( 'widget_tree', 'master' ) is None
    assert unqualified_default_branch_label(
            'git_https_example.com__org_widget.git', 'master', storage_type='archive'
    ) is None
    assert unqualified_default_branch_label(
            'git_https_example.com__org_widget.git', None
    ) is None


def test_tree_groups_referenced_siblings():
    leaves = [
        {
            'type': 'repository',
            'dependency': 'baa',
            'short_name': 'git.clearpool.io/cplx_core/baa',
            'stem': 'git_ssh_git@git.clearpool.io__cplx_core_baa',
            'qualifier': '@master',
            'tool_variant': '-',
            'state': 'referenced',
            'size_bytes': 100,
            'last_used_epoch': 1000.0,
            'path': '/deps/baa@master',
            'location': 'git_ssh...@master',
            'source_url': 'ssh://git@git.clearpool.io/cplx_core/baa',
        },
        {
            'type': 'repository',
            'dependency': 'git_ssh_git@git.clearpool.io__cplx_core_baa',
            'short_name': 'git.clearpool.io/cplx_core/baa',
            'stem': 'git_ssh_git@git.clearpool.io__cplx_core_baa',
            'qualifier': '@feature',
            'tool_variant': '-',
            'state': 'unreferenced',
            'size_bytes': 50,
            'last_used_epoch': 900.0,
            'path': '/deps/baa@feature',
            'location': 'git_ssh...@feature',
            'source_url': 'ssh://git@git.clearpool.io/cplx_core/baa',
        },
    ]
    tree = dependency_tree.build_tree( leaves )
    sections = { section['label']: section for section in tree['sections'] }
    assert sections['referenced']['children']
    assert not sections['unreferenced']['children']
    assert sections['referenced']['remark'] == '2 total'
    summaries = [
            child for child in sections['referenced']['children']
            if child.get( 'kind' ) == 'summary'
    ]
    assert [ child['label'] for child in summaries ] == [
            'dependencies in use',
            'potentially stale dependencies',
    ]
    assert summaries[0]['remark'] == '1 used'
    assert summaries[0]['size_bytes'] == 100
    assert summaries[1]['remark'] == '1 unused'
    assert summaries[1]['size_bytes'] == 50
    location_type = next(
            child for child in sections['referenced']['children']
            if child.get( 'kind' ) == 'type'
    )
    identity = next(
            child for child in location_type['children']
            if child.get( 'kind' ) == 'identity'
    )
    assert 'baa' in identity['label']
    assert identity['size_bytes'] == 150
    labels = [
            child['label'] for child in identity['children']
            if child.get( 'kind' ) == 'leaf'
    ]
    assert '@master' in labels
    assert '@feature' in labels
    # Single in-use leaf: no noisy "1 used" on the identity row.
    assert identity.get( 'remark' ) in ( '', None )
    assert location_type.get( 'remark' ) == '1 used'


def test_tree_missing_identity_prefers_remote_location():
    leaves = [
        {
            'type': 'repository',
            'dependency': 'matching_facility',
            'short_name': 'git.clearpool.io/cplx_core/matching_facility',
            'stem': 'git_ssh_git@git.clearpool.io__cplx_core_matching_facility',
            'qualifier': '@',
            'tool_variant': '-',
            'state': 'missing',
            'size_bytes': 0,
            'last_used_epoch': None,
            'path': '/deps/missing',
            'location': 'git_ssh...',
            'remote_location': 'git+ssh://git@git.clearpool.io/cplx_core/matching_facility@',
            'source_url': None,
        },
    ]
    tree = dependency_tree.build_tree( leaves )
    location_type = next(
            child for child in tree['sections'][0]['children']
            if child.get( 'kind' ) == 'type'
    )
    identity = next(
            child for child in location_type['children']
            if child.get( 'kind' ) == 'identity'
    )
    assert identity.get( 'remark' ) in ( '', None )
    assert identity['size_bytes'] is None
    leaf = next(
            child for child in identity['children']
            if child.get( 'kind' ) == 'leaf'
    )
    assert leaf['remark'] == 'missing'
    assert identity.get( 'missing' ) is True
    assert 'matching_facility' in identity['label']
    assert 'git+ssh://git@git.clearpool.io/cplx_core/matching_facility@' in identity['label']
    assert identity['label'].startswith( 'matching_facility [' )
    # Bracket detail is the configured URL, not the derived short name alone.
    assert identity['label'] != \
        'matching_facility [git.clearpool.io/cplx_core/matching_facility]'


def test_tree_missing_gitlab_version_and_dashes():
    leaves = [
        {
            'type': 'gitlab',
            'dependency': 'google_cloud_cpp',
            'short_name': 'google-cloud-cpp',
            'qualifier': '2.28.0',
            'tool_variant': 'gcc153_rel_x86_64_cxx2c',
            'state': 'missing',
            'size_bytes': 0,
            'last_used_epoch': None,
            'path': '/deps/missing/gcc.../google-cloud-cpp/2.28.0',
            'remote_location': (
                'https://git.clearpool.io/api/v4/projects/cplx_core%2Fregistry'
                '/google-cloud-cpp/2.28.0'
            ),
        },
    ]
    tree = dependency_tree.build_tree( leaves )
    lines, _ = dependency_tree.render_tree_lines( tree )
    plain = '\n'.join( lines )
    import re
    plain = re.sub( r'\x1b\[[0-9;]*m', '', plain )
    assert 'google_cloud_cpp' in plain
    # Referenced summary names missing trees; the toolchain leaf still carries REMARK missing.
    assert 'missing dependencies' in plain
    leaf_lines = [ line for line in plain.splitlines() if 'gcc153_rel' in line ]
    assert leaf_lines and 'missing' in leaf_lines[0]
    # Missing SIZE / LAST USED are dashes, not 0B.
    assert '0B' not in plain
    identity = None
    for type_node in tree['sections'][0]['children']:
        if type_node.get( 'kind' ) != 'type':
            continue
        for child in type_node.get( 'children' ) or []:
            if child.get( 'kind' ) == 'identity':
                identity = child
    assert identity is not None
    assert identity.get( 'remark' ) in ( '', None )
    version = next(
            child for child in identity['children']
            if child.get( 'kind' ) == 'version'
    )
    assert version.get( 'remark' ) in ( '', None )
    assert version['label'] == '2.28.0'
    leaf = version['children'][0]
    assert leaf['remark'] == 'missing'


def test_render_missing_dependency_emphasises_name_errors_children():
    from cuppa.colourise import as_emphasised, as_error

    leaves = [
        {
            'type': 'repository',
            'dependency': 'matching_facility',
            'short_name': 'git.clearpool.io/cplx_core/matching_facility',
            'qualifier': '@',
            'tool_variant': '-',
            'state': 'missing',
            'size_bytes': 0,
            'last_used_epoch': None,
            'path': '/deps/missing',
            'remote_location': 'git+ssh://git@git.clearpool.io/cplx_core/matching_facility@',
        },
    ]
    tree = dependency_tree.build_tree( leaves )
    lines, _ = dependency_tree.render_tree_lines( tree )
    joined = '\n'.join( lines )
    assert as_emphasised( as_error( 'matching_facility' ) ) in joined or \
        as_error( 'matching_facility' ) in joined
    # Leaf is error-coloured (and present); emphasis is reserved for the name.
    assert as_error( '@' ) in joined or '└── @' in joined or 'missing' in joined
    from cuppa.colourise import colouriser
    if colouriser.use_colour:
        assert as_emphasised( as_error( '@' ) ) not in joined


def test_render_package_mutes_version_size_keeps_in_use_size():
    from cuppa.colourise import as_info, as_subdued, colouriser

    leaves = [
        {
            'type': 'gitlab',
            'dependency': 'boost_package',
            'short_name': 'boost_package',
            'qualifier': '1.91',
            'tool_variant': 'gcc153_rel_x86_64_cxx2c',
            'state': 'referenced',
            'size_bytes': 299300000,
            'last_used_epoch': 1000.0,
            'path': '/deps/gcc.../boost_package/1.91',
        },
    ]
    tree = dependency_tree.build_tree( leaves )
    was_colour = colouriser.use_colour
    colouriser.enable()
    try:
        lines, _ = dependency_tree.render_tree_lines( tree )
        joined = '\n'.join( lines )
        from cuppa.utility import storage
        size_text = storage.human_size( 299300000 ).rjust( 8 )
        muted = as_subdued( size_text )
        assert muted in joined
        assert as_info( 'in use' ) in joined
        # In-use leaf keeps a non-muted size cell.
        assert size_text in joined.replace( muted, '' )
    finally:
        colouriser.use_colour = was_colour


def test_spacer_between_identities():
    leaves = [
        {
            'type': 'repository',
            'dependency': 'alpha',
            'short_name': 'alpha',
            'qualifier': '@master',
            'tool_variant': '-',
            'state': 'referenced',
            'size_bytes': 10,
            'last_used_epoch': 1000.0,
            'path': '/deps/alpha',
        },
        {
            'type': 'repository',
            'dependency': 'beta',
            'short_name': 'beta',
            'qualifier': '@master',
            'tool_variant': '-',
            'state': 'referenced',
            'size_bytes': 20,
            'last_used_epoch': 1000.0,
            'path': '/deps/beta',
        },
    ]
    tree = dependency_tree.build_tree( leaves )
    location_type = next(
            child for child in tree['sections'][0]['children']
            if child.get( 'kind' ) == 'type'
    )
    kinds = [ child.get( 'kind' ) for child in location_type['children'] ]
    assert kinds == [ 'spacer', 'identity', 'spacer', 'identity' ]


def test_render_referenced_colours_identity_and_mutes_sibling_leaves():
    from cuppa.colourise import as_emphasised, as_info, as_subdued

    leaves = [
        {
            'type': 'repository',
            'dependency': 'baa',
            'short_name': 'git.clearpool.io/cplx_core/baa',
            'qualifier': '@master',
            'tool_variant': '-',
            'state': 'referenced',
            'size_bytes': 100,
            'last_used_epoch': 1000.0,
            'path': '/deps/baa@master',
            'location': 'loc-master',
        },
        {
            'type': 'repository',
            'dependency': 'baa',
            'short_name': 'git.clearpool.io/cplx_core/baa',
            'qualifier': '@feature',
            'tool_variant': '-',
            'state': 'unreferenced',
            'size_bytes': 50,
            'last_used_epoch': 900.0,
            'path': '/deps/baa@feature',
            'location': 'loc-feature',
        },
    ]
    tree = dependency_tree.build_tree( leaves )
    lines, _ = dependency_tree.render_tree_lines( tree )
    joined = '\n'.join( lines )
    # Emphasised info on the registry name; bracketed short name muted.
    assert as_emphasised( as_info( 'baa' ) ) in joined or as_info( 'baa' ) in joined
    assert as_subdued( ' [git.clearpool.io/cplx_core/baa]' ) in joined
    assert as_info( '@master' ) in joined or 'in use' in joined
    # Sibling leaf is muted (not info).
    assert as_subdued( '@feature' ) in joined
    assert 'dependencies in use' in joined
    assert 'potentially stale dependencies' in joined


def test_render_partitions_sections_and_keeps_unreferenced_names_normal():
    from cuppa.colourise import as_emphasised, as_info

    leaves = [
        {
            'type': 'repository',
            'dependency': 'baa',
            'short_name': 'git.clearpool.io/cplx_core/baa',
            'qualifier': '@master',
            'tool_variant': '-',
            'state': 'referenced',
            'size_bytes': 100,
            'last_used_epoch': 1000.0,
            'path': '/deps/baa@master',
            'location': 'loc-master',
        },
        {
            'type': 'repository',
            'dependency': 'orphan',
            'short_name': 'git.clearpool.io/cplx_core/orphan',
            'qualifier': '@main',
            'tool_variant': '-',
            'state': 'unreferenced',
            'size_bytes': 20,
            'last_used_epoch': 800.0,
            'path': '/deps/orphan@main',
            'location': 'loc-orphan',
        },
    ]
    tree = dependency_tree.build_tree( leaves )
    lines, _ = dependency_tree.render_tree_lines( tree )
    plain_lines = []
    import re
    for line in lines:
        plain_lines.append( re.sub( r'\x1b\[[0-9;]*m', '', line ) )
    plain = '\n'.join( plain_lines )
    assert 'referenced' in plain
    assert 'unreferenced' in plain
    # Horizontal rule between the two sections.
    assert any( set( line.strip() ) <= set( '-' ) and len( line.strip() ) > 8 for line in plain_lines )
    # Unreferenced dependency name remains visible and is emphasised.
    unref_identity = next(
            child for section in tree['sections'] if section['label'] == 'unreferenced'
            for type_node in section['children'] if type_node.get( 'kind' ) == 'type'
            for child in type_node['children'] if child.get( 'kind' ) == 'identity'
    )
    assert 'git.clearpool.io/cplx_core/orphan' in plain
    joined = '\n'.join( lines )
    # Unreferenced names are emphasised but not info/blue.
    from cuppa.colourise import colouriser
    if colouriser.use_colour:
        assert as_info( 'git.clearpool.io/cplx_core/orphan' ) not in joined
        assert as_emphasised( 'git.clearpool.io/cplx_core/orphan' ) in joined
    else:
        assert as_emphasised( 'git.clearpool.io/cplx_core/orphan' ) in joined


def test_develop_remark_on_identity_not_on_branches():
    leaves = [
        {
            'type': 'repository',
            'dependency': 'baa',
            'short_name': 'git.clearpool.io/cplx_core/baa',
            'qualifier': '@master',
            'tool_variant': '-',
            'state': 'cached',
            'size_bytes': 100,
            'last_used_epoch': 1000.0,
            'path': '/deps/baa@master',
        },
        {
            'type': 'repository',
            'dependency': 'baa',
            'short_name': 'git.clearpool.io/cplx_core/baa',
            'qualifier': '@feature',
            'tool_variant': '-',
            'state': 'cached',
            'size_bytes': 50,
            'last_used_epoch': 900.0,
            'path': '/deps/baa@feature',
        },
    ]
    tree = dependency_tree.build_tree( leaves )
    location_type = next(
            child for child in tree['sections'][0]['children']
            if child.get( 'kind' ) == 'type'
    )
    identity = next(
            child for child in location_type['children']
            if child.get( 'kind' ) == 'identity'
    )
    assert identity['remark'] == 'develop'
    leaf_remarks = [
            child.get( 'remark' ) for child in identity['children']
            if child.get( 'kind' ) == 'leaf'
    ]
    assert leaf_remarks == [ '', '' ]
    lines, _ = dependency_tree.render_tree_lines( tree )
    plain = '\n'.join( lines )
    import re
    plain = re.sub( r'\x1b\[[0-9;]*m', '', plain )
    assert 'develop' in plain
    assert 'cached' not in plain


def test_with_vcs_qualifier_appends_branch():
    assert with_vcs_qualifier(
            'git+ssh://git@git.clearpool.io/cplx_core/baa', '@master'
    ) == 'git+ssh://git@git.clearpool.io/cplx_core/baa@master'
    assert with_vcs_qualifier(
            'git+ssh://git@git.clearpool.io/cplx_core/baa@', '@master'
    ) == 'git+ssh://git@git.clearpool.io/cplx_core/baa@master'
    assert with_vcs_qualifier(
            'git+ssh://git@git.clearpool.io/cplx_core/baa@feature', '@master'
    ) == 'git+ssh://git@git.clearpool.io/cplx_core/baa@master'
    assert with_vcs_qualifier(
            'git+ssh://git@git.clearpool.io/cplx_core/baa', None
    ).endswith( '@' )


def test_gitlab_archive_name():
    assert gitlab_archive_name( 'boost', 'gcc153_rel_x86_64_cxx2c', system='debian' ) == \
        'boost_debian_gcc153_rel_x86_64_cxx2c.tar.gz'


def test_gitlab_remote_for_version_substitutes_segment():
    from cuppa.core.dependency_identity import (
        gitlab_package_from_path,
        gitlab_remote_for_version,
    )
    base = 'https://git.example/api/v4/projects/1/boost/1.91'
    assert gitlab_remote_for_version( base, '1.86' ) == \
        'https://git.example/api/v4/projects/1/boost/1.86'
    assert gitlab_package_from_path( '/deps/gcc153_rel_x86_64_cxx2c/boost/1.91' ) == \
        ( 'boost', '1.91' )


def test_backfill_gitlab_remote_locations_from_sibling():
    from cuppa.core.dependency_actions import _backfill_gitlab_remote_locations
    rows = [
        {
            'type': 'gitlab',
            'short_name': 'boost',
            'qualifier': '1.91',
            'state': 'referenced',
            'path': '/deps/gcc153_rel_x86_64_cxx2c/boost/1.91',
            'remote_location': 'https://git.example/api/v4/projects/1/boost/1.91',
        },
        {
            'type': 'gitlab',
            'short_name': 'boost',
            'qualifier': '1.86',
            'state': 'unreferenced',
            'path': '/deps/gcc142_rel_x86_64_cxx2c/boost/1.86',
            'remote_location': None,
        },
    ]
    _backfill_gitlab_remote_locations( rows, '/deps', by_path={} )
    assert rows[1]['remote_location'] == \
        'https://git.example/api/v4/projects/1/boost/1.86'


def test_backfill_gitlab_remote_from_shared_registry():
    from cuppa.core.dependency_actions import _backfill_gitlab_remote_locations
    from cuppa.core.dependency_identity import (
        gitlab_registry_base,
        gitlab_remote_for_package_version,
    )
    base = 'https://git.example/api/v4/projects/1'
    assert gitlab_registry_base( base + '/google-cloud-cpp/2.28.0' ) == base
    assert gitlab_remote_for_package_version( base, 'capy', 'develop' ) == \
        base + '/capy/develop'
    rows = [
        {
            'type': 'gitlab',
            'short_name': 'google-cloud-cpp',
            'qualifier': '2.28.0',
            'state': 'referenced',
            'path': '/deps/gcc153_rel_x86_64_cxx2c/google-cloud-cpp/2.28.0',
            'remote_location': base + '/google-cloud-cpp/2.28.0',
        },
        {
            'type': 'gitlab',
            'short_name': 'capy',
            'qualifier': 'develop',
            'state': 'unreferenced',
            'path': '/deps/gcc153_rel_x86_64_cxx2c/capy/develop',
            'remote_location': None,
        },
        {
            'type': 'gitlab',
            'short_name': 'corosio',
            'qualifier': 'develop',
            'state': 'unreferenced',
            'path': '/deps/gcc153_rel_x86_64_cxx2c/corosio/develop',
            'remote_location': None,
        },
    ]
    _backfill_gitlab_remote_locations( rows, '/deps', by_path={} )
    assert rows[1]['remote_location'] == base + '/capy/develop'
    assert rows[2]['remote_location'] == base + '/corosio/develop'


def test_backfill_gitlab_skips_when_multiple_registries():
    from cuppa.core.dependency_actions import _backfill_gitlab_remote_locations
    rows = [
        {
            'type': 'gitlab',
            'short_name': 'a',
            'qualifier': '1',
            'path': '/deps/tv/a/1',
            'remote_location': 'https://reg-a.example/api/v4/projects/1/a/1',
        },
        {
            'type': 'gitlab',
            'short_name': 'b',
            'qualifier': '1',
            'path': '/deps/tv/b/1',
            'remote_location': 'https://reg-b.example/api/v4/projects/2/b/1',
        },
        {
            'type': 'gitlab',
            'short_name': 'capy',
            'qualifier': 'develop',
            'path': '/deps/tv/capy/develop',
            'remote_location': None,
        },
    ]
    _backfill_gitlab_remote_locations( rows, '/deps', by_path={} )
    assert rows[2]['remote_location'] is None


def test_gitlab_verbose_locations_on_version_and_archive_leaf():
    leaves = [
        {
            'type': 'gitlab',
            'dependency': 'boost_package',
            'short_name': 'boost',
            'qualifier': '1.91',
            'tool_variant': 'gcc153_rel_x86_64_cxx2c',
            'state': 'referenced',
            'size_bytes': 100,
            'last_used_epoch': 1000.0,
            'path': '/deps/gcc153_rel_x86_64_cxx2c/boost/1.91',
            'remote_location': 'https://git.example/api/v4/projects/1/boost/1.91',
            'package_archive': 'boost_debian_gcc153_rel_x86_64_cxx2c.tar.gz',
            'has_download': True,
        },
    ]
    tree = dependency_tree.build_tree( leaves )
    gitlab_type = next(
            child for child in tree['sections'][0]['children']
            if child.get( 'kind' ) == 'type' and 'gitlab' in ( child.get( 'label' ) or '' )
    )
    identity = next(
            child for child in gitlab_type['children'] if child.get( 'kind' ) == 'identity'
    )
    assert identity.get( 'location' ) in ( '', None )
    version = next(
            child for child in identity['children'] if child.get( 'kind' ) == 'version'
    )
    # Registry URL is not a downloads-root file — no [D] on the version row.
    assert version['location'] == 'https://git.example/api/v4/projects/1/boost/1.91'
    leaf = version['children'][0]
    from cuppa.core.dependency_identity import DOWNLOAD_MARK
    assert leaf['location'] == \
        '{} boost_debian_gcc153_rel_x86_64_cxx2c.tar.gz'.format( DOWNLOAD_MARK )


def test_location_leaf_location_includes_branch():
    leaves = [
        {
            'type': 'repository',
            'dependency': 'baa',
            'short_name': 'git.clearpool.io/cplx_core/baa',
            'qualifier': '@master',
            'tool_variant': '-',
            'state': 'referenced',
            'size_bytes': 10,
            'last_used_epoch': 1000.0,
            'path': '/deps/baa@master',
            'remote_location': 'git+ssh://git@git.clearpool.io/cplx_core/baa@',
            'source_url': 'ssh://git@git.clearpool.io/cplx_core/baa',
        },
        {
            'type': 'repository',
            'dependency': 'baa',
            'short_name': 'git.clearpool.io/cplx_core/baa',
            'qualifier': '@feature',
            'tool_variant': '-',
            'state': 'unreferenced',
            'size_bytes': 5,
            'last_used_epoch': 900.0,
            'path': '/deps/baa@feature',
            'remote_location': 'git+ssh://git@git.clearpool.io/cplx_core/baa@',
            'source_url': 'ssh://git@git.clearpool.io/cplx_core/baa',
        },
    ]
    tree = dependency_tree.build_tree( leaves )
    location_type = next(
            child for child in tree['sections'][0]['children']
            if child.get( 'kind' ) == 'type'
    )
    identity = next(
            child for child in location_type['children'] if child.get( 'kind' ) == 'identity'
    )
    # Identity LOCATION is the bare repo URL; leaves carry URL@branch.
    assert identity.get( 'location' ) in (
            'git+ssh://git@git.clearpool.io/cplx_core/baa',
            'ssh://git@git.clearpool.io/cplx_core/baa',
    )
    by_label = {
            child['label']: child['location']
            for child in identity['children'] if child.get( 'kind' ) == 'leaf'
    }
    assert by_label['@master'].endswith( '@master' )
    assert by_label['@feature'].endswith( '@feature' )
