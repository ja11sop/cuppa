import json
import re
from pathlib import Path

import pytest

from tests.helpers.cuppa_runner import assert_success, run_cuppa
from tests.helpers.project import copy_dummy_project, write_sconstruct
from tests.integration.test_list_dependencies import own_home, strip_ansi


pytestmark = pytest.mark.integration


def _json_payload( result ):
    match = re.search( r"\{.*\}", result.stdout, re.DOTALL )
    assert match, result.stdout
    return json.loads( match.group( 0 ) )


def _minimal_sconstruct():
    return """\
import cuppa

cuppa.run(
    default_variants=['dbg'],
)
"""


def _plant_publisher( forest: Path, name: str ):
    tree = forest / name
    tree.mkdir( parents=True )
    ( tree / '.git' ).mkdir()
    ( tree / 'sconstruct' ).write_text( '# publisher\n', encoding='utf-8' )
    ( tree / 'payload' ).write_text( 'bytes\n', encoding='utf-8' )
    return tree


def test_list_and_remove_publishers( tmp_path ):
    project = copy_dummy_project( tmp_path )
    write_sconstruct( project, body=_minimal_sconstruct() )
    storage = tmp_path / 'storage'
    forest = storage / 'publishers'
    _plant_publisher( forest, 'capy' )
    _plant_publisher( forest, 'corosio' )
    home = own_home( tmp_path )

    listed = run_cuppa(
            project,
            '--offline',
            '--list-publishers',
            '--storage-root={}'.format( storage ),
            extra_env=home,
    )
    assert_success( listed )
    text = strip_ansi( listed.stdout )
    assert 'Publishers in' in text
    assert 'capy' in text
    assert 'corosio' in text
    assert '2 publisher trees' in text

    as_json = run_cuppa(
            project,
            '--offline',
            '--list-publishers',
            '--list-format=json',
            '--storage-root={}'.format( storage ),
            extra_env=home,
    )
    assert_success( as_json )
    payload = _json_payload( as_json )
    assert payload['tree_count'] == 2
    names = sorted( entry['name'] for entry in payload['entries'] )
    assert names == [ 'capy', 'corosio' ]

    dry = run_cuppa(
            project,
            '--offline',
            '-n',
            '--remove-publishers=capy',
            '--storage-root={}'.format( storage ),
            extra_env=home,
    )
    assert_success( dry )
    assert ( forest / 'capy' ).is_dir()

    removed = run_cuppa(
            project,
            '--offline',
            '--remove-publishers=capy',
            '--storage-root={}'.format( storage ),
            extra_env=home,
    )
    assert_success( removed )
    assert not ( forest / 'capy' ).exists()
    assert ( forest / 'corosio' ).is_dir()

    listed_after = run_cuppa(
            project,
            '--offline',
            '--list-publishers',
            '--storage-root={}'.format( storage ),
            extra_env=home,
    )
    assert_success( listed_after )
    after = strip_ansi( listed_after.stdout )
    assert 'capy' not in after
    assert 'corosio' in after
    assert '1 publisher tree' in after
