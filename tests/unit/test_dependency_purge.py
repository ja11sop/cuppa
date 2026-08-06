"""Unit tests for --purge-dependencies download queuing and safety."""

import pytest

from cuppa.core import dependency_removal
from cuppa.core.dependency_storage import OwnedPath
from cuppa.utility import storage


pytestmark = pytest.mark.unit


def _owned( **kwargs ):
    defaults = dict(
            dependency='boost_package',
            storage_type='gitlab',
            category='downloads',
            path='',
            qualifier='1.91',
            tool_variant='gcc153_dbg_x86_64_cxx2c',
            develop=False,
            remote_location=None,
    )
    defaults.update( kwargs )
    return OwnedPath( **defaults )


def test_collect_purge_downloads_containment( tmp_path ):
    downloads = tmp_path / 'downloads'
    downloads.mkdir()
    outside = tmp_path / 'elsewhere' / 'evil.tar.gz'
    outside.parent.mkdir()
    outside.write_bytes( b'x' )
    cuppa_env = { 'downloads_root': str( downloads ), 'sconstruct_dir': str( tmp_path ) }
    owned = [ _owned( path=str( outside ) ) ]
    with pytest.raises( storage.StorageError, match='outside managed root' ):
        dependency_removal.collect_purge_downloads(
                None, cuppa_env, [ 'boost_package' ], owned=owned,
        )


def test_collect_purge_downloads_refuses_symlink( tmp_path ):
    downloads = tmp_path / 'downloads'
    downloads.mkdir()
    real = downloads / 'real.tar.gz'
    real.write_bytes( b'abc' )
    link = downloads / 'link.tar.gz'
    link.symlink_to( real )
    cuppa_env = { 'downloads_root': str( downloads ), 'sconstruct_dir': str( tmp_path ) }
    owned = [ _owned( path=str( link ) ) ]
    with pytest.raises( storage.StorageError, match='symlink' ):
        dependency_removal.collect_purge_downloads(
                None, cuppa_env, [ 'boost_package' ], owned=owned,
        )


def test_collect_purge_downloads_missing_is_ok( tmp_path ):
    downloads = tmp_path / 'downloads'
    downloads.mkdir()
    missing = downloads / 'packages' / 'boost' / '1.91' / 'boost_debian_gcc153_dbg_x86_64_cxx2c.tar.gz'
    cuppa_env = { 'downloads_root': str( downloads ), 'sconstruct_dir': str( tmp_path ) }
    owned = [ _owned( path=str( missing ) ) ]
    targets, leftovers, root = dependency_removal.collect_purge_downloads(
            None, cuppa_env, [ 'boost_package' ], owned=owned,
    )
    assert root == str( downloads )
    assert leftovers == []
    assert len( targets ) == 1
    assert targets[0].missing is True
    assert targets[0].size_bytes == 0


def test_collect_purge_downloads_queues_sibling_leftover( tmp_path ):
    downloads = tmp_path / 'downloads'
    pkg = downloads / 'packages' / 'boost' / '1.91'
    pkg.mkdir( parents=True )
    selected = pkg / 'boost_debian_gcc153_dbg_x86_64_cxx2c.tar.gz'
    leftover = pkg / 'boost_debian_clang999_dbg_x86_64_cxx2c.tar.gz'
    selected.write_bytes( b'selected-bytes' )
    leftover.write_bytes( b'other-bytes' )
    cuppa_env = { 'downloads_root': str( downloads ), 'sconstruct_dir': str( tmp_path ) }
    owned = [ _owned( path=str( selected ) ) ]
    targets, leftovers, _root = dependency_removal.collect_purge_downloads(
            None, cuppa_env, [ 'boost_package' ], owned=owned,
    )
    assert [ item.label for item in targets ] == [ selected.name ]
    assert not targets[0].missing
    assert [ item.label for item in leftovers ] == [ leftover.name ]


def test_prune_empty_package_dirs_after_download_delete( tmp_path ):
    downloads = tmp_path / 'downloads'
    pkg = downloads / 'packages' / 'boost' / '1.91'
    pkg.mkdir( parents=True )
    archive = pkg / 'boost_debian_gcc153_dbg_x86_64_cxx2c.tar.gz'
    archive.write_bytes( b'abc' )
    storage.remove_path( str( archive ), dry_run=False )
    storage.prune_empty_parents( str( pkg ), str( downloads ) )
    assert not ( downloads / 'packages' / 'boost' ).exists()
    assert downloads.is_dir()


def test_write_removal_tree_nests_download_and_extract( tmp_path ):
    import io

    deps = tmp_path / 'dependencies'
    downloads = tmp_path / 'downloads'
    extract = deps / 'gcc153_dbg_x86_64_cxx2c' / 'boost' / '1.91'
    extract.mkdir( parents=True )
    ( extract / 'include' ).mkdir()
    archive = downloads / 'packages' / 'boost' / '1.91' / 'boost_debian_gcc153_dbg_x86_64_cxx2c.tar.gz'
    archive.parent.mkdir( parents=True )
    archive.write_bytes( b'pkg' )

    target = dependency_removal.RemovalTarget(
            dependency='boost_package',
            path=str( extract ),
            qualifier='1.91',
            tool_variant='gcc153_dbg_x86_64_cxx2c',
            storage_type='gitlab',
            size_bytes=4,
            label='gcc153_dbg_x86_64_cxx2c/boost/1.91',
            extra_paths=(),
    )
    download = dependency_removal.DownloadTarget(
            dependency='boost_package',
            path=str( archive ),
            qualifier='1.91',
            tool_variant='gcc153_dbg_x86_64_cxx2c',
            storage_type='gitlab',
            size_bytes=3,
            label=archive.name,
            missing=False,
    )
    leftover_dl = dependency_removal.DownloadTarget(
            dependency='boost_package',
            path=str( archive.parent / 'boost_debian_clang999_dbg_x86_64_cxx2c.tar.gz' ),
            qualifier='1.91',
            tool_variant='clang999_dbg_x86_64_cxx2c',
            storage_type='gitlab',
            size_bytes=8,
            label='boost_debian_clang999_dbg_x86_64_cxx2c.tar.gz',
            missing=False,
    )
    ( archive.parent / leftover_dl.label ).write_bytes( b'leftover!' )

    leftover_extract = dependency_removal.Leftover(
            dependency='boost_package',
            path=str( deps / 'clang999_dbg_x86_64_cxx2c' / 'boost' / '1.91' ),
            qualifier='1.91',
            tool_variant='clang999_dbg_x86_64_cxx2c',
            size_bytes=10,
            label='clang999_dbg_x86_64_cxx2c/boost/1.91',
            storage_type='gitlab',
    )
    leftover_extract_path = deps / 'clang999_dbg_x86_64_cxx2c' / 'boost' / '1.91'
    leftover_extract_path.mkdir( parents=True )

    out = io.StringIO()
    outcomes = {
        storage.real_path( str( extract ) ): { 'result': 'removed' },
        storage.real_path( str( archive ) ): { 'result': 'removed' },
    }
    dependency_removal._write_removal_tree(
            out, [ target ], [ leftover_extract ], outcomes, False, str( deps ),
            downloads=[ download ], download_leftovers=[ leftover_dl ],
            downloads_root=str( downloads ),
    )
    text = out.getvalue()
    assert archive.name in text
    assert '[E]' in text
    assert 'removed' in text
    assert leftover_dl.label in text
    after_selected = text[text.index( archive.name ):]
    assert '[E]' in after_selected
    assert 'gcc153_dbg_x86_64_cxx2c/boost/1.91' in after_selected
    assert '[E] = dependency extracted from the download above' in text
