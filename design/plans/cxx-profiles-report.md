# Plan: C++ Profiles violation report (`--cxx-profiles-report`)

- **Status:** proposal
- **Related:** [`ROADMAP.md`](../../ROADMAP.md) — C++ Profiles (`profiles-violation-report`); shipped enablement [`archive/cxx-profiles.md`](../archive/cxx-profiles.md); [`removal-options.md`](removal-options.md) §4.6 Phase 6 artefacts [#135](https://github.com/ja11sop/cuppa/issues/135); test/coverage report patterns (`cuppa/test_report/`, `cuppa/cpp/run_gcov_coverage.py`)
- **Updated:** 2026-08-11
- **Impact:** minor — new opt-in CLI flag and HTML artefacts; no change to default builds

## Why

C++ Profiles enforcement (`--cxx-profiles` + `--cxx-profiles-enforce=`) can emit **thousands**
of diagnostics across a large tree. Pairing with `--cxx-disable-error-limit` surfaces the full
inventory, but the raw compiler stream is hard to triage:

- The same rule fires repeatedly on the same file (template instantiations, included headers).
- Violations span project sources, dependencies, and generated paths.
- Authors need a **classified summary** (rule → affected files → reference counts) before they
  edit code or add `[[profiles::suppress(…)]]` / `[[uninit]]` markers.

Cuppa already ships HTML reports for **tests** and **coverage** under `_artifacts/`, collated at
`sconstruct_end` via `NotifyProgress`. Profiles work should reuse that shape so reports can be
published alongside other build output — without requiring sconscript changes for the first pass
of analysis.

## Goals

1. **Classify** Profiles diagnostics from compiler output into **profile rule ids** (cross-referenced
   to [P4222](https://wg21.link/P4222) and Alliance Clang
   [`ProfilesFramework.rst`](https://github.com/cppalliance/clang/blob/profiles-framework/clang/docs/ProfilesFramework.rst)
   / [`ProfilesFrameworkInternals.rst`](https://github.com/cppalliance/clang/blob/profiles-framework/clang/docs/ProfilesFrameworkInternals.rst)).
2. **Dedupe** repeated identical `(file, line, col, message)` locations while retaining **per-file
   reference counts** and **totals per rule**.
3. Emit an **HTML report** (and machine-readable JSON sibling) styled like existing test/coverage
   indexes — suitable for CI artefacts and local review.
4. Enable analysis **without editing the project source tree** — opt-in CLI only for the first
   slices; optional `env.CxxProfilesReport()` method later once findings justify sconscript wiring.
5. Record generated paths in a **`.cuppa-reports` manifest** so `--clean` / `--remove-builds` can
   remove report files when invoked with matching report flags (until Phase 6 artefact removal is
   richer).

## Non-goals (initial slices)

- Fixing violations, rewriting sources, or auto-inserting suppressions.
- Session-wide `--cxx-profiles-require=` / `--cxx-profiles-suppress=` (see
  [`archive/cxx-profiles.md`](../archive/cxx-profiles.md) §2.6).
- Parallel-build-safe capture (document **serial builds only** for v1; scoped stack — see §Capture).
- GCC Profiles diagnostics (Clang Alliance fork first; parser should fail closed on unknown shapes).
- Replacing compiler exit status — a Profiles inventory build is still expected to **fail** when
  violations exist unless the project explicitly treats the run as report-only (future knob).

## Principle: analyse before you edit

Profiles adoption is exploratory: teams run enforce on an existing tree, review the inventory, then
decide what to fix, mark `[[uninit]]`, or suppress locally. Requiring `env.CxxProfilesReport()` in
every sconscript before the first inventory would block that workflow.

**Settled:** the first shipped surface is a **CLI flag** registered with other `--cxx-*` options.
It activates capture + collation whenever Profiles are enabled (or when enforce flags are present —
exact gate in §Settled behaviour). Projects opt in per invocation:

```text
cuppa -D --dbg --cxx-profiles --cxx-profiles-enforce=std::init \
  --cxx-disable-error-limit --cxx-profiles-report
```

An **`env.CxxProfilesReport(destination=…)`** method remains a **follow-on** (slice E): same HTML
/ JSON output, integrated with `NotifyProgress.add()` and SCons `Clean()` like
`CollateCoverageIndex` — for teams that want the report on every Profiles CI job without remembering
the CLI flag.

## Reference material

| Source | Use in this plan |
|--------|------------------|
| [P4222R2](https://wg21.link/P4222) | Rationale for `std::init` rules (`[[uninit]]`, `[[ref_to_uninit]]`, static init, ctor obligations) |
| Clang `ProfilesFramework.rst` § *The std::init Profile* | Canonical **rule names** (`uninit_decl`, `static_runtime_init`, …) and diagnostic intent |
| Clang `ProfilesFrameworkInternals.rst` | `ProfileRuleError` diagnostic class; rule ids are opaque strings in suppress attributes |
| Live sample (consumer project) | `profile_output.txt` — ~1310 `std::init` errors; message patterns below |
| Live sample + Progress markers | `profile_output_2.txt` — same run filtered with `grep -E 'under profile\|Progress\('`; shows **scope hierarchy** before the diagnostic block |

### Observed console shape (serial build)

A capture from a real Profiles inventory run (single sconscript, single variant, build failed
during compile) looks like:

```text
Progress( SconstructBegin )
Progress( Begin sconscript: [./matcher/sconscript] )
Progress( Starting variant: [_build/matcher/clang24_profiles_2026_08_07_27/dbg/x86_64/cxx2c] )
… ~1310 lines: path:line:col: error: … under profile 'std::init'
```

Important properties:

1. **Diagnostics are not a session-wide flat list.** Every Profiles line belongs inside the
   **innermost open Progress scope** — here, `./matcher/sconscript` ×
   `_build/matcher/clang24_profiles_2026_08_07_27/dbg/x86_64/cxx2c` × toolchain
   `clang24_profiles_2026_08_07_27`.
2. **`Progress( … )` lines are scope boundaries**, not noise to strip. They correspond to
   `NotifyProgress` events (`sconstruct_begin`, `begin`, `started`, `finished`, `end`,
   `sconstruct_end`) in `cuppa/progress.py`.
3. **Per-compile command lines are siblings, not parents.** SCons also prints `Progress( … )` /
   command lines for individual compile actions; those were omitted from the sample by
   `grep`. Violations from many `.cpp` files can appear **without** another `Starting variant`
   marker — they still share the same variant scope until `Progress( Finished variant: … )`.
4. **Multi-sconscript / multi-variant sessions nest.** A full build (not filtered) interleaves
   blocks: `Begin` → `Starting variant A` → diagnostics → `Finished variant A` →
   `Starting variant B` → … → `End` → next sconscript. Reports and dedupe keys must respect
   that tree, not merge across variants.

### Diagnostic line shape (Clang)

Profiles violations use the normal Clang file diagnostic form with a **`under profile '…'`** suffix:

```text
/path/to/file.hpp:79:25: error: non-local variable 'decimal_places_1' requires constant initialization under profile 'std::init'
```

Parser anchor (illustrative regex):

```text
^(?P<path>…):(?P<line>\d+):(?P<col>\d+): error: (?P<message>…) under profile '(?P<profile>[^']+)'
```

Notes and non-Profiles errors are ignored unless they carry the same suffix (future: optional
“unclassified Profiles” bucket).

### Message → rule id (v1 table)

Clang does **not** always print the rule id in the message text. Cuppa maps **normalised message
patterns** to rule names aligned with `ProfilesFramework.rst`. Extend the table as Alliance Clang
adds diagnostics; unknown messages land in **`_unclassified`** with the raw text preserved.

| Normalised message pattern (illustrative) | Rule id | P4222 / doc anchor |
|-------------------------------------------|---------|-------------------|
| `variable '…' must be initialized or marked '[[uninit]]'` | `uninit_decl` | §4.1 uninitialized variables |
| `non-local variable '…' requires constant initialization` | `static_runtime_init` | static / constant initialization |
| `constructor does not initialize member '…'` | `ctor_uninit_member` | §5.1 constructor obligations |
| `constructor does not initialize base class '…'` | `ctor_uninit_member` | base subobject init |
| `pointer to uninitialized memory must be marked '[[ref_to_uninit]]'` | `ref_to_uninit` | §4.3 references / pointers |
| *(future rows)* `…` | `uninit_read`, `destroy_uninit`, … | add when seen in output |

Normalisation replaces quoted identifiers (`'Foo_'`, `'decimal_places_1'`) with `'…'` before
lookup so template and member name spam collapse to one pattern key.

**Cross-reference column in HTML:** each rule section links to the ProfilesFramework.rst anchor
(stable GitHub URL) and cites P4222 section titles in prose — not a copy of the full rule table.

## Report content

### Progress scope model (settled)

Capture and aggregation treat compiler output as a **scoped stream**, not a linear bag of lines.

```text
sconstruct
  └─ sconscript (e.g. ./matcher/sconscript)
       └─ variant (e.g. _build/…/dbg/x86_64/cxx2c)
            └─ compile/link spawns (many; no extra Progress wrapper per violation)
                 └─ Profiles diagnostics
```

| Scope field | Source | Example from sample |
|-------------|--------|---------------------|
| `sconscript` | `NotifyProgress` `begin` / `started` events | `./matcher/sconscript` |
| `variant_dir` | `NotifyProgress.variant(env)` / `Starting variant: […]` | `_build/matcher/clang24_profiles_2026_08_07_27/dbg/x86_64/cxx2c` |
| `variant_label` | Parsed from variant path (e.g. `dbg`) | `dbg` |
| `toolchain` | Env at scope entry / cuppa session name | `clang24_profiles_2026_08_07_27` |
| `compile_target` | Optional: SCons target node when spawn env is wired (future) | e.g. `foo.cpp` object |

**Scope stack maintenance (v1):** register a `NotifyProgress` callback that pushes/pops on
`begin`, `started`, `finished`, `end`, and clears on `sconstruct_end`. The collector attaches
each parsed diagnostic to **`stack.top()`** at record time.

**Why not infer variant only from `ToolchainProcessor`'s install-time env:** `SpawnedProcessor`
today is constructed from the global `Processor` env (`cuppa/output_processor.py`), not the
per-action construction env passed to `SPAWN`. Serial builds remain correct because Progress
`started`/`finished` bracket all spawns for that variant; parallel builds can interleave spawns
*and* invalidate a single global stack unless each spawn carries its own scope (future slice).

### Aggregation keys

| Level | Key | Metrics |
|-------|-----|---------|
| Session | cuppa invocation (argv fingerprint, timestamp) | Roll-up across sconscripts / variants when multiple scopes ran |
| Scope | `(sconscript, variant_dir, toolchain)` | Total violations, unique files — **primary report partition** |
| Profile | e.g. `std::init` | Subtotals within a scope |
| Rule | e.g. `uninit_decl` | Unique files; sum of per-file reference counts; link to doc |
| File | normalised absolute path | Reference count *N*; list of distinct `(line, col, normalised message)` or collapsed “N identical” |
| Location | `(file, line, col, normalised message)` | Optional drill-down row in per-file detail |

**Deduping:** two diagnostics are the **same location** when all of
`(sconscript, variant_dir, file, line, column, profile, normalised message)` match. The same
`(file, line, message)` in **two variants** is **two locations** — do not merge across scopes.

Increment `reference_count` for duplicates within a scope; optionally retain first seen raw
message for the detail pane.

**Per-file roll-up:** one row per `(scope, rule, file)` with `references = N` even when line
numbers differ (same rule, same file → one row with *N* total refs and expandable line list).

### HTML layout (align with test / coverage)

Follow existing Bootstrap + Jinja patterns (`cuppa/test_report/templates/`, coverage
`coverage-index.html`):

1. **Master index** — `_artifacts/cxx-profiles/cxx-profiles-index.html` (path TBD; see §Artefacts).
   - Summary table: **sconscript × variant × toolchain** rows (when multiple scopes ran).
   - Links into per-scope reports.
2. **Per-scope report** — e.g.
   `cxx-profiles--<sconscript_slug>--<variant_label>--<toolchain_key>.html`.
   - Header: sconscript path, variant dir, toolchain, git branch/revision if available.
   - Sortable table: rule → unique files → total references → link to rule doc.
   - Expandable sections: files under each rule with `file://` or relative `href` to source
     (paths normalised for display; optional `--cxx-profiles-report-root=` to rebase links into
     the project tree).
3. **JSON sibling** — same directory, matching `.json` for scripting / CI gates.
4. **Session roll-up (optional):** when multiple scopes exist, master index totals are the **sum
   of scope reports**, not a dedupe across variants (the same header path violated in `dbg` and
   `rel` counts twice — that is intentional).

Optional later: `--cxx-profiles-report-threshold=` to fail CI when a rule exceeds *N* files (not
slice A).

## Settled CLI (proposal)

| Flag | Meaning |
|------|---------|
| `--cxx-profiles-report` | Enable capture + emit default report paths under artefacts root |
| `--cxx-profiles-report=` *path* | Explicit report **directory** or index **file** stem (directory if ends with `/` or exists as dir) |
| `--cxx-profiles-report-root=` *dir* | Rebase file links in HTML to project-relative paths (default: infer from sconstruct cwd) |

**Activation gate:** flag is a no-op unless Profiles are active for the build
(`--cxx-profiles` or env already has `cxx_profiles` / enforce inject). Otherwise **StopError** with
a message pointing at `--cxx-profiles` — same fail-clear style as other `--cxx-*` flags.

**Recommended pairing (docs only):** `--cxx-disable-error-limit` so the inventory is complete.

No legacy alias. Implementation env key: `cxx_profiles_report` (parallel to `cxx_profiles`).

## Capture architecture

### Scoped stream, not a linear list

The user's `profile_output_2.txt` confirms the design constraint: **classification runs on a
tree shaped by `NotifyProgress`,** matching how cuppa already orders work (see
[`terse-build-output.md`](terse-build-output.md) Phase 2 for the same hierarchy).

```text
  NotifyProgress callbacks                ToolchainProcessor / spawn
  ─────────────────────────               ────────────────────────────
  sconstruct_begin  ──push session
  begin             ──push sconscript
  started           ──push variant          compile spawn 1 ──diagnostics → scope.top
  (targets run)                             compile spawn 2 ──diagnostics → scope.top
  finished          ──pop variant
  end               ──pop sconscript
  sconstruct_end    ──flush reports         (collate per scope + master index)
```

Console `Progress( … )` lines are the user-visible markers for push/pop events. A filtered
transcript remains a valid mental model for serial builds: everything after
`Progress( Starting variant: […] )` and before the matching `Finished variant` belongs to that
scope.

### Where lines are seen

Primary hook: **`ToolchainProcessor`** (`cuppa/output_processor.py`) already classifies compiler
lines per toolchain interpretors and optionally dedupes console output via `ignore_duplicates`.
Extend with an optional **`ProfilesDiagnosticCollector`** registered when
`GetOption('cxx_profiles_report')` is set:

```text
  spawn stdout/stderr
        │
        v
  ToolchainProcessor.__call__
        │
        ├─ existing interpret / colour / console dedupe
        │
        └─ if collector active and line matches Profiles diagnostic regex
               → collector.record( scope_stack.top(), parsed fields )
```

**Scope stack:** maintained by a **`NotifyProgress.register_callback`** handler (same extension
point as `CoverageIndexBuilder.on_progress` and test suites), not by guessing from the
processor's install-time env.

**Why not only scrape log files:** post-hoc grep can reconstruct scope **only for serial builds**
(as the sample demonstrates). In-process capture stays correct for the same reason and avoids
requiring users to pipe through `grep`.

### Serial builds (v1)

When actions for variant *A* complete before variant *B* starts, the Progress stack and stdout
order agree — as in `profile_output_2.txt` (one `Starting variant`, then all diagnostics).

v1 docs state:

> Use `--cxx-profiles-report` without `--parallel` (or `-j1`) so Progress markers and compiler
> output stay nested.

**Partial failure:** if the build stops mid-variant (no `Finished variant`), diagnostics recorded
under that scope are still flushed; the HTML banner marks the scope **incomplete**.

### Parallel builds (explicit non-goal for v1)

**Parallel `-j` interleaves spawn output** from different variants (and sconscripts). A single
global scope stack then mis-attributes lines unless each `SPAWN` passes its action env into the
collector. Do not silently merge interleaved output into one scope.

Future slice: attach `(sconscript, variant_dir, target)` to `SpawnedProcessor` from the
per-action `env` argument in `posix_spawn` / `windows_spawn` (ties to terse-output spawn hooks).

### End-of-build collation

Mirror **`ReportIndexBuilder`** / **`CollateCoverageIndex`**:

```text
NotifyProgress.register_callback( None, CxxProfilesReportBuilder.on_progress )
  → on sconstruct_end: render HTML + JSON, append .cuppa-reports manifest entry
```

If the build **aborts early**, still flush partial report when `--cxx-profiles-report` was set
(configurable; default: write partial with banner).

## `.cuppa-reports` manifest (interim cleanup)

Until [`removal-options.md`](removal-options.md) §4.6 lands (`--remove-artefacts`,
`artefact_roots`, graph discovery), CLI-only reports need a **project-local manifest** so cleans
can find files not registered as SCons targets.

**Location:** `<project_root>/.cuppa-reports` (gitignored by convention; document in Antora).

**Entry shape (JSON lines, one object per report run):**

```json
{
  "kind": "cxx-profiles",
  "created": "2026-08-11T00:07:00Z",
  "invocation_key": "sha256:…",
  "argv": ["cuppa", "-D", "--dbg", "…"],
  "scopes": [
    {
      "sconscript": "./matcher/sconscript",
      "variant_dir": "_build/matcher/clang24_profiles_2026_08_07_27/dbg/x86_64/cxx2c",
      "variant_label": "dbg",
      "toolchain": "clang24_profiles_2026_08_07_27",
      "paths": [
        "_artifacts/cxx-profiles/cxx-profiles--matcher--dbg--clang24_profiles….html",
        "_artifacts/cxx-profiles/cxx-profiles--matcher--dbg--clang24_profiles….json"
      ]
    }
  ],
  "paths": [
    "_artifacts/cxx-profiles/cxx-profiles-index.html"
  ]
}
```

| Field | Purpose |
|-------|---------|
| `invocation_key` | Hash of normalised argv + cwd + key options (`cxx_profiles_report` destination) |
| `paths` | Files/dirs to delete on matched clean |
| `kind` | Extensible for other CLI reports (future terse summaries, etc.) |

**Removal behaviour (proposal):**

- When `--clean` or `--remove-builds` runs **and** the same `--cxx-profiles-report` destination
  (or default) is present on the command line, remove manifest entries whose `invocation_key`
  matches and delete listed `paths`.
- `--remove-builds` alone does **not** delete reports (artefacts live outside `_build/`).
- Document as **interim** — superseded by Phase 6 artefact roots + optional graph discovery.

**Honest limitation:** manifest matching is hacky; wrong argv → stale files remain. Phase 6 should
subsume this for declared `_artifacts/` trees.

## Artefacts layout and Phase 6 alignment

Default output tree (matches today’s coverage/test convention):

```text
_artifacts/cxx-profiles/
  cxx-profiles-index.html
  cxx-profiles--<sconscript_slug>--<variant>--<tc>.html
  cxx-profiles--<sconscript_slug>--<variant>--<tc>.json
```

[`removal-options.md`](removal-options.md) §4.6 sketches **`artefact_roots`** / `--remove-artefacts`
and possibly **`--set-artefacts-folder`**. This plan **does not invent** the final Phase 6 flag
names; it assumes:

1. A future **`--set-artefacts-folder=`** (or `artefact_roots` in `sconstruct`) redirects
   `_artifacts/` (or subfolders) for all cuppa-generated reports.
2. **`--cxx-profiles-report`** respects that root when set.
3. Built-in report types (test, coverage, cxx-profiles) register under a shared
   **`cuppa.reports`** registry so artefact listing can mention them consistently.

Until Phase 6 ships, hard-code `_artifacts/cxx-profiles/` as coverage does for `_artifacts/coverage/`.

## Built-in “reports” registration (sketch)

Silently register report producers when cuppa loads (no sconscript edit):

| Report | Trigger today | Trigger after this plan |
|--------|---------------|-------------------------|
| Test HTML | `env.GenerateHtmlTestReport` + collate | unchanged |
| Coverage | `--cov --test` + collate methods | unchanged |
| C++ Profiles | — | `--cxx-profiles-report` |

Registry records: `kind`, default subdir, CLI flag, manifest kind string. Enables future
`--list-reports` / doc samples in [`colourised-doc-samples.md`](colourised-doc-samples.md).

## Work slices

| Slice | Deliverable | Notes |
|-------|-------------|-------|
| **A — Parser + unit tests** | `cuppa/cpp/cxx_profiles_report.py` — parse lines, normalise, classify; `ProfilesScope` type | Fixture strings from samples; scope-aware dedupe keys |
| **B — Scope stack + collector** | `NotifyProgress` callback + `ToolchainProcessor` hook | Stack push/pop on progress events; unit tests simulate `profile_output_2.txt` event sequence |
| **C — HTML + JSON** | Jinja templates + `CxxProfilesReportBuilder` at `sconstruct_end` | Per-scope pages + master index; incomplete scope banner |
| **D — Manifest + clean** | Append `.cuppa-reports`; delete on matched `--clean` / `--remove-builds` | Integration test with tmp project root |
| **E — Method (optional)** | `env.CxxProfilesReport()` + `CollateCxxProfilesReportIndex` | `NotifyProgress.add`, SCons `Clean()` on outputs |
| **F — Parallel-safe spawn scope** | Per-action env on `SpawnedProcessor` | Lift serial-only restriction |
| **G — Phase 6 hook** | Honour `artefact_roots` / `--set-artefacts-folder` when #135 lands | Delete manifest hack or narrow to unmatched paths only |

Target cycle: **1.8.0** for slices A–D; E–G can spill to 1.9.0.

## Refusal rules

| Request | Response |
|---------|----------|
| Auto-fix sources from the report | Out of scope — report is read-only |
| `--cxx-profiles-report` without Profiles enabled | StopError |
| Invent rule ids not in Clang docs | Use `_unclassified`; file issue to extend table |
| Parallel `-j` accuracy guarantee in v1 | Document limitation; do not silently merge wrong scopes |
| MSVC Profiles diagnostics in v1 | StopError or empty report with notice until interpretor exists |

## Testing

| Layer | Cases |
|-------|-------|
| Unit | Parser regex; normalisation; pattern→rule map; **scope-aware** dedupe counts; JSON schema |
| Unit | Progress stack push/pop; replay `profile_output_2.txt` scope sequence |
| Unit | Manifest read/write; `invocation_key` stability |
| Integration | Tiny sconscript + Alliance Clang fixture (or mocked collector feed) produces HTML + JSON |
| Integration | `--clean` with matching flag removes manifest paths |
| Docs | Antora page section under [`cxx-profiles.adoc`](../../docs/modules/ROOT/pages/cxx-profiles.adoc); CHANGELOG under open `[1.8.0]` |

## Documentation updates (when implemented)

- Antora: workflow “inventory before fix”, flag table, serial-build note, sample HTML screenshot
  (optional via colourised-doc-samples pipeline).
- [`archive/cxx-profiles.md`](../archive/cxx-profiles.md): link this plan in follow-ons (already
  cites dedupe/report in §2.3).
- AGENTS.md consumer tip: `--cxx-profiles-report` one-liner next to coverage commands.

## Progress snapshot

| Slice | Status |
|-------|--------|
| Plan | **This document** |
| A — Parser | Not started |
| B — Scope stack + collector | Not started |
| C — HTML/JSON | Not started |
| D — Manifest | Not started |
| E — Method | Deferred |
| F — Parallel spawn scope | Deferred |
| G — Phase 6 | Blocked on #135 |

## Open questions (resolve in first PR)

1. **Partial builds:** if only one scope ran, omit master index or still write a single-scope index?
2. **Dependency paths:** default HTML links — absolute path vs rebased under `--cxx-profiles-report-root=`?
3. **Report-only exit code:** should `--cxx-profiles-report` imply `-k` / allow success for inventory
   runs? Default **no** (stay honest); optional `--cxx-profiles-report-allow-errors` if demanded.
4. **Cross-variant dedupe:** session roll-up never merges identical file paths across variants —
   confirm that remains the product choice when comparing `dbg` vs `rel` inventories.
