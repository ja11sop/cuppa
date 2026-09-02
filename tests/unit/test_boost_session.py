#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

import pytest

from cuppa.dependencies.boost.session import session_boost

pytestmark = pytest.mark.unit


class _BoostStub(object):
    def __init__( self, name, version, patched ):
        self.name = name
        self._version = version
        self._patched = patched

    def numeric_version( self ):
        return float( self._version )

    def patched_test( self ):
        return self._patched


def test_session_boost_prefers_package_and_skips_source_factory():
    calls = []

    def source_factory( env ):
        calls.append( 'boost' )
        raise AssertionError( 'source boost factory must not run when boost_package is declared' )

    def package_factory( env ):
        calls.append( 'boost_package' )
        return _BoostStub( 'boost_package', '1.92', True )

    env = {
        'dependencies': {
            'boost': source_factory,
            'boost_package': package_factory,
        }
    }

    boost = session_boost( env )

    assert calls == [ 'boost_package' ]
    assert boost.numeric_version() == 1.92
    assert boost.patched_test() is True


def test_session_boost_uses_source_when_package_absent():
    def source_factory( env ):
        return _BoostStub( 'boost', '1.88', False )

    env = { 'dependencies': { 'boost': source_factory } }

    boost = session_boost( env )

    assert boost.name == 'boost'
    assert boost.numeric_version() == 1.88
    assert boost.patched_test() is False


def test_session_boost_returns_none_without_factories():
    assert session_boost( {} ) is None
    assert session_boost( { 'dependencies': {} } ) is None
