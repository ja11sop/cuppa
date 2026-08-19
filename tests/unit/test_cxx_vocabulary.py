#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

import pytest

pytestmark = pytest.mark.unit


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
