#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

"""Integration: BuildStaticLib keeps both same-basename objects in the archive."""

import subprocess

import pytest

from tests.helpers.cuppa_runner import assert_success, find_final_binaries, run_cuppa
from tests.helpers.project import copy_dummy_project, write_sconstruct, write_sconscript


pytestmark = pytest.mark.integration


def _write_archive_collision_fixture( project ):
    ( project / "src" / "detail" ).mkdir( parents=True, exist_ok=True )
    ( project / "src" / "buffers" / "detail" ).mkdir( parents=True, exist_ok=True )
    ( project / "src" / "detail" / "except.cpp" ).write_text(
        "namespace detail { int except() { return 1; } }\n",
        encoding="utf-8",
    )
    ( project / "src" / "buffers" / "detail" / "except.cpp" ).write_text(
        "namespace buffers { namespace detail { int except() { return 2; } } }\n",
        encoding="utf-8",
    )
    ( project / "apps" ).mkdir( parents=True, exist_ok=True )
    ( project / "apps" / "both_excepts.cpp" ).write_text(
        "namespace detail { int except(); }\n"
        "namespace buffers { namespace detail { int except(); } }\n"
        "int main() {\n"
        "    return detail::except() + buffers::detail::except() == 3 ? 0 : 1;\n"
        "}\n",
        encoding="utf-8",
    )
    write_sconstruct( project )
    write_sconscript(
        project,
        "Import('env')\n"
        "sources = env.RecursiveGlob('except.cpp', start='src')\n"
        "assert len(sources) == 2\n"
        "lib = env.BuildStaticLib('excepts', sources)\n"
        "env.Build('both_excepts', ['apps/both_excepts.cpp'], LIBS=[lib])\n",
    )


def _static_libs( project, name_stem ):
    matches = []
    for path in project.glob( "_build/**/final/**" ):
        if not path.is_file():
            continue
        name = path.name
        if name == "lib{}.a".format( name_stem ) or name == "{}.lib".format( name_stem ):
            matches.append( path )
    return sorted( matches )


def _archive_member_names( archive_path ):
    """List member basenames in a static archive (ar t or dumpbin /lib)."""
    if archive_path.suffix == ".lib":
        result = subprocess.run(
            [ "dumpbin", "/HEADERS", str( archive_path ) ],
            capture_output=True,
            text=True,
            check=False,
        )
        # Fallback: if dumpbin is awkward, rely on link success alone on MSVC.
        if result.returncode != 0:
            return None
        members = []
        for line in result.stdout.splitlines():
            line = line.strip()
            if line.endswith( ".obj" ) and " " not in line:
                members.append( line )
        return members

    result = subprocess.run(
        [ "ar", "t", str( archive_path ) ],
        capture_output=True,
        text=True,
        check=True,
    )
    return [ line.strip() for line in result.stdout.splitlines() if line.strip() ]


def test_build_static_lib_keeps_nested_same_basename_objects( tmp_path ):
    """Both except() symbols must remain linkable after BuildStaticLib."""
    project = copy_dummy_project( tmp_path )
    _write_archive_collision_fixture( project )

    result = run_cuppa( project, "--dbg", "--offline" )
    assert_success( result )

    binaries = find_final_binaries( project, "both_excepts" )
    assert binaries, "expected both_excepts under final/"

    run = subprocess.run( [ str( binaries[0] ) ], capture_output=True, text=True )
    assert run.returncode == 0, run.stdout + run.stderr

    archives = _static_libs( project, "excepts" )
    assert archives, "expected libexcepts.a / excepts.lib under final/"
    members = _archive_member_names( archives[0] )
    if members is not None:
        basenames = [ m.split( "/" )[-1] for m in members ]
        assert len( basenames ) == len( set( basenames ) ), members
        assert len( basenames ) >= 2, members
