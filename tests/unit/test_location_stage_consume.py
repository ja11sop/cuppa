# Unit: resolve_develop_location_stage and StageLocationDevelop layout.

import os

import pytest

from cuppa.package_managers import package_cascade as cascade


pytestmark = pytest.mark.unit


def test_location_stage_version_defaults_to_develop( tmp_path ):
    assert cascade.location_stage_version( str( tmp_path ) ) == "develop"


def test_location_stage_version_reads_publish_manifest( tmp_path ):
    from cuppa.package_managers.cuppa_publish_manifest import write_publish_manifest

    write_publish_manifest(
            str( tmp_path ),
            package="widget",
            version="2.1.0",
            dependencies=[],
    )
    assert cascade.location_stage_version( str( tmp_path ) ) == "2.1.0"


def test_location_stage_version_ignores_floating_seed_token( tmp_path ):
    from cuppa.package_managers.cuppa_publish_manifest import write_publish_manifest

    write_publish_manifest(
            str( tmp_path ),
            package="boost",
            version="latest",
            dependencies=[],
    )
    assert cascade.location_stage_version( str( tmp_path ) ) == "develop"


def test_resolve_develop_location_stage_finds_usable_prefix( tmp_path ):
    stage = (
            tmp_path / "_build" / "gcc_dbg_x86_64_cxx2c" / "final" / "widget" / "develop"
    )
    ( stage / "include" ).mkdir( parents=True )
    ( stage / "lib" ).mkdir()
    ( stage / "include" / "widget.hpp" ).write_text( "//\n", encoding="utf-8" )
    ( stage / "lib" / "libwidget.a" ).write_text( "x", encoding="utf-8" )

    found = cascade.resolve_develop_location_stage(
            str( tmp_path ), "widget", version="develop"
    )
    assert found == str( stage )


def test_resolve_develop_location_stage_missing_returns_none( tmp_path ):
    assert cascade.resolve_develop_location_stage(
            str( tmp_path ), "widget"
    ) is None
