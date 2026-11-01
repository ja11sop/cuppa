#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

"""Installed .pc files become ${pcfiledir}-relative after install."""

from pathlib import Path

import pytest

from cuppa.buildsys.pkgconfig import (
        prefix_in_package_tree,
        relocate_pkgconfig,
        rewrite_pc_text,
)


pytestmark = pytest.mark.unit


_FMT = """\
prefix=/opt/pkg/fmt/12.2.0
libdir=${prefix}/lib
includedir=${prefix}/include

Name: fmt
Libs: -L${libdir} -lfmt
Cflags: -I${includedir}
"""

_PROTOBUF = """\
prefix=/opt/pkg/protobuf/36.1
exec_prefix=/opt/pkg/protobuf/36.1
libdir=/opt/pkg/protobuf/36.1/lib
includedir=/opt/pkg/protobuf/36.1/include

Libs: -L${libdir} -lprotobuf
Cflags: -I${includedir} -DPROTOBUF_USE_DLLS
"""

_RE2 = """\
includedir=/opt/pkg/re2/include
libdir=/opt/pkg/re2/lib

Cflags: -pthread -I${includedir}
Libs: -pthread -L${libdir} -lre2
"""

_OTEL = """\
prefix=${pcfiledir}/../..
exec_prefix=${prefix}
libdir=${exec_prefix}/lib
includedir=${prefix}/include
"""


def test_fmt_prefix_becomes_pcfiledir_and_keeps_variable_refs():
    pc_dir = "/opt/pkg/fmt/12.2.0/lib/pkgconfig"
    updated = rewrite_pc_text( _FMT, "/opt/pkg/fmt/12.2.0", pc_dir )
    assert updated.startswith( "prefix=${pcfiledir}/../..\n" )
    assert "libdir=${prefix}/lib" in updated
    assert "/opt/pkg" not in updated


def test_protobuf_absolute_variables_use_prefix():
    pc_dir = "/opt/pkg/protobuf/36.1/lib/pkgconfig"
    updated = rewrite_pc_text( _PROTOBUF, "/opt/pkg/protobuf/36.1", pc_dir )
    assert "prefix=${pcfiledir}/../.." in updated
    assert "exec_prefix=${prefix}" in updated
    assert "libdir=${prefix}/lib" in updated
    assert "includedir=${prefix}/include" in updated
    assert "/opt/pkg" not in updated


def test_re2_gains_a_prefix_line():
    pc_dir = "/opt/pkg/re2/lib/pkgconfig"
    updated = rewrite_pc_text( _RE2, "/opt/pkg/re2", pc_dir )
    assert updated.splitlines()[0] == "prefix=${pcfiledir}/../.."
    assert "includedir=${prefix}/include" in updated
    assert "libdir=${prefix}/lib" in updated


def test_share_pkgconfig_is_also_two_levels_up():
    text = "prefix=/opt/pkg/json/3.12.0\nincludedir=${prefix}/include\n"
    pc_dir = "/opt/pkg/json/3.12.0/share/pkgconfig"
    updated = rewrite_pc_text( text, "/opt/pkg/json/3.12.0", pc_dir )
    assert "prefix=${pcfiledir}/../.." in updated


def test_triple_pkgconfig_dir_is_three_levels_up():
    text = "prefix=/opt/pkg/grpc/1\nlibdir=${prefix}/lib\n"
    pc_dir = "/opt/pkg/grpc/1/lib/x86_64-linux-gnu/pkgconfig"
    updated = rewrite_pc_text( text, "/opt/pkg/grpc/1", pc_dir )
    assert "prefix=${pcfiledir}/../../.." in updated


def test_pcfiledir_prefix_is_left_alone():
    assert rewrite_pc_text( _OTEL, "/opt/pkg/otel/1.28.0", "/opt/pkg/otel/1.28.0/lib/pkgconfig" ) == _OTEL


def test_path_outside_the_prefix_is_left_alone():
    text = "prefix=/opt/pkg/fmt/1\nLibs: -L${libdir} -L/usr/lib -lfmt\n"
    updated = rewrite_pc_text( text, "/opt/pkg/fmt/1", "/opt/pkg/fmt/1/lib/pkgconfig" )
    assert "-L/usr/lib" in updated
    assert "prefix=${pcfiledir}/../.." in updated


def test_raw_cflags_path_under_the_prefix_is_rewritten():
    text = "Cflags: -I/opt/pkg/fmt/1/include -DFOO\n"
    updated = rewrite_pc_text( text, "/opt/pkg/fmt/1", "/opt/pkg/fmt/1/lib/pkgconfig" )
    assert "-I${prefix}/include" in updated
    assert "-DFOO" in updated
    assert updated.splitlines()[0] == "prefix=${pcfiledir}/../.."


def test_relocate_is_idempotent( tmp_path: Path ):
    pc_dir = tmp_path / "lib" / "pkgconfig"
    pc_dir.mkdir( parents=True )
    pc = pc_dir / "fmt.pc"
    pc.write_text( _FMT.replace( "/opt/pkg/fmt/12.2.0", str( tmp_path ) ), encoding="utf-8" )
    first = relocate_pkgconfig( str( tmp_path ) )
    assert first == [ "lib/pkgconfig/fmt.pc" ]
    assert "${pcfiledir}/../.." in pc.read_text( encoding="utf-8" )
    assert relocate_pkgconfig( str( tmp_path ) ) == []


def test_prefix_outside_the_package_tree_is_not_rewritten():
    env = {
            "sconstruct_dir": "/work/packages/fmt",
            "abs_final_dir": "/work/packages/fmt/_build/final",
            "abs_build_dir": "/work/packages/fmt/_build/working",
    }
    assert prefix_in_package_tree( env, "/work/packages/fmt/_build/final/fmt/12.2.0" )
    assert not prefix_in_package_tree( env, "/usr/local" )
    assert not prefix_in_package_tree( {}, "/work/packages/fmt/_build/final/fmt/12.2.0" )
