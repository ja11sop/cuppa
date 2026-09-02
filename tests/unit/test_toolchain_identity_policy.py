#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

from types import SimpleNamespace

import pytest

from cuppa.toolchains import identity
from cuppa.toolchains.clang import Clang
from cuppa.toolchains.cl import Cl, MsvcToolsetVersion
from cuppa.toolchains.gcc import Gcc


pytestmark = pytest.mark.unit


def _gcc( major=15, minor=3, encoded=None ):
    toolchain = Gcc.__new__( Gcc )
    name = encoded or 'gcc{}{}'.format( major, minor )
    toolchain._name = name
    toolchain._reported_version = {
        'name': name,
        'major': major,
        'minor': minor,
    }
    return toolchain


def _clang( major=21, minor=1, stdlib=None, encoded=None ):
    toolchain = Clang.__new__( Clang )
    name = encoded or 'clang{}{}'.format( major, minor )
    toolchain._name = name
    toolchain._stdlib = stdlib
    toolchain._reported_version = {
        'name': name,
        'major': major,
        'minor': minor,
    }
    return toolchain


def test_gnu_full_and_major_tokens():
    assert identity.gnu_layout_name( 'gcc', 15, 3, 'full' ) == 'gcc153'
    assert identity.gnu_layout_name( 'gcc', 15, 3, 'major' ) == 'gcc15'
    assert identity.gnu_layout_name( 'clang', 21, 1, 'major', tag='libc++' ) == 'clang21-libc++'
    assert identity.gnu_layout_name( 'clang', 21, 1, 'full', tag='libc++' ) == 'clang211-libc++'


def test_gnu_keeps_registered_archive_qualifiers():
    encoded = 'gcc17_gcc_snapshot_abc'
    assert identity.gnu_layout_name(
        'gcc', 17, 1, 'major', encoded_name=encoded,
    ) == encoded
    assert identity.gnu_layout_name(
        'clang', 24, 0, 'full', encoded_name='clang24_profiles_xyz', tag='libc++',
    ) == 'clang24_profiles_xyz-libc++'


def test_msvc_major_drops_toolset_minor():
    toolset = MsvcToolsetVersion( '14.5', 14, 5, False, 'vc145' )
    assert identity.msvc_layout_name( toolset, 'full' ) == 'vc145'
    assert identity.msvc_layout_name( toolset, 'major' ) == 'vc14'
    experimental = MsvcToolsetVersion( '14.2Exp', 14, 2, True, 'vc142e' )
    assert identity.msvc_layout_name( experimental, 'major' ) == 'vc14e'


def test_gcc_name_honours_policy( monkeypatch ):
    monkeypatch.setattr( 'cuppa.toolchains.identity.current_identity', lambda: 'full' )
    assert _gcc().name() == 'gcc153'
    monkeypatch.setattr( 'cuppa.toolchains.identity.current_identity', lambda: 'major' )
    assert _gcc().name() == 'gcc15'
    assert _gcc().package_name() == 'gcc15'


def test_clang_name_tags_non_default_stdlib( monkeypatch ):
    monkeypatch.setattr( 'cuppa.build_platform.name', lambda: 'Linux' )
    monkeypatch.setattr( 'cuppa.toolchains.identity.current_identity', lambda: 'major' )
    plain = _clang( stdlib='libstdc++' )
    tagged = _clang( stdlib='libc++' )
    assert plain.name() == 'clang21'
    assert tagged.name() == 'clang21-libc++'


def test_cl_name_honours_policy( monkeypatch ):
    toolchain = Cl.__new__( Cl )
    toolchain._toolset = MsvcToolsetVersion( '14.5', 14, 5, False, 'vc145' )
    toolchain._name = 'vc145'
    monkeypatch.setattr( 'cuppa.toolchains.identity.current_identity', lambda: 'full' )
    assert toolchain.name() == 'vc145'
    monkeypatch.setattr( 'cuppa.toolchains.identity.current_identity', lambda: 'major' )
    assert toolchain.name() == 'vc14'


