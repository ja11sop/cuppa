#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

import json
from pathlib import Path

import pytest

from cuppa.package_managers.cuppa_publish_manifest import (
        PUBLISH_FILENAME,
        build_publish_document,
        read_publish_manifest,
        write_publish_manifest,
)


pytestmark = pytest.mark.unit


def test_build_publish_document_keeps_package_source():
    document = build_publish_document(
            "widget",
            "1.0.0",
            dependencies=[
                    {
                            "name": "fmt",
                            "package": "fmt",
                            "version": "12.2.0",
                            "package_source": "/pubs/fmt",
                    }
            ],
            default_use_libs=[],
    )
    assert document["cuppa_publish_format"] == 1
    assert document["package"] == "widget"
    assert document["version"] == "1.0.0"
    assert document["default_use_libs"] == []
    assert document["dependencies"][0]["package_source"] == "/pubs/fmt"


def test_write_and_read_publish_manifest( tmp_path: Path ):
    path = write_publish_manifest(
            str( tmp_path ),
            "widget",
            "1.0.0",
            dependencies=[
                    {
                            "name": "fmt",
                            "package": "fmt",
                            "version": "12.2.0",
                            "registry": "same",
                            "package_source": str( tmp_path / "fmt" ),
                    }
            ],
    )
    assert Path( path ).name == PUBLISH_FILENAME
    loaded = read_publish_manifest( str( tmp_path ) )
    assert loaded["package"] == "widget"
    assert loaded["dependencies"][0]["package_source"] == str( tmp_path / "fmt" )


def test_write_publish_manifest_skips_key_order_only_rewrite( tmp_path: Path ):
    """Tracked manifests must not go dirty from sort_keys vs insertion order."""
    path = tmp_path / PUBLISH_FILENAME
    authored = (
            '{\n'
            '  "cuppa_publish_format": 1,\n'
            '  "package": "protobuf",\n'
            '  "version": "36.1",\n'
            '  "dependencies": [\n'
            '    {\n'
            '      "name": "abseil_cpp",\n'
            '      "package": "abseil-cpp",\n'
            '      "version": "20260107.1",\n'
            '      "registry": "same",\n'
            '      "package_source": "/pubs/abseil_cpp"\n'
            '    }\n'
            '  ]\n'
            '}\n'
    )
    path.write_text( authored, encoding="utf-8" )
    before = path.read_text( encoding="utf-8" )
    write_publish_manifest(
            str( tmp_path ),
            "protobuf",
            "36.1",
            dependencies=[
                    {
                            "name": "abseil_cpp",
                            "package": "abseil-cpp",
                            "version": "20260107.1",
                            "registry": "same",
                            "package_source": "/pubs/abseil_cpp",
                    }
            ],
    )
    assert path.read_text( encoding="utf-8" ) == before
    # New writes keep insertion order (package before version before dependencies).
    fresh = tmp_path / "fresh"
    fresh.mkdir()
    write_publish_manifest( str( fresh ), "widget", "1.0.0", dependencies=[] )
    text = ( fresh / PUBLISH_FILENAME ).read_text( encoding="utf-8" )
    assert text.index( '"package"' ) < text.index( '"version"' )
    assert text.index( '"version"' ) < text.index( '"dependencies"' )
    assert '"cuppa_publish_format"' in text
