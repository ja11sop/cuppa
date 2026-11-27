# Integration: StagePackageLibraries / env.Build default for shared package libs.

"""Tip binary with a shared develop package runs outside construction ENV.

Mirrors the local soak for package-runtime-deploy: publisher BuildSharedLib +
``link='shared'``, tip ``env.Build``, staged sibling ``lib/``, clean-env run,
disable flag, and ``-c`` removing the staged copy.
"""

from __future__ import annotations

import os
import platform
import subprocess
from pathlib import Path

import pytest

from tests.helpers.cuppa_runner import (
        assert_success,
        find_final_binaries,
        find_under_build,
        run_cuppa,
)
from tests.helpers.project import write_sconstruct, write_sconscript


pytestmark = pytest.mark.integration


_PUBLISHER_SCONSCRIPT = """\
Import('env')
from cuppa.package_managers.gitlab import GitlabPackagePublisher
env.AppendUnique(CPPPATH=['#/include'])
# MSVC only emits an import .lib when the DLL exports symbols.
env.AppendUnique(CPPDEFINES=['WIDGET_BUILDING'])
lib = env.BuildSharedLib('widget', 'src/widget.cpp')
publisher = GitlabPackagePublisher(
    env,
    source_include_dir='#/include',
    source_lib_dir=env['abs_final_dir'],
    registry='https://gitlab.example/api/v4/projects/1',
    package='widget',
    version='1.0.0',
    default_use_libs=['widget'],
    link='shared',
)
env.PublishPackage(lib, publisher)
"""


def own_home( tmp_path ):
    home = tmp_path / "home"
    home.mkdir( exist_ok=True )
    return {"HOME": str( home ), "USERPROFILE": str( home )}


def _write_shared_publisher( root: Path ):
    ( root / "include" / "widget" ).mkdir( parents=True )
    ( root / "src" ).mkdir( parents=True )
    # dllexport/dllimport so MSVC produces widget.lib for the tip link.
    ( root / "include" / "widget" / "api.hpp" ).write_text(
            "#ifndef WIDGET_API_HPP\n"
            "#define WIDGET_API_HPP\n"
            "#if defined(_WIN32)\n"
            "#  if defined(WIDGET_BUILDING)\n"
            "#    define WIDGET_API __declspec(dllexport)\n"
            "#  else\n"
            "#    define WIDGET_API __declspec(dllimport)\n"
            "#  endif\n"
            "#else\n"
            "#  define WIDGET_API\n"
            "#endif\n"
            "WIDGET_API int widget_answer();\n"
            "#endif\n",
            encoding="utf-8",
    )
    ( root / "src" / "widget.cpp" ).write_text(
            '#include "widget/api.hpp"\n'
            "WIDGET_API int widget_answer() { return 42; }\n",
            encoding="utf-8",
    )
    write_sconstruct( root )
    write_sconscript( root, _PUBLISHER_SCONSCRIPT )


def _write_tip( tip: Path, develop_path: str, *, stage: bool = True ):
    write_sconstruct(
            tip,
            body="""\
import cuppa

Widget = cuppa.package_dependency(
    'widget',
    registry='https://gitlab.example/api/v4/projects/1',
    package='widget',
    version='1.0.0',
    develop={develop!r},
)

cuppa.run(
    default_variants=['dbg'],
    import_dependencies=[Widget],
    auto_enable_dependencies=[Widget],
)
""".format( develop=develop_path ),
    )
    if stage:
        sconscript = "Import('env')\nenv.Build('widget_tip', 'main.cpp')\n"
    else:
        sconscript = (
                "Import('env')\n"
                "env.Build('widget_tip', 'main.cpp', stage_package_libraries=False)\n"
        )
    write_sconscript( tip, sconscript )
    ( tip / "main.cpp" ).write_text(
            "#include <widget/api.hpp>\n"
            "#include <cstdio>\n"
            "int main() {\n"
            '    std::printf("answer=%d\\n", widget_answer());\n'
            "    return widget_answer() == 42 ? 0 : 1;\n"
            "}\n",
            encoding="utf-8",
    )


def _staged_shared_libs( tip: Path ):
    """Return staged package shared libs under tip ``final/`` (sibling ``lib/`` or beside).

    POSIX uses ``libwidget.so``; MSVC uses ``widget.dll`` beside the exe.
    """
    matches = []
    for pattern in ( "libwidget*", "widget.dll", "widget.dylib" ):
        for path in find_under_build( tip, pattern ):
            if not path.is_file():
                continue
            if "final" not in path.parts:
                continue
            # Skip publisher package extract trees nested under tip storage.
            if path.suffix in ( ".so", ".dylib", ".dll" ) or ".so." in path.name:
                matches.append( path )
    # Stable unique preserve order
    seen = set()
    unique = []
    for path in matches:
        key = str( path )
        if key not in seen:
            seen.add( key )
            unique.append( path )
    return unique


