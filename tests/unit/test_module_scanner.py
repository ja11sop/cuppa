#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

import pytest

from cuppa.cpp.module_scanner import (
    ModuleImport,
    is_interface_source,
    module_bmi_name,
    owning_module_name,
    parse_header_unit_declaration,
    primary_module_name,
    qualify_relative_import,
    sanitize_header_filename,
    sanitize_module_filename,
    scan_file,
    scan_source_text,
    std_module_imports_from_scan,
    strip_comments,
)


@pytest.mark.unit
def test_strip_comments_line_and_block():
    text = (
        "export module math; // trailing\n"
        "/* block\n"
        "   comment */\n"
        "import std;\n"
    )
    cleaned = strip_comments( text )
    assert "//" not in cleaned
    assert "block" not in cleaned
    assert "export module math;" in cleaned
    assert "import std;" in cleaned


@pytest.mark.unit
def test_scan_export_module_and_named_import():
    scan = scan_source_text(
        "export module math;\n"
        "import util;\n"
        "export int add(int, int);\n"
    )
    assert scan.export_module == "math"
    assert scan.module_declaration is None
    assert scan.private_fragment is False
    assert scan.imports == [ ModuleImport( "named", "util" ) ]


@pytest.mark.unit
def test_scan_interface_partition_and_relative_reexport():
    scan = scan_source_text(
        "export module geo:point;\n"
        "export import :helpers;\n"
    )
    assert scan.export_module == "geo:point"
    assert scan.imports == [ ModuleImport( "named", ":helpers" ) ]
    assert module_bmi_name( scan ) == "geo:point"
    assert owning_module_name( scan ) == "geo:point"
    assert qualify_relative_import( ":helpers", owning_module_name( scan ) ) == "geo:helpers"


@pytest.mark.unit
def test_scan_implementation_partition_bmi():
    scan = scan_source_text( "module calc:core;\nimport calc;\n" )
    assert scan.export_module is None
    assert scan.module_declaration == "calc:core"
    assert module_bmi_name( scan ) == "calc:core"


@pytest.mark.unit
def test_scan_implementation_unit_has_no_bmi():
    scan = scan_source_text( "module math;\nint add( int A, int B ) { return A + B; }\n" )
    assert scan.module_declaration == "math"
    assert module_bmi_name( scan ) is None


@pytest.mark.unit
def test_scan_private_module_fragment():
    scan = scan_source_text(
        "export module secrets;\n"
        "export int reveal();\n"
        "module :private;\n"
        "int reveal() { return 42; }\n"
    )
    assert scan.export_module == "secrets"
    assert scan.private_fragment is True


@pytest.mark.unit
def test_scan_header_imports_quoted_and_angle():
    scan = scan_source_text(
        'import "include/widget.hpp";\n'
        "import <span>;\n"
        "export import <vector>;\n"
    )
    assert scan.imports == [
        ModuleImport( "header_quoted", "include/widget.hpp" ),
        ModuleImport( "header_angle", "span" ),
        ModuleImport( "header_angle", "vector" ),
    ]


@pytest.mark.unit
def test_scan_import_std_and_compat():
    scan = scan_source_text( "import std;\nimport std.compat;\n" )
    assert std_module_imports_from_scan( scan ) == { "std", "std.compat" }


@pytest.mark.unit
def test_scan_ignores_commented_out_imports():
    scan = scan_source_text(
        "export module m;\n"
        "// import hidden;\n"
        "/* import also_hidden; */\n"
        "import visible;\n"
    )
    assert scan.imports == [ ModuleImport( "named", "visible" ) ]


@pytest.mark.unit
def test_primary_and_qualify_helpers():
    assert primary_module_name( "geo:point" ) == "geo"
    assert primary_module_name( "geo" ) == "geo"
    assert primary_module_name( ":point" ) is None
    assert qualify_relative_import( "util", "geo" ) == "util"
    assert qualify_relative_import( ":point", None ) == ":point"


@pytest.mark.unit
def test_sanitize_filenames():
    assert sanitize_module_filename( "geo:point" ) == "geo--point"
    assert sanitize_module_filename( "std.compat" ) == "std--compat"
    assert sanitize_header_filename( "include/widget.hpp" ) == "header--include--widget.hpp"
    assert sanitize_header_filename( "<span>" ) == "header--angle--span"


@pytest.mark.unit
def test_parse_header_unit_declaration():
    assert parse_header_unit_declaration( "<span>" ) == ( "angle", "span", "<span>" )
    assert parse_header_unit_declaration( '"a/b.hpp"' ) == ( "quoted", "a/b.hpp", "a/b.hpp" )
    assert parse_header_unit_declaration( "include/widget.hpp" ) == (
        "quoted",
        "include/widget.hpp",
        "include/widget.hpp",
    )


@pytest.mark.unit
def test_is_interface_source_by_suffix_and_scan( tmp_path ):
    assert is_interface_source( "math.cppm" ) is True
    assert is_interface_source( "math.ixx" ) is True
    assert is_interface_source( "main.cpp" ) is False
    scan = scan_source_text( "export module math;\n" )
    assert is_interface_source( "math.cpp", scan ) is True
    path = tmp_path / "util.cppm"
    path.write_text( "export module util;\n" )
    assert scan_file( str( path ) ).export_module == "util"