def test_migrate_creates_major_when_file_missing( tmp_path ):
    path = str( tmp_path / '.cuppaconfig' )
    assert identity.migrate_global_toolchain_identity( path ) == 'major'
    text = ( tmp_path / '.cuppaconfig' ).read_text( encoding='utf-8' )
    assert 'toolchain_identity = major' in text


def test_migrate_grandfathers_full_when_key_missing( tmp_path ):
    conf = tmp_path / '.cuppaconfig'
    conf.write_text( 'offline = True\n', encoding='utf-8' )
    assert identity.migrate_global_toolchain_identity( str( conf ) ) == 'full'
    text = conf.read_text( encoding='utf-8' )
    assert 'toolchain_identity = full' in text
    assert 'offline = True' in text


def test_paired_package_tokens_full_and_major( monkeypatch ):
    monkeypatch.setattr( identity, 'current_identity', lambda: 'full' )
    gcc = _gcc( 15, 3 )
    assert identity.paired_package_tokens( gcc.package_name(), gcc ) == [ 'gcc153', 'gcc15' ]
    monkeypatch.setattr( identity, 'current_identity', lambda: 'major' )
    gcc_major = _gcc( 15, 3 )
    assert identity.paired_package_tokens( gcc_major.package_name(), gcc_major ) == [
        'gcc15', 'gcc153',
    ]


def test_paired_package_tokens_explicit_point_coarsens():
    gcc = _gcc( 15, 3 )
    assert identity.paired_package_tokens( 'gcc152', gcc ) == [ 'gcc152', 'gcc15' ]


def test_paired_package_tokens_archive_qualifier_unchanged():
    gcc = _gcc( 17, 0, encoded='gcc17_gcc_snapshot_abc' )
    assert identity.paired_package_tokens( gcc.package_name(), gcc ) == [
        'gcc17_gcc_snapshot_abc',
    ]


def test_paired_package_tokens_clang_tag( monkeypatch ):
    monkeypatch.setattr( identity, 'current_identity', lambda: 'full' )
    tagged = _clang( 21, 1, stdlib='libc++' )
    tagged.default_stdlib = lambda: 'libstdc++'
    tokens = identity.paired_package_tokens( tagged.package_name(), tagged )
    assert tokens == [ 'clang211-libc++', 'clang21-libc++' ]


def test_coarsen_msvc_token():
    assert identity.coarsen_package_token( 'vc145' ) == 'vc14'
    assert identity.coarsen_package_token( 'vc14' ) is None


def test_package_os_identity_defaults_to_include():
    assert identity.package_os_identity( {} ) == 'include'
    env = SimpleNamespace(
        get_option=lambda key, default=None:
            ['omit'] if key == 'package_gitlab_os_identity' else None
    )
    assert identity.package_os_identity( env ) == 'omit'


def test_package_identity_fallback_default_on():
    assert identity.package_identity_fallback_enabled( {} ) is True
    env = SimpleNamespace(
        get_option=lambda key, default=None:
            ['off'] if key == 'package_gitlab_identity_fallback' else None
    )
    assert identity.package_identity_fallback_enabled( env ) is False


def test_package_consume_identity_registers_gitlab_namespace():
    registered = []

    def add_option(flag, **attributes):
        registered.append((flag, attributes["dest"]))

    identity.PackageConsumeIdentity.add_options(add_option)

    assert registered == [
        ("--package-gitlab-os-override", "package_gitlab_os_override"),
        (
            "--package-gitlab-identity-fallback",
            "package_gitlab_identity_fallback",
        ),
        (
            "--package-gitlab-os-identity",
            "package_gitlab_os_identity",
        ),
    ]


def test_migrate_leaves_existing_key( tmp_path ):
    conf = tmp_path / '.cuppaconfig'
    conf.write_text( 'toolchain_identity = major\n', encoding='utf-8' )
    assert identity.migrate_global_toolchain_identity( str( conf ) ) == 'major'
    assert conf.read_text( encoding='utf-8' ).count( 'toolchain_identity' ) == 1
