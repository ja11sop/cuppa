#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

import pytest
import SCons.Errors

from cuppa.package_managers.conan import (
    ConanPackagePublisher,
    conan_reference,
    detect_library_names,
    package_type_for_libs,
    package_type_for_shared,
    write_conan_profile,
    write_prebuilt_conanfile,
)
from tests.helpers.fakes import FakeEnv


pytestmark = pytest.mark.unit


class _FakeNode(object):
    def __init__( self, path ):
        self.path = path

    def __str__( self ):
        return self.path


class PublisherEnv( FakeEnv ):
    def Dir( self, path ):
        return _FakeNode( path )

    def File( self, path ):
        return _FakeNode( path )


def test_conan_reference_variants():
    assert conan_reference( 'mylib', '1.2.3' ) == 'mylib/1.2.3'
    assert conan_reference( 'mylib', '1.2.3', user='org' ) == 'mylib/1.2.3@org'
    assert conan_reference( 'mylib', '1.2.3', user='org', channel='stable' ) == 'mylib/1.2.3@org/stable'
    assert conan_reference( 'mylib', '1.2.3', channel='stable' ) == 'mylib/1.2.3@_/stable'


def test_detect_library_names( tmp_path ):
    lib = tmp_path / 'lib'
    lib.mkdir()
    ( lib / 'libfoo.a' ).write_bytes( b'!' )
    ( lib / 'libbar.so.1' ).write_bytes( b'!' )
    ( lib / 'readme.txt' ).write_text( 'x', encoding='utf-8' )
    names = detect_library_names( str( lib ) )
    assert set( names ) == { 'foo', 'bar' }


def test_package_type_shared_vs_static( tmp_path ):
    lib = tmp_path / 'lib'
    lib.mkdir()
    ( lib / 'libfoo.a' ).write_bytes( b'!' )
    assert package_type_for_libs( str( lib ) ) == 'static-library'
    ( lib / 'libfoo.so' ).write_bytes( b'!' )
    assert package_type_for_libs( str( lib ) ) == 'shared-library'


def test_write_prebuilt_conanfile( tmp_path ):
    path = write_prebuilt_conanfile(
            str( tmp_path / 'conanfile.py' ),
            'mylib',
            '0.1.0',
            [ 'mylib' ],
    )
    text = open( path, encoding='utf-8' ).read()
    assert 'name = "mylib"' in text
    assert 'version = "0.1.0"' in text
    assert "self.cpp_info.libs = ['mylib']" in text
    assert 'def package(self):' in text
    assert 'package_type = "static-library"' in text
    assert 'options = {"shared": [True, False]}' in text
    assert 'default_options = {"shared": False}' in text
    assert 'requires =' not in text


def test_write_prebuilt_conanfile_shared_and_requires( tmp_path ):
    path = write_prebuilt_conanfile(
            str( tmp_path / 'conanfile.py' ),
            'wrap',
            '1.0.0',
            [ 'wrap' ],
            package_type='shared-library',
            shared=True,
            requires=[ 'fmt/11.1.4', 'cuppa_pub_mylib/0.1.0' ],
    )
    text = open( path, encoding='utf-8' ).read()
    assert 'package_type = "shared-library"' in text
    assert 'default_options = {"shared": True}' in text
    assert "requires = ('fmt/11.1.4', 'cuppa_pub_mylib/0.1.0')" in text


def test_write_conan_profile( tmp_path ):
    path = write_conan_profile(
            str( tmp_path / 'profile' ),
            { 'os': 'Linux', 'arch': 'x86_64', 'build_type': 'Debug' },
    )
    text = open( path, encoding='utf-8' ).read()
    assert '[settings]' in text
    assert 'os=Linux' in text
    assert 'build_type=Debug' in text


def test_publisher_requires_name_version( tmp_path ):
    env = PublisherEnv(
            final_dir=str( tmp_path / 'final' ),
            abs_final_dir=str( tmp_path / 'final' ),
    )
    with pytest.raises( SCons.Errors.StopError ):
        ConanPackagePublisher( env, name='mylib' )


def test_publisher_reference_and_paths( tmp_path ):
    env = PublisherEnv(
            final_dir=str( tmp_path / 'final' ),
            abs_final_dir=str( tmp_path / 'final' ),
    )
    pub = ConanPackagePublisher(
            env,
            name='mylib',
            version='1.0.0',
            user='org',
            channel='stable',
            remote='gitlab',
            source_include_dir=str( tmp_path / 'include' ),
            source_lib_dir=str( tmp_path / 'lib' ),
    )
    assert pub.reference() == 'mylib/1.0.0@org/stable'
    assert 'mylib-1.0.0.conan.pkg' in str( pub.package() )
    assert 'mylib-1.0.0.conan.published' in str( pub.package_published() )
    sources = [ str( s ) for s in pub.sources() ]
    assert any( 'include' in s for s in sources )
    # lib dir under abs_final_dir is omitted from sources() to avoid SCons cycles
    assert not any( s.rstrip( '/\\' ).endswith( 'lib' ) and 'final' in s for s in sources )


