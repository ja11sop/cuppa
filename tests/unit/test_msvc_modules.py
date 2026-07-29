#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

import os

import pytest

from cuppa.toolchains.cl import find_msvc_modules_dir, _modules_dir_from_cl_path


@pytest.mark.unit
def test_modules_dir_from_cl_path_layout(tmp_path):
    ver_root = tmp_path / "MSVC" / "14.38.33130"
    modules = ver_root / "modules"
    modules.mkdir(parents=True)
    (modules / "std.ixx").write_text("// stub\n")
    cl = ver_root / "bin" / "Hostx64" / "x64" / "cl.exe"
    cl.parent.mkdir(parents=True)
    cl.write_text("")

    found = _modules_dir_from_cl_path(str(cl))
    assert found == str(modules)


@pytest.mark.unit
def test_find_msvc_modules_dir_from_env_var(tmp_path, monkeypatch):
    modules = tmp_path / "modules"
    modules.mkdir()
    (modules / "std.ixx").write_text("// stub\n")
    monkeypatch.delenv("VCToolsInstallDir", raising=False)
    monkeypatch.setenv("VCToolsInstallDir", str(tmp_path))

    found = find_msvc_modules_dir()
    assert found == str(modules)


@pytest.mark.unit
def test_find_msvc_modules_dir_missing(monkeypatch):
    monkeypatch.delenv("VCToolsInstallDir", raising=False)
    monkeypatch.setattr(
        "cuppa.toolchains.cl._modules_dir_from_cl_path",
        lambda path: None,
    )

    import shutil
    monkeypatch.setattr(shutil, "which", lambda *a, **k: None)

    real_isdir = os.path.isdir

    def fake_isdir(path):
        text = str(path).replace("\\", "/").lower()
        if "visual studio" in text:
            return False
        return real_isdir(path)

    monkeypatch.setattr(os.path, "isdir", fake_isdir)
    assert find_msvc_modules_dir() is None
