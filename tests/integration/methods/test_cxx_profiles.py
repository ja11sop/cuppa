#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

import logging

import pytest

from tests.helpers.cuppa_runner import assert_failure, assert_success, run_cuppa
from tests.helpers.project import write_sconscript, write_sconstruct
from tests.helpers.toolchains import (
    default_toolchain_flags,
    require_profiles_capable_toolchain,
)

logger = logging.getLogger( __name__ )

pytestmark = pytest.mark.integration


def test_profiles_enforce_std_init_smoke( tmp_path ):
    """Build a TU with --cxx-profiles --cxx-profiles-enforce=std::init when capable."""
    _, toolchain_flag = require_profiles_capable_toolchain()
    write_sconstruct( tmp_path )
    write_sconscript(
        tmp_path,
        "Import('env')\n"
        "env.Build( 'app', [ 'main.cpp' ] )\n",
    )
    ( tmp_path / 'main.cpp' ).write_text(
        'int main()\n'
        '{\n'
        '    int Value = 0;\n'
        '    return Value;\n'
        '}\n'
    )
    result = run_cuppa(
        tmp_path,
        '--dbg',
        '--cxx-profiles',
        '--cxx-profiles-enforce=std::init',
        toolchain_flag,
    )
    assert_success( result )


def test_profiles_enforce_composes_with_source_attribute( tmp_path ):
    """Merge CLI enforce designators into an existing source enforce attribute."""
    _, toolchain_flag = require_profiles_capable_toolchain()
    write_sconstruct( tmp_path )
    write_sconscript(
        tmp_path,
        "Import('env')\n"
        "env.Build( 'app', [ 'main.cpp' ] )\n",
    )
    ( tmp_path / 'main.cpp' ).write_text(
        '[[profiles::enforce()]];\n'
        'int main()\n'
        '{\n'
        '    int Value = 0;\n'
        '    return Value;\n'
        '}\n'
    )
    result = run_cuppa(
        tmp_path,
        '--dbg',
        '--cxx-profiles',
        '--cxx-profiles-enforce=std::init',
        toolchain_flag,
    )
    assert_success( result )


def test_profiles_report_emits_html_and_json_via_sconscript_method( tmp_path ):
    """env.CollateCxxProfilesIndex() writes HTML + JSON without the CLI flag."""
    _, toolchain_flag = require_profiles_capable_toolchain()
    write_sconstruct( tmp_path )
    write_sconscript(
        tmp_path,
        "Import('env')\n"
        "env.CollateCxxProfilesIndex()\n"
        "env.Build( 'inventory_violation', 'inventory_violation.cpp' )\n"
        "env.Build( 'metrics_violation', 'metrics_violation.cpp' )\n",
    )
    ( tmp_path / 'inventory_violation.cpp' ).write_text(
        'int inventory_violation()\n'
        '{\n'
        '    int Value [[uninit]];\n'
        '    return Value;\n'
        '}\n'
    )
    ( tmp_path / 'metrics_violation.cpp' ).write_text(
        'int metrics_violation()\n'
        '{\n'
        '    int Value [[uninit]];\n'
        '    return Value;\n'
        '}\n'
    )
    result = run_cuppa(
        tmp_path,
        '--dbg',
        '--cxx-profiles',
        '--cxx-profiles-enforce=std::init',
        '--cxx-disable-error-limit',
        toolchain_flag,
    )
    report_dir = tmp_path / '_artefacts' / 'cxx-profiles'
    assert ( report_dir / 'cxx-profiles-index.html' ).is_file()
    assert ( report_dir / 'cxx-profiles-index.json' ).is_file()
    combined = ( result.stdout or '' ) + ( result.stderr or '' )
    assert 'C++ Profiles report:' in combined or report_dir.exists()
    payload = __import__( 'json' ).loads(
        ( report_dir / 'cxx-profiles-index.json' ).read_text( encoding='utf-8' )
    )
    total_references = ( payload.get( 'summary' ) or {} ).get( 'total_references' ) or 0
    assert total_references >= 2


