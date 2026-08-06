"""Unit tests for dependency removal helpers (Slice D)."""

import pytest

from cuppa.core import dependency_inventory, dependency_removal
from cuppa.utility import storage


pytestmark = pytest.mark.unit


def test_parse_dependency_names_splits_and_strips():
    assert dependency_removal.parse_dependency_names( 'widget, boost_package' ) == [
            'widget', 'boost_package',
    ]
    assert dependency_removal.parse_dependency_names( 'widget' ) == [ 'widget' ]
    assert dependency_removal.parse_dependency_names( '' ) == []
    assert dependency_removal.parse_dependency_names( None ) == []


def test_resolve_requested_names_unknown_error():
    cuppa_env = {
        'remove_dependencies': 'widgt',
        'dependencies': { 'widget': object(), 'boost_package': object(), 'boost': object() },
        'default_dependencies': [ 'widget', 'boost_package' ],
        'declared_dependencies': [ 'widget', 'boost_package' ],
    }
    names, error = dependency_removal.resolve_requested_names( cuppa_env )
    assert names == []
    assert isinstance( error, dependency_removal.UnknownDependencyNames )
    assert error.unknown == ( 'widgt', )
    assert 'widget' in error.project_used
    assert 'boost_package' in error.project_used


def test_resolve_requested_names_rejects_registry_only_builtin():
    """Built-in ``boost`` in the registry is not removable unless the project uses it."""
    cuppa_env = {
        'remove_dependencies': 'boost',
        'dependencies': { 'boost': object(), 'boost_package': object() },
        'default_dependencies': [ 'boost_package' ],
        'declared_dependencies': [ 'boost_package' ],
    }
    names, error = dependency_removal.resolve_requested_names( cuppa_env )
    assert names == []
    assert isinstance( error, dependency_removal.UnknownDependencyNames )
    assert error.unknown == ( 'boost', )
    assert error.project_used == ( 'boost_package', )


def test_resolve_requested_names_accepts_builtin_when_defaulted():
    cuppa_env = {
        'remove_dependencies': 'boost',
        'dependencies': { 'boost': object(), 'boost_package': object() },
        'default_dependencies': [ 'boost' ],
        'declared_dependencies': [],
    }
    names, error = dependency_removal.resolve_requested_names( cuppa_env )
    assert error is None
    assert names == [ 'boost' ]


def test_resolve_requested_names_accepts_selectors_and_stores_tokens():
    cuppa_env = {
        'remove_dependencies': '[source]boost,[gitlab]boost_package',
        'dependencies': { 'boost': object(), 'boost_package': object() },
        'default_dependencies': [ 'boost', 'boost_package' ],
        'declared_dependencies': [],
    }
    names, error = dependency_removal.resolve_requested_names( cuppa_env )
    assert error is None
    assert names == [ 'boost', 'boost_package' ]
    assert cuppa_env['dependency_tokens'] == [
            ( 'archive', 'boost', None ),
            ( 'gitlab', 'boost_package', None ),
    ]


def test_filter_plan_by_tokens_restricts_type_and_keeps_sibling_context():
    cuppa_env = {
        'dependency_tokens': [ ( 'archive', 'boost', '1.91.0' ) ],
    }
    targets = [
            dependency_removal.RemovalTarget(
                    dependency='boost',
                    path='/deps/boost@1.91.0',
                    qualifier='1.91.0',
                    tool_variant=None,
                    storage_type='archive',
                    size_bytes=10,
                    label='boost@1.91.0',
                    extra_paths=(),
            ),
            dependency_removal.RemovalTarget(
                    dependency='boost',
                    path='/deps/boost@1.89.0',
                    qualifier='1.89.0',
                    tool_variant=None,
                    storage_type='archive',
                    size_bytes=8,
                    label='boost@1.89.0',
                    extra_paths=(),
            ),
            dependency_removal.RemovalTarget(
                    dependency='boost',
                    path='/deps/gcc/boost/1.91.0',
                    qualifier='1.91.0',
                    tool_variant='gcc',
                    storage_type='gitlab',
                    size_bytes=12,
                    label='gcc/boost/1.91.0',
                    extra_paths=(),
            ),
    ]
    (
            kept, leftovers, archives, downloads, download_leftovers,
    ) = dependency_removal._filter_plan_by_tokens(
            cuppa_env, targets, [], [],
    )
    assert [ item.path for item in kept ] == [ '/deps/boost@1.91.0' ]
    assert [ item.path for item in leftovers ] == [ '/deps/boost@1.89.0' ]
    assert archives == []
    assert downloads == []
    assert download_leftovers == []


def test_item_matches_any_token_typed_identity():
    item = dependency_removal.RemovalTarget(
            dependency='boost',
            path='/deps/boost@1.91.0',
            qualifier='1.91.0',
            tool_variant=None,
            storage_type='archive',
            size_bytes=1,
            label=None,
            extra_paths=(),
    )
    assert dependency_removal._item_matches_any_token(
            item, [ ( 'archive', 'boost', None ) ]
    )
    assert not dependency_removal._item_matches_any_token(
            item, [ ( 'gitlab', 'boost', None ) ]
    )
    assert dependency_removal._item_matches_any_token(
            item, [ ( None, 'boost', None ) ]
    )


