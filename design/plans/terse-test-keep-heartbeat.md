# Note: terse long tests must keep `[....] · running-test`

- **Status:** done
- **Related:** [`archive/terse-build-action-heartbeat.md`](../archive/terse-build-action-heartbeat.md); ROADMAP `console-terse-test-keep-heartbeat`; `_ProgressLedger` / `begin_terse_executing`; `IncrementalSubProcess.keep_heartbeat`
- **Updated:** 2026-11-13
- **Impact:** `patch` — ships with 1.14.1

## Observed

Under `--terse-output` (± `-Q`) a multi-minute `BuildTest` / `Test` run left the
console on the previous durable `[ok]` with no sticky
`[....] · running-test · …` pulse. Compile/link still showed in-flight captions;
only the test (and `env.Run`) child looked hung until `[pass]` / `[ok]`.

## Cause

`PRINT_CMD_LINE` already arms `begin_terse_executing` for the Python test
action. Toolchain `SPAWN` and coverage `gcov` keep that caption alive with
`IncrementalSubProcess(..., keep_heartbeat=True)` under terse. Test runners and
`env.Run` passed `suppress_output=terse` **without** `keep_heartbeat`, so
`Popen2` called heartbeat `suppress()` for the whole child lifetime and held
the status row blank.

## Fix

Pass `keep_heartbeat=terse` from:

- `cuppa/cpp/run_process_test.py`
- `cuppa/cpp/run_boost_test.py` / `run_patched_boost_test.py`
- `cuppa/method_helpers/run_process.py`

Same pattern as toolchain SPAWN and `run_gcov_coverage.run_command`. Delegated
CMake / `b2` `[launch]` paths stay out of scope (bookend owns that cue).

## Non-goals

- Changing durable `[pass]` / `[ok]` spelling or action tallies.
- Re-opening deferred delegated-builder `[....]` beside `[launch]`.

## Hygiene (same PR)

POSIX hosts must not `open("CONOUT$", "w")` when resolving a progress TTY —
Windows device name, ordinary filename on Linux — and `CONOUT$` stays
gitignored so a stray cwd file cannot ride `git add -A`.
