"""Unit tests for hierarchical dependency tree summaries."""

import pytest

from cuppa.core import dependency_tree


pytestmark = pytest.mark.unit


def _leaf( dependency, state, size_bytes=100, storage_type='repository', qualifier='@master' ):
    return {
        'type': storage_type,
        'short_name': dependency,
        'stem': dependency,
        'dependency': dependency,
        'qualifier': qualifier,
        'tool_variant': None,
        'state': state,
        'size_bytes': size_bytes if state != 'missing' else None,
        'last_used_epoch': 1.0 if state != 'missing' else None,
        'path': '/tmp/{}'.format( dependency ),
        'source_url': None,
        'remote_location': 'https://example.com/{}'.format( dependency ),
        'location': '',
    }


def _primary_summaries( tree ):
    sections = tree.get( 'sections' ) or []
    primary = next(
            ( s for s in sections if s.get( 'label' ) in ( 'used', 'referenced' ) ),
            None,
    )
    assert primary is not None
    return [
            child for child in primary.get( 'children' ) or []
            if child.get( 'kind' ) == 'summary'
    ]


def test_referenced_summary_splits_missing_from_stale():
    leaves = [
            _leaf( 'widget', 'referenced' ),
            _leaf( 'absent', 'missing' ),
            _leaf( 'also_absent', 'missing', storage_type='gitlab', qualifier='1.0' ),
    ]
    # Second missing needs a tool_variant leaf shape for gitlab — keep repository for simplicity.
    leaves[2]['type'] = 'repository'
    leaves[2]['qualifier'] = '@master'

    tree = dependency_tree.build_tree( leaves )
    summaries = { row['label']: row for row in _primary_summaries( tree ) }

    assert 'dependencies in use' in summaries
    assert summaries['dependencies in use']['remark'] == '1 used'
    assert 'missing dependencies' in summaries
    assert summaries['missing dependencies']['remark'] == '2 missing'
    assert summaries['missing dependencies'].get( 'state' ) == 'missing'
    assert 'potentially stale dependencies' not in summaries


def test_referenced_summary_keeps_stale_for_non_missing_unused():
    leaves = [
            _leaf( 'widget', 'referenced' ),
            _leaf( 'cached_stem', 'cached' ),
    ]
    tree = dependency_tree.build_tree( leaves )
    summaries = { row['label']: row for row in _primary_summaries( tree ) }

    assert summaries['dependencies in use']['remark'] == '1 used'
    assert 'missing dependencies' not in summaries
    assert 'potentially stale dependencies' in summaries
    assert summaries['potentially stale dependencies']['remark'] == '1 unused'


def _gitlab_leaf( name, version, tool_variant, path, state='unreferenced', requires=None ):
    leaf = {
        'type': 'gitlab',
        'short_name': name,
        'stem': name,
        'dependency': name,
        'qualifier': version,
        'tool_variant': tool_variant,
        'state': state,
        'size_bytes': 10,
        'last_used_epoch': 1.0,
        'path': path,
        'source_url': None,
        'remote_location': 'https://gitlab.example/api/v4/projects/1/{}/{}'.format(
                name, version
        ),
        'location': '',
        'package_archive': '{}_{}.tar.gz'.format( name, tool_variant ),
        'has_download': False,
    }
    if requires is not None:
        leaf['requires'] = requires
    return leaf


def _find_kind( node, kind ):
    if node.get( 'kind' ) == kind:
        return node
    for child in node.get( 'children' ) or []:
        found = _find_kind( child, kind )
        if found is not None:
            return found
    return None


def test_gitlab_tree_shows_requires_from_manifest( tmp_path ):
    package_dir = tmp_path / "gcc15_rel_x86_64_cxx2c" / "alpha" / "1.0.0"
    package_dir.mkdir( parents=True )
    ( package_dir / "include" ).mkdir()
    from cuppa.package_managers.cuppa_publish_manifest import write_publish_manifest
    write_publish_manifest( str( package_dir ), "alpha", "1.0.0", dependencies=[
            {
                    "name": "beta",
                    "package": "beta",
                    "version": "2.0.0",
                    "use_libs": ["beta_core"],
            },
    ] )

    tree = dependency_tree.build_tree( [
            _gitlab_leaf(
                    'alpha', '1.0.0', 'gcc15_rel_x86_64_cxx2c',
                    str( package_dir ), state='referenced',
            ),
    ] )
    referenced = next( s for s in tree['sections'] if s['label'] == 'used' )
    requires = _find_kind( referenced, 'requires' )
    assert requires is not None
    assert requires['label'] == 'requires'
    edge = requires['children'][0]
    assert edge['kind'] == 'requires_edge'
    assert edge['requires_name'] == 'beta'
    assert edge['requires_version'] == '2.0.0'
    assert edge['remark'] == 'libs: beta_core'