def test_resolve_requested_names_purge_flags_use_same_gate():
    cuppa_env = {
        'purge_dependencies': 'widgt',
        'default_dependencies': [ 'widget' ],
        'declared_dependencies': [],
        'dependencies': { 'widget': object(), 'boost': object() },
    }
    names, error = dependency_removal.resolve_requested_names( cuppa_env )
    assert names == []
    assert isinstance( error, dependency_removal.UnknownDependencyNames )
    assert error.unknown == ( 'widgt', )

    cuppa_env = {
        'purge_all_dependencies': True,
        'default_dependencies': [ 'widget' ],
        'declared_dependencies': [ 'boost_package' ],
        'dependencies': { 'widget': object(), 'boost_package': object(), 'boost': object() },
    }
    names, error = dependency_removal.resolve_requested_names( cuppa_env )
    assert error is None
    assert names == [ 'widget', 'boost_package' ]


def test_purge_and_remove_combined():
    assert dependency_removal.purge_and_remove_combined( {
        'purge_dependencies': 'widget',
        'remove_dependencies': 'widget',
    } )
    assert dependency_removal.purge_and_remove_combined( {
        'purge_all_dependencies': True,
        'remove_all_dependencies': True,
    } )
    assert not dependency_removal.purge_and_remove_combined( {
        'purge_dependencies': 'widget',
    } )
    assert not dependency_removal.purge_and_remove_combined( {
        'remove_dependencies': 'widget',
    } )


def test_conflicting_dependency_modes_includes_wipe():
    assert dependency_removal.conflicting_dependency_modes( {
        'wipe_dependencies': 'widget',
        'remove_dependencies': 'widget',
    } ) == [ 'remove', 'wipe' ]
    assert dependency_removal.conflicting_dependency_modes( {
        'force_wipe_all_dependencies': True,
        'purge_dependencies': 'widget',
    } ) == [ 'purge', 'wipe' ]
    assert dependency_removal.conflicting_dependency_modes( {
        'force_wipe_unreferenced_dependencies': True,
        'wipe_dependencies': 'widget',
    } ) == [ 'wipe', 'force-wipe-unreferenced' ]
    assert dependency_removal.conflicting_dependency_modes( {
        'force_wipe_dependencies': 'boost/1.86.0',
        'wipe_dependencies': 'boost',
    } ) == [ 'wipe', 'force-wipe' ]
    assert dependency_removal.conflicting_dependency_modes( {
        'wipe_dependencies': 'widget',
    } ) is None


def test_parse_force_wipe_tokens():
    tokens, error = dependency_removal.parse_force_wipe_tokens(
            'boost/1.86.0, fmt/@11.1.1'
    )
    assert error is None
    assert tokens == [
            ( None, 'boost', '1.86.0' ),
            ( None, 'fmt', '@11.1.1' ),
    ]
    tokens, error = dependency_removal.parse_force_wipe_tokens( '[source]boost/1.8*' )
    assert error is None
    assert tokens == [ ( 'archive', 'boost', '1.8*' ) ]
    tokens, error = dependency_removal.parse_force_wipe_tokens( 'boost' )
    assert error is None
    assert tokens == [ ( None, 'boost', None ) ]
    tokens, error = dependency_removal.parse_force_wipe_tokens( '' )
    assert tokens == []
    assert error


def test_row_matches_force_token():
    row = {
        'short_name': 'boost',
        'dependency': 'boost',
        'qualifier': '1.86.0',
        'type': 'archive',
        'path': '/tmp/boost_1_86_0',
    }
    assert dependency_removal._row_matches_force_token( row, 'boost', '1.86.0' )
    assert not dependency_removal._row_matches_force_token( row, 'boost', '1.91.0' )
    assert dependency_removal._row_matches_force_token( row, 'boost', '1.8*' )
    assert dependency_removal._row_matches_force_token( row, 'boost', '1.86.?' )
    assert not dependency_removal._row_matches_force_token( row, 'boost', '1.9*' )
    assert dependency_removal._row_matches_force_token( row, 'bo*', '1.86.0' )
    loc = {
        'short_name': 'fmt',
        'dependency': 'fmt',
        'qualifier': '11.1.1',
        'type': 'repository',
        'path': '/tmp/fmt@11.1.1',
    }
    assert dependency_removal._row_matches_force_token( loc, 'fmt', '@11.1.1' )
    assert dependency_removal._row_matches_force_token( loc, 'fmt', '11.1.1' )
    assert dependency_removal._row_matches_force_token( loc, 'fmt', '@11*' )
    assert not dependency_removal._row_matches_force_token( loc, 'fmt', '@12*' )


def test_force_token_is_wildcard():
    assert not dependency_removal.force_token_is_wildcard( 'boost', '1.86.0' )
    assert dependency_removal.force_token_is_wildcard( 'boost', '1.8*' )
    assert dependency_removal.force_token_is_wildcard( 'bo?st', '1.86.0' )
    assert dependency_removal.force_token_is_wildcard( 'boost', '1.8[6-9]*' )


