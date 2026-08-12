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