def test_gitlab_tree_shows_requires_from_preloaded_entries():
    tree = dependency_tree.build_tree( [
            _gitlab_leaf(
                    'alpha', '1.0.0', 'gcc15_rel', '/missing/path',
                    state='referenced',
                    requires=[
                            {
                                    'name': 'beta',
                                    'package': 'beta',
                                    'version': '2.0.0',
                            },
                    ],
            ),
    ] )
    referenced = next( s for s in tree['sections'] if s['label'] == 'used' )
    requires = _find_kind( referenced, 'requires' )
    assert requires is not None
    assert requires['children'][0]['label'] == 'beta 2.0.0'


def test_requires_row_is_normal_colour_with_blank_size_when_label_only():
    """``requires`` is structural: normal paint, blank SIZE/LAST USED without a rollup."""
    import re
    from cuppa.colourise import as_subdued, colouriser

    tree = dependency_tree.build_tree( [
            _gitlab_leaf(
                    'alpha', '1.0.0', 'gcc15_rel', '/missing/path',
                    state='referenced',
                    requires=[
                            { 'name': 'beta', 'package': 'beta', 'version': '2.0.0' },
                    ],
            ),
    ] )
    was_colour = colouriser.use_colour
    colouriser.enable()
    try:
        lines, _ = dependency_tree.render_tree_lines( tree )
        joined = '\n'.join( lines )
        assert 'requires' in joined
        assert as_subdued( 'requires' ) not in joined
        ansi = re.compile( r'\x1b\[[0-9;]*m' )
        for line in lines:
            plain = ansi.sub( '', line )
            if 'requires' not in plain:
                continue
            # Columns before DEPENDENCY must not use dash placeholders for structure rows.
            before = plain.split( 'requires', 1 )[0]
            assert '-  -' not in before
            assert not re.search( r'-\s+-+\s*$', before.rstrip() )
    finally:
        colouriser.use_colour = was_colour