def test_collect_force_wipe_context_keeps_sibling_leaves( tmp_path ):
    root = tmp_path / 'dependencies'
    downloads = tmp_path / 'downloads'
    root.mkdir()
    downloads.mkdir()
    old = root / 'boost_1_86_0'
    keep = root / 'boost_1_91_0'
    old.mkdir()
    keep.mkdir()
    ( old / 'x' ).write_text( 'old' )
    ( keep / 'x' ).write_text( 'keep-keep-keep' )
    old_archive = downloads / 'boost_1_86_0.tar.gz'
    keep_archive = downloads / 'boost_1_91_0.tar.gz'
    old_archive.write_bytes( b'old-archive' )
    keep_archive.write_bytes( b'keep-archive-bytes' )

    rows = [
            {
                'short_name': 'boost',
                'dependency': 'boost',
                'qualifier': '1.86.0',
                'type': 'archive',
                'path': str( old ),
                'size_bytes': dependency_removal._measure_bytes( str( old ) ),
            },
            {
                'short_name': 'boost',
                'dependency': 'boost',
                'qualifier': '1.91.0',
                'type': 'archive',
                'path': str( keep ),
                'size_bytes': dependency_removal._measure_bytes( str( keep ) ),
            },
            {
                'short_name': 'fmt',
                'dependency': 'fmt',
                'qualifier': '11.1.1',
                'type': 'repository',
                'path': str( root / 'fmt@11.1.1' ),
                'size_bytes': 0,
            },
    ]
    ( root / 'fmt@11.1.1' ).mkdir()
    dl_rows = [
            {
                'role': 'archive',
                'short_name': 'boost',
                'dependency': 'boost',
                'qualifier': '1.86.0',
                'type': 'archive',
                'path': str( old_archive ),
                'size_bytes': old_archive.stat().st_size,
                'label': old_archive.name,
            },
            {
                'role': 'archive',
                'short_name': 'boost',
                'dependency': 'boost',
                'qualifier': '1.91.0',
                'type': 'archive',
                'path': str( keep_archive ),
                'size_bytes': keep_archive.stat().st_size,
                'label': keep_archive.name,
            },
    ]
    targets = [ dependency_removal._target_from_row( rows[0] ) ]
    download_targets = [ dependency_removal._download_from_row( dl_rows[0] ) ]
    leftovers, download_leftovers = dependency_removal._collect_force_wipe_context(
            rows, dl_rows, targets, download_targets,
    )
    assert [ item.path for item in leftovers ] == [ str( keep ) ]
    assert [ item.path for item in download_leftovers ] == [ str( keep_archive ) ]

    out = __import__( 'io' ).StringIO()
    outcomes = {
            storage.real_path( str( old ) ): { 'result': 'removed' },
            storage.real_path( str( old_archive ) ): { 'result': 'removed' },
    }
    dependency_removal._write_removal_tree(
            out, targets, leftovers, outcomes, planning=True, root=str( root ),
            downloads=download_targets, download_leftovers=download_leftovers,
            downloads_root=str( downloads ),
    )
    text = out.getvalue()
    parent_line = next(
            line for line in text.splitlines()
            if line.strip().endswith( 'boost' ) and 'SIZE' not in line
    )
    assert 'would rm' not in parent_line.lower()
    assert 'boost_1_91_0' in text
    assert 'would rm' in text.lower()


def test_parent_rollup_result_mixed_leaves_blank():
    assert dependency_removal._parent_rollup_result( [ 'would_rm', 'would_rm' ] ) == 'would rm'
    assert dependency_removal._parent_rollup_result( [ 'would_rm', 'left' ] ) == ''
    assert dependency_removal._parent_rollup_result( [ 'left', 'left' ] ) == ''


def test_removal_age_width_fits_double_digit_months():
    """Fixed LAST USED width must fit the longest ``relative_age`` form."""
    assert len( '21 months ago' ) <= dependency_removal.AGE_WIDTH
    assert len( '10 months ago' ) <= dependency_removal.AGE_WIDTH
    assert len( storage.relative_age( 0, now=700 * 86400 ) ) <= dependency_removal.AGE_WIDTH


def test_resolve_requested_names_wipe_flags_use_same_gate():
    cuppa_env = {
        'wipe_dependencies': 'widgt',
        'default_dependencies': [ 'widget' ],
        'declared_dependencies': [],
        'dependencies': { 'widget': object(), 'boost': object() },
    }
    names, error = dependency_removal.resolve_requested_names( cuppa_env )
    assert names == []
    assert isinstance( error, dependency_removal.UnknownDependencyNames )

    cuppa_env = {
        'force_wipe_all_dependencies': True,
        'default_dependencies': [ 'widget' ],
        'declared_dependencies': [ 'boost_package' ],
        'dependencies': { 'widget': object(), 'boost_package': object(), 'boost': object() },
    }
    names, error = dependency_removal.resolve_requested_names( cuppa_env )
    assert error is None
    assert names == [ 'widget', 'boost_package' ]


