"""Unit tests for CI poll scheduling and rate-limit helpers."""

import io

import pytest

from scripts import github_helpers as helpers


pytestmark = pytest.mark.unit


def test_iter_poll_delays_default_schedule():
    delays = helpers.iter_poll_delays()
    assert next( delays ) == 120
    assert next( delays ) == 480
    assert next( delays ) == 120
    assert next( delays ) == 120


def test_iter_poll_delays_fixed_interval():
    delays = helpers.iter_poll_delays( interval=45 )
    assert next( delays ) == 45
    assert next( delays ) == 45


def test_is_rate_limit_response():
    assert helpers.is_rate_limit_response( 429, {} )
    assert helpers.is_rate_limit_response( 403, { 'message': 'API rate limit exceeded' } )
    assert helpers.is_rate_limit_response( 403, { 'message': 'You have exceeded a secondary rate limit' } )
    assert not helpers.is_rate_limit_response( 403, { 'message': 'Forbidden' } )
    assert not helpers.is_rate_limit_response( 404, { 'message': 'API rate limit exceeded' } )


def test_watch_pull_request_uses_schedule_before_each_poll():
    sleeps = []
    polls = { 'count': 0 }

    class FakeClock:
        def __init__( self ):
            self.now = 0.0

        def __call__( self ):
            return self.now

    clock = FakeClock()

    def sleep( seconds ):
        sleeps.append( seconds )
        clock.now += seconds

    status_pending = helpers.PullRequestStatus(
            number=1, url='u', head_sha='abc12345deadbeef', state='open',
            mergeable_state='unstable', checks=[], outcome='pending',
    )
    status_ok = helpers.PullRequestStatus(
            number=1, url='u', head_sha='abc12345deadbeef', state='open',
            mergeable_state='clean', checks=[], outcome='success',
    )

    def fake_status( **_kwargs ):
        polls['count'] += 1
        if polls['count'] < 3:
            return status_pending
        return status_ok

    original = helpers.pull_request_status
    helpers.pull_request_status = fake_status
    try:
        out = io.StringIO()
        code, last = helpers.watch_pull_request(
                number=1,
                timeout=3600,
                out=out,
                sleep=sleep,
                clock=clock,
                schedule=( 2, 8, 2 ),
        )
    finally:
        helpers.pull_request_status = original

    assert code == helpers.EXIT_SUCCESS
    assert last.outcome == 'success'
    assert sleeps == [ 2, 8, 2 ]
    assert polls['count'] == 3