def test_profiles_inventory_exits_non_zero_for_non_profile_errors( tmp_path ):
    """Inventory writes the session index but exits non-zero for ordinary compile errors."""
    _, toolchain_flag = require_profiles_capable_toolchain()
    write_sconstruct( tmp_path )
    write_sconscript(
        tmp_path,
        "Import('env')\n"
        "env.CollateCxxProfilesIndex()\n"
        "env.Build( 'profile_violation', 'profile_violation.cpp' )\n"
        "env.Build( 'syntax_error', 'syntax_error.cpp' )\n",
    )
    ( tmp_path / 'profile_violation.cpp' ).write_text(
        'int profile_violation()\n'
        '{\n'
        '    int Value [[uninit]];\n'
        '    return Value;\n'
        '}\n'
    )
    ( tmp_path / 'syntax_error.cpp' ).write_text(
        'int syntax_error()\n'
        '{\n'
        '    return ;\n'
        '}\n'
    )
    result = run_cuppa(
        tmp_path,
        '--dbg',
        '--cxx-profiles',
        '--cxx-profiles-enforce=std::init',
        '--cxx-disable-error-limit',
        toolchain_flag,
    )
    assert_failure( result )
    report_dir = tmp_path / '_artefacts' / 'cxx-profiles'
    assert ( report_dir / 'cxx-profiles-index.html' ).is_file()
    assert ( report_dir / 'cxx-profiles-index.json' ).is_file()
    payload = __import__( 'json' ).loads(
        ( report_dir / 'cxx-profiles-index.json' ).read_text( encoding='utf-8' )
    )
    total_references = ( payload.get( 'summary' ) or {} ).get( 'total_references' ) or 0
    assert total_references >= 1
    combined = ( result.stdout or '' ) + ( result.stderr or '' )
    assert 'non-profile compile error' in combined


def test_profiles_report_emits_html_and_json( tmp_path ):
    """--cxx-profiles-report writes HTML + JSON under _artefacts/cxx-profiles/."""
    _, toolchain_flag = require_profiles_capable_toolchain()
    write_sconstruct( tmp_path )
    write_sconscript(
        tmp_path,
        "Import('env')\n"
        "env.Build( 'app', [ 'main.cpp' ] )\n",
    )
    ( tmp_path / 'main.cpp' ).write_text(
        'int main()\n'
        '{\n'
        '    int Value [[uninit]];\n'
        '    return Value;\n'
        '}\n'
    )
    result = run_cuppa(
        tmp_path,
        '--dbg',
        '--cxx-profiles',
        '--cxx-profiles-enforce=std::init',
        '--cxx-profiles-report',
        toolchain_flag,
    )
    report_dir = tmp_path / '_artefacts' / 'cxx-profiles'
    assert ( report_dir / 'cxx-profiles-index.html' ).is_file()
    assert ( report_dir / 'cxx-profiles-index.json' ).is_file()
    combined = ( result.stdout or '' ) + ( result.stderr or '' )
    assert 'C++ Profiles report:' in combined or report_dir.exists()


def test_profiles_report_implies_error_limit( tmp_path ):
    """Inventory mode appends unlimited error-limit flags without --cxx-disable-error-limit."""
    _, toolchain_flag = require_profiles_capable_toolchain()
    write_sconstruct( tmp_path )
    write_sconscript(
        tmp_path,
        "Import('env')\n"
        "env.Build( 'app', [ 'main.cpp' ] )\n",
    )
    ( tmp_path / 'main.cpp' ).write_text(
        'int main()\n'
        '{\n'
        '    int Value [[uninit]];\n'
        '    return Value;\n'
        '}\n'
    )
    result = run_cuppa(
        tmp_path,
        '--dbg',
        '--cxx-profiles',
        '--cxx-profiles-enforce=std::init',
        '--cxx-profiles-report',
        toolchain_flag,
    )
    assert_success( result )
    combined = ( result.stdout or '' ) + ( result.stderr or '' )
    assert '-ferror-limit=0' in combined or '-fmax-errors=0' in combined


