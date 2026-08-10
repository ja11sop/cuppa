#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

import pytest

pytestmark = pytest.mark.unit


def test_cxx_disable_error_limit_appends_toolchain_flags():
    from cuppa.methods.cxx_disable_error_limit import activate_disable_error_limit_for_env

    class FakeToolchain:
        def name( self ):
            return 'gcc15'

        def disable_error_limit_flags( self, env ):
            return [ '-fmax-errors=0' ]

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
        'CXXFLAGS': [],
        'cxx_disable_error_limit': True,
    } )
    assert activate_disable_error_limit_for_env( env ) is True
    assert env['CXXFLAGS'] == [ '-fmax-errors=0' ]


def test_cxx_disable_error_limit_get_options():
    from cuppa.methods.cxx_disable_error_limit import CxxDisableErrorLimitMethod

    class FakeEnv(dict):
        def __init__( self, options ):
            super().__init__()
            self._options = options

        def get_option( self, name ):
            return self._options.get( name )

    env = FakeEnv( { 'cxx_disable_error_limit': True } )
    CxxDisableErrorLimitMethod.get_options( env )
    assert env['cxx_disable_error_limit'] is True


def test_modules_legacy_flag_warns_and_enables(caplog):
    from cuppa.methods.modules import ModulesMethod

    class FakeEnv(dict):
        def __init__( self, options ):
            super().__init__()
            self._options = options

        def get_option( self, name ):
            return self._options.get( name )

    env = FakeEnv( { 'cxx_modules': False, 'modules_legacy': True } )
    with caplog.at_level( 'WARNING' ):
        ModulesMethod.get_options( env )
    assert env['modules'] is True
    assert 'deprecated' in caplog.text
    assert '--cxx-modules' in caplog.text


def test_cxx_modules_canonical_flag():
    from cuppa.methods.modules import ModulesMethod

    class FakeEnv(dict):
        def __init__( self, options ):
            super().__init__()
            self._options = options

        def get_option( self, name ):
            return self._options.get( name )

    env = FakeEnv( { 'cxx_modules': True, 'modules_legacy': False } )
    ModulesMethod.get_options( env )
    assert env['modules'] is True