def test_other_project_used_by():
    assert dependency_removal._other_project_used_by( {}, '/proj/a' ) == []
    assert dependency_removal._other_project_used_by(
            { 'used_by': { '/proj/a': 't' } }, '/proj/a'
    ) == []
    assert dependency_removal._other_project_used_by(
            { 'used_by': { '/proj/a': 't', '/proj/b': 't' } }, '/proj/a'
    ) == [ '/proj/b' ]


def test_resolve_requested_names_all_uses_project_used():
    cuppa_env = {
        'remove_all_dependencies': True,
        'default_dependencies': [ 'widget' ],
        'declared_dependencies': [ 'boost_package' ],
        'dependencies': {
            'widget': object(),
            'boost_package': object(),
            'boost': object(),
            'extra': object(),
        },
    }
    names, error = dependency_removal.resolve_requested_names( cuppa_env )
    assert error is None
    assert names == [ 'widget', 'boost_package' ]


def test_project_dependency_names_union_preserves_order():
    cuppa_env = {
        'default_dependencies': [ 'a', 'b' ],
        'declared_dependencies': [ 'b', 'c' ],
    }
    assert dependency_removal.project_dependency_names( cuppa_env ) == [ 'a', 'b', 'c' ]


def test_sibling_leftovers_gitlab(tmp_path):
    root = tmp_path / 'dependencies'
    gcc = root / 'gcc153_dbg_x86_64_cxx2c' / 'boost' / '1.91'
    clang = root / 'clang211_dbg_x86_64_cxx2c' / 'boost' / '1.91'
    gcc.mkdir(parents=True)
    clang.mkdir(parents=True)
    (gcc / 'f').write_text( 'x', encoding='utf-8' )
    (clang / 'f').write_text( 'x', encoding='utf-8' )

    target = dependency_removal.RemovalTarget(
            dependency='boost_package',
            path=str( gcc ),
            qualifier='1.91',
            tool_variant='gcc153_dbg_x86_64_cxx2c',
            storage_type='gitlab',
            size_bytes=1,
            label=None,
            extra_paths=(),
    )
    leftovers = dependency_removal._sibling_leftovers(
            str( root ), target, { storage.real_path( str( gcc ) ) },
    )
    assert len( leftovers ) == 1
    assert leftovers[0].tool_variant == 'clang211_dbg_x86_64_cxx2c'
    assert leftovers[0].dependency == 'boost_package'


def test_sibling_leftovers_location_branches(tmp_path):
    root = tmp_path / 'dependencies'
    master = root / 'git_https_example.com__org_widget.git@master'
    feature = root / 'git_https_example.com__org_widget.git@feature_x'
    master.mkdir(parents=True)
    feature.mkdir(parents=True)
    (master / 'f').write_text( 'x', encoding='utf-8' )
    (feature / 'f').write_text( 'x', encoding='utf-8' )

    target = dependency_removal.RemovalTarget(
            dependency='widget',
            path=str( master ),
            qualifier='@master',
            tool_variant=None,
            storage_type='repository',
            size_bytes=1,
            label=None,
            extra_paths=(),
    )
    leftovers = dependency_removal._sibling_leftovers(
            str( root ), target, { storage.real_path( str( master ) ) },
    )
    assert len( leftovers ) == 1
    assert leftovers[0].qualifier == '@feature_x'


def test_relative_removal_path_under_root(tmp_path):
    root = tmp_path / 'dependencies'
    path = root / 'gcc153_rel_x86_64_cxx2c' / 'boost' / '1.91'
    path.mkdir(parents=True)
    assert dependency_removal._relative_removal_path(
            str( path ), str( root )
    ) == 'gcc153_rel_x86_64_cxx2c/boost/1.91'


