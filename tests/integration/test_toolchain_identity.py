import json
import re
import shutil

import pytest

from tests.helpers.cuppa_runner import assert_success, find_under_build, run_cuppa
from tests.helpers.project import copy_dummy_project, write_sconstruct, write_sconscript


pytestmark = pytest.mark.integration

_VERSION_RE = re.compile( r'^\d+\.\d+' )


def _identity_env( home ):
    return {
        'HOME': str( home ),
        'USERPROFILE': str( home ),
        'CUPPA_TEST_IDENTITY_MIGRATE': '1',
    }


def _write_build_scripts( project ):
    write_sconstruct( project )
    write_sconscript(
        project,
        "Import('env')\n"
        "env.AppendUnique(CPPPATH=['#/include'])\n"
        "env.CompileStatic('src/hello.cpp')\n",
    )


def _layout_toolchain_tokens( project ):
    tokens = set()
    build_root = project / '_build'
    for path in find_under_build( project, 'working' ):
        if not path.is_dir() or path.name != 'working':
            continue
        try:
            parts = path.relative_to( build_root ).parts
        except ValueError:
            continue
        if len( parts ) >= 5 and parts[-1] == 'working':
            tokens.add( parts[-5] )
    return tokens


def _coarsened_token( token ):
    if '-' in token:
        base, tag = token.split( '-', 1 )
        return '{}-{}'.format( _coarsened_base( base ), tag )
    return _coarsened_base( token )


def _coarsened_base( base ):
    match = re.match( r'^(gcc|clang|vc)(\d+)$', base )
    if not match:
        return base
    family, digits = match.group( 1 ), match.group( 2 )
    if family == 'vc':
        if len( digits ) >= 3:
            return family + digits[:2]
        return base
    if len( digits ) >= 3:
        return family + digits[:-1]
    return base


def test_toolchain_identity_full_and_major_layout( tmp_path ):
    project = copy_dummy_project( tmp_path / 'project' )
    home = tmp_path / 'home'
    home.mkdir()
    _write_build_scripts( project )
    env = _identity_env( home )

    full = run_cuppa( project, '--dbg', '--toolchain-identity=full', extra_env=env )
    assert_success( full )
    full_tokens = _layout_toolchain_tokens( project )
    assert full_tokens

    shutil.rmtree( project / '_build', ignore_errors=True )

    major = run_cuppa( project, '--dbg', '--toolchain-identity=major', extra_env=env )
    assert_success( major )
    major_tokens = _layout_toolchain_tokens( project )
    assert major_tokens
    assert major_tokens == { _coarsened_token( token ) for token in full_tokens }


def test_missing_global_conf_persists_major( tmp_path ):
    project = copy_dummy_project( tmp_path / 'project' )
    home = tmp_path / 'home'
    home.mkdir()
    _write_build_scripts( project )
    result = run_cuppa( project, '--dbg', extra_env=_identity_env( home ) )
    assert_success( result )
    conf = home / '.cuppaconfig'
    assert conf.exists()
    assert 'toolchain_identity = major' in conf.read_text( encoding='utf-8' )


def test_existing_global_conf_grandfathers_full( tmp_path ):
    project = copy_dummy_project( tmp_path / 'project' )
    home = tmp_path / 'home'
    home.mkdir()
    ( home / '.cuppaconfig' ).write_text( 'offline = True\n', encoding='utf-8' )
    _write_build_scripts( project )
    result = run_cuppa( project, '--dbg', extra_env=_identity_env( home ) )
    assert_success( result )
    text = ( home / '.cuppaconfig' ).read_text( encoding='utf-8' )
    assert 'toolchain_identity = full' in text
    assert 'offline = True' in text


def test_list_toolchains_keeps_reported_version_under_major( tmp_path ):
    project = copy_dummy_project( tmp_path / 'project' )
    home = tmp_path / 'home'
    home.mkdir()
    write_sconstruct( project )
    write_sconscript( project, "Import('env')\n" )
    result = run_cuppa(
        project,
        '--list-toolchains',
        '--list-format=json',
        '--toolchain-identity=major',
        extra_env=_identity_env( home ),
    )
    assert_success( result )
    start = result.stdout.find( '{' )
    assert start >= 0
    payload = json.loads( result.stdout[start:] )
    versions = []
    for section in payload.get( 'sections' ) or []:
        for family in section.get( 'families' ) or []:
            for version in family.get( 'versions' ) or []:
                versions.append( str( version.get( 'version' ) or '' ) )
    assert any( _VERSION_RE.match( item ) for item in versions ), versions
