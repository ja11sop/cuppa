#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

import pytest

from cuppa.core.profiles_inventory_cli import (
    args_imply_profiles_inventory,
    inject_inventory_ignore_errors,
    user_passed_ignore_errors,
)

pytestmark = pytest.mark.unit


def test_inject_ignore_errors_for_profiles_report_flag():
    Args = [ '--dbg', '--cxx-profiles-report', '--cxx-profiles' ]
    assert inject_inventory_ignore_errors( Args ) == [ '-i' ] + Args


def test_inject_ignore_errors_for_collate_method_in_sconscript( tmp_path ):
    Sconstruct = tmp_path / 'sconstruct'
    Sconstruct.write_text(
        "import cuppa\n"
        "cuppa.run()\n",
        encoding='utf-8',
    )
    Sconscript = tmp_path / 'test' / 'sconscript'
    Sconscript.parent.mkdir()
    Sconscript.write_text(
        "Import('env')\n"
        "env.CollateCxxProfilesIndex()\n",
        encoding='utf-8',
    )
    Args = [ '--dbg', '--scripts=test/sconscript' ]
    Injected = inject_inventory_ignore_errors( Args, launch_dir=str( tmp_path ) )
    assert Injected[ 0 ] == '-i'
    assert args_imply_profiles_inventory( Args, launch_dir=str( tmp_path ) )


def test_inject_ignore_errors_for_collate_method_in_nested_sconscript( tmp_path ):
    ( tmp_path / 'sconstruct' ).write_text(
        "import cuppa\n"
        "cuppa.run()\n",
        encoding='utf-8',
    )
    Nested = tmp_path / 'orders' / 'sconscript'
    Nested.parent.mkdir()
    Nested.write_text(
        "Import('env')\n"
        "env.CollateCxxProfilesIndex()\n",
        encoding='utf-8',
    )
    Args = [ '--dbg' ]
    Injected = inject_inventory_ignore_errors( Args, launch_dir=str( tmp_path ) )
    assert Injected[ 0 ] == '-i'


def test_does_not_inject_for_nested_sconscript_without_collate( tmp_path ):
    ( tmp_path / 'sconstruct' ).write_text(
        "import cuppa\n"
        "cuppa.run()\n",
        encoding='utf-8',
    )
    Nested = tmp_path / 'orders' / 'sconscript'
    Nested.parent.mkdir()
    Nested.write_text(
        "Import('env')\n"
        "env.Build( 'app', 'main.cpp' )\n",
        encoding='utf-8',
    )
    Args = [ '--dbg' ]
    assert inject_inventory_ignore_errors( Args, launch_dir=str( tmp_path ) ) == Args
    Args = [ '-i', '--cxx-profiles-report' ]
    assert inject_inventory_ignore_errors( Args ) == Args


def test_does_not_inject_for_ordinary_build():
    Args = [ '--dbg', '--rel' ]
    assert inject_inventory_ignore_errors( Args ) == Args


def test_user_passed_ignore_errors_detects_long_form():
    assert user_passed_ignore_errors( [ '--ignore-errors', '--dbg' ] )
