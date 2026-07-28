#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

import pytest

from cuppa.cpp.module_scanner import (
    is_interface_source,
    sanitize_header_filename,
    sanitize_module_filename,
    scan_source_text,
)
from cuppa.methods.modules import dialect_rank


pytestmark = pytest.mark.unit


def test_scan_export_module_and_named_import():
    text = """
export module math;
import util;
export int add(int a, int b);
"""
    scan = scan_source_text( text )
    assert scan.export_module == "math"
    assert scan.module_declaration is None
    assert [ ( i.kind, i.name ) for i in scan.imports ] == [ ( "named", "util" ) ]


def test_scan_implementation_unit():
    text = """
module math;
import util;
int add(int a, int b) { return a + b; }
"""
    scan = scan_source_text( text )
    assert scan.export_module is None
    assert scan.module_declaration == "math"
    assert scan.imports[0].name == "util"


def test_scan_header_imports_and_comments():
    text = """
// import ignored;
/* import also;
   ignored */
import "widget.hpp";
import <vector>;
export import math;
"""
    scan = scan_source_text( text )
    kinds = [ ( i.kind, i.name ) for i in scan.imports ]
    assert kinds == [
        ( "header_quoted", "widget.hpp" ),
        ( "header_angle", "vector" ),
        ( "named", "math" ),
    ]


def test_is_interface_source_by_suffix_and_export():
    assert is_interface_source( "math.cppm" )
    assert is_interface_source( "math.cxxm" )
    scan = scan_source_text( "export module x;\n" )
    assert is_interface_source( "x.cpp", scan )
    assert not is_interface_source( "x.cpp", scan_source_text( "int x;\n" ) )


def test_sanitize_filenames():
    assert sanitize_module_filename( "foo.bar" ) == "foo--bar"
    assert sanitize_header_filename( "include/widget.hpp" ).startswith( "header--" )
    assert "/" not in sanitize_header_filename( "include/widget.hpp" )


def test_dialect_rank_cxx20_floor():
    assert dialect_rank( "c++17" ) < dialect_rank( "c++20" )
    assert dialect_rank( "c++2a" ) == dialect_rank( "c++20" )
    assert dialect_rank( "c++23" ) > dialect_rank( "c++20" )
