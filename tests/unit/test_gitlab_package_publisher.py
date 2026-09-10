import time

import pytest

from cuppa.package_managers import gitlab


pytestmark = pytest.mark.unit


def _publisher_env( tmp_path, touched=None ):
    class Env:
        abs_final_dir = str( tmp_path )

        def __getitem__( self, key ):
            if key == 'abs_final_dir':
                return str( tmp_path )
            raise KeyError( key )

        def Execute( self, action ):
            if touched is not None:
                touched.append( action )

    return Env()


def test_lib_copy_ignore_names_skips_staging_and_archives():
    ignored = gitlab.lib_copy_ignore_names(
            [
                    'libwidget.a',
                    'modules',
                    'widget',
                    'widget_debian_gcc15_rel.tar.gz',
                    'stamp.packaged',
                    'stamp.published',
                    'other.zip',
            ],
            'widget',
            'widget_debian_gcc15_rel.tar.gz',
    )
    assert ignored == {
            'modules',
            'widget',
            'widget_debian_gcc15_rel.tar.gz',
            'stamp.packaged',
            'stamp.published',
            'other.zip',
    }
    assert 'libwidget.a' not in ignored


def test_package_sidecar_id():
    path = "widget/2.0.0/widget_debian_gcc15_rel_x86_64_cxx2c.tar.gz"
    assert gitlab.package_sidecar_id( path, '.packaged' ) == (
        "widget_2_0_0_widget_debian_gcc15_rel_x86_64_cxx2c.packaged"
    )


def test_package_archive_is_up_to_date(tmp_path):
    staging = tmp_path / "widget" / "1.0.0"
    include_dir = staging / "include"
    lib_dir = staging / "lib"
    include_dir.mkdir( parents=True )
    lib_dir.mkdir( parents=True )
    ( include_dir / "widget.hpp" ).write_text( "header\n", encoding="utf-8" )
    ( lib_dir / "libwidget.a" ).write_text( "lib\n", encoding="utf-8" )
    time.sleep( 0.02 )

    archive = tmp_path / "widget_debian_gcc15_rel.tar.gz"
    archive.write_bytes( b"archive" )

    assert gitlab.package_archive_is_up_to_date(
            str( archive ),
            [ str( include_dir ), str( lib_dir ) ],
    )

    ( lib_dir / "libwidget.a" ).write_text( "updated\n", encoding="utf-8" )
    assert not gitlab.package_archive_is_up_to_date(
            str( archive ),
            [ str( include_dir ), str( lib_dir ) ],
    )


def test_staging_tree_needs_refresh( tmp_path ):
    source = tmp_path / "install" / "include"
    staging = tmp_path / "widget" / "1.0.0" / "include"
    source.mkdir( parents=True )
    ( source / "widget.hpp" ).write_text( "v1\n", encoding="utf-8" )

    assert gitlab.staging_tree_needs_refresh( str( source ), str( staging ) )

    staging.mkdir( parents=True )
    ( staging / "widget.hpp" ).write_text( "v1\n", encoding="utf-8" )
    time.sleep( 0.02 )
    assert not gitlab.staging_tree_needs_refresh( str( source ), str( staging ) )

    ( source / "widget.hpp" ).write_text( "v2\n", encoding="utf-8" )
    assert gitlab.staging_tree_needs_refresh( str( source ), str( staging ) )

    assert not gitlab.staging_tree_needs_refresh( str( staging ), str( staging ) )


def test_path_outside_package_final( tmp_path ):
    final = tmp_path / "final"
    final.mkdir()
    assert gitlab.path_outside_package_final( str( tmp_path / "install" ), str( final ) )
    assert not gitlab.path_outside_package_final( str( final ), str( final ) )
    assert not gitlab.path_outside_package_final(
            str( final / "widget" / "1.0.0" / "include" ),
            str( final ),
    )


def _bare_publisher( tmp_path, staging, include_dir, lib_dir, archive, source_include=None, source_lib=None ):
    publisher = gitlab.GitlabPackagePublisher.__new__( gitlab.GitlabPackagePublisher )
    publisher._target_include_dir = str( include_dir )
    publisher._target_lib_dir = str( lib_dir )
    publisher._package_base_dir = str( staging )
    publisher._package_archive = str( archive )
    publisher._abs_final_dir = str( tmp_path )
    publisher._package_source_dir = "widget"
    publisher._package_file_name = archive.name
    publisher._source_include_dir = str( source_include if source_include is not None else include_dir )
    publisher._source_lib_dir = str( source_lib if source_lib is not None else lib_dir )
    publisher._dependencies = []
    return publisher


def test_build_package_skips_create_when_archive_current( tmp_path, monkeypatch ):
    create_calls = []

    def _record_create( archive_path, working_dir, source_dir ):
        create_calls.append( ( archive_path, working_dir, source_dir ) )
        return 0

    monkeypatch.setattr( gitlab, 'create_package_archive', _record_create )

    staging = tmp_path / "widget" / "1.0.0"
    include_dir = staging / "include"
    lib_dir = staging / "lib"
    include_dir.mkdir( parents=True )
    lib_dir.mkdir( parents=True )
    ( include_dir / "widget.hpp" ).write_text( "header\n", encoding="utf-8" )
    ( lib_dir / "libwidget.a" ).write_text( "lib\n", encoding="utf-8" )
    time.sleep( 0.02 )

    archive = tmp_path / "widget_debian_gcc15_rel.tar.gz"
    archive.write_bytes( b"archive" )

    stamp = tmp_path / "widget_debian_gcc15_rel.packaged"
    publisher = _bare_publisher( tmp_path, staging, include_dir, lib_dir, archive )

    touched = []
    env = _publisher_env( tmp_path, touched )

    assert publisher.build_package( [ str( stamp ) ], [], env ) is None
    assert create_calls == []
    assert touched


