#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

import pytest

from cuppa.cpp.cxx_profiles_report import ProfilesScope
from cuppa.cpp.profiles_report_collector import ProfilesDiagnosticCollector
from cuppa.methods.cxx_profiles_report import reset_inventory_report_state_for_tests
from cuppa.output_processor import ToolchainProcessor
from cuppa.progress import NotifyProgress
from cuppa.toolchains.clang import Clang

pytestmark = pytest.mark.unit

_PROFILE_LINE = (
    "/home/user/project/include/widget/table.hpp"
    ":120:5: error: constructor does not initialize member 'Buffer_' "
    "under profile 'std::init'"
)

_ORDINARY_ERROR_LINE = "/home/user/project/main.cpp:4:5: error: use of undeclared identifier 'Missing'"

_SAMPLE_SCOPE = ProfilesScope(
    sconscript='./widget/sconscript',
    variant_dir='_build/widget/clang24_profiles/dbg/x86_64/cxx2c',
    toolchain='clang24_profiles',
    variant_label='dbg',
)


@pytest.fixture(autouse=True)
def _reset_state():
    ProfilesDiagnosticCollector.reset()
    reset_inventory_report_state_for_tests()
    yield
    ProfilesDiagnosticCollector.reset()
    reset_inventory_report_state_for_tests()


def _processor():
    return ToolchainProcessor(
        Clang,
        minimal_output=False,
        ignore_duplicates=False,
        profiles_scope=_SAMPLE_SCOPE,
    )


def test_inventory_mode_displays_profile_violation_as_error_with_warning_colour():
    NotifyProgress.set_inventory_report_mode( True )
    ProfilesDiagnosticCollector.activate()

    output = _processor()( _PROFILE_LINE )

    assert output is not None
    assert '= Error 1 =' in output
    assert '= Warning ' not in output
    assert ProfilesDiagnosticCollector.active().non_profile_error_count() == 0


def test_inventory_mode_increments_profile_error_labels():
    NotifyProgress.set_inventory_report_mode( True )
    ProfilesDiagnosticCollector.activate()

    Processor = _processor()
    First = (
        "/home/user/project/order.hpp:62:5: error: constructor does not initialize "
        "member 'Owner_' under profile 'std::init'"
    )
    Second = (
        "/home/user/project/order.hpp:62:5: error: constructor does not initialize "
        "member 'Side_' under profile 'std::init'"
    )

    assert '= Error 1 =' in Processor( First )
    assert '= Error 2 =' in Processor( Second )
    assert Processor.errors == 0


def test_inventory_mode_increments_profile_error_labels_across_processors():
    NotifyProgress.set_inventory_report_mode( True )
    ProfilesDiagnosticCollector.activate()

    First = (
        "/home/user/project/order.hpp:62:5: error: constructor does not initialize "
        "member 'Owner_' under profile 'std::init'"
    )
    Second = (
        "/home/user/project/order.hpp:62:5: error: constructor does not initialize "
        "member 'Side_' under profile 'std::init'"
    )

    assert '= Error 1 =' in _processor()( First )
    assert '= Error 2 =' in _processor()( Second )


def test_inventory_mode_tallies_non_profile_errors():
    NotifyProgress.set_inventory_report_mode( True )
    ProfilesDiagnosticCollector.activate()

    output = _processor()( _ORDINARY_ERROR_LINE )

    assert output is not None
    assert 'Error' in output
    assert ProfilesDiagnosticCollector.active().non_profile_error_count() == 1


def test_inventory_mode_ignores_keep_going_missing_object_link():
    NotifyProgress.set_inventory_report_mode( True )
    ProfilesDiagnosticCollector.activate()

    processor = _processor()
    output = processor(
        "clang++: error: no such file or directory: "
        "'_build/clang/dbg/working/main.o'"
    )

    assert output is not None
    processor.summary( 1 )
    assert ProfilesDiagnosticCollector.active().non_profile_error_count() == 0
    assert ProfilesDiagnosticCollector.inventory_process_exit_status() is None
    NotifyProgress.set_inventory_report_mode( True )
    ProfilesDiagnosticCollector.activate()

    processor = _processor()
    processor( _PROFILE_LINE )
    processor.summary( 1 )

    assert ProfilesDiagnosticCollector.inventory_process_exit_status() is None


def test_inventory_mode_exit_status_is_non_zero_for_non_profile_errors():
    NotifyProgress.set_inventory_report_mode( True )
    ProfilesDiagnosticCollector.activate()

    processor = _processor()
    processor( _ORDINARY_ERROR_LINE )

    assert ProfilesDiagnosticCollector.inventory_process_exit_status() == 1
