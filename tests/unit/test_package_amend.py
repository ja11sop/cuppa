#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

import pytest

from cuppa.package_managers.package_amend import (
        amend_package_manifest_enabled,
        package_stage_has_payload,
)


pytestmark = pytest.mark.unit


def test_package_stage_has_payload( tmp_path ):
    assert not package_stage_has_payload( str( tmp_path / "missing" ) )
    base = tmp_path / "widget" / "1.0.0"
    base.mkdir( parents=True )
    assert not package_stage_has_payload( str( base ) )
    ( base / "include" ).mkdir()
    assert package_stage_has_payload( str( base ) )


def test_amend_package_manifest_enabled():
    class _Env:
        def get_option( self, name, default=None ):
            return name == "amend-package-manifest"

    assert amend_package_manifest_enabled( _Env() )
    assert not amend_package_manifest_enabled( object() )
