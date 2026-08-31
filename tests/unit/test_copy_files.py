#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

"""CopyFiles / CopyFilesAs destination and filter behaviour (parity with Install*)."""

from types import SimpleNamespace

import pytest

from cuppa.methods.copyfiles import CopyFilesMethod
from cuppa.methods.copyfilesas import CopyFilesAsMethod


pytestmark = pytest.mark.unit


class _FakeNode:
    def __init__( self, path ):
        self.path = path
        self.abspath = path

    def __str__( self ):
        return self.path


class _RecordingEnv(dict):
    def __init__( self, abs_final_dir ):
        super().__init__( abs_final_dir=abs_final_dir )
        self.install_calls = []
        self.install_as_calls = []

    def Install( self, destination, sources ):
        self.install_calls.append( ( destination, sources ) )
        return list( sources ) if sources else []

    def InstallAs( self, destinations, sources ):
        self.install_as_calls.append( ( destinations, sources ) )
        return list( sources ) if sources else []


def test_copy_files_joins_relative_dest_to_abs_final_dir():
    env = _RecordingEnv( "/build/var/final" )
    src = [ _FakeNode( "/project/data/a.txt" ) ]
    # filter_nodes requires SCons.Node.Node — use match=None so it returns as-is
    # only for real Nodes. Patch filter to pass through.
    from cuppa.methods import copyfiles as mod

    original = mod.filter_nodes
    mod.filter_nodes = lambda source, match, exclude: source
    try:
        CopyFilesMethod()( env, "copied", src )
    finally:
        mod.filter_nodes = original

    assert env.install_calls == [ ( "/build/var/final/copied", src ) ]


def test_copy_files_leaves_hash_and_absolute_destinations():
    env = _RecordingEnv( "/build/var/final" )
    from cuppa.methods import copyfiles as mod
    original = mod.filter_nodes
    mod.filter_nodes = lambda source, match, exclude: source
    try:
        CopyFilesMethod()( env, "#_artifacts/out", [ "x" ] )
        CopyFilesMethod()( env, "/abs/out", [ "y" ] )
    finally:
        mod.filter_nodes = original

    assert env.install_calls[0][0] == "#_artifacts/out"
    assert env.install_calls[1][0] == "/abs/out"


def test_copy_files_skips_install_when_filter_empty():
    env = _RecordingEnv( "/build/var/final" )
    from cuppa.methods import copyfiles as mod
    original = mod.filter_nodes
    mod.filter_nodes = lambda source, match, exclude: []
    try:
        result = CopyFilesMethod()( env, "copied", [ "x" ] )
    finally:
        mod.filter_nodes = original

    assert result == []
    assert env.install_calls == []


def test_copy_files_as_joins_relative_dest_to_abs_final_dir():
    env = _RecordingEnv( "/build/var/final" )
    from cuppa.methods import copyfilesas as mod
    original = mod.filter_nodes
    mod.filter_nodes = lambda source, match, exclude: source
    try:
        CopyFilesAsMethod()( env, "renamed.txt", [ "x" ] )
    finally:
        mod.filter_nodes = original

    assert env.install_as_calls == [ ( [ "/build/var/final/renamed.txt" ], [ "x" ] ) ]


def test_copy_files_does_not_call_notify_progress_directly( monkeypatch ):
    """Progress must come from the wrapped Install, not a second NotifyProgress.add."""
    calls = []
    monkeypatch.setattr(
        "cuppa.progress.NotifyProgress.add",
        lambda env, target: calls.append( target ),
    )
    env = _RecordingEnv( "/build/var/final" )
    from cuppa.methods import copyfiles as mod
    original = mod.filter_nodes
    mod.filter_nodes = lambda source, match, exclude: source
    try:
        CopyFilesMethod()( env, "copied", [ "x" ] )
    finally:
        mod.filter_nodes = original

    assert env.install_calls  # Install was invoked
    assert calls == []  # CopyFiles itself must not NotifyProgress.add
