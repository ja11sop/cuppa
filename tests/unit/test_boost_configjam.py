#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

import pytest

from cuppa.dependencies.boost.configjam import (
    WriteToolsetConfigJam,
    _neutralise_cuppa_project_config_jam,
    ensure_toolset_user_config_jam,
)


class _Toolchain(object):
    def cxx_version( self ):
        return "15"

    def binary( self ):
        return "/usr/bin/g++-15"

    def toolset_name( self ):
        return "gcc"


@pytest.mark.unit
def test_ensure_toolset_user_config_jam_writes_once( tmp_path, monkeypatch ):
    monkeypatch.setattr(
        "cuppa.dependencies.boost.configjam.toolset_name_from_toolchain",
        lambda toolchain: "gcc",
    )

    jam_path = tmp_path / "gcc15._jam"
    assert ensure_toolset_user_config_jam( str( jam_path ), _Toolchain() ) is True
    text = jam_path.read_text()
    assert "using gcc : 15 : /usr/bin/g++-15 ;" in text
    assert ensure_toolset_user_config_jam( str( jam_path ), _Toolchain() ) is False
    assert jam_path.read_text() == text
    assert not ( tmp_path / "project-config.jam" ).exists()


@pytest.mark.unit
def test_write_toolset_config_jam_does_not_create_project_config( tmp_path, monkeypatch ):
    monkeypatch.setattr(
        "cuppa.dependencies.boost.configjam.toolset_name_from_toolchain",
        lambda toolchain: "gcc",
    )

    jam_path = tmp_path / "gcc15._jam"
    env = { "toolchain": _Toolchain() }
    WriteToolsetConfigJam()( [ jam_path ], [], env )

    assert jam_path.is_file()
    assert "using gcc : 15 : /usr/bin/g++-15 ;" in jam_path.read_text()
    assert not ( tmp_path / "project-config.jam" ).exists()


@pytest.mark.unit
def test_neutralise_removes_cuppa_authored_project_config( tmp_path ):
    project_config = tmp_path / "project-config.jam"
    project_config.write_text(
        "# File created by cuppa:boost\nusing gcc : 15 : /usr/bin/g++-15 ;\n"
    )

    _neutralise_cuppa_project_config_jam( str( tmp_path ) )

    assert not project_config.exists()


@pytest.mark.unit
def test_neutralise_leaves_non_cuppa_project_config( tmp_path ):
    project_config = tmp_path / "project-config.jam"
    project_config.write_text( "# hand-written\nusing gcc : 15 : /usr/bin/g++-15 ;\n" )

    _neutralise_cuppa_project_config_jam( str( tmp_path ) )

    assert project_config.exists()


@pytest.mark.unit
def test_write_toolset_config_jam_removes_leftover_cuppa_project_config( tmp_path, monkeypatch ):
    monkeypatch.setattr(
        "cuppa.dependencies.boost.configjam.toolset_name_from_toolchain",
        lambda toolchain: "gcc",
    )

    project_config = tmp_path / "project-config.jam"
    project_config.write_text( "# File created by cuppa:boost\nusing gcc : 16 : /usr/bin/g++-16 ;\n" )

    jam_path = tmp_path / "gcc15._jam"
    WriteToolsetConfigJam()( [ jam_path ], [], { "toolchain": _Toolchain() } )

    assert jam_path.is_file()
    assert not project_config.exists()
