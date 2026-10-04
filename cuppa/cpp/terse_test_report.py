#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   Terse test lines
#-------------------------------------------------------------------------------

import sys

import cuppa.progress
from cuppa.colourise import (
        as_badge,
        as_case_notice,
        as_colour,
        as_emphasised,
        as_notice,
        as_subdued,
        console_background,
)


def enabled( env ):
    return bool( env and env.get( "terse_output" ) )


def show_cases( env ):
    return bool( env and env.get( "show_test_cases" ) )


def _count( value ):
    if isinstance( value, ( list, tuple ) ):
        return len( value )
    try:
        return int( value or 0 )
    except ( TypeError, ValueError ):
        return 0


def _status_meaning( status ):
    return {
            "fail": "error",
            "skip": "skipped",
            "xfail": "expected_failure",
            "xpass": "unexpected_success",
    }.get( status, "success" )


def _paint( status, text ):
    """Status colour, not bold. A case leaf is what you scan for."""
    if status == "skip":
        return as_subdued( text )
    return as_colour( _status_meaning( status ), text )


def colour_test_name( status, name, case=False ):
    """Badge a test binary. A case colours only the leaf after ``binary/``."""
    text = str( name or "" )
    if not case:
        return as_badge( _status_meaning( status ), text )
    if "/" in text:
        prefix, leaf = text.rsplit( "/", 1 )
        return prefix + "/" + _paint( status, leaf )
    return _paint( status, text )


def _write( env, status, action, name, nanos, detail, case_name=None ):
    if action == "test-case":
        prefix, leaf = cuppa.progress.located_program_parts( name, env )
        head = as_subdued( prefix )
        if leaf:
            head = head + leaf + as_subdued( "/" )
        case = case_name
        if case is None:
            text = str( name or "" )
            case = text.rsplit( "/", 1 )[ -1 ] if "/" in text else text
        name = head + colour_test_name( status, case, case=True )
    elif action == "test":
        prefix, leaf = cuppa.progress.located_program_parts( name, env )
        name = as_subdued( prefix ) + colour_test_name( status, leaf )
    duration = cuppa.progress.format_terse_duration( nanos )
    line = cuppa.progress.format_terse_result_line(
            status, env, action, name, duration=duration, detail=detail,
    )
    sys.stdout.write( line + "\n" )
    sys.stdout.flush()


def case_status( raw ):
    if raw == "skipped":
        return "skip"
    if raw in ( "failed", "aborted" ):
        return "fail"
    return "pass"


def show_case( raw_status, env ):
    """Failing cases are always shown. The rest need ``--show-test-cases``."""
    if raw_status in ( "failed", "aborted" ):
        return True
    return show_cases( env )


def write_case( env, program, test_case, nanos ):
    raw = test_case.get( "status" ) or "passed"
    if not show_case( raw, env ):
        return
    if raw in ( "failed", "aborted" ):
        for line in test_case.get( "terse_lines" ) or []:
            sys.stdout.write( str( line ) + "\n" )
    total = _count( test_case.get( "total" ) )
    passed = _count( test_case.get( "passed" ) )
    detail = assertion_clause( passed, total, label=False )
    _write(
            env, case_status( raw ), "test-case", program, nanos, detail,
            case_name=str( test_case.get( "name" ) or "" ),
    )


def _status_phrase( count, label, meaning ):
    if not count:
        return ""
    text = "{} {}".format( count, label )
    if meaning == "subdued":
        return as_subdued( text )
    return as_colour( meaning, text )


def assertion_clause( passed, total, label=False ):
    """``14/14 assertions``, or ``no assertions`` when nothing was checked.

    A roll-up draws that phrase as a notice badge. A ``test-case`` uses a bold
    notice, so the case line does not grow another badge.
    """
    if not total:
        if label:
            return as_badge( "notice", "no assertions" )
        if console_background() == "light":
            return as_case_notice( "no assertions" )
        return as_emphasised( as_notice( "no assertions" ) )
    return "{}/{} assertions".format( passed, total )


def rollup_detail( passed, failed, skipped, aborted, expected, total, assertions=None, cases=True ):
    """Cases, then assertions, then only the non-zero extras.

    ``assertions`` is ``(passed, total)``. ``None`` omits that clause.
    ``(0, 0)`` is ``no assertions``. ``cases=False`` is one executable with
    no case breakdown, so the ``1/1 cases`` fraction is left off.
    """
    if cases and not total:
        total = passed + failed + skipped + aborted + expected
    parts = []
    if cases and total:
        parts.append( "{}/{} cases".format( passed, total ) )
    if assertions is not None:
        parts.append( assertion_clause( assertions[0], assertions[1], label=True ) )
    parts.append( _status_phrase( failed, "failed", "error" ) )
    parts.append( _status_phrase( aborted, "aborted", "error" ) )
    parts.append( _status_phrase( skipped, "skipped", "subdued" ) )
    parts.append( _status_phrase( expected, "xfailed", "expected_failure" ) )
    return ", ".join( part for part in parts if part )


def write_rollup( env, program, status, nanos, passed, failed, skipped, aborted, expected, total, assertions=None, cases=True ):
    detail = rollup_detail(
            passed, failed, skipped, aborted, expected, total,
            assertions=assertions, cases=cases,
    )
    _write( env, status, "test", program, nanos, detail )
    if cases:
        case_total = total or ( passed + failed + skipped + aborted + expected )
        cuppa.progress.note_terse_test_cases( case_total )
    cuppa.progress.note_terse_status_emitted()


def write_boost_rollup( env, program, suites ):
    passed = failed = skipped = aborted = expected = total = wall = 0
    assertions_passed = assertions_total = 0
    for suite in suites or []:
        passed += _count( suite.get( "passed_tests" ) )
        failed += _count( suite.get( "failed_tests" ) )
        skipped += _count( suite.get( "skipped_tests" ) )
        aborted += _count( suite.get( "aborted_tests" ) )
        expected += _count( suite.get( "expected_failures" ) )
        total += _count( suite.get( "total_tests" ) )
        assertions_passed += _count( suite.get( "passed_assertions" ) )
        assertions_total += _count( suite.get( "total_assertions" ) )
        times = suite.get( "total_cpu_times" )
        wall += int( getattr( times, "wall", 0 ) or 0 )
    status = "fail" if failed or aborted else "pass"
    write_rollup(
            env, program, status, wall,
            passed, failed, skipped, aborted, expected, total,
            assertions=( assertions_passed, assertions_total ),
    )


def write_process_case( env, program, status, expected, nanos ):
    """One executable with no inner cases, and no assertion total."""
    if status == "expected_failure":
        marker = "xfail"
        passed, failed, skipped, aborted, expected_n = 0, 0, 0, 0, 1
    elif status == "skipped":
        marker = "skip"
        passed, failed, skipped, aborted, expected_n = 0, 0, 1, 0, 0
    elif status == "passed" and expected not in ( None, "", "passed", status ):
        marker = "xpass"
        passed, failed, skipped, aborted, expected_n = 0, 0, 0, 0, 0
    elif status in ( "failed", "aborted" ):
        marker = "fail"
        passed, failed, skipped, aborted, expected_n = 0, 1, 0, 0, 0
    else:
        marker = "pass"
        passed, failed, skipped, aborted, expected_n = 0, 0, 0, 0, 0
    write_rollup(
            env, program, marker, nanos,
            passed, failed, skipped, aborted, expected_n, 0,
            assertions=( 0, 0 ), cases=False,
    )