def test_build_package_missing_conan( tmp_path, monkeypatch ):
    env = PublisherEnv(
            final_dir=str( tmp_path / 'final' ),
            abs_final_dir=str( tmp_path / 'final' ),
    )
    include = tmp_path / 'include'
    include.mkdir()
    ( include / 'h.hpp' ).write_text( '//\n', encoding='utf-8' )
    lib = tmp_path / 'lib'
    lib.mkdir()
    ( lib / 'libmylib.a' ).write_bytes( b'!' )

    pub = ConanPackagePublisher(
            env,
            name='mylib',
            version='0.1.0',
            source_include_dir=str( include ),
            source_lib_dir=str( lib ),
    )
    monkeypatch.setattr(
            'cuppa.package_managers.conan._find_conan_executable',
            lambda: None,
    )
    stamp = tmp_path / 'final' / 'mylib-0.1.0.conan.pkg'
    stamp.parent.mkdir( parents=True, exist_ok=True )
    rc = pub.build_package( [ str( stamp ) ], [], env )
    assert rc == 1
    assert not stamp.exists()


def test_build_package_export_pkg_success( tmp_path, monkeypatch ):
    env = PublisherEnv(
            final_dir=str( tmp_path / 'final' ),
            abs_final_dir=str( tmp_path / 'final' ),
            target_arch='x86_64',
            stdcpp='c++20',
            toolchain=_FakeToolchain(),
            variant=_FakeVariant(),
    )
    include = tmp_path / 'include'
    include.mkdir()
    ( include / 'h.hpp' ).write_text( '//\n', encoding='utf-8' )
    lib = tmp_path / 'lib'
    lib.mkdir()
    ( lib / 'libmylib.a' ).write_bytes( b'!' )

    pub = ConanPackagePublisher(
            env,
            name='mylib',
            version='0.1.0',
            source_include_dir=str( include ),
            source_lib_dir=str( lib ),
            libs=[ 'mylib' ],
    )

    calls = []

    class _Completed(object):
        returncode = 0
        stdout = ''
        stderr = ''

    def _run( cmd, **kwargs ):
        calls.append( cmd )
        return _Completed()

    monkeypatch.setattr(
            'cuppa.package_managers.conan._find_conan_executable',
            lambda: 'conan',
    )
    monkeypatch.setattr( 'cuppa.package_managers.conan.subprocess.run', _run )

    stamp = tmp_path / 'final' / 'mylib-0.1.0.conan.pkg'
    stamp.parent.mkdir( parents=True, exist_ok=True )
    rc = pub.build_package( [ str( stamp ) ], [], env )
    assert rc is None
    assert stamp.is_file()
    assert 'mylib/0.1.0' in stamp.read_text( encoding='utf-8' )
    export_calls = [ c for c in calls if c and c[0] == 'conan' ]
    assert export_calls
    assert 'export-pkg' in export_calls[0]
    assert '-pr:a' in export_calls[0]
    assert '-s' in export_calls[0]
    stage = tmp_path / 'final' / 'conan_pkg_mylib_0.1.0'
    assert ( stage / 'conanfile.py' ).is_file()
    assert ( stage / 'lib' / 'libmylib.a' ).is_file()


def test_package_type_for_shared_flag():
    assert package_type_for_shared( True ) == 'shared-library'
    assert package_type_for_shared( False ) == 'static-library'
    assert package_type_for_shared( None ) is None


def test_build_package_shared_option_and_requires( tmp_path, monkeypatch ):
    env = PublisherEnv(
            final_dir=str( tmp_path / 'final' ),
            abs_final_dir=str( tmp_path / 'final' ),
            target_arch='x86_64',
            stdcpp='c++20',
            toolchain=_FakeToolchain(),
            variant=_FakeVariant(),
    )
    include = tmp_path / 'include'
    include.mkdir()
    ( include / 'h.hpp' ).write_text( '//\n', encoding='utf-8' )
    lib = tmp_path / 'lib'
    lib.mkdir()
    ( lib / 'libwrap.a' ).write_bytes( b'!' )

    pub = ConanPackagePublisher(
            env,
            name='wrap',
            version='1.0.0',
            source_include_dir=str( include ),
            source_lib_dir=str( lib ),
            libs=[ 'wrap' ],
            shared=False,
            requires=[ 'cuppa_pub_mylib/0.1.0' ],
    )

    calls = []

    class _Completed(object):
        returncode = 0
        stdout = ''
        stderr = ''

    def _run( cmd, **kwargs ):
        calls.append( cmd )
        return _Completed()

    monkeypatch.setattr(
            'cuppa.package_managers.conan._find_conan_executable',
            lambda: 'conan',
    )
    monkeypatch.setattr( 'cuppa.package_managers.conan.subprocess.run', _run )

    stamp = tmp_path / 'final' / 'wrap-1.0.0.conan.pkg'
    stamp.parent.mkdir( parents=True, exist_ok=True )
    assert pub.build_package( [ str( stamp ) ], [], env ) is None
    export_calls = [ c for c in calls if c and c[0] == 'conan' ]
    assert '-o' in export_calls[0]
    assert 'shared=False' in export_calls[0]
    recipe = ( tmp_path / 'final' / 'conan_pkg_wrap_1.0.0' / 'conanfile.py' ).read_text(
            encoding='utf-8'
    )
    assert "requires = ('cuppa_pub_mylib/0.1.0',)" in recipe
    assert 'default_options = {"shared": False}' in recipe


