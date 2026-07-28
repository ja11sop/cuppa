#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

import pytest

from cuppa.cpp.module_scanner import (
    is_interface_source,
    module_bmi_name,
    primary_module_name,
    qualify_relative_import,
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
    assert scan.private_fragment is False
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
    assert module_bmi_name( scan ) is None
    assert scan.imports[0].name == "util"


def test_scan_interface_partition_and_relative_import():
    part = scan_source_text( "export module geo:point;\nexport struct Point { int x; int y; };\n" )
    assert part.export_module == "geo:point"
    assert module_bmi_name( part ) == "geo:point"

    primary = scan_source_text(
        "export module geo;\nexport import :point;\nexport int origin_distance(Point p);\n"
    )
    assert primary.export_module == "geo"
    assert [ ( i.kind, i.name ) for i in primary.imports ] == [ ( "named", ":point" ) ]
    assert qualify_relative_import( ":point", "geo" ) == "geo:point"
    assert qualify_relative_import( ":point", "geo:other" ) == "geo:point"
    assert primary_module_name( "geo:point" ) == "geo"


def test_scan_implementation_partition():
    scan = scan_source_text( "module calc:core;\nint core_add(int a, int b) { return a + b; }\n" )
    assert scan.export_module is None
    assert scan.module_declaration == "calc:core"
    assert module_bmi_name( scan ) == "calc:core"
    assert not is_interface_source( "calc/core.cpp", scan )


def test_scan_private_module_fragment():
    text = """
export module secrets;
export int public_answer();
module :private;
static int hidden = 7;
int public_answer() { return hidden; }
"""
    scan = scan_source_text( text )
    assert scan.export_module == "secrets"
    assert scan.private_fragment is True
    assert scan.module_declaration is None
    assert module_bmi_name( scan ) == "secrets"


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
    assert sanitize_module_filename( "geo:point" ) == "geo--point"
    assert sanitize_header_filename( "include/widget.hpp" ).startswith( "header--" )
    assert "/" not in sanitize_header_filename( "include/widget.hpp" )


def test_dialect_rank_cxx20_floor():
    assert dialect_rank( "c++17" ) < dialect_rank( "c++20" )
    assert dialect_rank( "c++2a" ) == dialect_rank( "c++20" )
    assert dialect_rank( "c++23" ) > dialect_rank( "c++20" )