def test_build_package_creates_archive_when_staging_newer( tmp_path, monkeypatch ):
    create_calls = []

    monkeypatch.setattr(
            gitlab,
            'create_package_archive',
            lambda archive_path, working_dir, source_dir: create_calls.append(
                    ( archive_path, working_dir, source_dir )
            ) or 0,
    )

    staging = tmp_path / "widget" / "1.0.0"
    include_dir = staging / "include"
    lib_dir = staging / "lib"
    include_dir.mkdir( parents=True )
    lib_dir.mkdir( parents=True )
    ( include_dir / "widget.hpp" ).write_text( "header\n", encoding="utf-8" )
    ( lib_dir / "libwidget.a" ).write_text( "lib\n", encoding="utf-8" )

    archive = tmp_path / "widget_debian_gcc15_rel.tar.gz"
    archive.write_bytes( b"old" )
    time.sleep( 0.02 )
    ( lib_dir / "libwidget.a" ).write_text( "new\n", encoding="utf-8" )

    stamp = tmp_path / "widget_debian_gcc15_rel.packaged"
    publisher = _bare_publisher( tmp_path, staging, include_dir, lib_dir, archive )

    env = _publisher_env( tmp_path )

    assert publisher.build_package( [ str( stamp ) ], [], env ) is None
    assert create_calls == [
            ( str( archive ), str( tmp_path ), "widget" ),
    ]


def test_build_package_refreshes_staging_when_source_newer( tmp_path, monkeypatch ):
    monkeypatch.setattr( gitlab, 'create_package_archive', lambda *args, **kwargs: 0 )

    install_include = tmp_path / "install" / "include"
    install_lib = tmp_path / "install" / "lib"
    install_include.mkdir( parents=True )
    install_lib.mkdir( parents=True )
    ( install_include / "widget.hpp" ).write_text( "old-header\n", encoding="utf-8" )
    ( install_lib / "libwidget.a" ).write_text( "old-lib\n", encoding="utf-8" )

    staging = tmp_path / "widget" / "1.0.0"
    include_dir = staging / "include"
    lib_dir = staging / "lib"
    include_dir.mkdir( parents=True )
    lib_dir.mkdir( parents=True )
    ( include_dir / "widget.hpp" ).write_text( "stale\n", encoding="utf-8" )
    ( lib_dir / "libwidget.a" ).write_text( "stale\n", encoding="utf-8" )
    time.sleep( 0.02 )
    ( install_include / "widget.hpp" ).write_text( "fresh-header\n", encoding="utf-8" )
    ( install_lib / "libwidget.a" ).write_text( "fresh-lib\n", encoding="utf-8" )

    archive = tmp_path / "widget_debian_gcc15_rel.tar.gz"
    archive.write_bytes( b"old" )
    stamp = tmp_path / "widget_debian_gcc15_rel.packaged"
    publisher = _bare_publisher(
            tmp_path,
            staging,
            include_dir,
            lib_dir,
            archive,
            source_include=install_include,
            source_lib=install_lib,
    )

    env = _publisher_env( tmp_path )
    assert publisher.build_package( [ str( stamp ) ], [], env ) is None
    assert ( include_dir / "widget.hpp" ).read_text( encoding="utf-8" ) == "fresh-header\n"
    assert ( lib_dir / "libwidget.a" ).read_text( encoding="utf-8" ) == "fresh-lib\n"


def test_publisher_sources_includes_lib_outside_final( tmp_path ):
    abs_final = tmp_path / "final"
    abs_final.mkdir()
    install_include = tmp_path / "prefix" / "include"
    install_lib = tmp_path / "prefix" / "lib"
    install_include.mkdir( parents=True )
    install_lib.mkdir( parents=True )

    archive = abs_final / "widget_debian_gcc15_rel.tar.gz"
    archive.write_bytes( b"x" )
    publisher = _bare_publisher(
            abs_final,
            abs_final / "widget" / "1.0.0",
            abs_final / "widget" / "1.0.0" / "include",
            abs_final / "widget" / "1.0.0" / "lib",
            archive,
            source_include=install_include,
            source_lib=install_lib,
    )
    assert publisher.sources() == [ str( install_include ), str( install_lib ) ]


def test_publisher_sources_omits_dirs_under_final( tmp_path ):
    archive = tmp_path / "widget_debian_gcc15_rel.tar.gz"
    archive.write_bytes( b"x" )
    under_include = tmp_path / "installed" / "include"
    under_lib = tmp_path / "installed" / "lib"
    under_include.mkdir( parents=True )
    under_lib.mkdir( parents=True )

    publisher = _bare_publisher(
            tmp_path,
            tmp_path / "widget" / "1.0.0",
            tmp_path / "widget" / "1.0.0" / "include",
            tmp_path / "widget" / "1.0.0" / "lib",
            archive,
            source_include=under_include,
            source_lib=under_lib,
    )
    assert publisher.sources() == []
