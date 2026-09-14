#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

"""Unit tests for shared-aware package library resolution."""

from pathlib import Path

import pytest
import SCons.Errors

from cuppa.package_managers.package_link_libs import (
    apply_resolved_libs,
    clear_package_link_contribution,
    find_shared_library_path,
    heuristic_default_use_libs,
    list_linkable_lib_stems,
    list_shared_lib_stems,
    list_static_lib_stems,
    record_package_link_contribution,
    resolve_library_artefact,
)


pytestmark = pytest.mark.unit


class _FakeEnv( dict ):

    def AppendUnique( self, **kwargs ):
        for key, value in kwargs.items():
            current = list( self.get( key ) or [] )
            for item in value if isinstance( value, ( list, tuple ) ) else [ value ]:
                if item not in current and str( item ) not in { str( x ) for x in current }:
                    current.append( item )
            self[key] = current

    def File( self, path ):
        return path


def test_list_static_and_shared_stems( tmp_path: Path ):
    lib_dir = tmp_path / "lib"
    lib_dir.mkdir()
    ( lib_dir / "libfmt.a" ).write_text( "a", encoding="utf-8" )
    ( lib_dir / "libfmt.so" ).write_text( "s", encoding="utf-8" )
    ( lib_dir / "libdate-tz.so.3" ).write_text( "s", encoding="utf-8" )
    ( lib_dir / "notes.txt" ).write_text( "x", encoding="utf-8" )

    assert list_static_lib_stems( str( lib_dir ), "lib", ".a" ) == ["fmt"]
    assert list_shared_lib_stems( str( lib_dir ), "lib", ".so" ) == ["date-tz", "fmt"]
    assert list_linkable_lib_stems(
            str( lib_dir ), "lib", ".a", "lib", ".so"
    ) == ["date-tz", "fmt"]


def test_find_versioned_shared_library( tmp_path: Path ):
    lib_dir = tmp_path / "lib"
    lib_dir.mkdir()
    path = lib_dir / "libfmt.so.12.2.0"
    path.write_text( "s", encoding="utf-8" )
    assert find_shared_library_path( str( lib_dir ), "fmt", "lib", ".so" ) == str( path )


def test_resolve_prefers_static_then_shared( tmp_path: Path ):
    lib_dir = tmp_path / "lib"
    lib_dir.mkdir()
    ( lib_dir / "libfmt.a" ).write_text( "a", encoding="utf-8" )
    ( lib_dir / "libfmt.so" ).write_text( "s", encoding="utf-8" )
    env = _FakeEnv( LIBPREFIX="lib", LIBSUFFIX=".a", SHLIBPREFIX="lib", SHLIBSUFFIX=".so" )

    kind, value = resolve_library_artefact( str( lib_dir ), "fmt", env )
    assert kind == "static"
    assert value.endswith( "libfmt.a" )

    ( lib_dir / "libfmt.a" ).unlink()
    kind, value = resolve_library_artefact( str( lib_dir ), "fmt", env )
    assert kind == "shared"
    assert value == "fmt"


def test_resolve_missing_raises( tmp_path: Path ):
    lib_dir = tmp_path / "lib"
    lib_dir.mkdir()
    env = _FakeEnv( LIBPREFIX="lib", LIBSUFFIX=".a", SHLIBPREFIX="lib", SHLIBSUFFIX=".so" )
    with pytest.raises( SCons.Errors.StopError, match="not found" ):
        resolve_library_artefact( str( lib_dir ), "missing", env )


def test_env_lib_naming_expands_scons_refs():
    class _Env( dict ):
        def subst( self, expression ):
            text = expression
            if text.startswith( "$" ):
                key = text[1:]
                value = self.get( key, "" )
                if isinstance( value, str ) and value.startswith( "$" ):
                    return self.subst( value )
                return str( value )
            return text

    env = _Env( LIBPREFIX="lib", LIBSUFFIX=".a", SHLIBPREFIX="$LIBPREFIX", SHLIBSUFFIX=".so" )
    from cuppa.package_managers.package_link_libs import env_lib_naming
    assert env_lib_naming( env ) == ( "lib", ".a", "lib", ".so" )


def test_apply_shared_sets_libpath_and_sharedlibs( tmp_path: Path ):
    lib_dir = tmp_path / "lib"
    lib_dir.mkdir()
    ( lib_dir / "libfmt.so" ).write_text( "s", encoding="utf-8" )
    env = _FakeEnv( LIBPREFIX="lib", LIBSUFFIX=".a", SHLIBPREFIX="lib", SHLIBSUFFIX=".so" )

    contrib = apply_resolved_libs( env, str( lib_dir ), ["fmt"], package_id="fmt/1/rel" )
    assert contrib["shared"] == ["fmt"]
    assert contrib["libpath"] == [str( lib_dir )]
    assert env["SHAREDLIBS"] == ["fmt"]
    assert env["LIBPATH"] == [str( lib_dir )]
    assert env.get( "STATICLIBS", [] ) == []


def test_replace_contribution_clears_prior_shared( tmp_path: Path ):
    lib_dir = tmp_path / "lib"
    lib_dir.mkdir()
    ( lib_dir / "libfmt.so" ).write_text( "s", encoding="utf-8" )
    ( lib_dir / "libextra.so" ).write_text( "s", encoding="utf-8" )
    env = _FakeEnv( LIBPREFIX="lib", LIBSUFFIX=".a", SHLIBPREFIX="lib", SHLIBSUFFIX=".so" )

    first = apply_resolved_libs( env, str( lib_dir ), ["fmt"] )
    record_package_link_contribution(
            env, "fmt", static=first["static"], shared=first["shared"], libpath=first["libpath"]
    )
    clear_package_link_contribution( env, "fmt" )
    assert env.get( "SHAREDLIBS", [] ) == []
    assert env.get( "LIBPATH", [] ) == []

    second = apply_resolved_libs( env, str( lib_dir ), ["extra"] )
    record_package_link_contribution(
            env, "fmt", static=second["static"], shared=second["shared"], libpath=second["libpath"]
    )
    assert env["SHAREDLIBS"] == ["extra"]