def test_collect_removal_plan_prefers_storage_clean_products( tmp_path, monkeypatch ):
    """When storage_clean is supported, remove product dirs and leave the extract."""
    root = tmp_path / 'dependencies'
    extract = root / 'boost_extract'
    home = extract / 'clean'
    dbg = home / 'build.c++2c' / 'gcc153' / 'debug' / 'x86_64'
    rel = home / 'build.c++2c' / 'gcc153' / 'release' / 'x86_64'
    bindir = home / 'bin.c++2c'
    dbg.mkdir( parents=True )
    rel.mkdir( parents=True )
    bindir.mkdir( parents=True )
    ( home / 'boost' ).mkdir()
    ( home / 'boost' / 'version.hpp' ).write_text(
            '#define BOOST_VERSION 109100\n', encoding='utf-8'
    )

    class CleanBoost( object ):
        def storage_paths( self ):
            return {
                'dependencies': [ str( extract ) ],
                'downloads': [],
                'build': [],
                'develop': [],
                'cached': [],
            }

        def storage_qualifier( self ):
            return '1.91.0'

        def storage_clean( self, env, selection ):
            variant = selection.get( 'variant' )
            paths = []
            if variant == 'dbg' and dbg.is_dir():
                paths.append( str( dbg ) )
                paths.append( str( bindir ) )
            return { 'paths': paths, 'extract': str( extract ) }

        def remote_location( self ):
            return None

    instance = CleanBoost()

    def fake_resolve( construct, cuppa_env, names, selections=None ):
        from cuppa.core.dependency_storage import OwnedPath
        return [
            OwnedPath(
                dependency='boost',
                storage_type='archive',
                category='dependencies',
                path=str( extract ),
                qualifier='1.91.0',
                tool_variant=None,
                develop=False,
                remote_location=None,
            ),
        ], []

    def fake_selections( construct, cuppa_env ):
        return [ {
            'variant': 'dbg',
            'target_arch': 'x86_64',
            'abi': 'cxx2c',
            'toolchain': object(),
            'env': {
                'dependencies_root': str( root ),
                'toolchain': object(),
                'target_arch': 'x86_64',
                'variant': type( 'V', (), { 'name': lambda self: 'dbg' } )(),
            },
        } ]

    monkeypatch.setattr(
            dependency_removal.dependency_storage,
            'resolve_named_dependencies',
            fake_resolve,
    )
    monkeypatch.setattr(
            dependency_removal.dependency_storage,
            'selection_build_envs',
            fake_selections,
    )
    monkeypatch.setattr(
            dependency_removal,
            '_collect_storage_clean',
            lambda construct, cuppa_env, names, selections: {
                'boost': {
                    'paths': [ str( dbg ), str( bindir ) ],
                    'extract': str( extract ),
                    'supported': True,
                    'storage_type': 'archive',
                    'qualifier': '1.91.0',
                },
            },
    )

    cuppa_env = { 'dependencies_root': str( root ), 'dependencies': { 'boost': lambda env: instance } }
    plan = dependency_removal.collect_removal_plan( object(), cuppa_env, [ 'boost' ] )
    target_paths = { t.path for t in plan['targets'] }
    assert str( extract ) not in target_paths
    assert str( dbg ) in target_paths or any( 'debug' in p for p in target_paths )
    assert extract.is_dir()
    leftover_paths = { leftover.path for leftover in plan['leftovers'] }
    assert any( 'release' in p for p in leftover_paths )


def test_collect_removal_plan_wipe_includes_extract( tmp_path, monkeypatch ):
    """Wipe queues the whole extract even when storage_clean is available."""
    root = tmp_path / 'dependencies'
    extract = root / 'boost_extract'
    home = extract / 'clean'
    dbg = home / 'build.c++2c' / 'gcc153' / 'debug' / 'x86_64'
    dbg.mkdir( parents=True )
    ( home / 'boost' ).mkdir()
    ( home / 'boost' / 'version.hpp' ).write_text(
            '#define BOOST_VERSION 109100\n', encoding='utf-8'
    )

    def fake_resolve( construct, cuppa_env, names, selections=None ):
        from cuppa.core.dependency_storage import OwnedPath
        return [
            OwnedPath(
                dependency='boost',
                storage_type='archive',
                category='dependencies',
                path=str( extract ),
                qualifier='1.91.0',
                tool_variant=None,
                develop=False,
                remote_location=None,
            ),
        ], []

    def fake_selections( construct, cuppa_env ):
        return [ {
            'variant': 'dbg',
            'target_arch': 'x86_64',
            'abi': 'cxx2c',
            'toolchain': object(),
            'env': {
                'dependencies_root': str( root ),
                'toolchain': object(),
                'target_arch': 'x86_64',
                'variant': type( 'V', (), { 'name': lambda self: 'dbg' } )(),
            },
        } ]

    monkeypatch.setattr(
            dependency_removal.dependency_storage,
            'resolve_named_dependencies',
            fake_resolve,
    )
    monkeypatch.setattr(
            dependency_removal.dependency_storage,
            'selection_build_envs',
            fake_selections,
    )
    monkeypatch.setattr(
            dependency_removal,
            '_collect_storage_clean',
            lambda *args, **kwargs: {
                'boost': {
                    'paths': [ str( dbg ) ],
                    'extract': str( extract ),
                    'supported': True,
                    'storage_type': 'archive',
                    'qualifier': '1.91.0',
                },
            },
    )

    cuppa_env = { 'dependencies_root': str( root ), 'dependencies': {} }
    plan = dependency_removal.collect_removal_plan(
            object(), cuppa_env, [ 'boost' ], wipe=True
    )
    target_paths = { t.path for t in plan['targets'] }
    assert str( extract ) in target_paths
    assert plan['archives'] == []
    assert str( dbg ) not in target_paths


