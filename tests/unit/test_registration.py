#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

import sys

import pytest

from cuppa.modules import registration


pytestmark = pytest.mark.unit


def test_get_module_list_finds_modules_skips_underscore(tmp_path):
    pkg = tmp_path / "synth_pkg"
    pkg.mkdir()
    (pkg / "a.py").write_text("class A: pass\n", encoding="utf-8")
    (pkg / "_skip.py").write_text("class Skip: pass\n", encoding="utf-8")
    (pkg / "~backup.py").write_text("class Backup: pass\n", encoding="utf-8")
    nested = pkg / "nested"
    nested.mkdir()
    (nested / "b.py").write_text("class B: pass\n", encoding="utf-8")

    modules = registration.get_module_list(str(pkg / "a.py"))
    assert "a" in modules
    assert "_skip" not in modules
    assert "~backup" not in modules
    # nested package dirs are listed by listdir but only *.py files match
    assert "nested" not in modules
    assert "b" not in modules

    qualified = registration.get_module_list(str(pkg / "a.py"), base="synth_pkg")
    assert "synth_pkg.a" in qualified


def test_try_load_module_invokes_add_options(tmp_path):
    pkg = tmp_path / "opt_pkg"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("", encoding="utf-8")
    (pkg / "with_options.py").write_text(
        "class Plugin:\n"
        "    @classmethod\n"
        "    def add_options(cls, add_option):\n"
        "        add_option('--plugin-flag')\n",
        encoding="utf-8",
    )

    module, pathname = registration.try_load_module(None, "with_options", str(pkg))
    assert module is not None
    assert pathname is not None

    recorded = []

    def add_option(flag):
        recorded.append(flag)

    registration.__call_classmethod_for_classes_in_module(
        None, "with_options", str(pkg), "add_options", add_option
    )
    assert recorded == ["--plugin-flag"]
    sys.modules.pop("with_options", None)
