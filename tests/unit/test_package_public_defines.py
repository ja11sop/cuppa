#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

"""Public compile defines travel with the package and are applied by BuildWith."""

import shutil
import subprocess
import textwrap
from pathlib import Path

import pytest

from cuppa.buildsys.cmake import cmake_public_defines
from cuppa.package_managers.cuppa_publish_manifest import (
        package_public_defines,
        write_publish_manifest,
)
from cuppa.package_managers.package_public_defines import (
        cmake_package_names,
        imported_cmake_targets,
        normalise_public_defines,
        query_cmake_public_defines,
        resolve_public_defines,
        union_target_defines,
)


pytestmark = pytest.mark.unit


_DATE_TARGETS = """
add_library(date::date INTERFACE IMPORTED)
set_target_properties(date::date PROPERTIES
  INTERFACE_COMPILE_DEFINITIONS "ONLY_C_LOCALE=0;HAS_STRING_VIEW=1"
)
add_library(date::date-tz SHARED IMPORTED)
set_target_properties(date::date-tz PROPERTIES
  INTERFACE_COMPILE_DEFINITIONS "USE_OS_TZDB=1"
  INTERFACE_LINK_LIBRARIES "date::date"
)
"""


def test_imported_target_names_ignore_the_define_text( tmp_path: Path ):
    cmake = tmp_path / "lib" / "cmake" / "date" / "dateTargets.cmake"
    cmake.parent.mkdir( parents=True )
    cmake.write_text( _DATE_TARGETS, encoding="utf-8" )
    ( cmake.parent / "dateConfig.cmake" ).write_text(
            'include("${CMAKE_CURRENT_LIST_DIR}/dateTargets.cmake")\n',
            encoding="utf-8",
    )
    assert imported_cmake_targets( str( tmp_path ) ) == [ "date::date", "date::date-tz" ]
    assert cmake_package_names( str( tmp_path ) ) == [ "date" ]


def test_union_keeps_first_token_and_rejects_a_conflict():
    assert union_target_defines( {
            "date::date-tz": [ "USE_OS_TZDB=1", "ONLY_C_LOCALE=0" ],
            "date::date": [ "ONLY_C_LOCALE=0", "HAS_STRING_VIEW=1" ],
    } ) == [ "ONLY_C_LOCALE=0", "HAS_STRING_VIEW=1", "USE_OS_TZDB=1" ]

    import SCons.Errors
    with pytest.raises( SCons.Errors.StopError, match="disagree on \\[FOO\\]" ):
        union_target_defines( {
                "a::a": [ "FOO=0" ],
                "b::b": [ "FOO=1" ],
        } )


def test_normalise_is_a_package_list_not_a_stem_map():
    import SCons.Errors
    assert normalise_public_defines( [ "USE_OS_TZDB=1", "USE_OS_TZDB=1" ] ) == [
            "USE_OS_TZDB=1",
    ]
    assert normalise_public_defines( [] ) is None
    assert normalise_public_defines( None ) is None
    with pytest.raises( SCons.Errors.StopError ):
        normalise_public_defines( { "date-tz": [ "USE_OS_TZDB=1" ] } )
    with pytest.raises( SCons.Errors.StopError ):
        normalise_public_defines( [ "USE_OS_TZDB = 1" ] )
    with pytest.raises( SCons.Errors.StopError ):
        normalise_public_defines( cmake_public_defines() )


def test_explicit_list_does_not_ask_cmake( monkeypatch ):
    def _fail( *args, **kwargs ):
        raise AssertionError( "cmake should not be asked" )

    monkeypatch.setattr(
            "cuppa.package_managers.package_public_defines.query_cmake_public_defines",
            _fail,
    )
    assert resolve_public_defines( [ "WIDGET_HAS_TLS=1" ], "/absent" ) == [
            "WIDGET_HAS_TLS=1",
    ]
    assert resolve_public_defines( None, "/absent" ) is None
    assert resolve_public_defines( [], "/absent" ) is None


def test_marker_asks_cmake( monkeypatch ):
    monkeypatch.setattr(
            "cuppa.package_managers.package_public_defines.query_cmake_public_defines",
            lambda package_dir, env=None: [ "USE_OS_TZDB=1" ],
    )
    assert resolve_public_defines( cmake_public_defines(), "/pkg" ) == [ "USE_OS_TZDB=1" ]


