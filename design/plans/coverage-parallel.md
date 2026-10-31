# Coverage collection and SCons parallelism

- **Status:** done
- **Related:** [`ROADMAP.md`](../../ROADMAP.md) — Coverage reporting and performance; [#236](https://github.com/ja11sop/cuppa/issues/236); [`coverage-performance.md`](coverage-performance.md)
- **Updated:** 2026-10-31
- **Impact:** patch — `--cov --test --parallel` is supported; the configure warning is removed

This records how Cuppa coverage works, and why `--cov --test --parallel` is a normal run.
It is **not** a performance plan (that remains [`coverage-performance.md`](coverage-performance.md)).

## Settled decisions (1.9.1)

| Decision | Choice |
|----------|--------|
| Parallel instrumented **compile** (`--cov --parallel`, no `--test`) | **Supported** — `--cov` does not run tests; `BuildTest` does not attach Coverage/Test nodes without `--test` |
| Parallel **coverage collection** (`--cov --test` with `--parallel` or `-j` > 1) | **Supported.** Notes and reports are per program. 1.9.1 warned and told people to collect serially; this slice removes that warning |
| Operator signal in 1.9.1 | **Was a warning** (not a hard fail). Removed in this slice. A shared port or database is a documentation note, not a Cuppa warning |
| `BuildTest` / `BuildBenchmark` graph | Coverage **Depends** on the Test/Benchmark node only — see [Appendix A](#appendix-a-coverage-depends) |
| `Coverage(program, sources)` | `program` is the executable from `Build()`, not the flattened `BuildTest` return list — [Appendix A](#appendix-a-coverage-depends) |
| Isolate `.gcda` per test (`GCOV_PREFIX`) | **Done** — test/benchmark spawn sets a per-binary prefix; `gcov` reads the `.gcda` there with the `.gcno` linked beside it (it does not honour `GCOV_PREFIX`) |
| gcovr HTML in the shared sconscript directory | **Done** — each program writes under `gcov-data/{program}/gcovr`, the detail glob is `name.*.html` so `lim` does not match `lim_table`, and gcovr runs once per program. A failed move fails the action. Collation publishes `{program}/` beside the sconscript index and does not `Install` from inside the action. `gcovr -j` will not be added: Cuppa passes `-g`, so gcovr is not running `gcov`, and another job pool would only oversubscribe under `--parallel` |

## How coverage runs today

### Variant vs action

`--cov` is both a **variant** (instrumented compile/link: `--coverage`) and an **action**
(`cuppa/variants/cov.py` calls `add_variant` and `add_action`). `--test` is an action only.

`BuildTest()`:

1. Always `env.Build()` (program).
2. If `test` or `force_test` is active: `env.Test(program, …)`.
3. If that ran **and** `cov` is active: `env.Coverage(program, sources, …)`.

So the documented two-step recipe is real for `BuildTest`:

```sh
cuppa -D --cov --parallel    # compile/link only
cuppa -D --cov --test        # run tests, then gcov/gcovr, then collate
```

A bare `env.Coverage(program, sources)` in a sconscript is created whenever `cov` **or** `test`
is in `variant_actions`. That path can run gcov on a `--cov` compile-only invocation. Prefer
`BuildTest` (or `Depends` the Coverage node on the Test node yourself).

### Where the notes live

GCC/Clang `--coverage` writes:

- `.gcno` at compile, beside the `.o` under the mirrored `working/` tree
- `.gcda` at **process exit** of the instrumented binary

When `cov` is active, the test or benchmark process sets `GCOV_PREFIX` to
`{abs_build_dir}/gcov-data/{program}` and `GCOV_PREFIX_STRIP=0`. The `.gcda` path is
that prefix plus the absolute object path, so two tests that link one static library do not
share a data file. Serial `--cov --test` uses the same path. The test keeps the working
directory the sconscript gave it.

The runners (`RunProcessTest`, `RunBoostTest`, `RunPatchedBoostTest`) own that decision:
they ask `cuppa/cpp/gcov_data.py` for `coverage_env_step()` and pass it as `prepare_env`
to `IncrementalSubProcess.Popen2`. `Popen2` runs that step on a copy of the environment it
already chose (construction `ENV`, the `inherit_process_env` policy, or an explicit `env=`)
and knows nothing about coverage. The step only adds the two variables. It never widens what
the child inherits, and when no environment was chosen it is not run.

`RunGcovCoverage` then:

1. Invokes `gcov` / `llvm-cov gcov` in `{prefix}/gcov-run`. `gcov` opens `.gcda` next to
   `-o` and does **not** read `GCOV_PREFIX`, so `-o` is the relocated `.gcda` stem with the
   `.gcno` linked beside it (copied if a symlink cannot be created). The `.gcda` itself is
   not linked or moved. The source argument stays relative (`-r`); a copy under `gcov-run`
   keeps the `#` filename the rename step already expects. `gcov` then names every other
   source in the notes. Each relative path it could not open (a project header such as
   `include/...`) is copied into `gcov-run` the same way, and `gcov` is run again so those
   `.gcov` files contain source lines. Absolute paths are left alone.
2. Globs `*.gcov` in that private directory and **renames** them, with a program-id suffix,
   into the build dir.
3. Calls `gcovr` (`-g`, HTML details, JSON) **once per program**, after every source
   has been collected. `-o` is `gcov-data/{program}/gcovr`, so two programs do not
   write the same HTML names into the sconscript directory. Detail pages are
   moved with `name.*.html` (a dot after the program name). `name*.html` also
   matches a longer program such as `name_table`.
4. Collation publishes that program's HTML and JSON into `{program}/` beside the
   sconscript index. The directory is a side effect of the collation target, and
   `-c` with the same `--cov --test` removes it. The per-program filter uses
   that same dotted pattern. By-source union indexes are unchanged.

Coverage builder **sources** are the C++ sources, not the Test stamp. SCons therefore treated
Test and Coverage as independent default targets until `BuildTest` added `Depends(coverage, test)`
([Appendix A](#appendix-a-coverage-depends)).

### What `--parallel` actually does

`--parallel` with `num_jobs == 1` sets SCons `-j` to `cpu_count()`. An explicit `-j N` with
`N > 1` is the same concurrency without the Cuppa flag. Both are “parallel collection” if tests
and coverage actions are in the graph.

## What is, and is not, feasible

### Safe today

| Combination | Why |
|-------------|-----|
| `--cov --parallel` without `--test` / `--benchmark` | No Test/Coverage nodes from `BuildTest`; objects are independent compile jobs |
| `--dbg --test --parallel` (no `--cov`) | No `.gcda`; tests are separate processes. Console/TestSuite summaries can still interleave |
| Serial `--cov --test` | One test, then its Coverage (after 1.9.1 `Depends`), then the next |
| `--cov --test --parallel` (or `-j` > 1) | Notes are per binary. gcov, gcovr, and the collated report directory are per program |
| Two tests that share a static library | Each has its own `shared.gcda` under `gcov-data/{program}`. The shared-lib fixture checks that |
| Two-step: parallel `--cov`, then `--cov --test` | Optional. The second step may also be parallel. It is not a required workaround |

### Not Cuppa's problem

| Combination | Why |
|-------------|-----|
| Tests that share a port, a database, or another fixture | Same under `--test --parallel` with or without `--cov`. The docs say so. Cuppa does not warn |

Test stdout can still interleave. That is presentation, not a coverage-note race.

### What would make parallel collection feasible

The usual GCC approach is **per-test note isolation**:

1. Set `GCOV_PREFIX` (and often `GCOV_PREFIX_STRIP`) uniquely for each test process.
2. Point `gcov` at that binary's relocated `.gcda`. `gcov` does not read `GCOV_PREFIX`;
   Cuppa links the `.gcno` beside the `.gcda` and starts `gcov` in `gcov-run` so the
   `*.gcov` files are per binary. `gcovr -g` then reads the `.gcov` text that produced.
3. Merge JSON (Cuppa already unions `coverage--*.json` for by-source) rather than merging
   `.gcda` in place.

That is the `cov-gcov-prefix` slice, and it is what this change ships. `--cov --test --parallel`
is a supported run. A sconscript that shares a port or a database is still that sconscript's
problem, and the docs say so. Cuppa does not warn about it.

Serializing all Test+Coverage behind one SCons `SideEffect` lock would make `-j` safe but
would also make `--parallel` pointless for the collect step.

`gcovr -j` is a thread pool for the part of gcovr that shells out to `gcov`. Cuppa passes
`-g`, so that work is already done. The flag does not isolate notes or HTML, and under
`--parallel` it would only add another job pool inside actions SCons is already running
together. It will not be added.

## 1.9.1 product behaviour

1.9.1 warned at configure when `job_count > 1` and `--cov` was combined with test or
benchmark collection, and the docs required a serial collect. This slice removes that
warning. What remains from 1.9.1:

- `BuildTest` / `BuildBenchmark` `Depends` coverage on the Test/Benchmark node
  ([Appendix A](#appendix-a-coverage-depends)).

## Tests that qualify the assumptions

| Test | What it locks |
|------|----------------|
| `tests/integration/methods/test_coverage.py` (`test_coverage_parallel_independent_tests`) | Two single-file tests under `--cov --test --parallel` succeed, and stdout does not contain the old collection warning |
| Same module (`test_coverage_shared_library_notes_are_per_test`, serial and parallel) | Two tests, one static lib, one lib function per test: each prefix has its own `shared.gcda`, none is written beside the object, and each report shows only its own lib function executed |
| Same module (`test_coverage_build_benchmark_uses_per_binary_notes`) | `--cov --benchmark` gets the same per-binary notes and a non-zero report |
| `tests/unit/test_prepare_env_spawn.py` | `Popen2` `prepare_env` runs on a copy of the chosen env, keeps parent-only variables out unless `inherit_process_env` allows them, and is skipped when no env was chosen; all three runners pass the step only under `cov` |
| `tests/unit/test_gcov_data.py` | `gcov-data` layout, relocated `.gcda` path, source copy into `gcov-run`, reported header paths copied (absolute and missing paths skipped), `.gcno` link beside the `.gcda` and its copy fallback, private `gcovr/` directory |
| `tests/unit/test_run_gcov_coverage.py` | Detail glob `lim.*.html` does not match `lim_table`; `--terse-output` notes a gcov/gcovr command instead of echoing it, and does not print the `lines:` summary |
| `tests/integration/methods/test_coverage.py` (`test_coverage_parallel_prefix_names_keep_their_reports`) | `--cov --test --parallel` with `lim` (two sources) and `lim_table`: two gcovr runs, both `coverage--*.html` indexes, neither program's filter matches the other |
| Same module (`test_coverage_method`) | `--terse-output` coverage run does not print raw `gcov` / `gcovr` command lines or the `lines:` / `functions:` / `branches:` summary |
| Same module (`test_coverage_report_includes_header_lines`) | A header included via `-I` has non-empty line data in the coverage JSON |

The shared-lib check is one successful run, not a stress loop. It proves the notes are per
test (a shared `.gcda` would show both functions executed in both reports), not that a race
can never happen elsewhere.

## Follow-ons

| ID | Work |
|----|------|
| `cov-gcov-prefix` | **This slice** — test/benchmark spawn sets `GCOV_PREFIX` to `gcov-data/{program}`; `gcov` runs in `gcov-run` with the `.gcno` linked beside that `.gcda`. gcovr runs once per program. Collation publishes `{program}/`. The configure warning is removed |
| `console-terse-heartbeat-chase` | **Not this work.** Terse lines no longer wait out a full cycle; the animation still restarts. The note is [`terse-heartbeat-chase.md`](terse-heartbeat-chase.md) |

## Reference

- `cuppa/methods/build_test.py`, `cuppa/methods/coverage.py`
- `cuppa/cpp/run_gcov_coverage.py`, `cuppa/cpp/gcov_data.py`
- `cuppa/variants/cov.py`, `cuppa/construct.py` (job count / `--parallel`)
- GCC `--coverage` / `GCOV_PREFIX` in the GCC instrumentation docs
- [Appendix A](#appendix-a-coverage-depends) — SCons graph for `Depends(coverage, test)` vs a cycle on the `BuildTest` return list

<a id="appendix-a-coverage-depends"></a>
## Appendix A — Why Coverage Depends on the Test node, not the BuildTest return list

`BuildTest` returns a **bundle** of SCons nodes. Coverage collection is a **second builder** whose
outputs have **fixed names** derived from the binary. Those two facts collide if Coverage
`Depends` on the bundle.

### What `BuildTest` returns

With `--cov --test` it constructs three things, then `Flatten`s them into one list
(`cuppa/methods/build_test.py`):

1. **Program** — `final/hello_test` (from `env.Build`).
2. **Test stamps** — `hello_test.success`, stdout/stderr logs, JSON report (from `env.Test`).
3. **Coverage artefacts** — `coverage--hello_test.html`, `.json`, `.log`, `.cov_filter`, plus
   `*_gcov.log` beside the sources (from `env.Coverage`).

So `prog = env.BuildTest('hello_test', …)` is not “the executable”. It is that whole list.

`env.Coverage` does **not** take those stamps as builder sources. The Coverage builder is fed
the **C++ sources**; the `program` argument is only used to name gcov/gcovr files (`hello_test`
→ `coverage--hello_test.*`). Before `Depends(coverage, test)`, SCons saw two independent default
targets: “run the test” and “run gcov on these `.cpp` files”. Nothing required gcov to wait for
the process that writes `.gcda`. Serial `-j1` often lucked into the right order; `-j` did not.

### The Depends that is acyclic

`env.Depends(coverage, test)` means every Coverage **target** waits for the Test **stamp**
(`.success` / logs). The graph is a line:

```
hello_test (exe)
    → Test (run, writes .gcda)
        → Coverage (gcov / gcovr)
```

That is ordered and acyclic. `BuildBenchmark` does the same with the Benchmark node.

### Why `Depends` on the whole `BuildTest` return list cycles

A natural extra would be “also `Depends` Coverage on `program`”, so gcov cannot run before
link. Inside `Coverage()`, `program` is whatever the **caller** passed.

`BuildTest` already passes the **executable** into `Coverage(program, source)` — that call is
fine. Cuppa’s own integration fixture then does this (`tests/integration/methods/test_coverage.py`,
`test_coverage_method`):

```python
prog = env.BuildTest('hello_test', 'tests/hello_test.cpp')
env.Coverage(prog, 'tests/hello_test.cpp')
```

That is **two** Coverage builders for the **same** binary:

1. `BuildTest` already called `Coverage(hello_test, hello_test.cpp)` → targets
   `coverage--hello_test.html` and siblings.
2. The sconscript calls `Coverage(prog, …)` again. `prog` is the **flattened bundle**, which
   **includes those same coverage files**.

If `Coverage()` did `Depends(coverage, Flatten(program))` with that bundle:

- The second builder’s targets are again `coverage--hello_test.html` (same paths; SCons treats
  them as the same nodes).
- Those nodes would `Depends` on a list that **already contains** `coverage--hello_test.html`.

That is a **self-edge**: the node is a prerequisite of itself. SCons reports:

`coverage--hello_test.html -> … -> coverage--hello_test.html`

(and the same for `.json` / `.log` / `.cov_filter` / the gcov log).

### Rule of thumb

- **Do** `Depends` Coverage on the **Test** (or Benchmark) node — a different file (`.success`),
  so no loop.
- **Do not** `Depends` Coverage on the **whole `BuildTest` return list**, because that list
  already contains Coverage’s own outputs.
- If a sconscript calls `env.Coverage` itself, pass the **executable** (`Build()` / the program
  node), not `prog = BuildTest(...)`.

That is why 1.9.1 only adds `Depends(coverage, test)` inside `BuildTest` / `BuildBenchmark`, and
does **not** add `Depends(coverage, program)` inside `Coverage()`: the latter would break any
sconscript that passes the `BuildTest` bundle back into `Coverage()`, including Cuppa’s coverage
integration test.
