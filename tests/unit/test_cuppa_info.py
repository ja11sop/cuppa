#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

"""Tests for cuppa --info version reporting."""

import io
import json

import pytest

from cuppa import version as cuppa_version
from cuppa.utility.version import get_version


pytestmark = pytest.mark.unit


def test_argv_wants_info():
    assert cuppa_version.argv_wants_info( ['--info'] )
    assert cuppa_version.argv_wants_info( ['-D', '--info', '--offline'] )
    assert not cuppa_version.argv_wants_info( ['-D', '--dbg'] )


def test_argv_offline_and_list_format():
    assert cuppa_version.argv_offline( ['--info', '--offline'] )
    assert not cuppa_version.argv_offline( ['--info'] )
    assert cuppa_version.argv_list_format( ['--list-format=json'] ) == 'json'
    assert cuppa_version.argv_list_format( ['--list-format', 'json'] ) == 'json'
    assert cuppa_version.argv_list_format( ['--info'] ) == 'text'


def test_report_info_text( monkeypatch ):
    monkeypatch.setattr( cuppa_version, 'probe_pypi_latest', lambda: '9.9.9' )
    out = io.StringIO()
    cuppa_version.report_info( offline=False, list_format='text', out=out )
    assert out.getvalue() == "cuppa {}\n".format( get_version() )


def test_report_info_json_includes_pypi( monkeypatch ):
    monkeypatch.setattr( cuppa_version, 'probe_pypi_latest', lambda: '9.9.9' )
    out = io.StringIO()
    cuppa_version.report_info( offline=False, list_format='json', out=out )
    payload = json.loads( out.getvalue() )
    assert payload['cuppa_version'] == get_version()
    assert payload['offline'] is False
    assert payload['pypi_latest'] == '9.9.9'


def test_report_info_json_offline_skips_pypi( monkeypatch ):
    called = []

    def boom():
        called.append( True )
        return '9.9.9'

    monkeypatch.setattr( cuppa_version, 'probe_pypi_latest', boom )
    out = io.StringIO()
    cuppa_version.report_info( offline=True, list_format='json', out=out )
    payload = json.loads( out.getvalue() )
    assert payload['offline'] is True
    assert 'pypi_latest' not in payload
    assert called == []


def test_report_info_json_omits_pypi_when_probe_fails( monkeypatch ):
    monkeypatch.setattr( cuppa_version, 'probe_pypi_latest', lambda: None )
    out = io.StringIO()
    cuppa_version.report_info( offline=False, list_format='json', out=out )
    payload = json.loads( out.getvalue() )
    assert 'pypi_latest' not in payload


def test_main_info_exits_without_scons( monkeypatch ):
    from cuppa import __main__ as cuppa_main

    calls = []

    def fake_report_info( **kwargs ):
        calls.append( kwargs )

    monkeypatch.setattr( cuppa_main.sys, 'argv', ['cuppa', '--info', '--offline'] )
    monkeypatch.setattr( cuppa_version, 'report_info', fake_report_info )
    monkeypatch.setattr( cuppa_main, 'run_scons', lambda args: calls.append( ('scons', args) ) or 0 )

    with pytest.raises( SystemExit ) as caught:
        cuppa_main.main()
    assert caught.value.code == 0
    assert calls == [ {'offline': True, 'list_format': 'text'} ]