def test_library_prefix_travels_and_the_consumer_can_replace_it( tmp_path: Path ):
    from cuppa.package_managers import gitlab as gitlab_module
    from cuppa.package_managers.cuppa_publish_manifest import package_library_prefix

    write_publish_manifest(
            str( tmp_path ),
            "capy",
            "1.0.0",
            dependencies=[],
            library_prefix="boost_",
    )
    assert package_library_prefix( str( tmp_path ) ) == "boost_"

    dep = object.__new__( gitlab_module.GitlabPackageDependency )
    dep._library_prefix_argument = None
    dep._package_dir = str( tmp_path )
    assert dep._resolved_library_prefix() == "boost_"

    dep._library_prefix_argument = "other_"
    assert dep._resolved_library_prefix() == "other_"

    dep._library_prefix_argument = ""
    assert dep._resolved_library_prefix() == ""


def test_pkg_config_dir_travels_only_when_published( tmp_path: Path ):
    import os

    from cuppa.package_managers import gitlab as gitlab_module
    from cuppa.package_managers.cuppa_dependency_manifest import _normalise_pkg_config_dir
    from cuppa.package_managers.cuppa_publish_manifest import package_pkg_config_dir

    published = tmp_path / "json"
    published.mkdir()
    write_publish_manifest(
            str( published ),
            "json",
            "3.11.3",
            dependencies=[],
            pkg_config_dir="share/pkgconfig",
    )
    assert package_pkg_config_dir( str( published ) ) == "share/pkgconfig"

    plain = tmp_path / "plain"
    plain.mkdir()
    write_publish_manifest( str( plain ), "widget", "1.0.0", dependencies=[] )
    assert package_pkg_config_dir( str( plain ) ) is None
    assert "pkg_config_dir" not in ( plain / "cuppa-publish.json" ).read_text()

    assert _normalise_pkg_config_dir( "./lib/pkgconfig" ) == "lib/pkgconfig"
    assert _normalise_pkg_config_dir( "lib\\pkgconfig" ) == "lib/pkgconfig"
    with pytest.raises( ValueError, match="relative" ):
        _normalise_pkg_config_dir( "/usr/lib/pkgconfig" )
    with pytest.raises( ValueError, match="inside the package" ):
        _normalise_pkg_config_dir( "../pkgconfig" )

    dep = object.__new__( gitlab_module.GitlabPackageDependency )
    dep._pkg_config_dir_argument = None
    dep._package_dir = str( published )
    assert dep._resolved_pkg_config_dir() == os.path.abspath(
            str( published / "share/pkgconfig" )
    )

    dep._pkg_config_dir_argument = "lib/pkgconfig"
    assert dep._resolved_pkg_config_dir() == os.path.abspath(
            str( published / "lib/pkgconfig" )
    )

    dep._pkg_config_dir_argument = ""
    assert dep._resolved_pkg_config_dir() is None

    dep._pkg_config_dir_argument = "/opt/pc"
    assert dep._resolved_pkg_config_dir() == os.path.abspath( "/opt/pc" )

    dep._pkg_config_dir_argument = None
    dep._package_dir = str( plain )
    assert dep._resolved_pkg_config_dir() is None


def test_publish_manifest_round_trips_public_defines( tmp_path: Path ):
    defines = [ "USE_OS_TZDB=1", "ONLY_C_LOCALE=0" ]
    write_publish_manifest(
            str( tmp_path ),
            "date",
            "3.0.5",
            dependencies=[],
            default_use_libs=[ "date-tz" ],
            public_defines=defines,
    )
    assert package_public_defines( str( tmp_path ) ) == defines


def test_missing_field_is_not_read_from_cmake_files( tmp_path: Path ):
    cmake = tmp_path / "lib" / "cmake" / "date" / "dateTargets.cmake"
    cmake.parent.mkdir( parents=True )
    cmake.write_text( _DATE_TARGETS, encoding="utf-8" )
    write_publish_manifest( str( tmp_path ), "date", "3.0.5", dependencies=[] )
    assert package_public_defines( str( tmp_path ) ) is None


