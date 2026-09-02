import os
from types import SimpleNamespace

import pytest

from cuppa.package_managers.gitlab import (
    GitlabPackageDependency,
    consume_package_file_stems,
    download_first_available_package,
    os_release_id,
    package_archive_extension,
    package_archive_extensions,
    package_file_name,
    package_url,
    remove_prefix,
    remove_suffix,
    resolve_existing_package_archive,
    strip_package_archive_extension,
    tool_variant,
)


pytestmark = pytest.mark.unit


def test_remove_prefix_and_suffix():
    assert remove_prefix("foobar", "foo") == "bar"
    assert remove_prefix("foobar", "baz") == "foobar"
    assert remove_suffix("foobar", "bar") == "foo"
    assert remove_suffix("foobar", "baz") == "foobar"
    assert strip_package_archive_extension("widget_debian_gcc15_rel.tar.gz") == (
        "widget_debian_gcc15_rel"
    )
    assert strip_package_archive_extension("widget_windows_vc143_rel.zip") == (
        "widget_windows_vc143_rel"
    )


def test_tool_variant_and_package_names(monkeypatch):
    toolchain = SimpleNamespace(package_name=lambda: "gcc15")
    variant = SimpleNamespace(name=lambda: "rel")
    env = {
        "toolchain": toolchain,
        "variant": variant,
        "target_arch": "x86_64",
        "abi": "cxx2c",
    }
    assert tool_variant(env) == "gcc15_rel_x86_64_cxx2c"
    assert tool_variant(env, variant="dbg") == "gcc15_dbg_x86_64_cxx2c"

    monkeypatch.setattr(
        "cuppa.package_managers.gitlab.platform.freedesktop_os_release",
        lambda: {"ID": "debian"},
    )
    monkeypatch.setattr(
        "cuppa.package_managers.gitlab.platform.system",
        lambda: "Linux",
    )
    name = package_file_name(env, package="widget")
    assert name == "widget_debian_gcc15_rel_x86_64_cxx2c.tar.gz"
    omit = package_file_name(env, package="widget", omit_os=True)
    assert omit == "widget_gcc15_rel_x86_64_cxx2c.tar.gz"
    url = package_url(
        env,
        registry="https://gitlab.example/api/v4/projects/1",
        package="widget",
        version="1.0.0",
    )
    assert url.endswith("/packages/generic/widget/1.0.0/" + name)


def test_os_release_id_falls_back_without_freedesktop(monkeypatch):
    def _missing():
        raise AttributeError("freedesktop_os_release")

    monkeypatch.setattr(
        "cuppa.package_managers.gitlab.platform.freedesktop_os_release",
        _missing,
    )
    monkeypatch.setattr(
        "cuppa.package_managers.gitlab.platform.system",
        lambda: "Windows",
    )
    assert os_release_id() == "windows"
    assert package_archive_extension() == ".zip"
    assert package_archive_extensions() == (".zip", ".tar.gz")

    monkeypatch.setattr(
        "cuppa.package_managers.gitlab.platform.system",
        lambda: "Darwin",
    )
    assert os_release_id() == "macos"
    assert package_archive_extension() == ".tar.gz"

    toolchain = SimpleNamespace(package_name=lambda: "vc143")
    variant = SimpleNamespace(name=lambda: "rel")
    env = {
        "toolchain": toolchain,
        "variant": variant,
        "target_arch": "x86_64",
        "abi": "cxx17",
    }
    monkeypatch.setattr(
        "cuppa.package_managers.gitlab.platform.system",
        lambda: "Windows",
    )
    assert package_file_name(env, package="boost") == (
        "boost_windows_vc143_rel_x86_64_cxx17.zip"
    )


def test_resolve_existing_package_archive_prefers_platform_then_alternate(
        tmp_path, monkeypatch
):
    monkeypatch.setattr(
        "cuppa.package_managers.gitlab.platform.system",
        lambda: "Windows",
    )
    stem = "boost_windows_vc143_rel_x86_64_cxx17"
    legacy = tmp_path / (stem + ".tar.gz")
    legacy.write_bytes(b"tar")
    assert resolve_existing_package_archive(str(tmp_path), stem) == str(legacy)

    preferred = tmp_path / (stem + ".zip")
    preferred.write_bytes(b"zip")
    assert resolve_existing_package_archive(str(tmp_path), stem) == str(preferred)


