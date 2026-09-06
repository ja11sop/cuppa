#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

"""Unit tests for cuppa-dependency.json helpers."""

import json
from pathlib import Path

import pytest

from cuppa.package_managers.cuppa_dependency_manifest import (
    MANIFEST_FILENAME,
    build_manifest,
    normalise_dependency_entry,
    read_manifest,
    write_manifest,
)


pytestmark = pytest.mark.unit


def test_build_manifest_none_when_empty():
    assert build_manifest( None ) is None
    assert build_manifest( [] ) is None


def test_normalise_dict_entry():
    entry = normalise_dependency_entry( {
        "name": "boost_package",
        "package": "boost",
        "version": "1.91.0",
        "use_libs": ["system", "filesystem"],
    } )
    assert entry["name"] == "boost_package"
    assert entry["package"] == "boost"
    assert entry["version"] == "1.91.0"
    assert entry["registry"] == "same"
    assert entry["use_libs"] == ["system", "filesystem"]


def test_normalise_requires_version():
    with pytest.raises( ValueError, match="version" ):
        normalise_dependency_entry( { "name": "fmt", "package": "fmt" } )


def test_write_and_read_round_trip( tmp_path: Path ):
    deps = [
        {
            "name": "fmt",
            "package": "fmt",
            "version": "12.1.0",
            "registry": "same",
        }
    ]
    path = write_manifest( str( tmp_path ), deps )
    assert path is not None
    assert Path( path ).name == MANIFEST_FILENAME
    loaded = read_manifest( str( tmp_path ) )
    assert loaded["cuppa_dependency_format"] == 1
    assert loaded["dependencies"][0]["name"] == "fmt"
    assert loaded["dependencies"][0]["version"] == "12.1.0"


def test_write_omits_file_when_no_deps( tmp_path: Path ):
    assert write_manifest( str( tmp_path ), [] ) is None
    assert not ( tmp_path / MANIFEST_FILENAME ).exists()


def test_read_absent_returns_none( tmp_path: Path ):
    assert read_manifest( str( tmp_path ) ) is None


def test_read_rejects_bad_format( tmp_path: Path ):
    path = tmp_path / MANIFEST_FILENAME
    path.write_text(
        json.dumps( {
            "cuppa_dependency_format": 99,
            "dependencies": [ { "name": "x", "package": "x", "version": "1" } ],
        } ),
        encoding="utf-8",
    )
    with pytest.raises( ValueError, match="unsupported" ):
        read_manifest( str( tmp_path ) )
