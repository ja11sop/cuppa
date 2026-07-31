# Coverage performance: measurements, analysis, and plan

Status: **analysis and proposal** (no performance work done yet)

This records what we measured, what the measurement ruled out, and where the remaining
suspects are, so the work can be picked up later without repeating the investigation.

Two consumer projects are referred to throughout by label, because they are private:

- **project A** — a header-heavy library: 38 test sconscripts, 362 test source files (one binary
  each), 545 headers under `include/`. This is where the A/B in §2 was run.
- **project B** — fewer, larger test binaries and a much longer coverage cycle. This is where the
  original slow-down was reported, and the A/B there is still outstanding.

---

## 1. What prompted this

A consumer project (**project B**) appeared to go from roughly 40 minutes to roughly
70 minutes for `--cov --test` after the by-source coverage union (`cuppa/cpp/coverage_by_source.py`)
was introduced. By-source was the obvious suspect: it reads every `coverage--*.json`, computes a
union, and writes a full-source HTML page per file, twice over (once per sconscript index, once
per toolchain in the master index).

To test that, a temporary opt-in flag `--cov-by-source` was added so by-source could be switched
off and the two runs compared. That flag is temporary scaffolding and is reverted along with
this write-up; by-source is on again by default.

---

## 2. Measurement

Run on **project A**, deliberately chosen as a repository with many headers and many
tests: **38 test sconscripts, 362 test source files (one binary each), 545 headers under
`include/`**.

Preparation before each timed run, so both start from the same state:

```sh
rm -rf _build
cuppa --cov --parallel --offline
```

Timed runs:

| Run | Command | Real | User | Sys |
|-----|---------|------|------|-----|
| Without by-source | `time cuppa --cov --test --offline` | **8m32.6s** | 7m53.3s | 0m38.3s |
| With by-source | `time cuppa --cov --cov-by-source --test --offline` | **7m43.3s** | 7m9.9s | 0m33.0s |

Both reported the same coverage: `94.3% : 96748/102564`.

### 2.1 What this tells us

**By-source is not the bottleneck, at least not on this shape of project.** The run *with*
by-source was 49 seconds faster, which is machine noise rather than a real speed-up, but the
important part is the sign: if by-source were responsible for anything like the reported
+30 minutes, it could not disappear into noise here.

The honest reading is that on project A the whole `--cov --test` cycle costs about 8m30 and
by-source is a small enough fraction to be invisible against background load. The earlier
hypothesis is not confirmed. It is not fully refuted either, because project B has a
different shape (fewer files, but different test-to-source ratios and a much longer run), so the
same A/B there is still worth doing.

### 2.2 Observation carried forward

The JSON generation step looked slow during both runs. It is present in both, so it does not
show up in the comparison, but it is the strongest remaining lead. Section 3 explains why that
observation is plausible and what specifically is wasteful.

---

## 3. Analysis of the current implementation

### 3.1 gcovr runs once per source file, not once per test binary

`RunGcovCoverage.__call__` loops over the sources of a test and calls `_run_gcov` for each. At
the end of `_run_gcov`:

```python
with open( gcov_log_path, 'w', encoding='utf-8' ) as summary_file:
    summary_file.write( output )

    coverage_suite.run_suite( self._target )
```

`run_suite` is the full gcovr report generation — HTML index, HTML details, and JSON — over all
the gcov data accumulated for that test. It is called **inside the per-source loop**, so a test
binary built from N sources runs the whole report N times, each time producing the same output.

On project A every test is a single `.cpp`, so N is 1 and this costs nothing — which is
consistent with by-source being invisible there and with the run still taking 8m30. On projects
where test binaries are built from several sources, this is a direct multiplier on the most
expensive step. Project B should be checked for this specifically.

The nesting inside the `with` block also means the report only runs when the log file write
succeeds, which is incidental rather than intended.

### 3.2 `gcovr --version` is a subprocess per report

`CoverageSuite.get_gcovr_version()` shells out `gcovr --version` on every `_run_gcovr` call, and
`CoverageSuite.create()` builds a fresh suite each time with no caching. That is one extra
process launch per report — negligible alone, multiplied by the same factor as above.

### 3.3 HTML details dominate the artefact volume

gcovr is invoked with `--html --html-details --html-self-contained --html-theme green`. Details
mode writes one page per covered file, and self-contained embeds the CSS and JavaScript in each
page. With 545 headers visible to 362 test binaries, the number of detail pages scales with
tests × covered files, and each is larger than it needs to be.

