#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

"""Per-test home isolation for integration runs (and unit tests of that path)."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path


def isolated_home_dir( tmp_path: Path ) -> Path:
    """Return ``tmp_path / 'home'``, creating it if needed."""
    home = tmp_path / 'home'
    home.mkdir( exist_ok=True )
    return home


def _real_home_before_isolation() -> Path:
    env_home = os.environ.get( 'HOME' ) or os.environ.get( 'USERPROFILE' )
    if env_home:
        return Path( env_home )
    return Path.home()


def _link_tooling_tree( real_home: Path, isolated_home: Path ) -> None:
    """Expose user-local tool installs (gems, pip --user) under the isolated home.

    Soft workstation policies often put Asciidoctor / user pip under
    ``~/.local``. A bare empty HOME breaks those tools even when PATH still
    points at absolute ``/home/.../.local/...`` binaries, because gem load
    paths resolve via HOME.
    """
    for name in ( '.local', ):
        src = real_home / name
        dst = isolated_home / name
        if not src.exists() or dst.exists():
            continue
        try:
            dst.symlink_to( src, target_is_directory=src.is_dir() )
        except OSError:
            pass


def _seed_conan_default_profile( isolated_home: Path, real_home: Path ) -> None:
    """Ensure Conan 2 finds a default profile under the isolated HOME.

    Many integration cases previously relied on the developer machine's
    ``~/.conan2/profiles/default``. With HOME isolation that file is missing
    unless we copy or detect one.
    """
    profiles = isolated_home / '.conan2' / 'profiles'
    default = profiles / 'default'
    if default.is_file():
        return

    real_default = real_home / '.conan2' / 'profiles' / 'default'
    if real_default.is_file():
        profiles.mkdir( parents=True, exist_ok=True )
        shutil.copy2( real_default, default )
        return

    conan = shutil.which( 'conan' )
    if not conan:
        return
    profiles.mkdir( parents=True, exist_ok=True )
    env = os.environ.copy()
    env['HOME'] = str( isolated_home )
    env['USERPROFILE'] = str( isolated_home )
    # Prefer an explicit CONAN_HOME under the isolated tree when detecting.
    env.setdefault( 'CONAN_HOME', str( isolated_home / '.conan2' ) )
    subprocess.run(
            [ conan, 'profile', 'detect', '--force' ],
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
    )


def apply_isolated_home( tmp_path: Path, monkeypatch ) -> Path:
    """Set HOME / USERPROFILE to a per-test directory under ``tmp_path``."""
    real_home = _real_home_before_isolation()
    home = isolated_home_dir( tmp_path )
    _link_tooling_tree( real_home, home )
    monkeypatch.setenv( 'HOME', str( home ) )
    monkeypatch.setenv( 'USERPROFILE', str( home ) )
    _seed_conan_default_profile( home, real_home )
    return home
