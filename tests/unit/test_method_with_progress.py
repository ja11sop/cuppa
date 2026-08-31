#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

"""MethodWithProgress must recognise list and NodeList builder returns."""

from types import SimpleNamespace

import pytest

import SCons.Node

from cuppa.core.environment import MethodWithProgress


pytestmark = pytest.mark.unit


class _Node(SCons.Node.Node):
    pass


def test_nodes_for_progress_accepts_plain_list():
    nodes = [ _Node() ]
    assert MethodWithProgress._nodes_for_progress( nodes ) is nodes


def test_nodes_for_progress_accepts_nodelist():
    nodes = SCons.Node.NodeList( [ _Node() ] )
    assert type( nodes ) is not list
    assert MethodWithProgress._nodes_for_progress( nodes ) is nodes


def test_nodes_for_progress_accepts_single_node():
    node = _Node()
    assert MethodWithProgress._nodes_for_progress( node ) == [ node ]


def test_nodes_for_progress_rejects_empty_and_non_nodes():
    assert MethodWithProgress._nodes_for_progress( [] ) is None
    assert MethodWithProgress._nodes_for_progress( SCons.Node.NodeList( [] ) ) is None
    assert MethodWithProgress._nodes_for_progress( [ "not-a-node" ] ) is None
    assert MethodWithProgress._nodes_for_progress( None ) is None
    assert MethodWithProgress._nodes_for_progress( "string" ) is None


def test_method_with_progress_notifies_for_nodelist( monkeypatch ):
    calls = []

    def _fake_add( env, target ):
        calls.append( ( env, target ) )

    monkeypatch.setattr( "cuppa.progress.NotifyProgress.add", _fake_add )

    env = SimpleNamespace()
    returned = SCons.Node.NodeList( [ _Node() ] )

    wrapped = MethodWithProgress( env, "Program", lambda *a, **k: returned )
    assert wrapped() is returned
    assert len( calls ) == 1
    assert calls[0][0] is env
    assert calls[0][1] is returned


def test_method_with_progress_notifies_for_install_list( monkeypatch ):
    calls = []
    monkeypatch.setattr(
        "cuppa.progress.NotifyProgress.add",
        lambda env, target: calls.append( target ),
    )

    env = SimpleNamespace()
    returned = [ _Node() ]
    wrapped = MethodWithProgress( env, "Install", lambda *a, **k: returned )
    wrapped()
    assert calls == [ returned ]
