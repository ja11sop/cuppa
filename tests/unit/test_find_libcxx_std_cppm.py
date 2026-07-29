#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

import os

import pytest

from tests.helpers.toolchains import find_libcxx_std_cppm


@pytest.mark.unit
def test_find_libcxx_std_cppm_homebrew_layout(tmp_path, monkeypatch):
    modules = tmp_path / "share" / "libc++" / "v1"
    modules.mkdir(parents=True)
    std_cppm = modules / "std.cppm"
    std_cppm.write_text("export module std;\n")

    resource = tmp_path / "lib" / "clang" / "20"
    resource.mkdir(parents=True)

    def fake_run(cmd, **kwargs):
        class Result(object):
            stdout = str(resource) + "\n"
            stderr = ""
            returncode = 0
        return Result()

    monkeypatch.setattr("tests.helpers.toolchains.subprocess.run", fake_run)
    # Avoid real filesystem Homebrew /usr paths interfering.
    real_isfile = os.path.isfile

    def fake_isfile(path):
        text = str(path)
        if text == str(std_cppm):
            return True
        if "opt/llvm" in text or "/usr/lib/llvm-" in text or text.endswith("/usr/share/libc++/v1/std.cppm"):
            return False
        return real_isfile(path)

    monkeypatch.setattr(os.path, "isfile", fake_isfile)
    found = find_libcxx_std_cppm("clang++", major=20)
    assert found == str(std_cppm)