gcovr's HTML writer is generally slower than its JSON writer, so this is a better suspect for
"report generation is slow" than the JSON is — the JSON simply happens in the same invocation
and is what people notice in the log.

### 3.4 The union is computed more than once per build

`generate_by_source_coverage` is called from two places:

- `CollateCoverageIndexAction.__call__` — once per sconscript index, over that sconscript's
  final directory.
- `CoverageIndexBuilder.on_progress` at `sconstruct_end` — once per toolchain, over the
  collated destination.

Both load every matching `coverage--*.json` from scratch, so the same JSON is parsed at least
twice per build, and the second pass covers the union of everything.

### 3.5 Smaller costs inside by-source

- `iter_coverage_json_paths` walks the search roots on each pass; there is no index of what was
  already found.
- `resolve_source_path` falls back to `os.walk` over the source roots for every unresolved bare
  filename, with no cache of the walk or its results.
- The line/branch classification is O(lines × branches per line): for each line it filters the
  whole branch map with `[ key for key in branch_map if key[0] == lineno ]`. Grouping branches
  by line number once would make it linear.
- `write_source_detail_pages` renders a Jinja template over the full text of every source file,
  for every toolchain, on every build.
- Coverage artefacts are walked and copied in more than one place
  (`_copy_coverage_artifacts_relative`, plus the Install-free copies added for shared
  destinations).

None of these are likely to dominate on their own, but together they are why by-source felt like
the obvious suspect.

---

## 4. Proposed work

### 4.1 Measure before optimising

Nothing here should be changed without per-phase numbers. Add opt-in timing (debug-level, or a
`--cov-timing` flag) that reports, per test and in total:

- time in `gcov`
- time in `gcovr` (split HTML vs JSON if gcovr allows separate invocations)
- time building the by-source union
- time writing by-source pages
- time in index collation

Then re-run the same A/B on project A and on project B. The output of that step decides
the order of everything below.

### 4.2 Candidate changes, roughly in expected value order

| ID | Change | Expected effect | Risk |
|----|--------|-----------------|------|
| `cov-once-per-test` | Hoist `run_suite` out of the per-source loop so gcovr runs once per test binary | Removes an N× multiplier on multi-source tests; no effect on single-source ones | Low; must confirm all sources' gcov data is present before the single call |
| `cov-version-cache` | Cache the gcovr version on the class instead of re-probing | One less process per report | Very low |
| `cov-html-optional` | Make gcovr `--html-details` opt-in, keeping JSON always, and let by-source be the browsing UI | Potentially large: removes tests × files HTML pages | Medium; changes what is in `_artifacts` by default |
| `cov-union-once` | Compute the union once per toolchain per build and share it between the sconscript indexes and the master index | Removes a duplicate full parse | Low |
| `cov-union-incremental` | Cache the union keyed on the JSON files' mtimes and sizes; skip regeneration when unchanged | Large on repeat runs where only some tests reran | Medium; cache invalidation |
| `cov-branch-index` | Group branches by line once instead of scanning the branch map per line | Removes an O(lines × branches) scan | Very low |
| `cov-source-cache` | Cache the `os.walk` used by `resolve_source_path` | Removes repeated tree walks | Very low |
| `cov-parallel-gcovr` | Pass gcovr `-j` where safe | Uses idle cores during report generation | Medium; interacts with SCons `--parallel` |

### 4.3 Explicit non-goal

Do **not** ship a permanent flag to disable by-source. The measurement does not support it, and
a flag that turns off part of the report is a worse answer than making the report cheap. The
temporary `--cov-by-source` existed only to run the experiment above and has been reverted.

---

## 5. Open items

- Run the same A/B on project B and record the numbers here. That project is where the
  original +30 minute observation came from, and it is the one that can still contradict §2.1.
- Check whether project B test binaries are built from multiple sources; if so,
  `cov-once-per-test` is likely the whole story there.
- Establish whether the original 40 → 70 minute change coincided with by-source or with another
  change in the same period. The project A measurement makes the by-source attribution look
  doubtful, so the timeline is worth re-checking before spending effort.

---

## 6. Reference

Key files:

- `cuppa/cpp/run_gcov_coverage.py` — gcov invocation, gcovr invocation, collation, indexes
- `cuppa/cpp/coverage_by_source.py` — JSON/HTML union, by-source entries and pages
- `cuppa/methods/coverage.py` — the `Coverage` method
- `scripts/analyze_coverage.py` in consumer projects — terminal summaries over the reports