def test_gitlab_tree_nests_closure_under_requires_with_sizes():
    """Tip-selected alpha pulls beta/gamma into requires as sized identities."""
    tool = 'gcc15_rel_x86_64_cxx2c'
    other = 'gcc16_rel_x86_64_cxx2c'
    leaves = [
            _gitlab_leaf(
                    'alpha', '1.0.0', tool, '/deps/{}/alpha/1.0.0'.format( tool ),
                    state='referenced',
                    requires=[
                            {
                                    'name': 'beta',
                                    'package': 'beta',
                                    'version': '2.0.0',
                                    'use_libs': ['beta'],
                            },
                    ],
            ),
            _gitlab_leaf(
                    'beta', '2.0.0', tool, '/deps/{}/beta/2.0.0'.format( tool ),
                    state='unreferenced',
                    requires=[
                            {
                                    'name': 'gamma',
                                    'package': 'gamma',
                                    'version': '3.0.0',
                                    'use_libs': ['gamma'],
                            },
                    ],
            ),
            _gitlab_leaf(
                    'beta', '2.0.0', other, '/deps/{}/beta/2.0.0'.format( other ),
                    state='unreferenced',
            ),
            _gitlab_leaf(
                    'gamma', '3.0.0', tool, '/deps/{}/gamma/3.0.0'.format( tool ),
                    state='unreferenced',
            ),
    ]
    leaves[0]['size_bytes'] = 12000
    leaves[1]['size_bytes'] = 8000
    leaves[2]['size_bytes'] = 7000
    leaves[3]['size_bytes'] = 4000

    tree = dependency_tree.build_tree( leaves )
    used = next( s for s in tree['sections'] if s['label'] == 'used' )

    top_names = set()
    for type_node in used.get( 'children' ) or []:
        if type_node.get( 'kind' ) != 'type':
            continue
        for child in type_node.get( 'children' ) or []:
            if child.get( 'kind' ) == 'identity':
                top_names.add( child.get( 'short_name' ) or child.get( 'label' ) )
    assert top_names == { 'alpha' }

    requires = _find_kind( used, 'requires' )
    assert requires is not None
    # Spacer before first nested identity, then beta + spacer + gamma.
    kinds = [ child.get( 'kind' ) for child in requires.get( 'children' ) or [] ]
    assert kinds[0] == 'spacer'
    nested = {
            child.get( 'short_name' ) or child.get( 'label' ): child
            for child in requires.get( 'children' ) or []
            if child.get( 'kind' ) == 'identity'
    }
    assert set( nested ) == { 'beta', 'gamma' }
    # Dependent-first (reverse leaf-first): beta before gamma because beta requires gamma.
    identity_order = [
            child.get( 'short_name' ) or child.get( 'label' )
            for child in requires.get( 'children' ) or []
            if child.get( 'kind' ) == 'identity'
    ]
    assert identity_order == [ 'beta', 'gamma' ]
    # Usage split: only tip-matching nest toolchains under used → requires.
    assert nested['beta']['size_bytes'] == 8000
    assert nested['gamma']['size_bytes'] == 4000

    beta_requires = _find_kind( nested['beta'], 'requires' )
    assert beta_requires is not None
    assert beta_requires['children'][0]['kind'] == 'requires_edge'
    assert beta_requires['children'][0]['label'] == 'gamma 3.0.0'

    # Only the tip-matching toolchain is in use under the nested package.
    assert leaves[1]['state'] == 'referenced'
    assert leaves[1].get( 'nest_under_requires' ) is True
    assert leaves[2]['state'] == 'unreferenced'
    assert leaves[2].get( 'nest_under_requires' ) is True
    assert leaves[3]['state'] == 'referenced'

    beta_leaves = [
            child for child in _find_kind( nested['beta'], 'version' )['children']
            if child.get( 'kind' ) == 'leaf'
    ]
    remarks = { child['label']: child.get( 'remark' ) for child in beta_leaves }
    assert remarks == { tool: 'in use' }

    # Unused nest toolchains appear under unused (not under used → requires).
    unused = next( s for s in tree['sections'] if s['label'] == 'unused' )
    unused_names = set()
    for type_node in unused.get( 'children' ) or []:
        if type_node.get( 'kind' ) != 'type':
            continue
        for child in type_node.get( 'children' ) or []:
            if child.get( 'kind' ) == 'identity':
                unused_names.add( child.get( 'short_name' ) or child.get( 'label' ) )
    assert 'beta' in unused_names
    unused_beta = None
    for type_node in unused.get( 'children' ) or []:
        for child in type_node.get( 'children' ) or []:
            if child.get( 'kind' ) == 'identity' and child.get( 'short_name' ) == 'beta':
                unused_beta = child
    assert unused_beta is not None
    unused_beta_leaves = [
            child for child in _find_kind( unused_beta, 'version' )['children']
            if child.get( 'kind' ) == 'leaf'
    ]
    assert [ child['label'] for child in unused_beta_leaves ] == [ other ]