def _dependency_for_pkg_config(tmp_path, clean):
    dependency = GitlabPackageDependency.__new__(GitlabPackageDependency)
    dependency._clean = clean
    dependency._library_prefix = ""
    dependency._package_id = "widget/2.28.0/rel"
    dependency._pkg_config_dir = str(tmp_path / "never_extracted" / "pkgconfig")
    dependency._env = SimpleNamespace(
        parsed=[], ParseConfig=lambda command: dependency._env.parsed.append(command)
    )
    return dependency


def test_parse_pkg_config_skipped_when_cleaning_without_package(tmp_path):
    dependency = _dependency_for_pkg_config(tmp_path, clean=True)
    dependency.parse_pkg_config(["widget_kms"])
    assert dependency._env.parsed == []


def test_parse_pkg_config_runs_when_not_cleaning(tmp_path):
    dependency = _dependency_for_pkg_config(tmp_path, clean=False)
    dependency.parse_pkg_config(["widget_kms"])
    assert len(dependency._env.parsed) == 1
    assert "widget_kms" in dependency._env.parsed[0]


def _lookup_env( package_name="gcc153", os_override=None, fallback=None, os_identity=None ):
    class Env( dict ):
        def get_option( self, key, default=None ):
            return self.get( key, default )

    toolchain = SimpleNamespace(
        package_name=lambda: package_name,
        family=lambda: "gcc",
        _reported_version={ "major": 15, "minor": 3 },
        _name=package_name,
    )
    env = Env(
        toolchain=toolchain,
        variant=SimpleNamespace( name=lambda: "rel" ),
        target_arch="x86_64",
        abi="cxx2c",
    )
    if os_override is not None:
        env["package_gitlab_os_override"] = os_override
    if fallback is not None:
        env["package_gitlab_identity_fallback"] = fallback
    if os_identity is not None:
        env["package_gitlab_os_identity"] = os_identity
    return env


def test_consume_stems_host_os_and_identity_pair( monkeypatch ):
    monkeypatch.setattr(
        "cuppa.package_managers.gitlab.platform.freedesktop_os_release",
        lambda: { "ID": "ubuntu" },
    )
    monkeypatch.setattr(
        "cuppa.package_managers.gitlab.platform.system",
        lambda: "Linux",
    )
    env = _lookup_env()
    stems = consume_package_file_stems( env, package="widget", variant="rel" )
    assert stems == [
        "widget_ubuntu_gcc153_rel_x86_64_cxx2c",
        "widget_ubuntu_gcc15_rel_x86_64_cxx2c",
        "widget_gcc153_rel_x86_64_cxx2c",
        "widget_gcc15_rel_x86_64_cxx2c",
    ]


def test_consume_stems_os_override_and_explicit_toolchain( monkeypatch ):
    monkeypatch.setattr(
        "cuppa.package_managers.gitlab.platform.freedesktop_os_release",
        lambda: { "ID": "ubuntu" },
    )
    monkeypatch.setattr(
        "cuppa.package_managers.gitlab.platform.system",
        lambda: "Linux",
    )
    env = _lookup_env( os_override="debian" )
    stems = consume_package_file_stems( env, package="widget", variant="rel" )
    assert stems[0].startswith( "widget_debian_" )
    stems = consume_package_file_stems(
            env, package="widget", variant="rel", package_os="fedora"
    )
    assert stems[0] == "widget_fedora_gcc153_rel_x86_64_cxx2c"
    stems = consume_package_file_stems(
            env, package="widget", variant="rel", package_toolchain="gcc152"
    )
    assert stems == [
        "widget_debian_gcc152_rel_x86_64_cxx2c",
        "widget_debian_gcc15_rel_x86_64_cxx2c",
    ]


def test_consume_stems_fallback_off( monkeypatch ):
    monkeypatch.setattr(
        "cuppa.package_managers.gitlab.platform.freedesktop_os_release",
        lambda: { "ID": "debian" },
    )
    env = _lookup_env( fallback="off" )
    stems = consume_package_file_stems( env, package="widget", variant="rel" )
    assert stems == [ "widget_debian_gcc153_rel_x86_64_cxx2c" ]


