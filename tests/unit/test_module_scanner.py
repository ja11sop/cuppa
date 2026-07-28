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
    qualify_relative_import,
    sanitize_header_filename,
    sanitize_module_filename,
    scan_source_text,
    std_module_imports_from_scan,
    strip_comments,
)


pytestmark = pytest.mark.unit


def test_scan_named_module_and_import():
    scan = scan_source_text(
        "export module math;\n"
        "export int add(int a, int b);\n"
    )
    assert scan.export_module == "math"
    assert module_bmi_name(scan) == "math"
    assert is_interface_source("math.cppm", scan)


def test_scan_partition_and_relative_import():
    scan = scan_source_text(
        "export module geo;\n"
        "export import :point;\n"
        "import util;\n"
    )
    assert scan.export_module == "geo"
    assert ModuleImport("named", ":point") in scan.imports
    assert ModuleImport("named", "util") in scan.imports
    assert qualify_relative_import(":point", "geo") == "geo:point"
    assert owning_module_name(scan) == "geo"


def test_scan_implementation_partition_bmi():
    scan = scan_source_text("module calc:core;\nint core_add(int, int);\n")
    assert scan.module_declaration == "calc:core"
    assert module_bmi_name(scan) == "calc:core"


def test_scan_implementation_unit_no_bmi():
    scan = scan_source_text("module math;\nint add(int a, int b) { return a + b; }\n")
    assert scan.module_declaration == "math"
    assert module_bmi_name(scan) is None


def test_scan_header_imports_and_private_fragment():
    scan = scan_source_text(
        'export module secrets;\n'
        'import "include/widget.hpp";\n'
        "import <span>;\n"
        "module :private;\n"
        "static int hidden = 1;\n"
    )
    assert scan.private_fragment is True
    assert ModuleImport("header_quoted", "include/widget.hpp") in scan.imports
    assert ModuleImport("header_angle", "span") in scan.imports


def test_strip_comments_removes_line_and_block():
    text = strip_comments(
        "// export module fake;\n"
        "export module real;\n"
        "/* import ghost; */\n"
        "import math;\n"
    )
    scan = scan_source_text(text)
    assert scan.export_module == "real"
    assert ModuleImport("named", "math") in scan.imports
    assert not any(item.name == "fake" for item in scan.imports)


def test_parse_header_unit_and_sanitize():
    assert parse_header_unit_declaration("<span>") == ("angle", "span", "<span>")
    assert sanitize_header_filename("<span>").startswith("header--angle--span")
    assert sanitize_module_filename("geo:point") == "geo--point"


def test_std_module_imports_from_scan():
    scan = scan_source_text("import std;\nimport std.compat;\nimport math;\n")
    assert std_module_imports_from_scan(scan) == {"std", "std.compat"}