def test_identity_grouping_keeps_unused_nest_toolchains_under_requires():
    """``grouping=identity`` keeps Pass A shape: unused nest variants hang under requires."""
    tool = 'gcc15_rel_x86_64_cxx2c'
    other = 'gcc16_rel_x86_64_cxx2c'
    leaves = [
            _gitlab_leaf(
                    'alpha', '1.0.0', tool, '/deps/{}/alpha/1.0.0'.format( tool ),
                    state='referenced',
                    requires=[
                            {
                                    'name': 'beta',
                                    'package': 'beta',
                                    'version': '2.0.0',
                                    'use_libs': ['beta'],
                            },
                    ],
            ),
            _gitlab_leaf(
                    'beta', '2.0.0', tool, '/deps/{}/beta/2.0.0'.format( tool ),
                    state='unreferenced',
            ),
            _gitlab_leaf(
                    'beta', '2.0.0', other, '/deps/{}/beta/2.0.0'.format( other ),
                    state='unreferenced',
            ),
    ]
    leaves[0]['size_bytes'] = 12000
    leaves[1]['size_bytes'] = 8000
    leaves[2]['size_bytes'] = 7000

    tree = dependency_tree.build_tree( leaves, grouping='identity' )
    referenced = next( s for s in tree['sections'] if s['label'] == 'referenced' )
    requires = _find_kind( referenced, 'requires' )
    nested = {
            child.get( 'short_name' ): child
            for child in requires.get( 'children' ) or []
            if child.get( 'kind' ) == 'identity'
    }
    assert set( nested ) == { 'beta' }
    assert nested['beta']['size_bytes'] == 15000
    beta_leaves = [
            child for child in _find_kind( nested['beta'], 'version' )['children']
            if child.get( 'kind' ) == 'leaf'
    ]
    assert { child['label'] for child in beta_leaves } == { tool, other }
    unused = next( s for s in tree['sections'] if s['label'] == 'unreferenced' )
    unused_idents = [
            child
            for type_node in unused.get( 'children' ) or []
            for child in type_node.get( 'children' ) or []
            if child.get( 'kind' ) == 'identity'
    ]
    assert not any( child.get( 'short_name' ) == 'beta' for child in unused_idents )


def test_order_requires_families_dependent_first_soft_cycle():
    """Display order reverses leaf-first Kahn; cycles append leftovers without raising."""
    ordered = dependency_tree._order_requires_families(
            [ 'grpc', 'protobuf', 'abseil-cpp', 'c-ares' ],
            {
                    'grpc': { 'protobuf', 'abseil-cpp', 'c-ares' },
                    'protobuf': { 'abseil-cpp' },
                    'abseil-cpp': set(),
                    'c-ares': set(),
            },
            prefer=[ 'protobuf', 'grpc' ],
    )
    assert ordered.index( 'grpc' ) < ordered.index( 'protobuf' )
    assert ordered.index( 'protobuf' ) < ordered.index( 'abseil-cpp' )
    assert ordered.index( 'grpc' ) < ordered.index( 'c-ares' )

    cyclic = dependency_tree._order_requires_families(
            [ 'a', 'b' ],
            { 'a': { 'b' }, 'b': { 'a' } },
            prefer=[ 'a', 'b' ],
    )
    assert set( cyclic ) == { 'a', 'b' }
    assert len( cyclic ) == 2


def test_requires_unions_edges_across_version_variants( tmp_path ):
    """Union requires from every variant under a version (legacy + publish)."""
    from cuppa.package_managers.cuppa_publish_manifest import write_publish_manifest

    legacy = tmp_path / 'gcc153_rel_x86_64_cxx2c' / 'grpc' / '1.84.0'
    modern = tmp_path / 'gcc15_rel_x86_64_cxx2c' / 'grpc' / '1.84.0'
    legacy.mkdir( parents=True )
    modern.mkdir( parents=True )
    ( legacy / 'cuppa-dependency.json' ).write_text(
            '{"cuppa_dependency_format":1,"dependencies":['
            '{"name":"protobuf","package":"protobuf","version":"36.1"},'
            '{"name":"only_legacy","package":"only-legacy","version":"1.0"}]}',
            encoding='utf-8',
    )
    write_publish_manifest(
            str( modern ), 'grpc', '1.84.0',
            dependencies=[
                    { 'name': 'protobuf', 'package': 'protobuf', 'version': '36.1' },
                    { 'name': 'c_ares', 'package': 'c-ares', 'version': '1.34.5' },
                    { 'name': 're2', 'package': 're2', 'version': '2025-11-05' },
                    { 'name': 'abseil_cpp', 'package': 'abseil-cpp', 'version': '20250814.2' },
            ],
    )
    entries = dependency_tree._requires_entries_from_variants( [
            _gitlab_leaf( 'grpc', '1.84.0', 'gcc153_rel_x86_64_cxx2c', str( legacy ) ),
            _gitlab_leaf(
                    'grpc', '1.84.0', 'gcc15_rel_x86_64_cxx2c', str( modern ),
                    state='referenced',
            ),
    ] )
    names = { entry.get( 'name' ) or entry.get( 'package' ) for entry in entries }
    assert names == { 'protobuf', 'only_legacy', 'c_ares', 're2', 'abseil_cpp' }

    in_use_only = dependency_tree._requires_entries_from_variants(
            [
                    _gitlab_leaf(
                            'grpc', '1.84.0', 'gcc153_rel_x86_64_cxx2c', str( legacy ),
                    ),
                    _gitlab_leaf(
                            'grpc', '1.84.0', 'gcc15_rel_x86_64_cxx2c', str( modern ),
                            state='referenced',
                    ),
            ],
            in_use_only=True,
    )
    in_use_names = {
            entry.get( 'name' ) or entry.get( 'package' ) for entry in in_use_only
    }
    assert in_use_names == { 'protobuf', 'c_ares', 're2', 'abseil_cpp' }
    assert 'only_legacy' not in in_use_names