def test_profiles_report_clean_removes_manifest_artefacts( tmp_path ):
    """--clean with matching --cxx-profiles-report flags removes listed report files."""
    _, toolchain_flag = require_profiles_capable_toolchain()
    write_sconstruct( tmp_path )
    write_sconscript(
        tmp_path,
        "Import('env')\n"
        "env.Build( 'app', [ 'main.cpp' ] )\n",
    )
    ( tmp_path / 'main.cpp' ).write_text(
        'int main()\n'
        '{\n'
        '    int Value [[uninit]];\n'
        '    return Value;\n'
        '}\n'
    )
    report_flags = [
        '--dbg',
        '--cxx-profiles',
        '--cxx-profiles-enforce=std::init',
        '--cxx-profiles-report',
        toolchain_flag,
    ]
    run_cuppa( tmp_path, *report_flags )

    report_dir = tmp_path / '_artefacts' / 'cxx-profiles'
    index_html = report_dir / 'cxx-profiles-index.html'
    index_json = report_dir / 'cxx-profiles-index.json'
    manifest = tmp_path / '.cuppa-reports'

    assert index_html.is_file()
    assert index_json.is_file()
    assert manifest.is_file()

    clean_result = run_cuppa( tmp_path, *report_flags, '--clean' )
    assert_success( clean_result )

    assert not index_html.is_file()
    assert not index_json.is_file()
    assert not manifest.is_file()
    combined = ( clean_result.stdout or '' ) + ( clean_result.stderr or '' )
    assert 'C++ Profiles report clean:' in combined


def test_profiles_unsupported_toolchain_fails( tmp_path ):
    """--cxx-profiles on a non-Profiles toolchain should StopError clearly."""
    # Prefer an explicit gcc (or default) that cannot support -fprofiles.
    flags = default_toolchain_flags()
    # Force gcc when available so we do not accidentally hit a Profiles clang default.
    import shutil
    if shutil.which( 'g++' ) or shutil.which( 'gcc' ):
        flags = [ '--toolchains=gcc' ]

    write_sconstruct( tmp_path )
    write_sconscript(
        tmp_path,
        "Import('env')\n"
        "env.Build( 'app', [ 'main.cpp' ] )\n",
    )
    ( tmp_path / 'main.cpp' ).write_text( 'int main() { return 0; }\n' )
    result = run_cuppa( tmp_path, '--dbg', '--cxx-profiles', *flags )
    assert_failure( result )
    combined = ( result.stdout or '' ) + ( result.stderr or '' )
    assert 'does not support C++ Profiles' in combined or 'StopError' in combined


_VIOLATION_CPP = (
    'int probe()\n'
    '{\n'
    '    int Value [[uninit]];\n'
    '    return Value;\n'
    '}\n'
)


def _two_sconscript_profiles_project( tmp_path ):
    write_sconstruct( tmp_path )
    orders = tmp_path / 'orders'
    trades = tmp_path / 'trades'
    orders.mkdir()
    trades.mkdir()
    ( orders / 'sconscript' ).write_text(
        "Import('env')\n"
        "env.CollateCxxProfilesIndex()\n"
        "env.Build( 'orders_probe', 'probe.cpp' )\n",
        encoding='utf-8',
    )
    ( trades / 'sconscript' ).write_text(
        "Import('env')\n"
        "env.Build( 'trades_probe', 'probe.cpp' )\n",
        encoding='utf-8',
    )
    ( orders / 'probe.cpp' ).write_text( _VIOLATION_CPP, encoding='utf-8' )
    ( trades / 'probe.cpp' ).write_text( _VIOLATION_CPP, encoding='utf-8' )


def _index_sconscripts( payload ):
    return {
        scope.get( 'sconscript' )
        for scope in ( payload.get( 'report' ) or {} ).get( 'scopes' ) or []
    }


