import pytest

from cuppa.utility import file_types
from cuppa.utility.version import get_version
from cuppa.dependencies.boost.library_naming import extract_library_name_from_path


pytestmark = pytest.mark.unit


def test_file_type_predicates():
    assert file_types.is_json("a.json")
    assert file_types.is_html("a.HTML")
    assert file_types.is_asciidoc("doc.adoc")
    assert file_types.is_yaml("x.yml")
    assert file_types.is_j2_template("t.html.j2")
    assert not file_types.is_json("a.txt")


def test_get_version_reads_package_version():
    version = get_version()
    assert isinstance(version, str)
    assert version


def test_extract_library_name_from_path():
    assert extract_library_name_from_path("/tmp/libboost_filesystem.so") == "filesystem"
    assert extract_library_name_from_path("libboost_system-mt.a") == "system"
