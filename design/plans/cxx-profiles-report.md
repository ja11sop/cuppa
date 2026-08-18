# Plan: C++ Profiles violation report (`--cxx-profiles-report`)

- **Status:** in progress
- **Related:** [`ROADMAP.md`](../../ROADMAP.md) — C++ Profiles (`profiles-violation-report`); umbrella [#184](https://github.com/ja11sop/cuppa/issues/184) (closed); semantics [#199](https://github.com/ja11sop/cuppa/issues/199) shipped [#203](https://github.com/ja11sop/cuppa/pull/203); scope filter follow-on [§Collate index scope filter](#prof-report-scope-filter-slice); shipped enablement [`archive/cxx-profiles.md`](../archive/cxx-profiles.md); [`removal-options.md`](removal-options.md) §4.6 Phase 6 artefacts [#135](https://github.com/ja11sop/cuppa/issues/135); test/coverage report patterns (`cuppa/test_report/`, `cuppa/cpp/run_gcov_coverage.py`)
- **Updated:** 2026-08-19
- **Impact:** minor — new opt-in CLI flag and HTML artefacts; no change to default builds

## Why

C++ Profiles enforcement (`--cxx-profiles` + `--cxx-profiles-enforce=`) can emit **thousands**
of diagnostics across a large tree. Profiles inventory mode implies unlimited per-TU diagnostics
on Clang/GCC (see [§Implied diagnostic error limit](#prof-report-error-limit)); for enforce-only
sweeps without a report, pass `--cxx-disable-error-limit` or `--cxx-error-limit=0`. The raw
compiler stream is still hard to triage:

- The same rule fires repeatedly on the same file (template instantiations, included headers).
- Violations span project sources, dependencies, and generated paths.
- Authors need a **classified summary** (rule → affected files → reference counts) before they
  edit code or add `[[profiles::suppress(…)]]` / `[[uninit]]` markers.

Cuppa already ships HTML reports for **tests** and **coverage** under `_artefacts/` (legacy
`_artifacts/` when that folder already exists), collated at
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
3. Emit an **HTML report** (and machine-readable JSON sibling) with **Coverage-like tabs** — an
   **Overview** of violations in codebase context, **By rule**, **By file**, and session roll-up
   views grouped by profile — suitable for CI artefacts, local review, and external sharing
   (e.g. WG21 papers).
4. Enable analysis **without editing the project source tree** — opt-in CLI for early slices; slice **E**
   adds **`env.CollateCxxProfilesIndex()`** for sconscript-declared session indexes (merged
   [#198](https://github.com/ja11sop/cuppa/pull/198)).
5. Record generated paths in a **`.cuppa-reports` manifest** so `--clean` / `--remove-builds` can
   remove report files when invoked with matching report flags (until Phase 6 artefact removal is
   richer).

## Non-goals (initial slices)

- Fixing violations, rewriting sources, or auto-inserting suppressions.
- Session-wide `--cxx-profiles-require=` / `--cxx-profiles-suppress=` (see
  [`archive/cxx-profiles.md`](../archive/cxx-profiles.md) §2.6).
- Parallel-build-safe capture without per-spawn scope (deferring spawn wiring makes a later retrofit invasive — see §Spawn-attributed scope).
- GCC Profiles diagnostics (Clang Alliance fork first; parser should fail closed on unknown shapes).
- Replacing compiler exit status — a Profiles inventory build is still expected to **fail** when
  violations exist unless the project explicitly treats the run as report-only (future knob).

## Principle: analyse before you edit

Profiles adoption is exploratory: teams run enforce on an existing tree, review the inventory, then
decide what to fix, mark `[[uninit]]`, or suppress locally. Requiring
`env.CollateCxxProfilesIndex()` in every sconscript before the first inventory would block that
workflow.

**Settled:** the first shipped surface is a **CLI flag** registered with other `--cxx-*` options.
It activates capture + collation whenever Profiles are enabled (or when enforce flags are present —
exact gate in §Settled behaviour). Projects opt in per invocation:

```text
cuppa -D --dbg --cxx-profiles --cxx-profiles-enforce=std::init \
  --cxx-disable-error-limit --cxx-profiles-report
```

An **`env.CollateCxxProfilesIndex(destination=…)`** method (slice **E**) provides the same
HTML / JSON session index, integrated with `NotifyProgress.add()` and SCons `Clean()` like
`CollateCoverageIndex` — for teams that want the report on every Profiles CI job without
remembering the CLI flag. See [§Method naming](#prof-report-method-naming). The shorter name
**`env.CxxProfilesReport()`** is **reserved** for a possible future **per-scope** report (one
`(sconscript × variant × toolchain)` page), mirroring `GenerateHtmlTestReport` →
`CollateTestReportIndex`.

## Reference material

| Source | Use in this plan |
|--------|------------------|
| [P4222R2](https://wg21.link/P4222) | Rationale for `std::init` rules (`[[uninit]]`, `[[ref_to_uninit]]`, static init, ctor obligations) |
| Clang `ProfilesFramework.rst` § *The std::init Profile* | Canonical **rule names** (`uninit_decl`, `static_runtime_init`, …) and diagnostic intent |
| Clang `ProfilesFrameworkInternals.rst` | `ProfileRuleError` diagnostic class; rule ids are opaque strings in suppress attributes |
| Live sample (consumer project) | `profile_output.txt` — ~1310 `std::init` errors; message patterns below |
| Live sample + Progress markers | `profile_output_2.txt` — serial `dbg` run; scope hierarchy before diagnostic block |
| Multi-variant invocation sample | `profile_output_3.txt` — `cuppa --dbg --rel …` (build failed during first variant; only `dbg` scope appears in capture — illustrates partial multi-variant session) |

### Observed console shape (serial build)

A capture from a real Profiles inventory run (single sconscript, single variant, build failed
during compile) looks like:

```text
Progress( SconstructBegin )
Progress( Begin sconscript: [./widget/sconscript] )
Progress( Starting variant: [_build/widget/clang24_profiles/dbg/x86_64/cxx2c] )
… ~1310 lines: path:line:col: error: … under profile 'std::init'
```

Important properties:

1. **Diagnostics are not a session-wide flat list.** Every Profiles line belongs inside the
   **innermost open Progress scope** — here, `./widget/sconscript` ×
   `_build/widget/clang24_profiles/dbg/x86_64/cxx2c` × toolchain
   `clang24_profiles`.
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
  └─ sconscript (e.g. ./widget/sconscript)
       └─ variant (e.g. _build/…/dbg/x86_64/cxx2c)
            └─ compile/link spawns (many; no extra Progress wrapper per violation)
                 └─ Profiles diagnostics
```

| Scope field | Source | Example from sample |
|-------------|--------|---------------------|
| `sconscript` | `NotifyProgress` `begin` / `started` events | `./widget/sconscript` |
| `variant_dir` | `NotifyProgress.variant(env)` / `Starting variant: […]` | `_build/widget/clang24_profiles/dbg/x86_64/cxx2c` |
| `variant_label` | Parsed from variant path (e.g. `dbg`) | `dbg` |
| `toolchain` | Env at scope entry / cuppa session name | `clang24_profiles` |
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

Follow existing Bootstrap + Jinja patterns (`cuppa/test_report/templates/`,
`cuppa/cpp/templates/coverage_index.html`). Coverage already splits **By sconscript** vs **By source
file** tabs on the master index; Profiles reporting needs a similar **multi-view** model, grouped
first by **language profile** (`std::init` today; `std::type`, … as compilers add them).

#### Navigation levels

```text
cxx-profiles-index.html          ← session master (all scopes that ran)
  ├─ scope summary rows          ← sconscript × variant × toolchain (incomplete scopes flagged)
  └─ per-scope detail pages      ← cxx-profiles--<script>--<variant>--<tc>.html
       └─ tabs (see below)       ← filtered to that scope’s captured diagnostics
```

When the invocation builds multiple variants (e.g. `--dbg --rel`) and more than one scope
completes or partially runs, the master index lists **each scope separately** — as in
`profile_output_3.txt`, a failed `dbg` pass may be the only scope captured even though `rel` was
requested.

#### Tabs on master index and per-scope pages

| Tab | Primary sort (default) | Expandable rows | Purpose |
|-----|------------------------|-----------------|---------|
| **Overview** | Fixed layout — headline metrics and tables | Per-profile **full rule matrix** (including zero counts); **Build inventory load** | “How bad is it relative to the codebase?” — shareable executive summary ([§Context summary](#prof-report-context-summary)) |
| **Violations By-Rule** | `(profile, rule_id)` — references / violations | File detail subtable (**Union Refs**, **Peak Refs**, **Build Refs**) | Session roll-up by rule; multi-build **common + delta** notation |
| **Violations By-File** | Source file | Rule detail subtable (symmetric to By-Rule) | Session roll-up by file |
| **Violations By-Build** | Build id (`dbg1`, …) | **By-Rule** / **By-File** pair per build (all sconscripts) | One compile inventory row at a time — **Profile** column; **Build Refs** only |
| **Violations By-Sconscript** | Sconscript × variant rows | Links to per-scope detail pages | Navigate multi-variant / multi-sconscript sessions |

The master index **Overview** tab is the **default landing view** when context capture is enabled.
Per-scope detail pages use the same **By-Rule** / **By-File** layout as **Violations By-Build**
detail (**Profile** column, **Build Refs**, no **Peak Refs**) — not a separate per-profile tab
pair per scope.

**Entry row shape (both views):** display path (linked — see §Source links), **reference count**,
**unique locations** (distinct line/col after dedupe), optional **affected scopes** badge when
viewing roll-up. Expanded detail lists `(line, col)` anchors and raw message (first seen).

**Sorting:** ship with the defaults above baked into Jinja iteration order. Add **client-side
re-sort** (column header clicks or a small `<select>` — same Bootstrap/JS approach as other cuppa
reports) for at least: references desc/asc, path A–Z, rule id A–Z. Server-side `--cxx-profiles-report-sort=` is **not** required for v1 if the HTML toggles suffice.

#### Master index summary table

- Rows: `(sconscript, variant_label, variant_dir, toolchain, profile names seen, total refs, unique files, complete?)`
- Links into per-scope detail pages (each page opens on **By rule** tab by default).
- When only one scope exists, master index may redirect or embed the detail page (open question §8).

#### JSON sibling (`cxx-profiles-index.json`)

**File:** `{artifacts_root}/cxx-profiles/cxx-profiles-index.json` — one **session-level** document.
Per-scope detail is **HTML only** (`{report_stem}.html`); the `.cuppa-reports` manifest lists those
HTML paths under `scopes[].paths`, not separate per-scope JSON files.

##### Versioned envelope (schema v1)

Writers emit `schema_version: 1` (`cuppa/cpp/profiles_report/report_json.py`,
`REPORT_JSON_SCHEMA_VERSION`). This is the **first shipped** report JSON format — there is no
earlier public envelope to migrate from. Loaders also accept legacy bare `{ scopes, rollup }`
objects (pre-envelope captures used in tests).

```json
{
  "schema_version": 1,
  "generated_at": "2026-08-14T00:35:00+00:00",
  "metadata": { },
  "summary": { },
  "context": { },
  "locations": [ ],
  "report": {
    "scopes": [ ],
    "rollup": { "rules": [ ], "files": [ ] }
  }
}
```

| Top-level field | Purpose |
|-----------------|---------|
| `schema_version` | Report JSON format version (writers emit `1`) |
| `generated_at` | UTC ISO-8601 timestamp |
| `metadata` | Session fields needed to re-render HTML without a rebuild |
| `summary` | Compact violation counts for CI/agents — no nested tree walk |
| `context` | Optional — codebase-relative metrics and full per-profile rule matrix ([§Context summary](#prof-report-context-summary)); omit in legacy loads |
| `locations` | Flat, sorted violation rows for machine analysis |
| `report` | Nested view model consumed by Jinja templates |

**`metadata`:** `sconstruct_dir`, `report_project`, `link_style`, `cxx_profiles_report_root`, VCS
header fields (`report_uri`, `report_branch`, `report_revision`), `profiles_enforce`,
`variant_labels`, `incomplete_scopes`, and `partial` (true when any scope did not finish its
variant).

**`summary`:** `total_references`, `unique_violation_count`, `unique_rule_count`,
`unique_locations`, `scope_count`, and `by_rule` (map of `rule_id` → reference count). Stays
small for CI gates; **`context`** carries the richer narrative metrics (see below).

**`locations[]` row:** `location_key` (SHA-256 of the scope-aware dedupe tuple from
`location_dedupe_key()`), scope fields (`sconscript`, `variant_dir`, `variant_label`, `toolchain`),
`profile`, `rule_id`, `path`, `line`, `column`, `references`, `normalised_message`, `message`.

##### Nested `report` model

Same directory as the HTML index. Pre-sorted view models for HTML plus machine-readable roll-up:

```text
scopes[] → profiles[] → rules[] → { rule_id, total_references, files[] }
scopes[] → profiles[] → files[]  → { path, total_references, rules[] }
rollup → { rules[], files[] }   // cross-profile, cross-scope union with scope attribution
```

Rule entries under `scopes[].profiles[].rules[]`, `rollup.rules[]`, and nested
**`files[].rules[]`** include **`doc_href`** (published Antora std::init rule pages).

**Roll-up dedupe policy (settled):** union **adds reference counts** across scopes for the same
`(profile, rule, normalised_path, line, col, message)`. The same header violated in `dbg` and
`rel` contributes **twice** to roll-up totals unless the user filters to one scope — mirrors
coverage union semantics (counts reflect all runs, not “unique issues across variants”).

##### Template iteration / JSON regen

For HTML template work without recompiling, prefer **JSON regen** over capture replay:

```text
python -m scripts.regenerate_profiles_report \
  --from-json _artefacts/cxx-profiles/cxx-profiles-index.json
```

Omit `--sconstruct-dir` to take `sconstruct_dir`, `link_style`, and related fields from JSON
``metadata`` (`env_from_report_metadata` in `report_json.py`).

| Flag | Meaning |
|------|---------|
| `--skip-source-pages` | Omit `by-source/` marked-up pages (sources must exist on disk otherwise) |
| `--write-json` | Rewrite `cxx-profiles-index.json` at the current schema after re-render |

When `locations[]` is present, regen rebuilds inventory from the flat array (faster and more
 reliable than walking nested `report`). Otherwise it falls back to nested `report` reconstruction.
Capture replay (`capture.txt` without `--from-json`) remains a legacy path — parallel or
interleaved `tee` output can mis-attribute scope; use only when no JSON exists.

**Regen script CLI scoping (settled):** flags on `scripts/regenerate_profiles_report.py` live in
that script's `argparse` namespace, not cuppa `AddOption`. Reuse cuppa vocabulary where values map
to the same `env` keys (`--artifacts-root`, `--sconstruct-dir`). Profiles-specific behaviour uses
descriptive names (`--skip-source-pages`, `--write-json`); mode switch `--from-json` is
script-local (mutually exclusive input interpretation, not a global cuppa flag).

Optional later: `--cxx-profiles-report-threshold=` to fail CI when a rule exceeds *N* files (not
slice A).

### Source links (`link_style`)

Shared module `cuppa/reports/link_style.py` (shipped with slice C):

- `REPORT_LINK_STYLES` — `local`, `gitlab`, `github`
- `resolve_report_link_style(env, …)` — precedence: per-report CLI → `--reports-link-style=` →
  method kwarg → `local`
- `initialise_report_linking(env, link_style)` — blob base URI (GitHub `/blob/`, GitLab `/-/blob/`)
- `source_file_href(…)` — repo-relative path + `#L{line}` for test and Profiles tables

Session override: **`--reports-link-style=`** applies to every report kind the invocation emits
(test HTML via `GenerateHtmlTestReport`, Profiles via `--cxx-profiles-report`). Profiles-only
**`--cxx-profiles-report-link-style=`** overrides the session flag for Profiles output and manifest
clean matching.

Test reports previously accepted `link_style=` only as a method kwarg; the session flag overrides
the method default when CI publishes artefacts.

| `link_style` | Href shape | When to use |
|--------------|------------|---------------|
| `local` (default) | `file://{sconstruct_dir}/{relpath}#L{line}` | Developer machine; opens editor/IDE handler |
| `gitlab` | `{remote}/-/blob/{branch}/{relpath}#L{line}` | GitLab CI published artefacts (project VCS only) |
| `github` | `{remote}/blob/{branch}/{relpath}#L{line}` | GitHub Actions published artefacts (project VCS only) |
| `remote` | Per path: infer GitHub vs GitLab from that file's repo URL | Mixed project + dependency hosts ([#216](https://github.com/ja11sop/cuppa/issues/216)) |

Source-page **link text** matches the active style: local paths for `local`, full blob URL for
`github` / `gitlab` (same string as the href, without the line fragment).

**Path rebasing:** map absolute diagnostic paths (including dependency trees under
`~/_cuppa/_download/…`) to a **repo-relative** path when under `sconstruct_dir` or
`--cxx-profiles-report-root=`; otherwise show absolute path with `local` link only (no remote blob —
same caveat as test report: *“Might need VCS detection per file”* for dependency sources).

**Dependency display paths (shipped heuristic; metadata gap):** for location-dependency sources,
the by-file / by-rule tables use a **two-line** title:

1. **Repo line** — `host/org/repo@branch` (muted), from `describe_tree_path` / git short name.
2. **Local line** — path under the dependency checkout on one line: the configured **include root**
   prefix (muted, e.g. `include/`) immediately followed by the **#include-relative** tail (bold,
   link-coloured when href is set), e.g. `include/widget/common_types/number.hpp` reads as
   `include/` + `widget/common_types/number.hpp` on a single second row.

Today slice D infers the include root as the **first path segment** when it matches a known folder
name (`include`, `inc`, `src`, …). That matches the common `location_dependency(..., include="include")`
case but is **wrong** when `sys_include` / `include` spans multiple segments (e.g.
`include/widget/extra` on the compile line — the muted prefix should be `include/widget/`, not
`include/` alone). **Follow-up:** persist the resolved include/sys-include directory(s) per dependency tree
(e.g. in `.cuppa-inventory/` entry JSON or a small sidecar written at `BuildWith` time) and read
that in `source_pages._split_location_include_remainder()` instead of the first-segment heuristic.
Until then, document the limitation in report help text if users hit mis-split paths.

**CLI / method surface (settled for v1 CLI):**

| Flag / arg | Meaning |
|------------|---------|
| `--cxx-profiles-report-link-style=local` | Default |
| `--cxx-profiles-report-link-style=gitlab` | Blob links from `vcs_info_from_location` |
| `--cxx-profiles-report-link-style=github` | GitHub blob links (add alongside test report) |

Slice **E** (`env.CollateCxxProfilesIndex(…, link_style=…)`) mirrors `CollateCoverageIndex` /
`CollateTestReportIndex` kwargs (destination, link_style).
Collated master index passes `link_style="raw"` VCS metadata into the template header (same as test
suite index).

**Known limitation (v1 `github` / `gitlab`):** one blob base from the **project** VCS applies to
every href. Dependency sources get human-readable `host/org/repo@branch/…` display paths but remote
hrefs still use the project repository until the follow-up slice below.

### Follow-up: per-repo `remote` link style (minor release)

**Status:** in progress — [#216](https://github.com/ja11sop/cuppa/issues/216); PR [#219](https://github.com/ja11sop/cuppa/pull/219); target **1.9.0**.

Add **`remote`** to `REPORT_LINK_STYLES` (and CLI choices). Keep **`github`** / **`gitlab`** as
**force-all overrides** when the whole tree lives on one host.

| `link_style` | Href shape | When to use |
|--------------|------------|---------------|
| `remote` (new) | Per path: detect provider from host (GitHub, GitLab, Bitbucket, Gitea/Forgejo/Codeberg, Azure DevOps); project files → project VCS; dependency files → `enrich_described` / `source_url` + qualifier | Mixed hosts; configurable host suffix lists; unmapped hosts show linked repo URL + plain path suffix with optional GH/GL/BB/GT/AD hint links |
| `github` / `gitlab` | Single blob base from project VCS for every path | Monorepo or single-host CI publish |

**Implementation sketch:**

- Shared provider detection + blob URL builders in `cuppa/reports/link_style.py`.
- `resolve_path_remote_link(path, env) → RemoteLinkResolution` — reuse `describe_tree_path` /
  `enrich_described` / `remote_href_display_path()` (shipped in
  [#214](https://github.com/ja11sop/cuppa/pull/214) for project + working-dir paths).
- `source_link_display()` — mapped providers emit full blob hrefs; unmapped hosts emit partial
  HTML (`<a href="repo">repo</a>/path#Ln` + optional hint links).
- CLI / `configure.conf`: `--reports-{github,gitlab,bitbucket,gitea,azure_devops}-hosts=`,
  `--reports-remote-provider-hints` / `--no-reports-remote-provider-hints`.
- Default stays **`local`**; document **`remote`** for mixed-dependency Profiles runs in Antora +
  `cli-reference.adoc`.

**Settled:** name is **`remote`** (not `repo`) — contrasts with `local` and avoids confusion with
“repository” as a noun.

## Settled CLI (proposal)

| Flag | Meaning |
|------|---------|
| `--cxx-profiles-report` | Enable capture + emit default report paths under artefacts root |
| `--cxx-profiles-report=` *path* | Explicit report **directory** or index **file** stem (directory if ends with `/` or exists as dir) |
| `--cxx-profiles-report-root=` *dir* | Rebase project-owned paths for display and remote links (default: infer from sconstruct cwd) |
| `--cxx-profiles-report-link-style=` *local\|gitlab\|github* | Profiles-only source link override (overrides `--reports-link-style=`; see §Source links) |
| `--reports-link-style=` *local\|gitlab\|github* | Session-wide source links for all HTML reports this run emits (test, Profiles, …) |

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
               → collector.record( spawn_scope or stack_scope, parsed fields )
```

**Scope stack:** maintained by a **`NotifyProgress.register_callback`** handler (same extension
point as `CoverageIndexBuilder.on_progress` and test suites), not by guessing from the
processor's install-time env. Spawn scope uses **`NotifyProgress.scope_from_env`** (same
``variant`` / ``sconscript`` rules as Progress markers); per-sconscript ``SPAWN`` rebinding
uses **`NotifyProgress.register_sconscript_env_hook``** so ``construct`` stays feature-agnostic.

**Why not only scrape log files:** post-hoc grep can reconstruct scope **only for serial builds**
(as the sample demonstrates). In-process capture stays correct for the same reason and avoids
requiring users to pipe through `grep`.

### Spawn-attributed scope (settled for 1.8.0)

A **Progress scope stack alone is not enough** under `--parallel`: compiler stdout from
concurrent actions interleaves, so lines cannot be assigned from “whatever variant started last”.

**Settled:** capture uses **two mechanisms together**:

| Mechanism | Role | When it applies |
|-----------|------|-----------------|
| **`NotifyProgress` stack** | Bookkeeping for scope boundaries, `complete` flags, flush at `sconstruct_end` | Always |
| **Per-spawn scope on `SpawnedProcessor`** | Authoritative `(sconscript, variant_dir, toolchain, …)` for each diagnostic line | Every spawn when `--cxx-profiles-report` is active |

Implement spawn attribution **in the same workstream as the collector** (former “slice F”) —
retrofitting after HTML/manifest land would touch `posix_spawn` / `windows_spawn` again and risk
reports that silently mis-attribute under `-j`.

#### Per-spawn wiring (proposal)

Today `Processor.posix_spawn` / `windows_spawn` construct `SpawnedProcessor( self.scons_env )`
using the **install-time** env, not the per-action construction `env` SCons passes to `SPAWN`.

```text
  posix_spawn( …, action_env )
        │
        ├─ derive ProfilesScope from action_env:
        │     build_dir → variant_dir (NotifyProgress.variant pattern)
        │     sconscript_file, toolchain name from cuppa env snapshot
        │
        v
  SpawnedProcessor( install_env, profiles_scope=… )
        │
        └─ ToolchainProcessor line → collector.record( profiles_scope, … )
```

**Thread safety:** each spawn owns its processor instance; the collector aggregates into a
**lock-protected** session store keyed by scope (same pattern as parallel compile processes today
— no shared mutable `SpawnedProcessor` across threads).

**Progress stack:** still push/pop on `begin` / `started` / `finished` / `end` for incomplete-scope
detection and manifest metadata; diagnostics **must not** use `stack.top()` alone when
`profiles_scope` is available on the processor.

**Partial failure:** if the build stops mid-variant (no `Finished variant`), diagnostics already
recorded under that spawn scope are still flushed; HTML/manifest mark the scope **incomplete**.

**Docs:** do **not** tell users to avoid `--parallel` for Profiles reporting in 1.8.0 once slice B
ships; retain an honest note if spawn scope derivation fails for a builder path (log + bucket under
`_unscoped` rather than silent wrong variant).

Optional cross-link: [`terse-build-output.md`](terse-build-output.md) Phase 2 may reuse the same
spawn exit hooks later — Profiles report should not block on terse landing first.

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

**One JSON object per line** — appended once per cuppa invocation that wrote Profiles report
artefacts (at `sconstruct_end`, or on early abort with `partial: true`). The manifest records
**paths to delete** and **matching metadata**; it does **not** embed the diagnostic inventory
(that lives in the per-scope `.json` siblings described in §JSON sibling).

**Entry shape:**

```json
{
  "kind": "cxx-profiles",
  "schema": 1,
  "created": "2026-08-11T00:07:00Z",
  "partial": false,
  "invocation_key": "sha256:…",
  "argv": ["cuppa", "-D", "--dbg", "--rel", "…"],
  "cwd": "/home/user/project/widget",
  "options": {
    "destination": "_artefacts/cxx-profiles",
    "link_style": "local",
    "report_root": null,
    "enforce": ["std::init"],
    "cxx_profiles": true
  },
  "session_paths": [
    "_artefacts/cxx-profiles/cxx-profiles-index.html"
  ],
  "scopes": [
    {
      "sconscript": "./widget/sconscript",
      "variant_dir": "_build/widget/clang24_profiles/dbg/x86_64/cxx2c",
      "variant_label": "dbg",
      "toolchain": "clang24_profiles",
      "complete": false,
      "profiles": ["std::init"],
      "paths": [
        "_artefacts/cxx-profiles/cxx-profiles--widget--dbg--clang24_profiles.html"
      ]
    }
  ]
}
```

| Field | Purpose |
|-------|---------|
| `kind` | `"cxx-profiles"` — extensible for other CLI report types later |
| `schema` | Manifest format version (increment when fields change) |
| `partial` | `true` when the build aborted before `sconstruct_end` or any scope lacks `Finished variant` (see `profile_output_3.txt`) |
| `invocation_key` | Hash of normalised `argv`, `cwd`, and `options` (`destination`, `link_style`, `report_root`, `enforce`) — must match for clean removal |
| `argv` | Echo for human audit; not used alone for matching |
| `cwd` | Project / sconstruct working directory at report time |
| `options` | Report flags that affect output location and link behaviour (see §Settled CLI) |
| `session_paths` | Master index HTML (includes **Roll-up** tab — no separate roll-up file in v1) |
| `scopes[]` | One object per captured Progress scope (sconscript × variant × toolchain) |
| `scopes[].complete` | `false` when diagnostics were captured under `Starting variant` but `Finished variant` never ran |
| `scopes[].profiles` | Profile names seen in that scope (usually one; multi-enforce lists may yield several) |
| `scopes[].paths` | Per-scope detail **HTML** only (`{report_stem}.html`) |

**Paths to delete:** union of `session_paths` and every `scopes[].paths` entry (implementation may
also store a denormalised `all_paths[]` for convenience — not required in the schema).

**Relationship to report JSON:** violation data lives in session-level
`cxx-profiles-index.json` (see §JSON sibling). The manifest records **paths to delete**
(`session_paths`, `scopes[].paths`, optional `all_paths[]`); it does not embed the inventory.

<a id="json-follow-ups"></a>

**JSON follow-ups (not blocking slice C merge):**

| Gap | Notes |
|-----|-------|
| CI threshold flag | `--cxx-profiles-report-threshold=` deferred |
| **Anonymized sharing** | See [§Anonymized report sharing](#prof-report-anonymize) — after slice H |
| **Context summary** | See [§Context summary](#prof-report-context-summary) — slice H on [#196](https://github.com/ja11sop/cuppa/pull/196) |

<a id="prof-report-artefacts-min"></a>

## Report artefacts catalogue (F-min)

**Id:** `prof-report-artefacts-min` · **Status:** **shipped** — merged [#198](https://github.com/ja11sop/cuppa/pull/198) (umbrella [#184](https://github.com/ja11sop/cuppa/issues/184), closed)

| Piece | Behaviour |
|-------|-----------|
| Registry | `cuppa/reports/registry.py` — static rows for Profiles, coverage, test |
| Discovery | `--list-available-reports` (+ `--list-format=json`) — judgement tree with `{artefacts_root}` / `{build_root}` resolved in-tree; report kinds × toolchain capability on this system |
| Artefacts root | British `--artefacts-root` / `env.artefacts_root`; US `--artifacts-root` / `env.artifacts_root` aliases; default `_artefacts` |
| Clean | Profiles still use `.cuppa-reports` manifest until #135 Phase 6 |

**Naming:** `--list-available-reports` — crosses the static report registry with
``cuppa_env['toolchains']`` (same inventory as ``--list-toolchains``). Lists **which toolchains on
this system can produce each kind**; does not scan `_artefacts/` for existing index files (Phase 6).

**Deferred to #135:** `artefact_roots`, `--remove-artefacts`, on-disk report inventory, registry-driven wipe of whole trees.

<a id="prof-report-method"></a>

## Scons method (slice E)

**Id:** `prof-report-method` · **Status:** **shipped** — `env.CollateCxxProfilesIndex()` merged [#198](https://github.com/ja11sop/cuppa/pull/198) (umbrella [#184](https://github.com/ja11sop/cuppa/issues/184), closed)

| Piece | Behaviour |
|-------|-----------|
| API | `env.CollateCxxProfilesIndex(destination=None, link_style=None)` |
| Activation | Same gate and collector path as `--cxx-profiles-report` |
| Default path | `<artefacts-root>/cxx-profiles/` from registry helper |

<a id="prof-report-method-naming"></a>

### Method naming — `CollateCxxProfilesIndex()` (settled)

**Settled name (1.8.0 slice E, not yet released):** **`env.CollateCxxProfilesIndex()`** — session
master index collator, parallel to test and coverage:

| Report kind | Per-target / per-scope (typical) | Session index method |
|-------------|----------------------------------|----------------------|
| Test | `env.GenerateHtmlTestReport(…)` | `env.CollateTestReportIndex( sources, … )` |
| Coverage | `env.CollateCoverageFiles(…)` | `env.CollateCoverageIndex( sources, … )` |
| C++ Profiles | **`env.CxxProfilesReport(…)`** *(reserved — not shipped)* | **`env.CollateCxxProfilesIndex( … )`** |

**Why `Collate` + `Index`:** the verb **`Collate`** matches cuppa’s other session masters and
signals roll-up into `cxx-profiles-index.{html,json}`. It avoids squatting on
**`CxxProfilesReport()`**, which we reserve for a possible future **per-scope** HTML/JSON page (one
`(sconscript × variant × toolchain)` row), fed into the index the same way test/coverage sources
feed their collators.

**Why not `CxxProfilesReportIndex()`:** that name binds both “report” and “index”, leaving no clean
API when per-scope `CxxProfilesReport()` arrives.

**No alias:** slice E has not shipped; rename directly to `CollateCxxProfilesIndex` (no
`CxxProfilesReport` method alias).

**Difference from test/coverage today:** Profiles collation is **not fed** explicit upstream nodes in
the sconscript — capture comes from compiler stderr via the spawn processor once activated; write
happens at `sconstruct_end`. When per-scope `CxxProfilesReport()` exists, expect:
`env.CollateCxxProfilesIndex( reports, destination='…' )`.

**Future naming tree:**

```text
env.CxxProfilesReport( target )              # future: one scope page + JSON sibling
env.CollateCxxProfilesIndex( reports, … )  # session: cxx-profiles-index.*
--cxx-profiles-report                          # CLI: same as Collate… at root (today)
```

<a id="prof-report-method-semantics"></a>

### Method vs CLI — product intent and current behaviour (2026-08-16)

**Intended value** (author workflow):

1. On profile **enforcement** runs, continue processing as much of the tree as possible, **collate
   violations once** for the whole sconstruct tree, and emit HTML/JSON at the end.
2. **`--cxx-profiles-report`** — ad-hoc / local inventory without editing sconscripts.
3. **`env.CollateCxxProfilesIndex()`** — same collation, declared in sconscript (e.g. Profiles CI
   jobs that should always publish the index without remembering the CLI flag).

That product story assumes **keep-going** behaviour under failed compiles — shipped in
[#203](https://github.com/ja11sop/cuppa/pull/203) (inventory mode prepends ``-i`` when needed).

#### Behaviour audit (post-#203)

| Topic | Shipped | Remaining gap |
|-------|---------|---------------|
| **Session collation** | One `ProfilesReportSession` per process; one write at `sconstruct_end` (+ fallback flush) | — |
| **CLI vs method activation** | CLI sets `cxx_profiles_report` on cuppa root env; method calls `ProfilesDiagnosticCollector.activate()` | — |
| **Scope of capture** | Session-wide capture once inventory mode is active | Method-only **index filter** — [§Collate index scope filter](#prof-report-scope-filter-slice) |
| **Multiple method calls** | Idempotent `activate()`; one index | Conflicting `destination=` / `link_style=` — first wins + warn in scope-filter slice |
| **`-H` / parsed files** | On envs with `cxx_profiles_report` set | Per-sconscript `-H` without spawn gating — deferred with `CxxProfilesReport()` |
| **Implied `-i`** | Cuppa CLI prepends `-i` when inventory mode active ([#203](https://github.com/ja11sop/cuppa/pull/203)) | — |
| **Selective exit** | Non-profile tally; exit non-zero after index write ([#203](https://github.com/ja11sop/cuppa/pull/203)) | Optional `--cxx-profiles-report-allow-errors` deferred |
| **Report write hook** | Progress decoupling + `finalize_inventory_session()` ([#203](https://github.com/ja11sop/cuppa/pull/203)) | — |
| **Partial sessions** | `VariantCompletionTracker` warns; manifest `partial: true`; fallback flush | — |

**Capture content:** only Clang lines matching the Profiles diagnostic shape enter the inventory.
Ordinary compile errors are **not** classified as profile violations; they still fail the action
like any other error.

#### Follow-on semantics (plan settled — [#199](https://github.com/ja11sop/cuppa/issues/199))

These follow from the product intent above and align the method name with test/coverage index
methods. **Settled decisions, work slices, and hooks:** [§Collate index semantics](#prof-report-method-semantics-slice).

| Proposal | Rationale | Settled |
|----------|-----------|---------|
| **`--cxx-profiles-report` implies `-i`** when the user did not pass `-i` explicitly | Inventory runs are report-first; stopping at the first failed TU defeats the feature | **Yes** |
| **`--cxx-profiles-report` implies unlimited per-TU diagnostic cap** when not overridden | Without `-ferror-limit=0` / `-fmax-errors=0`, each TU can stop early and the inventory under-counts violations — a silent “better” report | **Shipped** [#225](https://github.com/ja11sop/cuppa/pull/225) — [§Implied diagnostic error limit](#prof-report-error-limit) |
| **At end of invocation:** non-zero exit for **non-profile** compile failures while still writing the index | Keeps CI honest while allowing profile inventory to complete | **Yes (v1)** — profile-violation-only sessions exit 0 |
| **Optional scope filter:** index lists only scopes whose owning sconscript declared ``CollateCxxProfilesIndex()`` (union of declarers); CLI lists all scopes | Matches test/coverage collator opt-in; capture stays session-wide | **Follow-on** — [§Collate index scope filter](#prof-report-scope-filter-slice) |
| **Decouple report write from `finished` → target success** | Ensure `sconstruct_end` collation runs when capture buffer is non-empty even if compiles failed | **Yes** — Progress fix + fallback flush |

Track as slice **`prof-report-method-semantics`** — see [§Collate index semantics](#prof-report-method-semantics-slice). Do not rename or change failure policy in slice E / F-min without that dedicated follow-up.

<a id="prof-report-method-semantics-slice"></a>

## Collate index semantics (`prof-report-method-semantics`)

**Id:** `prof-report-method-semantics` · **Status:** **shipped** ([#203](https://github.com/ja11sop/cuppa/pull/203)) — [#199](https://github.com/ja11sop/cuppa/issues/199) · **Impact:** minor · **Target:** 1.8.0

Align `--cxx-profiles-report` and `env.CollateCxxProfilesIndex()` with the [product intent](#prof-report-method-semantics). Slice **E** shipped method + CLI wiring with today’s capture and Progress behaviour; this slice closes the audit-table gaps without reopening E / F-min.

### Why now

Real enforce inventories need **keep-going** compiles and a **session index at end**, even when many TUs fail Profiles checks. Today authors pass **`-i`** manually (Antora std-init example, integration tests); without it, failed compiles can block `#SconstructEnd` and the index never writes. Exit code is pure SCons: a green inventory artefact can still leave CI red, or a failed build can leave CI red with no report.

### Settled decisions (2026-08-16)

| Topic | Decision |
|-------|----------|
| **Implied `-i`** | **Yes.** Cuppa CLI prepends SCons ``-i`` when ``--cxx-profiles-report`` is present or scanned sconscripts declare ``CollateCxxProfilesIndex()`` (and the user did not pass ``-i``). SCons forbids ``SetOption('ignore_errors')`` from SConscript files. Activation logs a warning if ``-i`` is still absent at report enable time. |
| **Progress decoupling** | **Two layers.** (1) **Primary:** relax `NotifyProgress` so variant **`finished`** / sconscript **`end`** / `#SconstructEnd` still run after variant **started** even when compile targets failed (inventory mode only — gate on report activation). (2) **Fallback:** if the capture buffer is non-empty and the session index was not written, flush from `ProfilesDiagnosticCollector.finalize_inventory_session()` after `build()` (mark `metadata.partial`, reuse `incomplete_scopes`). |
| **Non-profile errors under implied `-i`** | **Settled A+B.** Tally non-profile compile failures during inventory runs; after the session index write (or fallback flush), exit **non-zero** when the tally is non-zero. Console: profile-shaped diagnostics keep an **Error** label but use **warning** colours; ordinary errors stay red. Global `ignore_errors` remains required so profile violations do not abort early. |
| **Selective exit (v1)** | Same as **Non-profile errors** row — tally + `finalize_inventory_session()` after `build()` in `construct.py` (`inventory_process_exit_status`). |
| **Scope filter** | **Follow-on** — [§Collate index scope filter](#prof-report-scope-filter-slice). Session-wide capture; method-only write-time filter (union of declaring sconscripts); CLI unchanged. Per-sconscript spawn semantics deferred with **`env.CxxProfilesReport()`**. |
| **`--cxx-profiles-report-allow-errors`** | **Deferred.** v1 selective exit is fixed policy above; add an opt-out flag only if consumers need “report + always exit 0”. |
| **Activation hook** | Single path: `activate_cxx_profiles_report()` in `cuppa/methods/cxx_profiles_report.py` (covers CLI + method). |
| **Write hook** | `ProfilesReportSession._emit_session_summary()` → `write_profiles_reports()`; fallback flush shares the same emitter. |
| **Exit hook** | `ProfilesDiagnosticCollector.finalize_inventory_session()` after `build()` in `construct.py`; applies selective exit when report mode was active. |
| **Tests / docs** | Drop manual `-i` from examples and integration tests where inventory mode now implies it; keep `-i` in docs only as “SCons keep-going (automatic in inventory mode)”. Extend `test_cxx_profiles`, `test_available_reports` for failed-TU inventory + exit policy. |

### Work slices

| Id | Slice | Deliverable |
|----|--------|-------------|
| `prof-report-semantics` | Inventory mode (#199) | Implied `-i` (CLI); Progress decoupling; fallback flush; non-profile tally + selective exit; console differentiation; docs + integration |

**Suggested landing:** **Shipped** [#203](https://github.com/ja11sop/cuppa/pull/203) — closes [#199](https://github.com/ja11sop/cuppa/issues/199) except scope filter follow-on.

Former sub-ids (`prof-report-semantics-i`, `-progress`, `-exit`, `-docs`) are bookkeeping only; all shipped together in #203.

### Refusal rules

- Do not enable implied `-i` when Profiles/report is not active.
- Do not override an explicit user `-i` / `--ignore-errors`.
- Do not filter the index by declaring sconscript until **`prof-report-scope-filter`** lands — see [§Collate index scope filter](#prof-report-scope-filter-slice).
- Do not treat ordinary compile errors as Profiles violations for exit policy.
- Do not skip writing the index when the capture buffer is non-empty and the build aborted early (fallback flush).
- Do not change F-min catalogue, `--list-available-reports`, or Phase 6 artefact roots in this slice.

### Implementation hooks (code map)

| Area | File | Hook |
|------|------|------|
| Implied `-i` | `cuppa/core/profiles_inventory_cli.py`, `cuppa/__main__.py` | CLI prepends `-i` when report flag or scanned `CollateCxxProfilesIndex()` |
| Progress DAG | `cuppa/progress.py` | `NotifyProgress.add()` — decouple `_finished[variant]` from failed targets when inventory active |
| Fallback flush + exit | `cuppa/construct.py`, `cuppa/cpp/profiles_report_collector.py` | `finalize_inventory_session()` after `build()`; `ProfilesReportSession.flush_pending()` |
| Failure tally | `cuppa/output_processor.py` | `ToolchainProcessor` — count non-profile errors when report active |
| Selective exit | `cuppa/cpp/profiles_report_collector.py` | `inventory_process_exit_status()` → `SCons.Script.Exit(1)` from `finalize_inventory_session()` |
| Scope filter | `cuppa/cpp/profiles_report/inventory.py`, `cuppa/methods/cxx_profiles_report.py` | **Follow-on** — [§Collate index scope filter](#prof-report-scope-filter-slice) |

### Progress snapshot (#199)

| Id | Status |
|----|--------|
| `prof-report-semantics` | **Shipped on [#203](https://github.com/ja11sop/cuppa/pull/203)** — implied `-i`, Progress decoupling, fallback flush, non-profile tally + selective exit, console differentiation, unit + integration tests, Antora + CHANGELOG |

**Out of scope (deferred):** scope filter → [§Collate index scope filter](#prof-report-scope-filter-slice); F-min display; per-scope **`env.CxxProfilesReport()`**; full Phase 6 **`--remove-artefacts`** ([#135](https://github.com/ja11sop/cuppa/issues/135)); `--cxx-profiles-report-allow-errors`.

<a id="prof-report-error-limit"></a>

## Implied diagnostic error limit (`prof-report-error-limit`)

**Id:** `prof-report-error-limit` · **Status:** **shipped** ([#225](https://github.com/ja11sop/cuppa/pull/225) /
[#224](https://github.com/ja11sop/cuppa/issues/224)) · **Impact:** minor · **Target:** 1.9.0

### Why

Implied `-i` keeps the **session** alive; it does not lift the **per-TU** compiler diagnostic cap.
Without `-ferror-limit=0` / `-fmax-errors=0`, each failing translation unit can stop emitting
after the toolchain default, so the Profiles inventory under-reports violations in that TU. That
is easy to miss because the report still renders and looks authoritative.

### Settled direction (2026-08-18)

| Topic | Decision |
|-------|----------|
| **Inventory implies unlimited** | Same activation gate as implied `-i` (`--cxx-profiles-report` or `CollateCxxProfilesIndex()`), unless the user overrides |
| **Override: compiler default** | `--cxx-default-error-limit` — strip existing `-ferror-limit` / `-fmax-errors` flags; append no cuppa flag |
| **Override: explicit cap** | `--cxx-error-limit=N` (`0` = unlimited); wins over inventory implication |
| **Existing flag** | `--cxx-disable-error-limit` remains shorthand for unlimited on non-inventory enforce sweeps |
| **Sconscript methods** | `env.CxxErrorLimit(N)`, `env.CxxDefaultErrorLimit()`, `env.CxxDisableErrorLimit()` mirror the CLI vocabulary |
| **Toolchain API** | Generalise `disable_error_limit_flags` → `error_limit_flags(env, limit)`; MSVC warns when unsupported |
| **`configure.conf`** | **No new loader** — keys are the usual internal option names (`cxx_error_limit`, `cxx_default_error_limit`, `cxx_disable_error_limit`). Documented in Antora Configuration + C++ Profiles hub. |

Report mode implies unlimited; `--cxx-disable-error-limit` remains in docs for enforce-only builds
and explicit `configure.conf` defaults.

### Progress snapshot (2026-08-19, [#225](https://github.com/ja11sop/cuppa/pull/225))

| Area | Status |
|------|--------|
| `cuppa/methods/cxx_error_limit.py` | Resolve effective limit from CLI, `configure.conf`, inventory, and sconscript methods; strip before apply |
| `init_env_for_variant` | Inventory implies unlimited when not overridden |
| Toolchains `error_limit_flags(env, limit)` | Clang/GCC/MSVC |
| Env methods | `CxxErrorLimit(N)`, `CxxDefaultErrorLimit()`, `CxxDisableErrorLimit()` |
| Unit tests | Precedence, strip/default/disable, method surface, idempotent CLI registration |
| Integration test | `test_profiles_report_implies_error_limit` (Profiles-capable Clang) |
| Antora + CHANGELOG | CLI reference, cxx-profiles hub, configuration.adoc |
| Bootstrap fixes | Early `configured_options` / `add_base_options` before verbosity; cuppa logger honours `--verbosity=exception` |

| Id | Status |
|----|--------|
| `prof-report-error-limit` | **Shipped on [#225](https://github.com/ja11sop/cuppa/pull/225)** — implied unlimited per-TU cap with explicit overrides; generalised error-limit module and env methods |

<a id="prof-report-scope-filter-slice"></a>

## Collate index scope filter (`prof-report-scope-filter`)

**Id:** `prof-report-scope-filter` · **Status:** **proposal** (settled decisions 2026-08-16) · **Impact:** minor · **Target:** 1.8.0 follow-on — [#205](https://github.com/ja11sop/cuppa/issues/205) after [#203](https://github.com/ja11sop/cuppa/pull/203) / [#199](https://github.com/ja11sop/cuppa/issues/199)

### Why

[#203](https://github.com/ja11sop/cuppa/pull/203) ships session-wide inventory mode: capture and index list **every**
`(sconscript × variant × toolchain)` scope once inventory mode is active. That matches ad-hoc
``--cxx-profiles-report`` runs and root-level CI jobs.

Authors who declare ``env.CollateCxxProfilesIndex()`` in a **specific** sconscript often want the
session index to cover **only the scopes that sconscript owns** — the same opt-in shape as
``CollateTestReportIndex`` / ``CollateCoverageIndex``, which collate explicit upstream sources into
one master index. Today Profiles capture is global (one spawn processor) while the index is also
global, so a declaration in ``test/orders/sconscript`` still lists ``test/trades/…`` scopes.

We cannot realistically give each subtree different compile behaviour (keep-going, ``-H``, report
env) without **isolated spawn semantics per sconscript** based on whether that sconscript declared
``CollateCxxProfilesIndex()``. v1 scope filter is therefore a **write-time** subset of an
otherwise session-wide capture buffer.

### Product intent (author mental model)

1. **Capture:** continue recording profile-shaped diagnostics for **every** scope the build
   compiles (unchanged global collector).
2. **Index (method-only):** include only scopes whose **owning sconscript** registered
   ``CollateCxxProfilesIndex()`` during the session — **union** of all registering sconscripts,
   parallel to test/coverage collators fed from multiple sconscripts.
3. **Index (CLI):** ``--cxx-profiles-report`` bypasses the filter and lists **all** captured
   scopes (today’s behaviour).
4. **Metrics:** Overview ``context`` and session ``summary`` are computed on the **filtered**
   inventory (the rows that appear in HTML/JSON), not on the full capture buffer.
5. **Transparency:** when the filter omits scopes, log a warning naming how many scopes were
   excluded and suggest ``--cxx-profiles-report`` (or declaring collation at the root) to see the
   full session inventory.

### Settled decisions (2026-08-16)

| Topic | Decision |
|-------|----------|
| **Filter trigger** | Apply only when activation is **method-only** (one or more ``CollateCxxProfilesIndex()`` calls). **CLI** ``--cxx-profiles-report`` → **no filter** (full session index). |
| **Declaring set** | **Union** of normalized sconscript paths that invoked ``CollateCxxProfilesIndex()`` (duplicate calls on the same path are idempotent). |
| **Inclusion rule** | Include capture scope row **iff** ``scope.sconscript`` is **exactly** in the declaring set (same path normalization as ``NotifyProgress.scope_from_env`` / ``ProfilesScope``). No automatic subtree roll-up — a parent sconscript that declares collation does **not** include child sconscript scopes unless the child also declares. |
| **Capture scope** | **Write-time filter only.** Do not gate spawn capture, ``-H``, or inventory mode per subtree in this slice. |
| **Session summary / Overview context** | Recompute ``summary``, roll-ups, and ``context`` tier metrics on the **filtered** inventory before emit. |
| **Omitted scopes notice** | After filter, if any captured scopes were dropped: ``logger.warn`` with omitted scope count (and optionally example paths); message suggests ``--cxx-profiles-report`` for the full tree. |
| **``destination=`` / ``link_style=``** | **First declaration wins** for the session write env; if a later call disagrees, **warn** and ignore the conflicting values (same destination/link_style still allowed). |
| **Multiple declaring sconscripts** | **Union** of scopes — same collator pattern as test/coverage index methods listing sources from several sconscripts. |
| **JSON metadata** | Record ``metadata.scope_filter`` (declaring paths, omitted scope count) when filter active so regen/offline tools stay honest. |
| **Per-scope ``CxxProfilesReport()``** | Remains a **separate** slice — explicit per-scope pages + ``CollateCxxProfilesIndex( sources )`` fed from upstream nodes; see [§Method naming](#prof-report-method-naming). |

### Why not capture gating in v1

Per-sconscript compile flags (keep-going, ``-H``, enforce pairing) would require spawn/processor
behaviour that depends on whether **that** sconscript’s construction ``env`` declared collation.
That is a larger architectural change than a write-time filter and is deferred with
``env.CxxProfilesReport()``.

### Work slice

| Id | Slice | Deliverable |
|----|--------|-------------|
| `prof-report-scope-filter` | Method-only index filter | Declaring-set registry; write-time scope filter; filtered metrics; warnings; unit + integration tests; Antora + CHANGELOG |

**Suggested landing:** one PR after [#203](https://github.com/ja11sop/cuppa/pull/203) merges; track [#205](https://github.com/ja11sop/cuppa/issues/205); cite ``prof-report-scope-filter``.

### Refusal rules

- Do not filter when ``--cxx-profiles-report`` is active (CLI means full tree).
- Do not silently drop scopes — always warn when filter excludes captured scopes.
- Do not guess subtree inclusion from a parent declaration (exact sconscript path match only).
- Do not recompute metrics from the unfiltered buffer while displaying a filtered index.
- Do not implement per-sconscript spawn semantics in this slice.

### Implementation hooks (code map)

| Area | File | Hook |
|------|------|------|
| Declaring registry | `cuppa/methods/cxx_profiles_report.py` | Record normalized sconscript path on each ``CollateCxxProfilesIndex()`` call; first ``destination`` / ``link_style`` |
| Session state | `cuppa/cpp/profiles_report_collector.py` | ``ProfilesReportSession.declaring_sconscripts``; ``activation_via_cli`` flag |
| Filter + metrics | `cuppa/cpp/profiles_report/inventory.py`, `report_html.py`, `context_summary.py` | ``filter_inventory_for_index( inventory, declaring_set )``; rebuild model on filtered copy |
| Notice | `cuppa/cpp/profiles_report_collector.py` | Warn after filter with omitted count + ``--cxx-profiles-report`` hint |
| Tests | `tests/unit/`, `tests/integration/methods/test_cxx_profiles.py` | Two-sconscript project: one declarer → other scope captured but omitted from index + warning |
| Docs | `cxx-profiles.adoc`, `report-introduction.adoc` | Method vs CLI scope; union of declarers; full-tree CLI escape hatch |

### Progress snapshot

| Id | Status |
|----|--------|
| `prof-report-scope-filter` | **Proposal** — [#205](https://github.com/ja11sop/cuppa/issues/205); implementation after [#203](https://github.com/ja11sop/cuppa/pull/203) |

<a id="prof-report-anonymize"></a>

## Anonymized report sharing (sketch)

**Id:** `prof-report-anonymize` · **Status:** **shipped** — merged [#197](https://github.com/ja11sop/cuppa/pull/197) on [#184](https://github.com/ja11sop/cuppa/issues/184); slice H merged [#196](https://github.com/ja11sop/cuppa/pull/196)

### Shipped implementation (PR #197)

| Piece | Location / behaviour |
|-------|----------------------|
| Core transform | `anonymise_report_payload()` in `cuppa/cpp/profiles_report/anonymise.py`; US shim `anonymize.py` |
| Thematic pools | `thematic_names.json` — dependency slugs, project slugs, path stems/compounds; deterministic hash pick + `slot-…` synthesis when exhausted |
| Path policy | Project tree → `project/<slug>/…`; encoded download folders → `deps/lib-<slug>/…`; passthrough for common segments (`include`, `test`, …); variant tails preserved |
| Verify | `collect_forbidden_tokens()` from input JSON; `verify_anonymised_output()` before write |
| Metadata scrub | Placeholder roots `/anon/widget/root`; `report_project` → `example-project`; VCS fields cleared; `link_style` → `local` |
| HTML enrichment | Strip display-only path copies (`scope_path_suffix`, `display_path`, …) from JSON; catch-all path scrub on regen-sensitive keys |
| Regen headers | `report_header_context_from_metadata()` — index/scope titles and VCS line from JSON, not live git/cwd |
| CLI | `python -m scripts.anonymise_profiles_report`; `regenerate_profiles_report --from-json` honours `metadata.anonymised` |
| Tests | `tests/unit/test_profiles_report_anonymise.py` |

British spelling is canonical (`anonymised`, `--anonymised`); US aliases accepted without CLI help.

### Goal

Take a **saved** `cxx-profiles-index.json` from a real Profiles run (consumer project or local
tree), produce a **shareable anonymized JSON** artefact, then regenerate **HTML** from that JSON
**without source files** and **without** links that re-identify the project.

**Settled:** anonymized sharing is **JSON + summary HTML only**. Source file contents cannot be
anonymized in place (snippets would still leak identifiers and structure), so an anonymized
artefact **never** ships with `by-source/` pages, local file hrefs, or a source tree on disk.
Regeneration must use `--skip-source-pages` (or equivalent) and suppress file/repo links when
`metadata.anonymized` is set.

Typical workflow:

1. Build with `--cxx-profiles-report` (or copy the JSON sibling from CI artefacts).
2. Run an anonymizer CLI on the JSON → `cxx-profiles-index.anonymized.json`.
3. Share the anonymized JSON (issue attachment, public fixture, doc sample).
4. Recipient (or doc pipeline) runs `scripts/regenerate_profiles_report --from-json …
   --skip-source-pages` → browsable HTML with counts, rules, and **semi-readable** path labels.

The JSON envelope already separates **inventory** (`report`, `summary`, `locations[]`) from
**session metadata** (`metadata`). Anonymization is a **pure transform** on disk — no rebuild,
no compiler, no access to the original tree (except optionally a local sidecar mapping file kept
out of the shared artefact).

### Settled anonymization policy

| Topic | Decision |
|-------|----------|
| **Variant shape** | **Keep** variant information as-is: `variant_label` (`dbg`, `rel`, …) and the variant path tail (`…/dbg/x86_64/cxx2c`, toolchain folder name under `_build/`, etc.). These are build-shape metadata, not project identity. |
| **Readability** | Paths should stay **semi-readable** — plausible software tree names, not `file-001.hpp` serials. Reports should look like a generic project, not the original. |
| **Path segments** | Replace **most** path components using a curated synonym dictionary (~200 common software terms). Very common segments (e.g. `include`, `src`, `test`, `lib`, `util`) may pass through unchanged. |
| **Multi-part names** | For `snake_case` directory or file stems (`common_types`, `order_manager`), **always** replace at least one `_`-delimited segment, preferably with a dictionary synonym (`common_types` → `core_elements`). |
| **Tree shape** | Preserve **multiple roots** and relative depth — project include root vs dependency download root vs generated paths — under anonymized top-level labels, e.g. `include/acme/widget/core_elements/number.hpp` and `_cuppa/_download/vendor/widget/core_elements/number.hpp`. |
| **Fingerprinting** | **Out of scope** — structural similarity (counts, line numbers, directory depth) is acceptable; goal is deniability of *identity*, not statistical anonymity. |
| **Source files** | **Not shipped** — anonymized bundle = JSON (+ optional HTML regen). No source pages, no snippets, no links to paths on disk. |

### What must change in the JSON

| Area | Today | Anonymized |
|------|-------|------------|
| `metadata.sconstruct_dir`, `cxx_profiles_report_root` | Absolute project path | Generic placeholder root, e.g. `/home/user/project/widget` |
| `metadata.report_project`, `report_uri`, `report_branch`, `report_revision` | VCS / hosting identity | Empty or placeholders (`example-project`, no URI) |
| `metadata.link_style` | May be `gitlab` / `github` with real repo | `local`; HTML must not emit repo browse links when `metadata.anonymized` |
| `metadata.anonymized` | — | `true` (+ optional `anonymization_version: 1`) |
| `locations[].path`, nested `report.*.files[].path`, rule file refs | Absolute or real dependency paths | Same **relative shape** under anonymized roots; segments rewritten via dictionary (see below) |
| `locations[].message`, nested sample / raw messages | May contain identifiers | Drop or replace with `normalised_message` only (classifier output already collapses identifiers) |
| `locations[].sconscript` | Real module path | Anonymized module slug (e.g. `./widget/sconscript`) — not the original name |
| `locations[].variant_dir`, `variant_label`, `toolchain` | Real scope strings | **Keep variant tail and labels** (`dbg`, `x86_64`, `cxx2c`, …); anonymize only the **project-specific prefix** inside `variant_dir` (and `sconscript` stem) so `_build/<real>/…/dbg/x86_64/cxx2c` becomes `_build/<anon>/…/dbg/x86_64/cxx2c` |
| `location_key` | SHA-256 of scope + path + line + col + normalised message | **Recompute** after path/scope/message transforms |
| `generated_at` | Real timestamp | Keep or round to date — low priority |

**Manifest (`.cuppa-reports`):** out of scope for the shared artefact; anonymizer operates on
report JSON only.

### Path anonymization (multi-root, semi-readable)

**Algorithm sketch:**

1. **Detect roots** — split each absolute path into one or more logical roots (project
   `sconstruct_dir` / include tree, `_cuppa/_download/…` dependency tree, `_build/…` generated
   tree, etc.). Each root maps to a stable anonymized top-level label (`include`, `src`,
   `_cuppa/_download/vendor`, `_build/module`, …).
2. **Walk relative path** — for each directory and file stem (extension preserved):
   - If stem is in the **pass-through allowlist** (`include`, `src`, `test`, …) and is a single
     common segment, leave unchanged.
   - If stem contains `_`, replace **≥1** segment using the synonym dictionary; deterministic
     pick (e.g. hash of original segment mod dict size) so reruns match.
   - Otherwise replace the whole stem with a dictionary synonym when one exists; fall back to a
     generic stem (`module`, `component`, `item`) only when no match.
3. **Uniqueness** — if two files collide after rewrite, disambiguate with a numeric suffix on the
   **last** segment only (`handler.cpp` vs `handler_2.cpp`), not a flat serial tree.
4. **Determinism** — same input JSON → same anonymized paths (CI fixtures, doc samples).
5. **Optional sidecar** (`--mapping-out`, gitignored): `{original_path: anonymized_path}` for
   internal debugging — **never** ship with the public JSON.

**Synonym dictionary:**

- Ship a **built-in offline** map (~200 entries): `common_types→core_elements`, `order→trade`,
  `matcher→router`, `handler→processor`, … — enough for typical C++ tree vocabulary.
- **Default:** no network. Optional `--online-synonyms` (or similar) may call a third-party
  library if installed; document that CI and air-gapped use should rely on the built-in dict only.
  Online enrichment is a nice-to-have, not a requirement.

**Example** (illustrative):

```text
/home/acme/matcher/include/matcher/common_types/number.hpp
  → include/acme/widget/core_elements/number.hpp

/home/acme/_cuppa/_download/git_…/matcher/include/matcher/common_types/number.hpp
  → _cuppa/_download/vendor/widget/core_elements/number.hpp

_build/matcher/clang24/dbg/x86_64/cxx2c/…   # variant tail unchanged
  → _build/widget/clang24/dbg/x86_64/cxx2c/…
```

### HTML regeneration behaviour

Existing pieces:

- `scripts/regenerate_profiles_report --from-json` + `env_from_report_metadata()` — session
  fields from JSON `metadata`.
- `--skip-source-pages` — skips `by-source/` HTML generation.

Gaps for anonymized sharing:

1. **`metadata.anonymized: true`** (and optional `anonymization_version: 1`) — regen **must**
   treat this as “no source artefacts”: `--skip-source-pages`, no `by-source/`, no file hrefs.
2. **Suppress source / repo hrefs** in `enrich_model_for_html` / `annotate_file_links` when
   anonymized — even if source files exist locally on the recipient machine, do not link to them.
   Rule `doc_href` (P4222 / ProfilesFramework.rst) stays — public documentation, not project
   identity.
3. **Regen CLI sugar:** `--anonymized` implies `--skip-source-pages` and honours
   `metadata.anonymized` (fail or warn if flag/json disagree).
4. **Dependency path display** (slice D): anonymized segment names should read naturally under
   muted-prefix rows without a real `report_root` on disk.

### API / CLI sketch

| Piece | Location |
|-------|----------|
| Core transform | `anonymize_report_payload(payload, *, dictionary=None, mapping=None) -> payload` in `cuppa/cpp/profiles_report/anonymize.py`; bundled `synonym_dictionary.json` (~200 terms) |
| CLI | `python -m scripts.anonymize_profiles_report --in index.json --out index.anonymized.json [--mapping-out mapping.local.json] [--online-synonyms]` |
| Tests | `tests/unit/test_profiles_report_anonymize.py` — golden input → no original path segments / hostnames / VCS URIs; `common_types` absent when present in input; counts unchanged; multi-root shape preserved |
| Public fixture | Optional: commit anonymized JSON derived from `examples/profiles/std-init-violations/` for docs / regen smoke |

Regen chain:

```text
cxx-profiles-index.json
  → anonymize_profiles_report
  → cxx-profiles-index.anonymized.json
  → regenerate_profiles_report --from-json --skip-source-pages
  → cxx-profiles-index.html (no by-source/, no file hrefs)
```

### Issues and limits (honest)

| Issue | Mitigation / note |
|-------|-------------------|
| **Identifier leakage in messages** | Raw `message` may survive if classifier missed a pattern | Prefer `normalised_message` only in output; unit test scans anonymized JSON for `@`, `::`, common identifier regex |
| **Dictionary gaps** | Unusual domain jargon may pass through unchanged | Extend built-in dict over time; optional online synonyms behind flag; sidecar mapping for internal review only |
| **Collision after rewrite** | Two distinct paths map to same anonymized path | Numeric suffix on last segment only (`_2`) |
| **`location_key` drift** | Must recompute after every path/message change | Single helper reused by writer and anonymizer tests |
| **Schema version** | Same `schema_version: 1` + `metadata.anonymized` | No envelope bump unless shape changes |
| **Partial / incomplete scopes** | `incomplete_scopes`, `partial` are behavioural | Keep as-is (including real `dbg` / variant labels) |
| **Reverse mapping** | Sidecar only on producer machine | Never upload mapping with shared JSON |
| **Source snippets** | Cannot redact file contents safely | **Settled:** anonymized share never includes source pages or files — inventory tables only |
| **Capture replay path** | Anonymizer targets **JSON**, not raw console capture | Document that sharing should start from JSON |

### Testing (when implemented)

| Layer | Cases |
|-------|-------|
| Unit | Anonymize golden v1 JSON; grep serialized output for forbidden substrings |
| Unit | `location_key` stable across anonymize → reload → regen |
| Unit | `summary` / roll-up counts unchanged; scope count unchanged |
| Unit | HTML regen from anonymized JSON: no `href` to `by-source/`, no `file://`, no repo browse links when `metadata.anonymized` |
| Unit | Anonymize preserves numeric `context` fields unchanged |
| Docs | Antora subsection under cxx-profiles: “Sharing an inventory (anonymized JSON)” |

### Open choices (resolve in implementation PR)

1. Exact **pass-through allowlist** for ultra-common segments (`include`, `src`, `test`, …).
2. Whether anonymizer **requires** `--force` when input already has `metadata.anonymized`.
3. Single command `regenerate_profiles_report --anonymize-out` vs separate script only.
4. Which optional online synonym backend (if any) — defer unless built-in dict proves insufficient.

<a id="prof-report-context-summary"></a>

## Context summary — violations relative to codebase size (sketch)

**Id:** `prof-report-context-summary` · **Status:** **shipped** — merged [#196](https://github.com/ja11sop/cuppa/pull/196) on [#184](https://github.com/ja11sop/cuppa/issues/184); slice G follows

### Why

Raw violation counts (“1310 references across 78 files”) are hard to interpret without **denominator
context**. External audiences — standards papers, conference posts, cross-project comparisons — need
answers like:

- What **fraction of the compiled codebase** showed at least one violation?
- Among files that violated, how **concentrated** are violations (two bad lines in a ten-line header
  vs scattered refs across a large translation unit)?
- Which **rules dominate** the inventory, including rules that did **not** fire (a complete profile
  checklist)?
- Was the run **partial** (one variant only) and does the summary say so?

Today the master index headline (`N violations of M rules through R references`) and compact
`summary.by_rule` answer “what fired” but not “how big was the haystack”. Slice C ships the
drill-down tabs; this slice adds a dedicated **Overview** tab and a JSON `context` object.

### Goals (Overview tab + JSON)

Single master-index page section (default tab when present) showing:

| Block | Content |
|-------|---------|
| **Session headline** | Profiles enforced; scope count; partial/incomplete banner; existing ref / rule / location totals |
| **Codebase reach (tier 1)** | `files_parsed` (TUs + includes seen via `-H` or `.d`); `files_with_violations`; **file violation rate %** |
| **Violation density (tier 2)** | Unique violation lines; `source_lines_v1` in violating files only; **violation line % in affected files** |
| **Rule concentration** | Top rules by reference share (% of session total); bar or sorted table |
| **Full profile matrix** | For each enforced profile, **every documented rule id** with reference count, unique files, unique lines — **zero-filled** when not observed |
| **Build inventory load** | Per-build **Hits** (violation / rule / file / reference) summed across sconscripts; **Session total (union)** row with distinct violation, rule, and file styling; short **build ids** (`dbg1`, `rel1`, …) for chart labelling |
| **Scope footnote** | When multiple scopes ran, small table of per-scope file/TU counts (optional phase 2) |

The same structure is serialized under top-level **`context`** in `cxx-profiles-index.json` so
anonymized JSON ([§Anonymized report sharing](#prof-report-anonymize)) can be shared **with
denominators intact** — counts do not reveal identity; compute `context` **before** path
anonymization and store in JSON (do not re-scan disk on anonymized regen).

### Two-tier exposure model (settled)

Overview answers **overall Profiles exposure** with two complementary measures plus existing
inventory metrics (references, rules, locations, rule matrix):

| Tier | Question | Metric | Doable? |
|------|----------|--------|---------|
| **1 — Breadth** | How **extensive** are issues across the code that was **actually parsed**? | **`files_with_violations / files_parsed`** (%) — distinct inventory paths vs distinct **physical source files** (TUs **plus** headers and other includes the compiler pulled in during Profiles compiles). Also report absolute counts and optional TU companion stats. | **Yes** — requires recording the **parsed-file union** per session (see [§Parsed file universe](#prof-report-parsed-files)); not TU-only. |
| **2 — Severity in hot files** | When files **do** violate, are issues **sparse or dense**? | **`unique_violation_lines / source_lines_v1`** summed over **violating files only** — physical files (headers + sources), same path set as tier 1 numerator. | **Yes** — at report write from inventory + `source_lines_v1` on violating paths. |

**Tier 1 is file-based, not TU-based:** translation units are how the build runs, but Profiles
diagnostics attach to **paths** (often headers). The useful breadth question is “what fraction of
**parsed files** had at least one violation?” — not “what fraction of `.cpp` primary sources had
a diagnostic somewhere in their include tree?” (TU-only % undercounts header-heavy codebases).

**Tier 2 denominator scope:** only files that **appear in the violation inventory** — measures
concentration in hot files (e.g. 2 violation lines in a 10-line header ≈ 20%).

**Existing metrics (unchanged):** `total_references`, `unique_violation_count`,
`unique_rule_count`, `summary.by_rule`, roll-up tables, zero-filled profile rule matrix.

<a id="prof-report-parsed-files"></a>

#### Parsed file universe (tier 1 denominator)

**Goal:** `files_parsed` = every distinct source file whose contents the compiler front-end
**actually read** while compiling Profiles-enforced TUs in this session (project sources **and**
dependency headers under `_cuppa/_download/…`, etc.).

You do **not** need to compile headers as separate TUs, and you do **not** need a whole-project
header glob. You **do** need to learn includes from **real TU compiles** (which a Profiles
inventory build already performs) — or accept a weaker static approximation.

| Option | How | Accuracy | Cost / trade-offs |
|--------|-----|----------|-------------------|
| **A — `-H` include stack (recommended v1)** | Add `-H` to `CXXFLAGS` when `--cxx-profiles-report` is active. Clang/GCC print one line per included file to **stderr** (e.g. `. /path/to/header`). Parse lines in the existing Profiles spawn output processor; union paths per compile, then per session. | **Matches compiler** — only files parsed for that TU; respects `#if` / skipped includes. | Captured lines are **not echoed** to the console (spawn processor swallows them after recording). Must normalise paths. Form differs slightly GCC vs Clang — small parser. Failed compiles may still emit partial `-H` before error. |
| **B — `-MMD` dependency files** | Add `-MMD -MP` (or `-MD`) on report builds; after each compile, read the `.d` Makefile next to the `.o` and union listed prerequisites. | **Matches compiler** for included headers. | Cuppa does **not** emit `.d` today — new flags + locate `.d` beside object in `_build/…`. Module / BMI builds need checking. Slightly less live noise than `-H`. |
| **C — SCons implicit dependencies** | At `sconstruct_end`, walk compiled `Object` nodes and union SCons-scanned `#include` deps. | **Approximate** — scanner may differ from real compile (macros, `-include`, modules). | No extra compiler flags; harder to wire from report collator to SCons node graph; may miss system headers. |
| **D — Lexical `#include` closure** | For each compiled TU path, recursively resolve `#include "…"` / `<…>` using compile `CPPPATH` / `SYSINCPATH`. | **Over- and under-includes** — ignores `#if`, may pull headers never compiled, may miss generated paths. | No compiler help; still need TU list from compile hook; **not recommended** for tier 1 %. |
| **E — Dependency tree glob** | Glob all headers under location deps + project. | **Very wrong** — vast overcount. | Simple but unsuitable for “files parsed”. |
| **F — Violations-only set** | Denominator = violating files only. | **Circular** for breadth (100% by definition). | Useful only for tier 2, not tier 1. |

**Settled direction:** implement **A (`-H`)** first — reuses the Profiles diagnostic capture pipe,
no new artefact files, accurate for Alliance Clang Profiles workflows. **B (`.d`)** as fallback if
`-H` proves too noisy or MSVC parity is needed later (MSVC `/showIncludes` analogue).

**`-H` on failed compiles (rationale):** Profiles inventory builds **expect** non-zero compile exit
status — violations are `error:` diagnostics. That does **not** block include capture:

1. **stderr is drained before spawn returns** — `IncrementalSubProcess` reads every stderr line
   until the compiler process exits, then returns the failure code. `-H` lines are not discarded
   because the compile failed.
2. **`-H` precedes most Profiles errors** — the compiler prints each included file as the front-end
   opens it; Profiles rule checks run later on the parsed translation unit. For a typical TU,
   includes are logged before semantic violations in those headers.
3. **Pair with `--cxx-disable-error-limit`** — without `-ferror-limit=0` / `-fmax-errors=0`, the
   compiler may stop mid-TU after the default cap and **skip later includes** in that file. Report
   builds that populate `files_parsed` should treat unlimited diagnostics as **recommended**
   (same pairing already documented for a complete violation inventory).
4. **Numerator is independent** — `files_with_violations` comes from Profiles diagnostic paths,
   not from `-H`; both streams share stderr but serve different fields.

**Honest limits:** fatal errors before an include is reached (missing header, `#error`) yield
**partial** `-H` for that TU; partial sessions only include TUs that started; GCC vs Clang differ
on error-recovery after a bad first `#include`. Acceptable for inventory runs on trees that
otherwise compile; document `partial` / incomplete scope in Overview.

<a id="prof-report-variant-roll-up-display"></a>

### Variant roll-up display (slice H, same PR)

Pre-context **By-Rule** / **By-File** tabs repeat per-variant lines (`1/77 (dbg)`, `1/76 (rel)`, …).
That duplicates information now expressed on the Overview tab as **Build inventory load** (Hits)
vs **session union**. The same PR extends slice H to align roll-up tables with build ids and
**common + delta** notation.

**Settled (2026-08-15):**

| Topic | Decision |
|-------|----------|
| **Roll-up grain** | One bucket per **Build inventory load** row (`build_key`: variant + arch/abi tail + toolchain) — **not** merged by `variant_label` alone (supports dbg/rel × two toolchains → four ids). |
| **Display ids** | Short tokens (`dbg1`, `rel1`, `dbg2`, `rel2`) assigned in inventory-load sort order; stable `build_key` in the model; tooltip carries full `variant/arch/abi — toolchain`. Display scheme may evolve (e.g. `Da` / `Ra`). |
| **Common set** | **Strict intersection** across **every** session build bucket (empty bucket → common = 0). Example: d1=7, r1=8, d2=0, r2=2 → `0, +7d1, +8r1, +2r2`. |
| **Violation deltas** | `\|keys(build) − common\|` per build; omit zero deltas. |
| **Reference deltas** | **Exclusive keys only** — refs from violations in `keys(build) \ common` (R1 union semantics on the common line only). |
| **By-Rule columns** | **Profile**, **Rule**, **Violations**, **Union Refs**, **Peak Refs**, **Violating Files** — multi-build cells use bold total = common + deltas. |
| **By-File columns** | **Profile**, **Rules**, **Violations**, **Union Refs**, **Peak Refs**, **Violated Rules** — same partition logic as By-Rule with file/rule roles swapped. |
| **File / rule lists** | Common bracket when identity **and** ref count match in **all** builds; delta lines (`+1 rel2 [ 5:3 ]`) for build-specific entries. Subtable **Build Refs** column repeats `(index, refs)` partition for one file row. |
| **By-Build index tab** | One sub-tab per **build id** (`dbg1`, …); **Build inventory load** table at top; **By-Rule** / **By-File** pair per build across all sconscripts and profiles (**Profile** column; **Build Refs**, no **Peak Refs**). |
| **Scope detail pages** | Same layout as By-Build detail for one `(sconscript, variant, toolchain)` row — one tab pair, **Profile** column, no per-profile subheadings. |
| **Docs** | Antora hub + `report-introduction.adoc` (generate, regen, JSON, vocabulary); tab guides (`report-by-rule`, `report-by-file`, `report-by-build`, `report-by-sconscript`, `report-overview`, `report.adoc` index). Worked example on By-Rule for **Violating Files** vs **Build Refs** vs **Union Refs** / **Peak Refs**. Violation totals card: distinct violations / distinct rules / union references with `(Violations)` / `(Rules)` / `(Union Refs)` column labels. |
| **JSON** | Attach structured `variant_display` / `peak_refs_display` / `build_refs_display` (`common`, `deltas[]`, `build_order`) on roll-up rows for HTML regen and agents. |
| **Scope** | Index By-Rule / By-File + subtables; index **Violations By-Build**; unified per-scope pages; Overview matrices retain **Peak Refs / %**. |

**Status on [#196](https://github.com/ja11sop/cuppa/pull/196):** **Merged** — Overview + Build inventory load, index By-Rule / By-File variant roll-up (`variant_display`, **Union Refs**, **Peak Refs**, **Build Refs**, `dbg1`-style build IDs), **Violations By-Build** tab, unified scope detail pages, Antora doc split.

**`record_parsed_file()` (include collector sketch):** extend `ProfilesReportSession` (or sibling
store on `ProfilesDiagnosticCollector`) with a **set per session** (and optionally per Progress
scope) of normalised absolute paths:

```python
def record_parsed_file( scope, path ):
    """Record one path seen via -H (or .d); idempotent — no double count."""
```

| Concern | Approach |
|---------|----------|
| **Double counting** | Store **`files_parsed` as a set** — the same header included from many TUs is counted **once** in the session denominator (union, not sum of per-compile lines). |
| **`-H` repeat lines** | One TU may print the same path at multiple stack depths (`.` vs `..` prefix); normalise to path only before insert. |
| **Separate from diagnostics** | Parse `-H` with a dedicated regex (e.g. `^\.+ \S+`) — do not route through `parse_profiles_diagnostic`; call `record_parsed_file` only on match. |
| **Path normalisation** | Reuse the same absolute-path normalisation as diagnostic capture (`realpath` / consistent separators) so one file on disk → one set entry. |
| **TU primary sources** | Also call `record_parsed_file(scope, tu_path)` from the compile hook so the TU itself is in the set even if `-H` formatting differs by toolchain. |
| **Thread safety** | Same lock as `ProfilesInventory.record` under `--parallel`. |
| **At report time** | `files_parsed = len(session.parsed_files)`; optional per-scope subsets for phase 3. |

**Cannot avoid TU compiles:** there is no reliable way to know which dependency headers were
**processed for Profiles** without either the compiler reporting includes (A/B) or a full
preprocessor (out of scope). Static parsing (D) without compiles does not know which includes
reached the front-end.

**Session aggregation:**

```text
files_parsed = ⋃ ( TU primary sources compiled in session )
             ∪ ⋃ ( headers/includes recorded for each of those compiles )

files_with_violations = distinct paths in inventory (already have)

tier1_pct = 100 * files_with_violations / files_parsed   (cap at 100%; subset check in tests)
```

**Optional companion stats** (not the primary tier 1 %): `translation_units_compiled`,
`translation_units_with_violations` — still useful for “how many compiles failed Profiles” but
secondary to file breadth.

Store in JSON: `files_parsed`, `files_with_violations`, `files_with_violations_pct`, methodology
`parsed_files: "include_stack_h_v1"` (or `"compiler_deps_mmd_v1"` if B lands).

**Partial builds:** `files_parsed` reflects only TUs that **ran** before abort — same honesty
banner as today’s `partial` metadata.

**Anonymization:** counts in `context.codebase` stay numeric; path lists inside optional debug
fields are stripped — not required for Overview percentages.

### What we already have (no new capture)

From the existing inventory / roll-up model:

| Metric | Source today |
|--------|----------------|
| Files with ≥1 violation | `len(rollup.files)` or distinct paths in `locations[]` |
| Unique violation lines | `rollup.unique_violation_count` / per-file `unique_line_count` |
| Per-rule references, files, lines | `rollup.rules[]` |
| Enforced profiles | `metadata.profiles_enforce` |
| Scope / partial status | `metadata.partial`, `incomplete_scopes`, `scope_count` |

**Phase 1 (violation-only context)** can ship these plus a **zero-filled rule matrix** from profile
classifier modules (`std_init.RULE_DOC_REFERENCES` keys today; generalize via
`profile_module.documented_rule_ids()`).

### What requires new capture or measurement

| Metric | Feasibility | Approach |
|--------|-------------|----------|
| **Files parsed (tier 1 denominator)** | **Doable — `-H` or `.d`** | Union of compiled TU paths and all includes the compiler reported for those compiles ([§Parsed file universe](#prof-report-parsed-files)). |
| **Files with violations (tier 1 numerator)** | **Have today** | Distinct paths in `rollup.files` / `locations[]`. |
| **Tier 1 ratio** | **Doable** | `files_with_violations_pct` = 100 × files_with_violations / files_parsed. |
| **Translation units compiled** | **Doable — compile hook** | Optional companion stat; not the primary breadth %. |
| **Source lines in violating files only** | **Doable — at report write** | `source_lines_v1` summed over violating paths — tier 2 denominator. |
| **Unique violation lines in violating files** | **Have today** | `rollup.unique_violation_count` (same set as tier 2 numerator). |
| **Tier 2 ratio** | **Doable** | `violation_line_pct_in_affected_files` = unique violation lines ÷ source lines in violating files. |
| **Source lines (all compiled TUs)** | **Optional / secondary** | Sum `source_lines_v1` over compiled TUs — session-wide density; **not** the primary tier 2 metric. |
| **Object file size as size proxy** | **Weak** — optional | Sum `.o` sizes in variant dir correlates loosely with code size but varies with debug info, LTO, platform — **not** recommended for papers; mention as fallback when sources unavailable. |
| **Logical / PP LOC** | **Impractical v1** | Needs external tools or full preprocessor — out of scope. |

### Recommended phasing

| Phase | Deliverable | Depends on |
|-------|-------------|------------|
| **1 — Rule matrix + concentration** | Overview tab (partial): headline stats, `by_rule` % share, full `std::init` rule table with zeros, link to By rule / By file | #194 merged only |
| **2 — Parsed-file denominators** | `-H` (or `.d`) include capture + compile TU hook + tier 1/2 metrics in Overview + `context.codebase` | Collector + Profiles-report-only `CXXFLAGS` |
| **3 — Per-scope context** | Scope rows on Overview when multi-variant; optional scope-level `context` in nested model | Phase 2 |

Ship **phase 1** quickly for paper drafts; phase 2 before claiming “X% of the codebase violated”
with confidence.

<a id="prof-report-loc-method"></a>

#### Source line counting (`source_lines_v1`)

**Default for phase 2 denominators:** a fast **lexical** line scan — not a C++ parser, not the
preprocessor. Goal: a stable denominator for **“how much C++-ish source could have violated?”**
— aligned with where Profiles diagnostics actually point (declarations, statements, initializers),
not build scaffolding.

**Counted (one per line, after trimming leading whitespace for classification only):**

- Non-blank lines that are not wholly comment and not preprocessor directives
- Lines with code **and** a trailing `//` comment (code portion counts as one line)

**Excluded:**

- Blank lines (empty or whitespace only)
- Whole-line `//` comments
- Lines inside `/* … */` block comments (multi-line state machine)
- **Preprocessor directive lines** — after skipping strings/comments, the first token is `#`
  (`#include`, `#define`, `#if` / `#ifdef` / `#ifndef`, `#else`, `#elif`, `#endif`, `#pragma`,
  `#line`, …). These rarely carry Profiles violations; including them inflates the denominator
  (especially include guards and header include stacks) and weakens “violations per 1k lines” /
  “2 bad lines in 10 lines of code” intuition.
- Lines that contain only `{` or `}` (optional refinement — reduces brace-only noise in dense
  formatting; document if enabled as part of v1)

**Scanner behaviour (single pass, no external tools):**

1. Track `in_block_comment` across lines.
2. On each line, skip string/char literal regions before looking for `//`, `/*`, or `#` so
   `const char* s = "http://example.com";` and `"#include <fake>"` do not mis-classify.
3. Classify `#` only when it starts a directive at line start (after whitespace) — not `#` in
   the middle of code (`int n = 1 # 2` is exotic; still count if `#` is not first token).
4. Support C++11 raw string prefixes `R"delim(… )delim"` at best effort; if ambiguous, prefer
   **over-counting** to crashing.
5. Do **not** strip `#if 0` / `#ifdef` dead branches — that requires a preprocessor; excluded
   `#if` lines still disappear from the count, but dead *code* lines inside disabled blocks remain
   (honest limit below).

**Methodology id:** store `"loc_count": "source_lines_v1"` in `context.methodology` so JSON
consumers and papers cite the exact rule. If the algorithm changes (e.g. brace-only exclusion,
`#if 0` body stripping), bump to `source_lines_v2` rather than silently changing numbers.

**Why not raw physical lines?** Blank and comment-heavy headers (license blocks, Doxygen) skew
metrics downward; excluding comments and `#` lines matches violation locality better without
calling cloc or Clang.

**Why not smarter still?** Macro-expanded LOC or attributing `#include`d body lines needs
preprocessor/frontend integration — impractical for a report collator at `sconstruct_end`.
Optional future **`source_lines_v2`** could omit lines inside `#if 0` blocks when a lightweight
PP pass is justified; not required for v1.

**Testing:** fixture pairs under `tests/fixtures/profiles_loc/` — block comments, trailing
comments, strings with `//`, blank lines, `#include` / include-guard blocks (excluded),
`#define`, raw strings — golden expected counts.

### JSON shape (additive to schema v1)

Optional top-level **`context`** — omit when not computed (legacy regen); no schema version bump
if field is optional.

```json
{
  "context": {
    "methodology": {
      "loc_count": "source_lines_v1",
      "loc_count_note": "Non-blank C++ lines; excludes //, block comments, and # directives (lexical; see plan)",
      "parsed_files": "include_stack_h_v1",
      "compile_units": "notify_progress_hook_v1"
    },
    "codebase": {
      "files_parsed": 412,
      "files_with_violations": 78,
      "files_with_violations_pct": 18.9,
      "translation_units_compiled": 240,
      "unique_violation_lines": 312,
      "source_lines_in_violating_files": 11800,
      "violation_line_pct_in_affected_files": 2.6,
      "violation_lines_per_1000_source_lines_affected": 26.4
    },
    "concentration": {
      "top_rules": [
        { "profile": "std::init", "rule_id": "ref_to_uninit", "total_references": 520, "pct_of_session_refs": 39.7 }
      ]
    },
    "profiles": [
      {
        "profile": "std::init",
        "documented_rule_count": 12,
        "observed_rule_count": 8,
        "rules": [
          {
            "rule_id": "ref_to_uninit",
            "total_references": 520,
            "unique_files": 34,
            "unique_lines": 89,
            "observed": true,
            "doc_href": "…"
          },
          {
            "rule_id": "uninit_read",
            "total_references": 0,
            "unique_files": 0,
            "unique_lines": 0,
            "observed": false,
            "doc_href": "…"
          }
        ]
      }
    ]
  }
}
```

**`summary`** remains the small CI-facing slice; agents can read `summary.by_rule` without
walking `context.profiles[]`.

### HTML / template sketch

- New template fragment `cxx_profiles_overview.html`; include from `cxx_profiles_index.html` as
  **first tab** (`#overview`), `show active` when `context` present.
- Stat cards (Bootstrap grid): **tier 1** file violation % (`files_with_violations / files_parsed`)
  plus absolute counts; **tier 2** violation line % in affected files; existing ref/rule totals.
- **Full rule matrix** table per profile: columns rule id, references, unique files, unique lines,
  % of session refs, doc link — sort by references desc, zeros visible (muted row).
- Reuse existing partials / CSS from scope stat blocks (`prof-stat-value`, monospaced paths).

Regen from JSON: rebuild Overview from `context` + `summary` + `metadata` only — no source tree
required (aligns with anonymized sharing).

### Trade-offs and honest limits

| Topic | Trade-off |
|-------|-----------|
| **Partial builds** | `files_parsed` reflects only compiles that **ran** before abort — banner must stay prominent. |
| **Tier 1** | **`files_with_violations / files_parsed`** — physical files (TUs + included headers), not TU-only. |
| **Tier 2 scope** | Denominator is **violating files only** — concentration in hot files (headers + sources). |
| **Include capture** | `-H` on report builds only; pair with **`--cxx-disable-error-limit`** for complete per-TU include logs; disable context capture → omit tier 1 % or show “not captured”. |
| **Dependencies** | Violations under `_cuppa/_download/…` inflate “files affected”; optional **`context.include_dependencies`** boolean (default true) with subtotals for project-only paths when `report_root` / include roots allow classification. |
| **Source line counting** | Lexical `source_lines_v1`: excludes blanks, comments, and `#` directives — denominator aligned with where violations attach; mis-counts rare string/comment edge cases; still no `#include` body attribution. |
| **Zero-filled rules** | Tied to **documented** rule ids in cuppa classifiers, not every possible future Clang rule — `_unclassified` row when observed but unknown. |
| **Multi-profile enforce** | Matrix repeats per profile; roll-up totals stay in `summary`. |
| **Anonymization** | Replace path lists inside `context` if any are added later; **numeric** `context.codebase` and `context.profiles[]` counts survive anonymization unchanged. |
| **Performance** | LOC scan at `sconstruct_end` reads each TU once — acceptable for typical projects; skip with `--cxx-profiles-report-context=off` if needed (open choice). |

### API sketch

| Piece | Location |
|-------|----------|
| Rule catalog | `documented_rule_ids(profile)` on each `profiles_report/profiles/*.py` module |
| Context builder | `build_report_context(inventory, env, *, compiled_sources=None)` in `report_json.py` or `context_summary.py` |
| TU collector | Compile hook records primary TU path per object build |
| Include collector | Parse `-H` lines (or `.d` prereqs) in spawn processor → `record_parsed_file(scope, path)` into a **session set** (dedupe by normalised path; separate parser from diagnostics) |
| LOC helper | `source_line_count(path, method='source_lines_v1') -> int` in `context_summary.py` |
| Writer | `wrap_report_payload(…)` adds `context` when enabled |
| CLI | Optional `--cxx-profiles-report-context=full|rules-only|off` (default `full` when flag lands) |

### Testing (when implemented)

| Layer | Cases |
|-------|-------|
| Unit | Phase 1: golden inventory → `context.profiles[].rules` includes zero rows for unobserved documented rules |
| Unit | Phase 1: `concentration.top_rules` percentages sum ≤ 100; stable ordering |
| Unit | Phase 2: mock `-H` stderr lines → `record_parsed_file` dedupes repeated paths across compiles |
| Unit | Phase 2: `source_lines_v1` fixtures (comments, blanks, strings-with-//, block comments) |
| Unit | Phase 2: missing file → omit from denominator + `methodology` note |
| Unit | HTML: Overview tab renders with `context` only (no `locations`) |
| Unit | Anonymize: `context.codebase` counts unchanged; no original path substrings in serialized JSON |
| Integration | `std-init-violations` example → non-zero TU count matches compile count |
| Docs | Antora: Overview tab / `context` JSON for papers and external summaries |

### Relationship to other slices

| Slice | Interaction |
|-------|-------------|
| **C (#194)** | Overview tab is new master-index UI; By rule / By file tabs unchanged |
| **G (anonymize)** | Compute and store `context` before anonymizing paths; Overview regen works from JSON alone |
| **E (method)** | Same context when report triggered via `env.CollateCxxProfilesIndex()` |

**Example — partial multi-variant invocation** (`profile_output_3.txt`): one scope with
`complete: false`, `variant_label: "dbg"`, no `rel` scope row (that variant never started).

**Removal behaviour (proposal):**

- When `--clean` or `--remove-builds` runs **and** the same `--cxx-profiles-report` destination,
  `link_style`, and `report_root` (or defaults) are present on the command line, remove manifest
  entries whose `invocation_key` matches and delete `session_paths` ∪ `scopes[].paths`.
- `--remove-builds` alone does **not** delete reports (artefacts live outside `_build/`).
- Document as **interim** — superseded by Phase 6 artefact roots + optional graph discovery.

**Honest limitation:** manifest matching is hacky; wrong argv or changed defaults → stale files
remain. Phase 6 should subsume this for declared `_artefacts/` trees (legacy `_artifacts/`).

## Artefacts layout and Phase 6 alignment

Default output tree (matches today’s coverage/test convention):

```text
_artefacts/cxx-profiles/
  cxx-profiles-index.html
  cxx-profiles--<sconscript_slug>--<variant>--<tc>.html
  cxx-profiles--<sconscript_slug>--<variant>--<tc>.json
```

[`removal-options.md`](removal-options.md) §4.6 sketches **`artefact_roots`** / `--remove-artefacts`
and possibly **`--set-artefacts-folder`**. This plan **does not invent** the final Phase 6 flag
names; it assumes:

1. A future **`--set-artefacts-folder=`** (or `artefact_roots` in `sconstruct`) redirects
   `_artefacts/` (or subfolders; legacy `_artifacts/` when present) for all cuppa-generated reports.
2. **`--cxx-profiles-report`** respects that root when set.
3. Built-in report types (test, coverage, cxx-profiles) register under a shared
   **`cuppa.reports`** registry so artefact listing can mention them consistently.

Until Phase 6 ships, default Profiles output is `{artefacts_root}/cxx-profiles/` (default
`_artefacts/cxx-profiles/`), matching coverage’s conventional tree today.

## Built-in “reports” registration (sketch)

Silently register report producers when cuppa loads (no sconscript edit):

| Report | Trigger today | Trigger after this plan |
|--------|---------------|-------------------------|
| Test HTML | `env.GenerateHtmlTestReport` + collate | unchanged |
| Coverage | `--cov --test` + collate methods | unchanged |
| C++ Profiles | — | `--cxx-profiles-report` |

Registry records: `kind`, default subdir, CLI flag, manifest kind string. Enables future
`--list-available-reports` / doc samples in [`colourised-doc-samples.md`](colourised-doc-samples.md).

## Work slices

Slice **letters** (A–H) are shorthand in tables; **`prof-report-*` ids** are the stable names for
issues, PR titles, and ROADMAP cross-links (same pattern as `list-tc-*` in
[`list-toolchains-verbose.md`](list-toolchains-verbose.md)).

| Letter | Id | Deliverable | Notes |
|--------|-----|-------------|-------|
| **A** | `prof-report-parser` | `cuppa/cpp/cxx_profiles_report.py` — parse, normalise, classify; `ProfilesScope` type; `scripts/replay_profiles_capture.py`; `scripts/regenerate_profiles_report.py` (capture → HTML/JSON without rebuild) | Fixture strings from samples; scope-aware dedupe keys; Progress replay smoke |
| **B** | `prof-report-collector` | Progress callback **and** per-action `env` → `SpawnedProcessor`; thread-safe session store | Includes former slice F; do not ship collector without spawn scope |
| **C** | `prof-report-html` | Jinja templates + `CxxProfilesReportBuilder` at `sconstruct_end` | By rule / By file / Roll-up tabs; `link_style`; incomplete scope banner |
| **D** | `prof-report-manifest` | `.cuppa-reports` schema v1; matched `--clean` / `--remove-builds` | `invocation_key`, `partial`, path union |
| **E** | `prof-report-method` | `env.CollateCxxProfilesIndex()` + CLI parity | Merged [#198](https://github.com/ja11sop/cuppa/pull/198); see [§Method naming](#prof-report-method-naming) |
| **F-min** | `prof-report-artefacts-min` | Registry + `--list-available-reports` + British `--artefacts-root` | Merged [#198](https://github.com/ja11sop/cuppa/pull/198); judgement tree lists methods / CLI / toolchains |
| **F** | `prof-report-artefacts` | `artefact_roots` / `--remove-artefacts` when #135 lands | Supersedes manifest hack for declared trees; full wipe deferred to #135 |
| **G** | `prof-report-anonymize` | Anonymize saved report JSON; shareable artefact + HTML regen without sources | After C; see [§Anonymized report sharing](#prof-report-anonymize) |
| **H** | `prof-report-context-summary` | Overview tab + `context` JSON — violations vs codebase size, full rule matrix; variant roll-up; By-Build tab; unified scope detail | After C; see [§Context summary](#prof-report-context-summary); landed on [#196](https://github.com/ja11sop/cuppa/pull/196) |
| **—** | `prof-report-method-semantics` | Implied `-i`, Progress decoupling, selective exit | **Shipped [#203](https://github.com/ja11sop/cuppa/pull/203)** — [#199](https://github.com/ja11sop/cuppa/issues/199); see [§Collate index semantics](#prof-report-method-semantics-slice) |
| **—** | `prof-report-scope-filter` | Method-only index filter (union of declaring sconscripts) | **Proposal** — see [§Collate index scope filter](#prof-report-scope-filter-slice) |

Target cycle: **1.8.0** for **`prof-report-parser` … `prof-report-manifest`** (slice A–D; **`prof-report-collector` must** include parallel spawn scope); **E** + **F-min** merged [#198](https://github.com/ja11sop/cuppa/pull/198); full **F** blocked on #135; **G–H** shipped; **`prof-report-method-semantics`** shipped [#203](https://github.com/ja11sop/cuppa/pull/203); **`prof-report-scope-filter`** next follow-on.

**Tracking:** Umbrella [#184](https://github.com/ja11sop/cuppa/issues/184) closed after **E** + **F-min** ([#198](https://github.com/ja11sop/cuppa/pull/198)). Collation semantics [#199](https://github.com/ja11sop/cuppa/issues/199) shipped [#203](https://github.com/ja11sop/cuppa/pull/203); scope filter follow-on [§Collate index scope filter](#prof-report-scope-filter-slice). Land slices as **multiple PRs** (cite letter and/or `prof-report-*` id).

## Refusal rules

| Request | Response |
|---------|----------|
| Auto-fix sources from the report | Out of scope — report is read-only |
| `--cxx-profiles-report` without Profiles enabled | StopError |
| Invent rule ids not in Clang docs | Use `_unclassified`; file issue to extend table |
| Silent mis-attribution under `-j` | Refuse — ship spawn scope in **`prof-report-collector`** (slice B) |
| Assign diagnostics to wrong variant without `_unscoped` fallback | Refuse |
| MSVC Profiles diagnostics in v1 | StopError or empty report with notice until interpretor exists |

## Testing

| Layer | Cases |
|-------|-------|
| Unit | Parser regex; normalisation; pattern→rule map; **scope-aware** dedupe counts; JSON schema |
| Unit | Progress stack push/pop; replay `profile_output_2.txt` / partial multi-variant `profile_output_3.txt` sequences |
| Unit | JSON view models (by rule / by file / roll-up); link URI generation for `local` and `gitlab` |
| Unit | Manifest read/write; `invocation_key` includes `options`; `partial` + `complete` flags; path union for delete |
| Unit | Spawn scope derivation from mock action `env`; thread-safe collector merge |
| Unit | Context summary: zero-filled rule matrix; TU/LOC denominators when compile hook present |
| Integration | `--list-available-reports` on generated project; canonical `_artefacts/` collate wiring (`test_available_reports`) |
| Integration | Profiles report under `--parallel` with two variants (or mocked interleaved spawns) |
| Integration | `--clean` with matching flag removes manifest paths |
| Docs | Antora page section under [`cxx-profiles.adoc`](../../docs/modules/ROOT/pages/cxx-profiles.adoc); CHANGELOG under open `[1.8.0]` |

## Documentation updates (when implemented)

- Antora: **done** on [#196](https://github.com/ja11sop/cuppa/pull/196) — `report-introduction.adoc` (feature entry), tab guides (`report-overview`, `report-by-rule`, `report-by-file`, `report-by-build`, `report-by-sconscript`, `report.adoc` index), hub updates in `cxx-profiles.adoc`; **Union Refs** / **Peak Refs** / **Build Refs** vocabulary aligned with UI.
- Antora: **done** on [#197](https://github.com/ja11sop/cuppa/pull/197) — `report-introduction.adoc#sharing-anonymized` (*Sharing an inventory (anonymized JSON)*); hub regen table documents `--anonymized`.
- Antora: **done** on [#203](https://github.com/ja11sop/cuppa/pull/203) — inventory mode on `cxx-profiles.adoc` and `report-introduction.adoc`; `integration/test-available-reports.adoc` drops manual `-i`.
- Optional: sample HTML screenshot via [`colourised-doc-samples.md`](colourised-doc-samples.md) pipeline.
- [`archive/cxx-profiles.md`](../archive/cxx-profiles.md): link this plan in follow-ons (already
  cites dedupe/report in §2.3).
- AGENTS.md consumer tip: `--cxx-profiles-report` one-liner next to coverage commands.

## Progress snapshot

| Slice | Status |
|-------|--------|
| Plan | **This document** |
| A — `prof-report-parser` | **Done** — merged [#190](https://github.com/ja11sop/cuppa/pull/190) |
| B — `prof-report-collector` | **Done** — merged [#191](https://github.com/ja11sop/cuppa/pull/191) |
| B½ — `prof-report-parser-layers` | **Done** — merged [#192](https://github.com/ja11sop/cuppa/pull/192) |
| B½-doc — `doc-folder-layout` | **Done** — merged [#193](https://github.com/ja11sop/cuppa/pull/193) |
| C — `prof-report-html` | **Done** — merged [#194](https://github.com/ja11sop/cuppa/pull/194): HTML index/scope/source pages, By rule / By file / Roll-up tabs, presentation polish, rule `doc_href` links, JSON regen (`--from-json`), **schema v1** envelope (`summary`, `locations[]`, `location_key`, extended `metadata`) |
| D — `prof-report-manifest` | **Done** — core in [#194](https://github.com/ja11sop/cuppa/pull/194); clean/`invocation_key` fix in [#195](https://github.com/ja11sop/cuppa/pull/195); `--artifacts-root` in `e4d5318` |
| H — `prof-report-context-summary` | **Done** — merged [#196](https://github.com/ja11sop/cuppa/pull/196): Overview tab, `context` JSON, `-H`, tier metrics, Build inventory load, [variant roll-up display](#prof-report-variant-roll-up-display) (**Union Refs**, **Peak Refs**, common + deltas, `build_key` grain), **Violations By-Build** tab, unified scope detail (**Profile** column), Antora doc split |
| G — `prof-report-anonymize` | **Done** — merged [#197](https://github.com/ja11sop/cuppa/pull/197): thematic anonymiser + verify + metadata-driven HTML headers |
| E — `prof-report-method` | **Done** — merged [#198](https://github.com/ja11sop/cuppa/pull/198): `env.CollateCxxProfilesIndex()`, CLI parity, default `<artefacts-root>/cxx-profiles/` |
| F-min — `prof-report-artefacts-min` | **Done** — merged [#198](https://github.com/ja11sop/cuppa/pull/198): registry, `--list-available-reports` judgement tree (`{artefacts_root}` / `{build_root}` in-tree), British `--artefacts-root`, default `_artefacts` |
| F — `prof-report-artefacts` | **Blocked on #135** — full `artefact_roots` / `--remove-artefacts`; F-min covers discovery only |
| `prof-report-method-semantics` | **Shipped** — [#203](https://github.com/ja11sop/cuppa/pull/203) / [#199](https://github.com/ja11sop/cuppa/issues/199) |
| `prof-report-scope-filter` | **Proposal** — see [§Collate index scope filter](#prof-report-scope-filter-slice) |

**Next focus:** **`prof-report-scope-filter`** (method-only write-time filter); full **F** when [#135](https://github.com/ja11sop/cuppa/issues/135) Phase 6 starts.

## Open questions (resolve in first PR)

1. **Partial builds:** if only one scope ran, omit master index or embed detail inline?
2. **Dependency paths:** `--cxx-profiles-report-root=` vs absolute-only links for `_cuppa/_download/…` trees?
3. **Report-only exit code:** optional `--cxx-profiles-report-allow-errors` if inventory runs should succeed?
4. **Cross-variant roll-up:** session **union** for headline / Overview (settled); By-Rule / By-File show **per-build Hits + common/delta** display ([§Variant roll-up display](#prof-report-variant-roll-up-display)) — Antora documents both.
5. **GitHub `link_style`:** → **Settled** — shared helper in `link_style.py`; per-repo **`remote`**
   style tracked in [#216](https://github.com/ja11sop/cuppa/issues/216).
6. **`_unscoped` bucket:** when spawn scope cannot be derived, record under session `_unscoped` with warning in HTML — never guess variant.
7. **Implied `-i`:** → **Settled yes** — [#199](https://github.com/ja11sop/cuppa/issues/199) / [§Collate index semantics](#prof-report-method-semantics-slice).
8. **Progress vs failed compiles:** → **Settled yes** — Progress decoupling + fallback flush — [#199](https://github.com/ja11sop/cuppa/issues/199).
9. **Method-only scope filter:** → **Settled** — union of declaring sconscripts, write-time filter, filtered metrics, CLI full tree — [§Collate index scope filter](#prof-report-scope-filter-slice).
10. **Per-scope `CxxProfilesReport()`:** when to introduce per-scope HTML/JSON and wire `CollateCxxProfilesIndex( sources )` — see [§Method naming](#prof-report-method-naming).

## Parser layering follow-on (`prof-report-parser-layers`)

Slice A shipped a deliberate v1 shortcut: Alliance Clang line shape parsing and a flat
``std::init`` message→rule table live together in ``cuppa/cpp/cxx_profiles_report.py``.
Slice B smoke (serial and ``--parallel``) validates capture and scope; rule attribution still
assumes ``std::init`` prose even though the **profile name** is parsed from
`` under profile '…'`` and grouped correctly in the inventory.

Land **before slice C HTML** so doc links and rule sections live in profile modules, not in the
generic report builder.

**Status (2026-08-12):** merged [#192](https://github.com/ja11sop/cuppa/pull/192) — package layout below,
profile-keyed ``classify_rule``, multi-file ``examples/profiles/std-init-violations/`` covering
all twelve documented ``std::init`` rules, ``std_init_golden.json`` refreshed from Alliance Clang
capture (``destroy_uninit`` / ``double_destroy`` golden lines use documented wording until the
snapshot emits them live), and ``parse_clang`` handles messages that embed ``under profile '…'``
before a trailing clause.

### Target layout

| Module | Responsibility |
|--------|----------------|
| ``cxx_profiles_report.py`` (or ``profiles_report/inventory.py``) | Scope, dedupe, ``ProfilesInventory``, replay, JSON view model — **no rule tables** |
| ``profiles_report/parse_clang.py`` | Clang ``: error: … under profile '…'`` line detector → path, message, **profile** |
| ``profiles_report/profiles/std_init.py`` | ``std::init`` classifiers, P4222 / ProfilesFramework.rst doc anchors |
| *(future)* ``parse_gcc.py``, ``profiles/std_type.py``, … | New compiler shapes and profile rule sets |

**Dispatch:** ``parse_profiles_diagnostic(line, compiler='clang')`` then
``classify_rule(profile, normalised_message)`` — classifiers are keyed by profile, not one
global tuple.

### Spec-driven fixtures (not smoke-only)

Add ``examples/profiles/std-init-violations/`` (name illustrative): minimal C++ that deliberately
violates each documented ``std::init`` rule (including rows not seen in consumer smoke, e.g.
``uninit_read``, ``destroy_uninit``). Workflow:

1. Build with Profiles-capable Clang + ``--cxx-profiles-enforce=std::init``.
2. Capture diagnostic lines into ``tests/fixtures/profiles_capture/`` (one snippet or golden file
   per rule id).
3. Unit tests assert each golden line → expected ``(profile, rule_id)``.

Automation (CI integration test comparing live build to golden) can follow; manual capture once
is enough to expand the classifier table beyond observed production trees.

### Refusal rules (unchanged)

- Unknown message under a known profile → ``_unclassified`` with raw text preserved.
- Unknown compiler line shape → ignore (or empty bucket + notice until a parser exists).
- Do not map ``std::init`` patterns onto other profile names without an explicit classifier module.
