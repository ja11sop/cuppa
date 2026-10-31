# Coverage collection and SCons parallelism

- **Status:** in progress
- **Related:** [`ROADMAP.md`](../../ROADMAP.md) — Coverage reporting and performance; [#236](https://github.com/ja11sop/cuppa/issues/236); [`coverage-performance.md`](coverage-performance.md)
- **Updated:** 2026-10-31
- **Impact:** patch — warn + `Depends` ordering; `GCOV_PREFIX` isolation is in progress and the parallel-collection warning remains

This records how Cuppa coverage works today, which parallel combinations are safe, and what
would be required to make `--cov --test --parallel` correct. It is the analysis behind the
[#236](https://github.com/ja11sop/cuppa/issues/236) warning and docs; it is **not** a performance
plan (that remains [`coverage-performance.md`](coverage-performance.md)).

## Settled decisions (1.9.1)

| Decision | Choice |
|----------|--------|
| Parallel instrumented **compile** (`--cov --parallel`, no `--test`) | **Supported** — `--cov` does not run tests; `BuildTest` does not attach Coverage/Test nodes without `--test` |
| Parallel **coverage collection** (`--cov --test` with `--parallel` or `-j` > 1) | **Not supported** as a correct workflow |
| Operator signal in 1.9.1 | **Warn** (do not fail the build). A hard refuse would break trees that currently “get lucky” |
| `BuildTest` / `BuildBenchmark` graph | Coverage **Depends** on the Test/Benchmark node only — see [Appendix A](#appendix-a-coverage-depends) |
| `Coverage(program, sources)` | `program` is the executable from `Build()`, not the flattened `BuildTest` return list — [Appendix A](#appendix-a-coverage-depends) |
| Isolate `.gcda` per test (`GCOV_PREFIX`) | **In progress** — test/benchmark spawn sets a per-binary prefix; gcov reads those notes via a private `-o` stem (it does not honour `GCOV_PREFIX`). Warning stays until the shared-lib fixture is stable in CI |
| gcovr `-j` during report generation | **Deferred** — independent of test-process races; see `cov-parallel-gcovr` in the performance plan |

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
`{build}/gcov-notes/{sconscript}/{program}` and `GCOV_PREFIX_STRIP=0`. The `.gcda` path is
that prefix plus the absolute object path, so two tests that link one static library do not
share a note file. Serial `--cov --test` uses the same path.

`RunGcovCoverage` then:

1. Invokes `gcov` / `llvm-cov gcov` in `{prefix}/gcov-text`. `gcov` opens `.gcda` next to
   `-o` and does **not** read `GCOV_PREFIX`, so `-o` is a private stem whose `.gcno` and
   `.gcda` are symlinks (the `.gcda` symlink targets the relocated note). The source
   argument stays relative (`-r`); a symlink under that directory keeps the `#` filename
   the rename step already expects.
2. Globs `*.gcov` in that private directory and **renames** them, with a program-id suffix,
   into the build dir.
3. Calls `gcovr` (`-g`, HTML details, JSON) on those renamed files — historically **inside**
   the per-source loop (performance issue; see `cov-once-per-test`).
4. Collation copies HTML/JSON and builds by-source union indexes.

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
| Two-step: parallel `--cov`, then serial `--cov --test` | Intended large-project workflow |

### Unsafe without new machinery

| Combination | Why |
|-------------|-----|
| `--cov --test --parallel` (or `-j` > 1) | (1) **Shared `.gcda`** and (3) **gcov glob/rename** are what `GCOV_PREFIX` plus a private `*.gcov` directory address. The configure warning stays until that fixture is stable in CI. Still open: (4) gcovr/collation overlap, (5) interleaved stdout, and any fixture the sconscript itself shares (port, database). (2) Coverage vs Test ordering was fixed for `BuildTest` in 1.9.1 |
| Parallel tests that share a static/shared lib, even after `Depends(coverage, test)` | Ordering is per binary. Note isolation is per binary too (`gcov-notes/…/{program}`), which is what the shared-lib fixture checks |

Independent single-file tests with **no shared instrumented library** can appear to work under
`-j` (the integration suite checks that this still exits 0). That is not a correctness
guarantee for consumer trees.

### What would make parallel collection feasible

The usual GCC approach is **per-test note isolation**:

1. Set `GCOV_PREFIX` (and often `GCOV_PREFIX_STRIP`) uniquely for each test process.
2. Point `gcov` at that binary's relocated `.gcda`. `gcov` does not read `GCOV_PREFIX`;
   Cuppa symlinks the note next to a private `-o` stem. `gcovr -g` then reads the
   `.gcov` text that produced.
3. Merge JSON (Cuppa already unions `coverage--*.json` for by-source) rather than merging
   `.gcda` in place.

That is the `cov-gcov-prefix` slice: env plumbing on the test runner, Coverage runner
awareness, and a fixture of two tests that share a static lib. It does not by itself make
`--cov --test --parallel` a supported workflow. The warning stays, and a sconscript that
shares a port or a database is still that sconscript's problem.

Serializing all Test+Coverage behind one SCons `SideEffect` lock would make `-j` safe but
would also make `--parallel` pointless for the collect step.

gcovr `-j` only parallelises **report generation** after notes are stable. It does not fix
test-process races.

## 1.9.1 product behaviour

- Warn at configure when `job_count > 1` and `--cov` is on and `--test` / `--force-test` /
  `--benchmark` / `--force-benchmark` is on (`cuppa/cpp/coverage_workflow.py`).
- `BuildTest` / `BuildBenchmark` `Depends` coverage on the Test/Benchmark node
  ([Appendix A](#appendix-a-coverage-depends)).
- Docs state the two-step recipe as the supported contract, with the reasons above instead of
  “historically flaky”.

## Tests that qualify the assumptions

| Test | What it locks |
|------|----------------|
| `tests/unit/test_coverage_workflow.py` | Warn predicate: compile-only `--cov --parallel` is silent; collect + `-j` warns |
| `tests/integration/methods/test_coverage.py` (`test_coverage_parallel_independent_tests`) | Two single-file tests under `--cov --test --parallel` still succeed (no shared lib) |
| Same module (`test_coverage_parallel_collection_warns`) | Warning text appears when the run actually enters parallel mode |
| Same module (`test_coverage_parallel_shared_library_keeps_separate_notes`) | Two tests, one static lib, `--cov --test --parallel`: each prefix has `shared.gcda`, and each coverage JSON reports lines hit |

The shared-lib check is one successful run, not a stress loop. It locks the layout (separate
notes, non-zero reports), not that a race can never happen.

## Follow-ons (not this cycle)

| ID | Work |
|----|------|
| `cov-gcov-prefix` | **In progress** — test/benchmark spawn sets `GCOV_PREFIX`; gcov uses a private `-o` stem (symlinked `.gcno`/`.gcda`) and a private `*.gcov` directory. Shared-library integration fixture checks separate `shared.gcda` and non-zero JSON. Warning stays until that fixture is stable in CI |
| `cov-once-per-test` | Hoist gcovr out of the per-source loop ([`coverage-performance.md`](coverage-performance.md)) |
| `cov-parallel-gcovr` | gcovr `-j` after notes are isolated or after a serial test pass |

## Reference

- `cuppa/methods/build_test.py`, `cuppa/methods/coverage.py`
- `cuppa/cpp/run_gcov_coverage.py`, `cuppa/cpp/coverage_workflow.py`
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