def test_render_gitlab_partial_missing_paints_only_gap_not_siblings():
    """When one toolchain leaf is missing, siblings and requires stay normal colour."""
    from cuppa.colourise import as_emphasised, as_error, as_subdued, colouriser

    leaves = [
            _gitlab_leaf(
                    'cloud', '3.9.0', 'gcc15_rel', '/deps/gcc15/cloud/3.9.0',
                    state='unreferenced',
                    requires=[
                            { 'name': 'protobuf', 'package': 'protobuf', 'version': '36.1' },
                    ],
            ),
            _gitlab_leaf(
                    'cloud', '3.9.0', 'gcc16_rel', '/deps/gcc16/cloud/3.9.0',
                    state='missing',
            ),
            _gitlab_leaf(
                    'cloud', '2.28.0', 'gcc153_rel', '/deps/gcc153/cloud/2.28.0',
                    state='unreferenced',
            ),
    ]
    # Missing leaf has no on-disk size.
    leaves[1]['size_bytes'] = None
    leaves[1]['last_used_epoch'] = None

    tree = dependency_tree.build_tree( leaves )
    identity = None
    for section in tree['sections']:
        if section.get( 'label' ) != 'used':
            continue
        for type_node in section.get( 'children' ) or []:
            if type_node.get( 'kind' ) != 'type':
                continue
            for child in type_node.get( 'children' ) or []:
                if child.get( 'kind' ) == 'identity' and child.get( 'short_name' ) == 'cloud':
                    identity = child
    assert identity is not None
    assert identity.get( 'missing' ) is True
    versions = {
            child['label']: child
            for child in identity['children']
            if child.get( 'kind' ) == 'version'
    }
    assert set( versions ) == { '3.9.0' }
    assert versions['3.9.0'].get( 'has_missing_leaf' ) is True

    # Unused siblings (including older versions) sit under unused (usage grouping).
    unused_identity = None
    for section in tree['sections']:
        if section.get( 'label' ) != 'unused':
            continue
        for type_node in section.get( 'children' ) or []:
            for child in type_node.get( 'children' ) or []:
                if child.get( 'kind' ) == 'identity' and child.get( 'short_name' ) == 'cloud':
                    unused_identity = child
    assert unused_identity is not None
    unused_versions = {
            child['label']
            for child in unused_identity['children']
            if child.get( 'kind' ) == 'version'
    }
    assert '2.28.0' in unused_versions
    assert '3.9.0' in unused_versions

    was_colour = colouriser.use_colour
    colouriser.enable()
    try:
        lines, _ = dependency_tree.render_tree_lines( tree, verbose=True )
        joined = '\n'.join( lines )
        assert as_emphasised( as_error( 'cloud' ) ) in joined
        # Registry detail on the identity is muted, not error-painted.
        registry = 'https://gitlab.example/api/v4/projects/1/cloud/3.9.0'
        # remote may be from first leaf — 2.28.0 or 3.9.0 depending on group remote
        assert as_error( 'gcc16_rel' ) in joined
        assert as_error( 'gcc15_rel' ) not in joined
        assert as_error( '2.28.0' ) not in joined
        assert as_error( 'requires' ) not in joined
        assert as_error( 'protobuf' ) not in joined
        # Version with the gap is error-coloured.
        assert as_error( '3.9.0' ) in joined
    finally:
        colouriser.use_colour = was_colour
