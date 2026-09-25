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


def test_compute_payload_sha256_stable_and_ignores_traveling_json( tmp_path: Path ):
    from cuppa.package_managers.cuppa_publish_manifest import (
            PAYLOAD_SHA256_KEY,
            compute_payload_sha256,
            write_publish_manifest,
    )

    ( tmp_path / "include" ).mkdir()
    ( tmp_path / "lib" ).mkdir()
    header = tmp_path / "include" / "widget.hpp"
    header.write_text( "int x;\n", encoding="utf-8" )
    ( tmp_path / "lib" / "libwidget.a" ).write_bytes( b"archive" )

    first = compute_payload_sha256( str( tmp_path ) )
    assert first
    write_publish_manifest( str( tmp_path ), "widget", "1.0.0", dependencies=[] )
    # Traveling JSON must not change the payload digest.
    assert compute_payload_sha256( str( tmp_path ) ) == first

    loaded = read_publish_manifest( str( tmp_path ) )
    assert loaded[PAYLOAD_SHA256_KEY] == first

    header.write_text( "int y;\n", encoding="utf-8" )
    assert compute_payload_sha256( str( tmp_path ) ) != first


def test_compute_payload_sha256_none_without_payload( tmp_path: Path ):
    from cuppa.package_managers.cuppa_publish_manifest import compute_payload_sha256

    assert compute_payload_sha256( str( tmp_path ) ) is None
    write_publish_manifest( str( tmp_path ), "widget", "1.0.0", dependencies=[] )
    loaded = read_publish_manifest( str( tmp_path ) )
    assert "payload_sha256" not in loaded


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


def test_read_traveling_manifest_prefers_publish( tmp_path: Path ):
    from cuppa.package_managers.cuppa_dependency_manifest import (
            MANIFEST_FILENAME,
            write_manifest,
    )
    from cuppa.package_managers.cuppa_publish_manifest import (
            read_traveling_manifest,
            remove_legacy_dependency_manifest,
    )

    write_manifest(
            str( tmp_path ),
            [
                    {
                            "name": "legacy",
                            "package": "legacy",
                            "version": "1.0.0",
                    }
            ],
    )
    write_publish_manifest(
            str( tmp_path ),
            "widget",
            "2.0.0",
            dependencies=[
                    {
                            "name": "fmt",
                            "package": "fmt",
                            "version": "12.2.0",
                    }
            ],
    )
    document = read_traveling_manifest( str( tmp_path ) )
    assert document["cuppa_publish_format"] == 1
    assert document["dependencies"][0]["name"] == "fmt"


def test_read_traveling_manifest_falls_back_to_legacy_dependency( tmp_path: Path ):
    from cuppa.package_managers.cuppa_dependency_manifest import write_manifest
    from cuppa.package_managers.cuppa_publish_manifest import read_traveling_manifest

    write_manifest(
            str( tmp_path ),
            [
                    {
                            "name": "legacy",
                            "package": "legacy",
                            "version": "1.0.0",
                    }
            ],
    )
    document = read_traveling_manifest( str( tmp_path ) )
    assert document["dependencies"][0]["name"] == "legacy"
    assert "cuppa_publish_format" not in document


def test_remove_legacy_dependency_manifest( tmp_path: Path ):
    from cuppa.package_managers.cuppa_dependency_manifest import (
            MANIFEST_FILENAME,
            write_manifest,
    )
    from cuppa.package_managers.cuppa_publish_manifest import (
            remove_legacy_dependency_manifest,
    )

    write_manifest(
            str( tmp_path ),
            [ { "name": "fmt", "package": "fmt", "version": "1.0.0" } ],
    )
    assert ( tmp_path / MANIFEST_FILENAME ).is_file()
    assert remove_legacy_dependency_manifest( str( tmp_path ) ) is True
    assert not ( tmp_path / MANIFEST_FILENAME ).exists()
    assert remove_legacy_dependency_manifest( str( tmp_path ) ) is False
