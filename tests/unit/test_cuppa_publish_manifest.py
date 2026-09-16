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
