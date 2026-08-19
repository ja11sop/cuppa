#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

import logging

import pytest

pytestmark = pytest.mark.unit


class AppendEnv(dict):
    def AppendUnique( self, **kwargs ):
        for key, values in kwargs.items():
            current = list( self.get( key, [] ) )
            for value in values:
                if value not in current:
                    current.append( value )
            self[ key ] = current

    def Replace( self, **kwargs ):
        self.update( kwargs )


class FakeToolchain(object):
    def __init__( self, flags=None ):
        self._flags = flags or []

    def name( self ):
        return 'clang24'

    def error_limit_flags( self, env, limit ):
        if limit == 0:
            return [ '-ferror-limit=0' ]
        if limit and limit > 0:
            return [ '-ferror-limit={}'.format( limit ) ]
        return []


@pytest.fixture(autouse=True)
def _reset_error_limit_state():
    from cuppa.methods.cxx_error_limit import reset_error_limit_state_for_tests

    reset_error_limit_state_for_tests()
    yield
    reset_error_limit_state_for_tests()


def test_resolve_effective_error_limit_precedence():
    from cuppa.methods.cxx_error_limit import resolve_effective_error_limit

    assert resolve_effective_error_limit( {} ) is None
    assert resolve_effective_error_limit( { 'cxx_profiles_report': True } ) == 0
    assert resolve_effective_error_limit( {
        'cxx_profiles_report': True,
        'cxx_disable_error_limit': True,
    } ) == 0
    assert resolve_effective_error_limit( {
        'cxx_profiles_report': True,
        'cxx_default_error_limit': True,
    } ) is None
    assert resolve_effective_error_limit( {
        'cxx_profiles_report': True,
        'cxx_error_limit': 5,
    } ) == 5
    assert resolve_effective_error_limit( { 'cxx_disable_error_limit': True } ) == 0
    assert resolve_effective_error_limit( { 'cxx_error_limit': 0 } ) == 0


def test_apply_error_limit_inventory_logs_once( caplog ):
    from cuppa.methods.cxx_error_limit import apply_error_limit_for_env

    caplog.set_level( logging.INFO, logger='cuppa' )
    env = AppendEnv( {
        'toolchain': FakeToolchain(),
        'CXXFLAGS': [],
        'cxx_profiles_report': True,
    } )
    assert apply_error_limit_for_env( env ) is True
    assert env[ 'CXXFLAGS' ] == [ '-ferror-limit=0' ]
    apply_error_limit_for_env( env )
    info_messages = [
        record.getMessage()
        for record in caplog.records
        if record.levelno == logging.INFO
    ]
    assert len( info_messages ) == 1
    assert 'Profiles inventory' in info_messages[ 0 ]
    assert '--cxx-default-error-limit' in info_messages[ 0 ]


def test_apply_error_limit_explicit_value():
    from cuppa.methods.cxx_error_limit import apply_error_limit_for_env

    env = AppendEnv( {
        'toolchain': FakeToolchain(),
        'CXXFLAGS': [],
        'cxx_error_limit': 12,
    } )
    assert apply_error_limit_for_env( env ) is True
    assert env[ 'CXXFLAGS' ] == [ '-ferror-limit=12' ]


def test_apply_error_limit_strips_hardcoded_flags_before_apply():
    from cuppa.methods.cxx_error_limit import apply_error_limit_for_env

    env = AppendEnv( {
        'toolchain': FakeToolchain(),
        'CXXFLAGS': [ '-Wall', '-ferror-limit=5', '-fmax-errors=3' ],
        'CCFLAGS': [ '-ferror-limit', '5' ],
        'cxx_profiles_report': True,
    } )
    assert apply_error_limit_for_env( env ) is True
    assert env[ 'CXXFLAGS' ] == [ '-Wall', '-ferror-limit=0' ]
    assert env[ 'CCFLAGS' ] == []


def test_apply_error_limit_default_strips_hardcoded_flags():
    from cuppa.methods.cxx_error_limit import apply_error_limit_for_env

    env = AppendEnv( {
        'toolchain': FakeToolchain(),
        'CXXFLAGS': [ '-ferror-limit=5' ],
        'CCFLAGS': [ '-fmax-errors=3' ],
        'cxx_default_error_limit': True,
        'cxx_profiles_report': True,
    } )
    assert apply_error_limit_for_env( env ) is True
    assert env[ 'CXXFLAGS' ] == []
    assert env[ 'CCFLAGS' ] == []


def test_apply_error_limit_leaves_flags_when_no_policy():
    from cuppa.methods.cxx_error_limit import apply_error_limit_for_env

    env = AppendEnv( {
        'toolchain': FakeToolchain(),
        'CXXFLAGS': [ '-ferror-limit=5' ],
    } )
    assert apply_error_limit_for_env( env ) is False
    assert env[ 'CXXFLAGS' ] == [ '-ferror-limit=5' ]


