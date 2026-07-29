#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

import pytest

from cuppa.methods.remove_flags import RemoveFlagsMethod


@pytest.mark.unit
@pytest.mark.parametrize(
    "flag,family",
    [
        ( "-std=c++20", "-std" ),
        ( "-std:c++20", "-std" ),
        ( "-std:c++23", "-std" ),
        ( "/std:c++latest", "-std" ),
        ( "-Wall", "-Wall" ),
        ( "-DBOOST=1", "-DBOOST" ),
    ],
)
def test_flag_family( flag, family ):
    assert RemoveFlagsMethod._flag_family( flag ) == family


@pytest.mark.unit
def test_remove_flags_swaps_msvc_std_dialect():
    """ReplaceFlags relies on RemoveFlags matching MSVC -std: as a family."""
    class _Env(dict):
        def Replace( self, **kwargs ):
            self.update( kwargs )

    env = _Env(
        CCFLAGS=[],
        CXXFLAGS=[ "-W4", "-std:c++20", "-EHsc" ],
        CFLAGS=[],
        LINKFLAGS=[],
    )
    RemoveFlagsMethod()( env, [ "-std:c++23" ] )
    assert "-std:c++20" not in env["CXXFLAGS"]
    assert "-W4" in env["CXXFLAGS"]
    assert "-EHsc" in env["CXXFLAGS"]
