#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

import pytest

pytestmark = pytest.mark.unit


def test_parse_enforce_list_and_implies_profiles():
    from cuppa.methods.cxx_profiles import CxxProfilesMethod

    class FakeEnv(dict):
        def __init__( self, options ):
            super().__init__()
            self._options = options

        def get_option( self, name ):
            return self._options.get( name )

    env = FakeEnv( {
        'cxx_profiles': False,
        'cxx_profiles_enforce': 'std::init, std::type',
    } )
    CxxProfilesMethod.get_options( env )
    assert env['cxx_profiles'] is True
    assert env['cxx_profiles_enforce'] == [ 'std::init', 'std::type' ]


def test_cxx_profiles_env_keys_do_not_use_buildprofile_profiles():
    from cuppa.methods.cxx_profiles import CxxProfilesMethod

    class FakeEnv(dict):
        def __init__( self ):
            super().__init__()
            self['profiles'] = { 'quad_float': object() }

        def get_option( self, name ):
            return None

    env = FakeEnv()
    CxxProfilesMethod.get_options( env )
    assert env['cxx_profiles'] is False
    assert env['cxx_profiles_enforce'] == []
    assert 'quad_float' in env['profiles']


def test_format_enforce_attribute():
    from cuppa.cpp.cxx_profiles import format_enforce_attribute

    assert format_enforce_attribute( ['std::init'] ) == '[[profiles::enforce(std::init)]];'
    assert (
        format_enforce_attribute( ['std::init', 'std::type'] )
        == '[[profiles::enforce(std::init, std::type)]];'
    )
    assert format_enforce_attribute( [] ) == ''


def test_parse_and_merge_enforce_designators():
    from cuppa.cpp.cxx_profiles import (
        merge_enforce_designators,
        parse_enforce_designators,
    )

    assert parse_enforce_designators( '[[profiles::enforce()]];\n' ) == []
    assert parse_enforce_designators(
        'module;\n[[profiles::enforce(foo)]];\n'
    ) == ['foo']
    assert merge_enforce_designators( ['foo'], ['std::init'] ) == [
        'foo', 'std::init',
    ]
    assert merge_enforce_designators( ['std::init'], ['std::init'] ) == ['std::init']


def test_write_merged_enforce_view(tmp_path):
    from cuppa.cpp.cxx_profiles import _write_merged_enforce_view

    source = tmp_path / 'tu.cpp'
    source.write_text(
        '[[profiles::enforce(foo)]];\n'
        'int main() { return 0; }\n'
    )
    merged = tmp_path / 'merged.cpp'
    _write_merged_enforce_view( str( source ), str( merged ), ['foo', 'std::init'] )
    text = merged.read_text()
    assert text.startswith( '#line 1 "' )
    assert '[[profiles::enforce(foo, std::init)]];' in text
    assert 'int main()' in text


def test_source_has_profiles_enforce(tmp_path):
    from cuppa.cpp.cxx_profiles import source_has_profiles_enforce

    path = tmp_path / 'main.cpp'
    path.write_text( '[[profiles::enforce(std::init)]];\nint main() { return 0; }\n' )
    assert source_has_profiles_enforce( str( path ) ) is True
    other = tmp_path / 'plain.cpp'
    other.write_text( 'int main() { return 0; }\n' )
    assert source_has_profiles_enforce( str( other ) ) is False


def test_ensure_enforce_header_and_include_flags(tmp_path):
    from cuppa.cpp.cxx_profiles import (
        append_profiles_enforce_include,
        ensure_enforce_header,
        source_has_profiles_enforce,
    )

    env = {
        'abs_build_dir': str( tmp_path / 'build' ),
        'build_dir': str( tmp_path / 'build' ),
    }
    header = ensure_enforce_header( env, ['std::init'] )
    assert header
    assert ( tmp_path / 'build' / 'profiles' ).is_dir()
    text = open( header ).read()
    assert '[[profiles::enforce(std::init)]];' in text

    env['_cuppa_profiles_enforce_header'] = header
    flags = append_profiles_enforce_include( env, ['-Wall'] )
    assert flags == [ '-Wall', '-include', header ]

    already = tmp_path / 'with_enforce.cpp'
    already.write_text( '[[profiles::enforce(std::init)]];\nint x;\n' )
    assert source_has_profiles_enforce( str( already ) )
    skipped = append_profiles_enforce_include(
        env, ['-Wall'], source_path=str( already )
    )
    assert skipped == [ '-Wall' ]