def _run_detached( binary: Path ):
    """Run without package search-path ENV (loader must use ORIGIN / side-by-side)."""
    if platform.system() == "Windows":
        # Keep the runner PATH for the CRT; Windows still searches the exe
        # directory first for DLLs (where Stage places widget.dll).
        env = {
                "PATH": os.environ.get( "PATH", "" ),
                "SystemRoot": os.environ.get( "SystemRoot", "" ),
                "SYSTEMROOT": os.environ.get( "SYSTEMROOT", "" ),
        }
    else:
        env = {
                "PATH": os.environ.get( "PATH", "/usr/bin:/bin" ),
        }
    # Drop any inherited library path so the soak matches a clean shell.
    return subprocess.run(
            [ str( binary ) ],
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=30,
    )


def _elf_runpath( binary: Path ):
    if platform.system() != "Linux":
        return None
    result = subprocess.run(
            [ "readelf", "-d", str( binary ) ],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=30,
    )
    if result.returncode != 0:
        return None
    for line in result.stdout.splitlines():
        if "RUNPATH" in line or "RPATH" in line:
            return line
    return None


def test_build_stages_shared_package_libs_for_detached_run( tmp_path ):
    publisher = tmp_path / "publisher"
    _write_shared_publisher( publisher )
    assert_success(
            run_cuppa( publisher, "--dbg", timeout=360, extra_env=own_home( tmp_path ) )
    )
    if platform.system() == "Windows":
        import_libs = [
                path for path in find_under_build( publisher, "widget.lib" )
                if path.is_file() and "final" in path.parts
        ]
        assert import_libs, (
                "MSVC shared package needs widget.lib (import library) under final/; "
                "export symbols with WIDGET_BUILDING / dllexport"
        )

    tip = tmp_path / "tip"
    tip.mkdir()
    storage = tmp_path / "storage"
    _write_tip( tip, os.path.relpath( str( publisher ), str( tip ) ), stage=True )

    result = run_cuppa(
            tip,
            "--dbg",
            "--develop",
            "--storage-root={}".format( storage ),
            timeout=360,
            extra_env=own_home( tmp_path ),
    )
    assert_success( result )
    assert "Applying default_use_libs" in result.stdout or "default_use_libs" in result.stdout

    binaries = find_final_binaries( tip, "widget_tip" )
    assert binaries, "expected tip program under final/"
    binary = binaries[0]

    staged = [
            path for path in _staged_shared_libs( tip )
            if path.parent.name == "lib" or path.parent == binary.parent
    ]
    assert staged, "expected staged libwidget under final/lib/ (or widget.dll beside exe on Windows)"

    runpath = _elf_runpath( binary )
    if runpath is not None:
        assert "$ORIGIN" in runpath
        assert "$ORIGIN/lib" in runpath or "ORIGIN/lib" in runpath

    detached = _run_detached( binary )
    assert detached.returncode == 0, detached.stdout
    assert "answer=42" in detached.stdout

    # Clean removes the staged copy with the program.
    assert_success(
            run_cuppa(
                    tip,
                    "--dbg",
                    "--develop",
                    "--storage-root={}".format( storage ),
                    "-c",
                    timeout=360,
                    extra_env=own_home( tmp_path ),
            )
    )
    assert not binary.exists()
    assert not any( path.exists() for path in staged )


def test_build_stage_package_libraries_false_skips_stage( tmp_path ):
    publisher = tmp_path / "publisher"
    _write_shared_publisher( publisher )
    assert_success(
            run_cuppa( publisher, "--dbg", timeout=360, extra_env=own_home( tmp_path ) )
    )

    tip = tmp_path / "tip"
    tip.mkdir()
    storage = tmp_path / "storage"
    _write_tip( tip, os.path.relpath( str( publisher ), str( tip ) ), stage=False )

    result = run_cuppa(
            tip,
            "--dbg",
            "--develop",
            "--storage-root={}".format( storage ),
            timeout=360,
            extra_env=own_home( tmp_path ),
    )
    assert_success( result )

    binaries = find_final_binaries( tip, "widget_tip" )
    assert binaries
    binary = binaries[0]

    sibling_lib = binary.parent / "lib"
    assert not sibling_lib.exists() or not any( sibling_lib.iterdir() )
    if platform.system() == "Windows":
        assert not ( binary.parent / "widget.dll" ).exists()

    detached = _run_detached( binary )
    assert detached.returncode != 0
    if platform.system() != "Windows":
        assert "libwidget" in detached.stdout or "shared libraries" in detached.stdout