def test_write_removal_tree_summary_and_version_nesting():
    """Removal reports nest version under identity and show action/remaining rollup."""
    import io

    targets = [
            dependency_removal.RemovalTarget(
                    dependency='boost',
                    path='/deps/boost@1.91.0/a',
                    qualifier='1.91.0',
                    tool_variant='gcc',
                    storage_type='archive',
                    size_bytes=100,
                    label='product-a',
                    extra_paths=(),
            ),
    ]
    leftovers = [
            dependency_removal.Leftover(
                    dependency='boost',
                    path='/deps/boost@1.91.0/b',
                    qualifier='1.91.0',
                    tool_variant='clang',
                    size_bytes=40,
                    label='product-b',
                    storage_type='archive',
            ),
            dependency_removal.Leftover(
                    dependency='boost',
                    path='/deps/boost@1.88.0/c',
                    qualifier='1.88.0',
                    tool_variant='',
                    size_bytes=20,
                    label='product-c',
                    storage_type='archive',
            ),
    ]
    out = io.StringIO()
    dependency_removal._write_removal_tree(
            out, targets, leftovers, {}, planning=True, root='/deps',
            summary_label='related dependencies for boost',
            action_label='removing',
    )
    text = out.getvalue()
    lines = [ line for line in text.splitlines() if 'DEPENDENCY' not in line ]
    # Spacer under summary root, under types, and between identity and versions.
    assert any(
            line.rstrip().endswith( ( '│', '|' ) )
            for line in lines
    )
    assert any( 'related dependencies for boost' in line for line in lines )
    assert any( line.rstrip().endswith( 'removing' ) for line in lines )
    assert any( line.rstrip().endswith( 'remaining' ) for line in lines )
    assert any( line.rstrip().endswith( 'source archives' ) for line in lines )
    boost_line = next(
            line for line in lines
            if line.rstrip().endswith( 'boost' ) and 'related dependencies' not in line
    )
    version_line = next( line for line in lines if line.rstrip().endswith( '1.91.0' ) )
    assert '1.91.0' not in boost_line
    # Version row is indented further than the identity row.
    assert version_line.index( '1.91.0' ) > boost_line.index( 'boost' )
    # Untouched leftover version uses --- (same as extract rollups).
    leftover_version = next(
            line for line in lines if line.rstrip().endswith( '1.88.0' )
    )
    assert '---' in leftover_version
    assert 'product-a' in text
    assert 'product-b' in text
    # No spacer between a version and its leaves.
    version_idx = next( i for i, line in enumerate( lines ) if line.rstrip().endswith( '1.91.0' ) )
    assert 'product-a' in lines[version_idx + 1] or 'product-b' in lines[version_idx + 1]
    # Partial identity keeps a partial mark.
    assert '-✔-' in boost_line or '-✓-' in boost_line or '-*-' in boost_line


def test_write_removal_tree_spacers_encode_on_legacy_consoles( monkeypatch ):
    """Spacer pipes must use glyphs(), not a hardcoded box-drawing character."""
    import io

    monkeypatch.setattr(
            storage, 'glyphs', lambda encoding=None: storage.ASCII_GLYPHS,
    )
    targets = [
            dependency_removal.RemovalTarget(
                    dependency='boost',
                    path='/deps/boost@1.91.0/a',
                    qualifier='1.91.0',
                    tool_variant='gcc',
                    storage_type='archive',
                    size_bytes=100,
                    label='product-a',
                    extra_paths=(),
            ),
    ]
    leftovers = [
            dependency_removal.Leftover(
                    dependency='boost',
                    path='/deps/boost@1.88.0/c',
                    qualifier='1.88.0',
                    tool_variant='',
                    size_bytes=20,
                    label='product-c',
                    storage_type='archive',
            ),
    ]
    out = io.StringIO()
    dependency_removal._write_removal_tree(
            out, targets, leftovers, {}, planning=True, root='/deps',
            summary_label='related dependencies for boost',
            action_label='removing',
    )
    text = out.getvalue()
    assert '\u2502' not in text
    assert '|' in text


def test_write_removal_tree_uses_folded_display_labels( tmp_path ):
    """Removal table must print target/leftover labels, not only primary paths."""
    import io

    root = tmp_path / 'dependencies'
    root.mkdir()
    bin_primary = root / 'archive' / 'clean' / 'bin.c++2c' / 'boost' / 'predef' / 'clang-linux-21' / 'debug'
    stage = root / 'archive' / 'clean' / 'build.c++2c' / 'clang211' / 'debug' / 'x86_64'
    leftover_path = root / 'archive' / 'patched' / 'bin.c++2c' / 'gcc-15' / 'release'
    bin_primary.mkdir( parents=True )
    stage.mkdir( parents=True )
    leftover_path.mkdir( parents=True )

    targets = [
            dependency_removal.RemovalTarget(
                    dependency='boost',
                    path=str( bin_primary ),
                    qualifier='1.91.0',
                    tool_variant='clang-linux-21*/debug',
                    storage_type='archive',
                    size_bytes=100,
                    label='archive/clean/bin.c++2c [clang-linux-21*/debug]',
                    extra_paths=(),
            ),
            dependency_removal.RemovalTarget(
                    dependency='boost',
                    path=str( stage ),
                    qualifier='1.91.0',
                    tool_variant='clang211/debug/x86_64',
                    storage_type='archive',
                    size_bytes=50,
                    label='archive/clean/build.c++2c [clang211/debug/x86_64]',
                    extra_paths=(),
            ),
    ]
    leftovers = [
            dependency_removal.Leftover(
                    dependency='boost',
                    path=str( leftover_path ),
                    qualifier='1.91.0',
                    tool_variant='gcc-15*',
                    size_bytes=40,
                    label='archive/patched/bin.c++2c [gcc-15*]',
                    storage_type='archive',
            ),
    ]
    out = io.StringIO()
    outcomes = {
            storage.real_path( str( bin_primary ) ): { 'result': 'removed' },
            storage.real_path( str( stage ) ): { 'result': 'removed' },
    }
    dependency_removal._write_removal_tree(
            out, targets, leftovers, outcomes, planning=True, root=str( root ),
    )
    text = out.getvalue()
    assert 'related dependencies for' in text
    assert 'removing' in text or 'removed' in text
    assert 'remaining' in text
    assert 'source archives' in text
    assert 'boost' in text
    assert '1.91.0' in text
    # Version nested under identity — not flattened onto one label.
    assert 'boost  1.91.0' not in text
    assert 'archive/clean/bin.c++2c [clang-linux-21*/debug]' in text
    assert 'archive/clean/build.c++2c [clang211/debug/x86_64]' in text
    assert 'archive/patched/bin.c++2c [gcc-15*]' in text
    assert 'predef/clang-linux-21/debug' not in text


