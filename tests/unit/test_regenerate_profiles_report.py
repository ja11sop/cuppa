#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

from pathlib import Path

import pytest

from cuppa.cpp.profiles_report.report_html import INDEX_BASENAME, JSON_BASENAME

pytestmark = pytest.mark.unit

_FIXTURE_CAPTURE = (
    Path( __file__ ).resolve().parents[ 1 ]
    / 'fixtures'
    / 'profiles_capture'
    / 'sample_capture.txt'
)


def test_regenerate_profiles_report_writes_html_and_json( tmp_path, monkeypatch ):
    source = tmp_path / 'home' / 'user' / 'include' / 'widget' / 'nonce.hpp'
    source.parent.mkdir( parents=True )
    source.write_text( 'int x;\n', encoding='utf-8' )

    from scripts import regenerate_profiles_report

    argv = [
        str( _FIXTURE_CAPTURE ),
        '--sconstruct-dir',
        str( tmp_path ),
        '--artifacts-root',
        '_artifacts',
    ]
    assert regenerate_profiles_report.main( argv ) == 0

    report_dir = tmp_path / '_artifacts' / 'cxx-profiles'
    assert ( report_dir / INDEX_BASENAME ).is_file()
    assert ( report_dir / JSON_BASENAME ).is_file()
    index_html = ( report_dir / INDEX_BASENAME ).read_text( encoding='utf-8' )
    assert 'Violations By-Rule' in index_html
    assert 'table-layout: fixed' not in index_html