def test_build_package_conanfile_override( tmp_path, monkeypatch ):
    env = PublisherEnv(
            final_dir=str( tmp_path / 'final' ),
            abs_final_dir=str( tmp_path / 'final' ),
            target_arch='x86_64',
            stdcpp='c++20',
            toolchain=_FakeToolchain(),
            variant=_FakeVariant(),
    )
    include = tmp_path / 'include'
    include.mkdir()
    ( include / 'h.hpp' ).write_text( '//\n', encoding='utf-8' )
    lib = tmp_path / 'lib'
    lib.mkdir()
    ( lib / 'libwrap.a' ).write_bytes( b'!' )
    recipe_src = tmp_path / 'handwritten_conanfile.py'
    recipe_src.write_text(
            'from conan import ConanFile\n'
            'class Pkg(ConanFile):\n'
            '    name = "wrap"\n'
            '    version = "1.0.0"\n'
            '    requires = "cuppa_pub_mylib/0.1.0"\n'
            '    def package(self):\n'
            '        pass\n'
            '    def package_info(self):\n'
            '        self.cpp_info.libs = ["wrap"]\n',
            encoding='utf-8',
    )

    pub = ConanPackagePublisher(
            env,
            name='wrap',
            version='1.0.0',
            source_include_dir=str( include ),
            source_lib_dir=str( lib ),
            conanfile=str( recipe_src ),
            requires=[ 'ignored/1.0' ],
            shared=True,
    )

    class _Completed(object):
        returncode = 0
        stdout = ''
        stderr = ''

    calls = []

    def _run( cmd, **kwargs ):
        calls.append( cmd )
        return _Completed()

    monkeypatch.setattr(
            'cuppa.package_managers.conan._find_conan_executable',
            lambda: 'conan',
    )
    monkeypatch.setattr( 'cuppa.package_managers.conan.subprocess.run', _run )

    stamp = tmp_path / 'final' / 'wrap-1.0.0.conan.pkg'
    stamp.parent.mkdir( parents=True, exist_ok=True )
    assert pub.build_package( [ str( stamp ) ], [], env ) is None
    staged = ( tmp_path / 'final' / 'conan_pkg_wrap_1.0.0' / 'conanfile.py' ).read_text(
            encoding='utf-8'
    )
    assert 'handwritten' not in staged  # content copied, not path
    assert 'requires = "cuppa_pub_mylib/0.1.0"' in staged
    assert 'CuppaPrebuiltConan' not in staged
    assert 'ignored/1.0' not in staged
    export_calls = [ c for c in calls if c and c[0] == 'conan' ]
    assert 'shared=True' in export_calls[0]


def test_publish_package_offline_fails( tmp_path ):
    env = PublisherEnv(
            final_dir=str( tmp_path / 'final' ),
            abs_final_dir=str( tmp_path / 'final' ),
            offline=True,
    )
    pub = ConanPackagePublisher(
            env,
            name='mylib',
            version='0.1.0',
            remote='gitlab',
            source_include_dir=str( tmp_path / 'include' ),
            source_lib_dir=str( tmp_path / 'lib' ),
    )
    rc = pub.publish_package( [ str( tmp_path / 'published' ) ], [], env )
    assert rc == 1


def test_publish_package_requires_remote( tmp_path ):
    env = PublisherEnv(
            final_dir=str( tmp_path / 'final' ),
            abs_final_dir=str( tmp_path / 'final' ),
            offline=False,
    )
    pub = ConanPackagePublisher(
            env,
            name='mylib',
            version='0.1.0',
            source_include_dir=str( tmp_path / 'include' ),
            source_lib_dir=str( tmp_path / 'lib' ),
    )
    rc = pub.publish_package( [ str( tmp_path / 'published' ) ], [], env )
    assert rc == 1


class _FakeToolchain(object):
    def family( self ):
        return 'gcc'

    def version( self ):
        return '15'

    def short_version( self ):
        return '15'

    def package_name( self ):
        return 'gcc15'

    def abi( self, env ):
        return 'cxx20'


class _FakeVariant(object):
    def name( self ):
        return 'dbg'