def test_consume_stems_omit_os_identity( monkeypatch ):
    monkeypatch.setattr(
        "cuppa.package_managers.gitlab.platform.freedesktop_os_release",
        lambda: { "ID": "ubuntu" },
    )
    monkeypatch.setattr(
        "cuppa.package_managers.gitlab.platform.system",
        lambda: "Linux",
    )
    env = _lookup_env( os_identity="omit", fallback="off" )
    stems = consume_package_file_stems( env, package="widget", variant="rel" )
    assert stems == [ "widget_gcc153_rel_x86_64_cxx2c" ]
    env = _lookup_env( os_identity="omit" )
    stems = consume_package_file_stems( env, package="widget", variant="rel" )
    assert stems == [
        "widget_gcc153_rel_x86_64_cxx2c",
        "widget_gcc15_rel_x86_64_cxx2c",
        "widget_ubuntu_gcc153_rel_x86_64_cxx2c",
        "widget_ubuntu_gcc15_rel_x86_64_cxx2c",
    ]
    env = _lookup_env( os_override="debian", os_identity="omit" )
    stems = consume_package_file_stems( env, package="widget", variant="rel" )
    assert stems[0] == "widget_debian_gcc153_rel_x86_64_cxx2c"
    assert all( "_debian_" in stem for stem in stems )


def test_download_first_skips_404_then_succeeds( tmp_path ):
    from cuppa.utility.download import DownloadError

    calls = []

    def fake_download( url, dest, custom_token=None, label=None ):
        calls.append( url )
        if "gcc153" in url:
            raise DownloadError( "missing", http_status=404 )
        with open( dest, "wb" ) as handle:
            handle.write( b"ok" )
        return dest

    candidates = [
        ( "s153", "widget_gcc153.tar.gz", "https://example/widget_gcc153.tar.gz", "gcc153" ),
        ( "s15", "widget_gcc15.tar.gz", "https://example/widget_gcc15.tar.gz", "gcc15" ),
    ]
    dest, filename, stem = download_first_available_package(
            candidates, str( tmp_path ), download=fake_download
    )
    assert filename == "widget_gcc15.tar.gz"
    assert stem == "s15"
    assert os.path.isfile( dest )
    assert len( calls ) == 2


def test_download_first_does_not_fallback_on_forbidden( tmp_path ):
    from cuppa.utility.download import DownloadError

    calls = []

    def fake_download( url, dest, custom_token=None, label=None ):
        calls.append( url )
        raise DownloadError( "denied", http_status=403 )

    candidates = [
        ( "s153", "widget_gcc153.tar.gz", "https://example/widget_gcc153.tar.gz", "gcc153" ),
        ( "s15", "widget_gcc15.tar.gz", "https://example/widget_gcc15.tar.gz", "gcc15" ),
    ]
    with pytest.raises( DownloadError ) as caught:
        download_first_available_package(
                candidates, str( tmp_path ), download=fake_download
        )
    assert "widget_gcc153.tar.gz" in str( caught.value.parameter )
    assert "widget_gcc15.tar.gz" not in str( caught.value.parameter )
    assert calls == [ "https://example/widget_gcc153.tar.gz" ]


def test_download_first_lists_stems_when_all_404( tmp_path ):
    from cuppa.utility.download import DownloadError

    def fake_download( url, dest, custom_token=None, label=None ):
        raise DownloadError( "missing", http_status=404 )

    candidates = [
        ( "s153", "widget_gcc153.tar.gz", "https://example/widget_gcc153.tar.gz", "gcc153" ),
        ( "s15", "widget_gcc15.tar.gz", "https://example/widget_gcc15.tar.gz", "gcc15" ),
    ]
    with pytest.raises( DownloadError ) as caught:
        download_first_available_package(
                candidates, str( tmp_path ), download=fake_download
        )
    message = str( caught.value.parameter )
    assert "widget_gcc153.tar.gz" in message
    assert "widget_gcc15.tar.gz" in message
