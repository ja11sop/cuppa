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
    publisher = gitlab.GitlabPackagePublisher.__new__( gitlab.GitlabPackagePublisher )
    publisher._target_include_dir = str( include_dir )
    publisher._target_lib_dir = str( lib_dir )
    publisher._package_base_dir = str( staging )
    publisher._package_archive = str( archive )
    publisher._package_source_dir = "widget"
    publisher._package_file_name = archive.name
    publisher._source_lib_dir = str( lib_dir )

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
    publisher = gitlab.GitlabPackagePublisher.__new__( gitlab.GitlabPackagePublisher )
    publisher._target_include_dir = str( include_dir )
    publisher._target_lib_dir = str( lib_dir )
    publisher._package_base_dir = str( staging )
    publisher._package_archive = str( archive )
    publisher._package_source_dir = "widget"
    publisher._package_file_name = archive.name
    publisher._source_lib_dir = str( lib_dir )

    env = _publisher_env( tmp_path )

    assert publisher.build_package( [ str( stamp ) ], [], env ) is None
    assert create_calls == [
            ( str( archive ), str( tmp_path ), "widget" ),
    ]
