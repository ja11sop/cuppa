#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

import io

import pytest

from cuppa.configure import Configure, never_save
from tests.helpers.fakes import FakeEnv


pytestmark = pytest.mark.unit


def _configure(tmp_path, options=None, conf_name="configure.conf"):
    env = FakeEnv(options or {})
    env["default_options"] = {}
    conf = Configure(env, conf_path=str(tmp_path / conf_name))
    conf._global_conf_path = str(tmp_path / ".cuppaconfig")
    return conf, env


def test_load_settings_from_file_skips_blank_and_comments(tmp_path):
    conf, _env = _configure(tmp_path)
    content = io.StringIO(
        "\n"
        "# comment\n"
        "dbg = True\n"
        "toolchains = ['gcc']\n"
        "projects = foo\n"
    )
    settings = {}
    conf._load_settings_from_file(str(tmp_path / "c.conf"), content, settings)
    assert settings["dbg"] is True
    assert settings["toolchains"] == ["gcc"]
    assert settings["projects"] == "foo"


def test_load_migrates_missing_global_file_to_major( tmp_path, monkeypatch ):
    monkeypatch.setenv( 'CUPPA_TEST_IDENTITY_MIGRATE', '1' )
    conf, env = _configure( tmp_path )
    conf.load()
    global_conf = tmp_path / '.cuppaconfig'
    assert global_conf.exists()
    assert 'toolchain_identity = major' in global_conf.read_text( encoding='utf-8' )
    assert env['default_options']['toolchain_identity'] == 'major'


def test_load_grandfathers_existing_global_without_key( tmp_path, monkeypatch ):
    monkeypatch.setenv( 'CUPPA_TEST_IDENTITY_MIGRATE', '1' )
    ( tmp_path / '.cuppaconfig' ).write_text( 'dbg = True\n', encoding='utf-8' )
    conf, env = _configure( tmp_path )
    conf.load()
    text = ( tmp_path / '.cuppaconfig' ).read_text( encoding='utf-8' )
    assert 'toolchain_identity = full' in text
    assert env['default_options']['dbg'] is True
    assert env['default_options']['toolchain_identity'] == 'full'

    global_conf = tmp_path / ".cuppaconfig"
    project_conf = tmp_path / "configure.conf"
    global_conf.write_text("dbg = True\ntoolchains = ['gcc']\n", encoding="utf-8")
    project_conf.write_text("dbg = False\nprojects = ['app']\n", encoding="utf-8")

    conf, env = _configure(tmp_path)
    settings = conf._load_conf()
    assert settings["dbg"] is False
    assert settings["toolchains"] == ["gcc"]
    assert settings["projects"] == ["app"]

    conf.load()
    assert env["configured_options"]["dbg"] is False
    assert env["default_options"]["dbg"] is False


def test_is_saveable_filters_never_save_and_conf_keys(tmp_path):
    conf, _env = _configure(tmp_path)
    assert conf._is_saveable("dbg", True) is True
    assert conf._is_saveable("__internal", True) is False
    assert conf._is_saveable("save_conf", True) is False
    assert conf._is_saveable("cuppa-mode", True) is False
    assert conf._is_saveable("climb_up", never_save()) is False
    assert conf._is_saveable("debug_explain", False) is False
    assert conf._is_saveable("debug_explain", True) is True


def test_clear_config_removes_file(tmp_path):
    conf_path = tmp_path / "configure.conf"
    conf_path.write_text("dbg = True\n", encoding="utf-8")
    conf, _env = _configure(tmp_path)
    conf._clear_config(str(conf_path))
    assert not conf_path.exists()
    conf._clear_config(str(conf_path))


def test_remove_settings_updates_conf(tmp_path, monkeypatch):
    conf, _env = _configure(tmp_path)
    conf_path = tmp_path / "configure.conf"
    conf._loaded_options = {"dbg": True, "rel": True, "projects": ["a"]}
    updated = []

    def fake_update(path):
        updated.append(path)
        with open(path, "w", encoding="utf-8") as fh:
            for key, value in conf._loaded_options.items():
                fh.write("{} = {}\n".format(key, value))

    monkeypatch.setattr(conf, "_update_conf", fake_update)
    conf._remove_settings(str(conf_path), ["dbg", "missing"])
    assert "dbg" not in conf._loaded_options
    assert conf._loaded_options["rel"] is True
    assert updated == [str(conf_path)]
    assert "rel = True" in conf_path.read_text(encoding="utf-8")
