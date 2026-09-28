#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

"""Unit coverage for integration HOME isolation helpers."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from tests.helpers.home import apply_isolated_home, isolated_home_dir


pytestmark = pytest.mark.unit


def test_isolated_home_dir_creates_under_tmp( tmp_path ):
    home = isolated_home_dir( tmp_path )
    assert home == tmp_path / 'home'
    assert home.is_dir()
    # Idempotent for tests that also call own_home(tmp_path).
    again = isolated_home_dir( tmp_path )
    assert again == home


def test_apply_isolated_home_sets_env( tmp_path, monkeypatch ):
    home = apply_isolated_home( tmp_path, monkeypatch )
    assert os.environ['HOME'] == str( home )
    assert os.environ['USERPROFILE'] == str( home )


def test_apply_isolated_home_seeds_conan_profile_when_real_one_exists(
        tmp_path, monkeypatch
):
    real_default = Path.home() / '.conan2' / 'profiles' / 'default'
    if not real_default.is_file():
        pytest.skip( 'no developer Conan default profile to copy' )
    home = apply_isolated_home( tmp_path, monkeypatch )
    assert ( home / '.conan2' / 'profiles' / 'default' ).is_file()