def test_build_with_applies_defines_and_use_libs_keeps_them( tmp_path: Path, monkeypatch ):
    from cuppa.package_managers import gitlab as gitlab_module
    import cuppa.package_managers.cuppa_dependency_apply as apply_mod
    import cuppa.package_managers.runtime_paths as runtime_paths

    package_dir = tmp_path / "date"
    ( package_dir / "include" ).mkdir( parents=True )
    ( package_dir / "lib" ).mkdir()
    write_publish_manifest(
            str( package_dir ),
            "date",
            "3.0.5",
            dependencies=[],
            default_use_libs=[ "date-tz" ],
            public_defines=[ "USE_OS_TZDB=1", "HAS_STRING_VIEW=1" ],
    )

    monkeypatch.setattr( runtime_paths, "apply_package_runtime_paths", lambda *a, **k: None )
    monkeypatch.setattr( apply_mod, "apply_transitive_build_with", lambda *a, **k: None )
    monkeypatch.setattr( apply_mod, "apply_transitive_use_libs", lambda *a, **k: None )

    class _Env( dict ):
        def AppendUnique( self, **kwargs ):
            return None

        def Depends( self, *args ):
            return None

    class _Named:
        def name( self ):
            return "gcc"

    dep = object.__new__( gitlab_module.GitlabPackageDependency )
    dep._env = _Env()
    dep._package_dir = str( package_dir )
    dep._include_dir = str( package_dir / "include" )
    dep._lib_dir = str( package_dir / "lib" )
    dep._library_prefix = ""
    dep._pkg_config_dir = None
    dep._package_id = "date/3.0.5"
    dep._package = "date"
    dep._registry = object()
    dep._resolve_lib_groups = gitlab_module.GitlabPackageDependency._resolve_lib_groups.__get__(
            dep
    )
    dep._link_contrib_key = gitlab_module.GitlabPackageDependency._link_contrib_key.__get__(
            dep
    )
    dep._package_link_mode = lambda: "prefer_shared"
    dep.include_dir = lambda: str( package_dir / "include" )
    dep._apply_default_use_libs = lambda env, dependency_name=None: None
    dep.initialise_build_variant = (
            gitlab_module.GitlabPackageDependency.initialise_build_variant.__get__( dep )
    )
    dep.use_libs = gitlab_module.GitlabPackageDependency.use_libs.__get__( dep )

    dep.initialise_build_variant( dep._env, _Named(), "rel" )
    assert dep._env["CPPDEFINES"] == [ "USE_OS_TZDB=1", "HAS_STRING_VIEW=1" ]

    dep.use_libs( [] )
    assert dep._env["CPPDEFINES"] == [ "USE_OS_TZDB=1", "HAS_STRING_VIEW=1" ]


def test_cmake_reports_transitive_interface_defines( tmp_path: Path ):
    if shutil.which( "cmake" ) is None:
        pytest.skip( "cmake is not on PATH" )

    source = tmp_path / "src"
    install = tmp_path / "install"
    source.mkdir()
    ( source / "CMakeLists.txt" ).write_text( textwrap.dedent( """\
            cmake_minimum_required(VERSION 3.20)
            project(widget LANGUAGES CXX)
            add_library(widget INTERFACE)
            target_compile_definitions(widget INTERFACE WIDGET_HAS_TLS=1)
            add_library(widget_extra INTERFACE)
            target_link_libraries(widget_extra INTERFACE widget)
            target_compile_definitions(widget_extra INTERFACE WIDGET_EXTRA=1)
            install(TARGETS widget widget_extra EXPORT widgetTargets)
            install(EXPORT widgetTargets
                NAMESPACE widget::
                DESTINATION lib/cmake/widget)
            install(FILES "${CMAKE_CURRENT_BINARY_DIR}/widgetConfig.cmake"
                DESTINATION lib/cmake/widget)
            file(WRITE "${CMAKE_CURRENT_BINARY_DIR}/widgetConfig.cmake"
                "include(\\"\\${CMAKE_CURRENT_LIST_DIR}/widgetTargets.cmake\\")\\n")
            """ ), encoding="utf-8" )
    build = tmp_path / "build"
    result = subprocess.run(
            [
                    "cmake", "-S", str( source ), "-B", str( build ),
                    "-DCMAKE_INSTALL_PREFIX={}".format( install ),
            ],
            capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr
    result = subprocess.run(
            [ "cmake", "--install", str( build ) ],
            capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr

    assert query_cmake_public_defines( str( install ) ) == [
            "WIDGET_HAS_TLS=1",
            "WIDGET_EXTRA=1",
    ]