def test_profiles_report_method_index_filters_undeclared_sconscript( tmp_path ):
    """Method-only index lists declaring sconscript scopes, not sibling projects."""
    import json

    _, toolchain_flag = require_profiles_capable_toolchain()
    _two_sconscript_profiles_project( tmp_path )
    result = run_cuppa(
        tmp_path,
        '--dbg',
        '--cxx-profiles',
        '--cxx-profiles-enforce=std::init',
        '--cxx-disable-error-limit',
        toolchain_flag,
    )
    report_dir = tmp_path / '_artefacts' / 'cxx-profiles'
    assert ( report_dir / 'cxx-profiles-index.json' ).is_file()
    payload = json.loads(
        ( report_dir / 'cxx-profiles-index.json' ).read_text( encoding='utf-8' )
    )
    scripts = _index_sconscripts( payload )
    assert any( 'orders' in ( script or '' ) for script in scripts )
    assert not any( 'trades' in ( script or '' ) for script in scripts )
    scope_filter = ( payload.get( 'metadata' ) or {} ).get( 'scope_filter' ) or {}
    assert scope_filter.get( 'active' ) is True
    assert scope_filter.get( 'omitted_scope_count', 0 ) >= 1
    combined = ( result.stdout or '' ) + ( result.stderr or '' )
    assert 'omitted' in combined
    assert '--cxx-profiles-report' in combined


def test_profiles_report_cli_index_lists_all_sconscripts( tmp_path ):
    """--cxx-profiles-report bypasses the method-only scope filter."""
    import json

    _, toolchain_flag = require_profiles_capable_toolchain()
    _two_sconscript_profiles_project( tmp_path )
    run_cuppa(
        tmp_path,
        '--dbg',
        '--cxx-profiles',
        '--cxx-profiles-enforce=std::init',
        '--cxx-profiles-report',
        '--cxx-disable-error-limit',
        toolchain_flag,
    )
    payload = json.loads(
        ( tmp_path / '_artefacts' / 'cxx-profiles' / 'cxx-profiles-index.json' )
        .read_text( encoding='utf-8' )
    )
    scripts = _index_sconscripts( payload )
    assert any( 'orders' in ( script or '' ) for script in scripts )
    assert any( 'trades' in ( script or '' ) for script in scripts )
    assert 'scope_filter' not in ( payload.get( 'metadata' ) or {} )


def test_profiles_report_method_index_filters_under_parallel( tmp_path ):
    """Write-time filter still omits undeclared scopes when compiles run in parallel."""
    import json

    _, toolchain_flag = require_profiles_capable_toolchain()
    _two_sconscript_profiles_project( tmp_path )
    result = run_cuppa(
        tmp_path,
        '--dbg',
        '--parallel',
        '--cxx-profiles',
        '--cxx-profiles-enforce=std::init',
        '--cxx-disable-error-limit',
        toolchain_flag,
    )
    payload = json.loads(
        ( tmp_path / '_artefacts' / 'cxx-profiles' / 'cxx-profiles-index.json' )
        .read_text( encoding='utf-8' )
    )
    scripts = _index_sconscripts( payload )
    assert any( 'orders' in ( script or '' ) for script in scripts )
    assert not any( 'trades' in ( script or '' ) for script in scripts )
    combined = ( result.stdout or '' ) + ( result.stderr or '' )
    assert 'omitted' in combined


def test_profiles_report_method_index_unions_declaring_sconscripts( tmp_path ):
    """Two CollateCxxProfilesIndex() calls union their scopes in the index."""
    import json

    _, toolchain_flag = require_profiles_capable_toolchain()
    _two_sconscript_profiles_project( tmp_path )
    trades_script = tmp_path / 'trades' / 'sconscript'
    trades_script.write_text(
        "Import('env')\n"
        "env.CollateCxxProfilesIndex()\n"
        "env.Build( 'trades_probe', 'probe.cpp' )\n",
        encoding='utf-8',
    )
    run_cuppa(
        tmp_path,
        '--dbg',
        '--parallel',
        '--cxx-profiles',
        '--cxx-profiles-enforce=std::init',
        '--cxx-disable-error-limit',
        toolchain_flag,
    )
    payload = json.loads(
        ( tmp_path / '_artefacts' / 'cxx-profiles' / 'cxx-profiles-index.json' )
        .read_text( encoding='utf-8' )
    )
    scripts = _index_sconscripts( payload )
    assert any( 'orders' in ( script or '' ) for script in scripts )
    assert any( 'trades' in ( script or '' ) for script in scripts )
    omitted = ( ( payload.get( 'metadata' ) or {} ).get( 'scope_filter' ) or {} ).get(
        'omitted_scope_count'
    )
    assert omitted == 0