def test_archive_contexts_and_source_assets_report( tmp_path ):
    """Archive remove reports match list sizing: extract parent + source assets leaf."""
    import io

    root = tmp_path / 'dependencies'
    extract = root / 'boost_extract'
    home = extract / 'clean'
    stage = home / 'build.c++2c' / 'gcc153' / 'debug' / 'x86_64'
    bindir = home / 'bin.c++2c' / 'boost' / 'bin.v2' / 'libs' / 'system' / 'gcc-15' / 'debug'
    headers = home / 'boost'
    stage.mkdir( parents=True )
    bindir.mkdir( parents=True )
    headers.mkdir( parents=True )
    ( stage / 'lib.a' ).write_bytes( b'x' * 1000 )
    ( bindir / 'obj.o' ).write_bytes( b'y' * 500 )
    ( headers / 'version.hpp' ).write_bytes( b'z' * 2000 )

    stage_size = dependency_removal._measure_bytes( str( stage ) )
    bin_size = dependency_removal._measure_bytes( str( bindir ) )
    extract_size = dependency_removal._measure_bytes( str( extract ) )

    targets = [
            dependency_removal.RemovalTarget(
                    dependency='boost',
                    path=str( stage ),
                    qualifier='1.91.0',
                    tool_variant='gcc153/debug/x86_64',
                    storage_type='archive',
                    size_bytes=stage_size,
                    label='boost_extract/clean/build.c++2c [gcc153/debug/x86_64]',
                    extra_paths=(),
            ),
            dependency_removal.RemovalTarget(
                    dependency='boost',
                    path=str( bindir ),
                    qualifier='1.91.0',
                    tool_variant='gcc-15*/debug',
                    storage_type='archive',
                    size_bytes=bin_size,
                    label='boost_extract/clean/bin.c++2c [gcc-15*/debug]',
                    extra_paths=(),
            ),
    ]
    archives = dependency_removal._archive_contexts(
            str( root ),
            {
                'boost': {
                    'extract': str( extract ),
                    'qualifier': '1.91.0',
                },
            },
            targets,
            [],
    )
    assert len( archives ) == 1
    assert archives[0]['extract_bytes'] == extract_size
    assert archives[0]['source_bytes'] == max( 0, extract_size - stage_size - bin_size )

    out = io.StringIO()
    outcomes = {
            storage.real_path( str( stage ) ): { 'result': 'removed' },
            storage.real_path( str( bindir ) ): { 'result': 'removed' },
    }
    dependency_removal._write_removal_tree(
            out, targets, [], outcomes, planning=True, root=str( root ), archives=archives,
    )
    text = out.getvalue()
    assert 'source assets' in text
    assert '[E]' in text
    assert storage.human_size( extract_size ) in text
    assert storage.human_size( archives[0]['source_bytes'] ) in text
    assert 'boost_extract/clean/build.c++2c [gcc153/debug/x86_64]' in text
    # Product-clean remove has no download parent — no list-downloads [E] legend.
    assert '[E] = dependency extracted from the download above' not in text
    source_idx = text.index( 'source assets' )
    product_idx = text.index( 'boost_extract/clean/build.c++2c' )
    extract_idx = text.index( '[E]' )
    assert extract_idx < source_idx < product_idx

    remaining = dependency_removal._remaining_archive_bytes(
            archives, targets, outcomes, planning=True,
    )
    assert remaining == archives[0]['source_bytes']

    summary = io.StringIO()
    dependency_removal._write_freed_summary(
            summary, True, 2, stage_size + bin_size, remaining_archive_bytes=remaining,
    )
    summary_text = summary.getvalue()
    assert 'leaving a final archive size of' in summary_text
    assert storage.human_size( remaining ) in summary_text