def test_activate_profiles_stoperror_unsupported():
    import SCons.Errors
    from cuppa.methods.cxx_profiles import activate_profiles_for_env

    class FakeToolchain:
        def name( self ):
            return 'fake-tc'

        def profiles_supported( self, env ):
            return False

    env = { 'toolchain': FakeToolchain(), 'cxx_profiles': True }
    with pytest.raises( SCons.Errors.StopError ) as exc:
        activate_profiles_for_env( env )
    assert '--cxx-profiles' in str( exc.value )
    assert env['cxx_profiles'] is False


def test_activate_profiles_enable_and_inject(tmp_path):
    from cuppa.methods.cxx_profiles import activate_profiles_for_env

    class FakeToolchain:
        def name( self ):
            return 'clang24_profiles_test'

        def profiles_supported( self, env ):
            return True

        def profiles_enable_flags( self, env ):
            return [ '-fprofiles' ]

        def profiles_enforce_flags( self, env, names ):
            return []

    class AppendEnv(dict):
        def AppendUnique( self, **kwargs ):
            for key, values in kwargs.items():
                current = list( self.get( key, [] ) )
                for value in values:
                    if value not in current:
                        current.append( value )
                self[key] = current

        def Clean( self, *args, **kwargs ):
            return None

        def Dir( self, path ):
            return path

    env = AppendEnv( {
        'toolchain': FakeToolchain(),
        'cxx_profiles': True,
        'cxx_profiles_enforce': ['std::init'],
        'abs_build_dir': str( tmp_path / 'build' ),
        'build_dir': str( tmp_path / 'build' ),
        'CXXFLAGS': [],
    } )
    activate_profiles_for_env( env )
    assert env['cxx_profiles'] is True
    assert '-fprofiles' in env['CXXFLAGS']
    assert env['_cuppa_profiles_enforce_header']
    assert 'enforce_std_init.hpp' in env['_cuppa_profiles_enforce_header']


def test_activate_profiles_uses_native_enforce_flags(tmp_path):
    from cuppa.methods.cxx_profiles import activate_profiles_for_env

    class FakeToolchain:
        def name( self ):
            return 'clang24_profiles_test'

        def profiles_supported( self, env ):
            return True

        def profiles_enable_flags( self, env ):
            return [ '-fprofiles' ]

        def profiles_enforce_flags( self, env, names ):
            return [ '-fprofiles-enforce={}'.format( name ) for name in names ]

    class AppendEnv(dict):
        def AppendUnique( self, **kwargs ):
            for key, values in kwargs.items():
                current = list( self.get( key, [] ) )
                for value in values:
                    if value not in current:
                        current.append( value )
                self[key] = current

    env = AppendEnv( {
        'toolchain': FakeToolchain(),
        'cxx_profiles': True,
        'cxx_profiles_enforce': ['std::init'],
        'CXXFLAGS': [],
    } )
    activate_profiles_for_env( env )
    assert '-fprofiles-enforce=std::init' in env['CXXFLAGS']
    assert env.get( '_cuppa_profiles_enforce_header' ) is None


def test_gcc_and_cl_profiles_unsupported():
    from cuppa.toolchains.gcc import Gcc
    from cuppa.toolchains.cl import Cl

    gcc = Gcc.__new__( Gcc )
    assert gcc.profiles_supported( None ) is False
    assert gcc.profiles_enable_flags( None ) == []
    assert gcc.profiles_enforce_flags( None, ['std::init'] ) == []
    assert gcc.disable_error_limit_flags( None ) == [ '-fmax-errors=0' ]

    cl = Cl.__new__( Cl )
    assert cl.profiles_supported( None ) is False
    assert cl.profiles_enable_flags( None ) == []
    assert cl.disable_error_limit_flags( None ) == []


def test_clang_profiles_probe_cached(monkeypatch):
    from cuppa.toolchains.clang import Clang

    clang = Clang.__new__( Clang )
    clang._reported_version = { 'major': 24, 'apple': False }
    clang._name = 'clang24_profiles_test'
    calls = []

    def fake_binary( self ):
        return 'clang++'

    def fake_run( *args, **kwargs ):
        calls.append( args )
        class Result:
            returncode = 0
        return Result()

    monkeypatch.setattr( Clang, 'binary', fake_binary )
    monkeypatch.setattr( 'cuppa.build_platform.name', lambda: 'Linux' )
    monkeypatch.setattr( 'subprocess.run', fake_run )

    assert clang.profiles_enable_flags( None ) == [ '-fprofiles' ]
    assert clang.profiles_supported( None ) is True
    assert clang.profiles_enable_flags( None ) == [ '-fprofiles' ]
    assert clang.disable_error_limit_flags( None ) == [ '-ferror-limit=0' ]
    assert len( calls ) == 1