def test_apply_error_limit_warns_when_unsupported( caplog ):
    from cuppa.methods.cxx_error_limit import apply_error_limit_for_env

    class UnsupportedToolchain( FakeToolchain ):
        def error_limit_flags( self, env, limit ):
            return []

    caplog.set_level( logging.WARNING, logger='cuppa' )
    env = AppendEnv( {
        'toolchain': UnsupportedToolchain(),
        'CXXFLAGS': [],
        'cxx_disable_error_limit': True,
    } )
    assert apply_error_limit_for_env( env ) is False
    assert 'does not support' in caplog.text


def test_cxx_error_limit_get_options():
    from cuppa.methods.cxx_error_limit import CxxErrorLimitMethod

    class FakeEnv(dict):
        def __init__( self, options ):
            super().__init__()
            self._options = options

        def get_option( self, name ):
            return self._options.get( name )

    env = FakeEnv( {
        'cxx_error_limit': '5',
        'cxx_default_error_limit': False,
        'cxx_disable_error_limit': False,
    } )
    CxxErrorLimitMethod.get_options( env )
    assert env[ 'cxx_error_limit' ] == 5
    assert env[ 'cxx_default_error_limit' ] is False
    assert env[ 'cxx_disable_error_limit' ] is False


def test_init_env_for_variant_applies_inventory_implied_limit():
    from cuppa.methods.cxx_error_limit import CxxErrorLimitMethod

    env = AppendEnv( {
        'toolchain': FakeToolchain(),
        'CXXFLAGS': [ '-ferror-limit=20' ],
        'cxx_profiles_report': True,
    } )
    CxxErrorLimitMethod.init_env_for_variant( { 'env': env } )
    assert env[ 'CXXFLAGS' ] == [ '-ferror-limit=0' ]


def test_add_options_is_idempotent():
    from cuppa.methods.cxx_error_limit import CxxErrorLimitMethod, reset_error_limit_state_for_tests

    registered = []

    def capture_option( *args, **kwargs ):
        registered.append( args[ 0 ] )

    reset_error_limit_state_for_tests()
    CxxErrorLimitMethod.add_options( capture_option )
    CxxErrorLimitMethod.add_options( capture_option )
    assert registered.count( '--cxx-error-limit' ) == 1


def test_cxx_disable_error_limit_shorthand_appends_flags():
    from cuppa.methods.cxx_error_limit import apply_error_limit_for_env

    env = AppendEnv( {
        'toolchain': FakeToolchain(),
        'CXXFLAGS': [],
        'cxx_disable_error_limit': True,
    } )
    assert apply_error_limit_for_env( env ) is True
    assert env[ 'CXXFLAGS' ] == [ '-ferror-limit=0' ]


def test_cxx_error_limit_method_sets_explicit_cap():
    from cuppa.methods.cxx_error_limit import CxxErrorLimitMethod

    env = AppendEnv( {
        'toolchain': FakeToolchain(),
        'CXXFLAGS': [],
        'cxx_disable_error_limit': True,
        'cxx_default_error_limit': True,
    } )
    CxxErrorLimitMethod()( env, 12 )
    assert env.get( 'cxx_error_limit' ) == 12
    assert env.get( 'cxx_default_error_limit' ) is False
    assert env.get( 'cxx_disable_error_limit' ) is False
    assert env[ 'CXXFLAGS' ] == [ '-ferror-limit=12' ]


def test_cxx_default_error_limit_method_strips_flags():
    from cuppa.methods.cxx_error_limit import CxxErrorLimitMethod

    env = AppendEnv( {
        'toolchain': FakeToolchain(),
        'CXXFLAGS': [ '-ferror-limit=5' ],
        'cxx_error_limit': 20,
        'cxx_profiles_report': True,
    } )
    CxxErrorLimitMethod().default_limit( env )
    assert 'cxx_error_limit' not in env
    assert env.get( 'cxx_default_error_limit' ) is True
    assert env.get( 'cxx_disable_error_limit' ) is False
    assert env[ 'CXXFLAGS' ] == []


def test_cxx_disable_error_limit_method_clears_siblings():
    from cuppa.methods.cxx_error_limit import CxxErrorLimitMethod

    env = AppendEnv( {
        'toolchain': FakeToolchain(),
        'CXXFLAGS': [],
        'cxx_error_limit': 5,
    } )
    CxxErrorLimitMethod().disable_limit( env )
    assert 'cxx_error_limit' not in env
    assert env.get( 'cxx_default_error_limit' ) is False
    assert env.get( 'cxx_disable_error_limit' ) is True
    assert env[ 'CXXFLAGS' ] == [ '-ferror-limit=0' ]


def test_cxx_disable_error_limit_method_false_reverts_override():
    from cuppa.methods.cxx_error_limit import CxxErrorLimitMethod

    env = AppendEnv( {
        'toolchain': FakeToolchain(),
        'CXXFLAGS': [ '-ferror-limit=0' ],
        'cxx_disable_error_limit': True,
        'cxx_profiles_report': True,
    } )
    CxxErrorLimitMethod().disable_limit( env, enabled=False )
    assert env.get( 'cxx_disable_error_limit' ) is False
    assert env[ 'CXXFLAGS' ] == [ '-ferror-limit=0' ]