def test_write_removal_tree_nests_extract_rollup_under_download( tmp_path ):
    import io

    root = tmp_path / 'dependencies'
    downloads = tmp_path / 'downloads'
    extract = root / 'boost_source'
    home = extract / 'clean'
    stage = home / 'build.c++2c' / 'gcc153' / 'debug' / 'x86_64'
    leftover_stage = home / 'build.c++2c' / 'gcc153' / 'release' / 'x86_64'
    stage.mkdir( parents=True )
    leftover_stage.mkdir( parents=True )
    ( extract / 'headers.hpp' ).write_bytes( b'h' * 50 )
    archive = downloads / 'boost_source'
    archive.parent.mkdir( parents=True )
    archive.write_bytes( b'tarball' )

    targets = [
            dependency_removal.RemovalTarget(
                    dependency='boost',
                    path=str( stage ),
                    qualifier='1.91.0',
                    tool_variant='gcc153/debug/x86_64',
                    storage_type='archive',
                    size_bytes=10,
                    label='boost_source/clean/build.c++2c [gcc153/debug/x86_64]',
                    extra_paths=(),
            ),
    ]
    leftovers = [
            dependency_removal.Leftover(
                    dependency='boost',
                    path=str( leftover_stage ),
                    qualifier='1.91.0',
                    tool_variant='gcc153/release/x86_64',
                    size_bytes=8,
                    label='boost_source/clean/build.c++2c [gcc153/release/x86_64]',
                    storage_type='archive',
            ),
    ]
    archives = dependency_removal._archive_contexts(
            str( root ),
            { 'boost': { 'extract': str( extract ), 'qualifier': '1.91.0' } },
            targets,
            leftovers,
    )
    download = dependency_removal.DownloadTarget(
            dependency='boost',
            path=str( archive ),
            qualifier='1.91.0',
            tool_variant='',
            storage_type='archive',
            size_bytes=7,
            label=archive.name,
            missing=False,
    )
    out = io.StringIO()
    outcomes = {
            storage.real_path( str( stage ) ): { 'result': 'removed' },
            storage.real_path( str( archive ) ): { 'result': 'removed' },
    }
    dependency_removal._write_removal_tree(
            out, targets, leftovers, outcomes, planning=True, root=str( root ),
            archives=archives, downloads=[ download ], downloads_root=str( downloads ),
    )
    text = out.getvalue()
    assert archive.name in text
    assert '[E]' in text
    assert 'source assets' in text
    assert 'boost_source/clean/build.c++2c [gcc153/debug/x86_64]' in text
    assert 'boost_source/clean/build.c++2c [gcc153/release/x86_64]' in text
    download_idx = text.index( archive.name )
    extract_idx = text.index( '[E]' )
    source_idx = text.index( 'source assets' )
    assert download_idx < extract_idx < source_idx
    assert '-✔-' in text or '-*-' in text
    assert '[E] = dependency extracted from the download above' in text


def test_write_verify_archive_notes_source_assets( tmp_path ):
    import io

    out = io.StringIO()
    dependency_removal._write_verify( out )
    assert 'source assets' not in out.getvalue()
    assert '--list-dependencies' in out.getvalue()

    out = io.StringIO()
    dependency_removal._write_verify( out, archives=[ { 'extract': str( tmp_path ) } ] )
    text = out.getvalue()
    assert 'cuppa -Q -D --list-dependencies' in text
    assert '--exact-sizes' not in text
    assert 'source assets' in text

    out = io.StringIO()
    dependency_removal._write_verify(
            out, archives=[ { 'extract': str( tmp_path ) } ], purge=True,
    )
    text = out.getvalue()
    assert 'cuppa -Q -D --list-downloads' in text
    assert '--list-dependencies still useful' in text


def test_refresh_archive_inventory_sizes_writes_exact( tmp_path ):
    root = tmp_path / 'dependencies'
    extract = root / 'boost_extract'
    product = extract / 'clean' / 'build.c++2c' / 'gcc153' / 'debug' / 'x86_64'
    product.mkdir( parents=True )
    ( product / 'lib.a' ).write_bytes( b'x' * 100 )
    ( extract / 'headers.hpp' ).write_bytes( b'y' * 50 )

    # Seed a bad sampled inventory entry.
    key = dependency_inventory.entry_key_for_path( str( extract ) )
    dependency_inventory.write_entry( str( root ), {
        'path': str( extract ),
        'type': 'archive',
        'kind': 'archive',
        'dependency': 'boost',
        'qualifier': '1.91.0',
        'size': { 'bytes': 1, 'measured': '2020-01-01T00:00:00Z', 'method': 'sampled' },
    }, key=key )

    target = dependency_removal.RemovalTarget(
            dependency='boost',
            path=str( product ),
            qualifier='1.91.0',
            tool_variant='gcc153/debug/x86_64',
            storage_type='archive',
            size_bytes=100,
            label='build',
            extra_paths=(),
    )
    archives = [ {
        'dependency': 'boost',
        'extract': str( extract ),
        'extract_bytes': 150,
        'source_bytes': 50,
        'qualifier': '1.91.0',
    } ]
    outcomes = { storage.real_path( str( product ) ): { 'result': 'removed' } }
    dependency_removal._refresh_archive_inventory_sizes(
            str( root ), archives, [ target ], outcomes,
    )
    entry = dependency_inventory.load_entry( str( root ), key )
    assert entry['size']['method'] == 'exact'
    assert entry['size']['bytes'] == dependency_removal._measure_bytes( str( extract ) )
