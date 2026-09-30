# Plan: terse build output with coloured progress (`--terse-output`)

- **Status:** in progress
- **Related:** [`ROADMAP.md`](../../ROADMAP.md) — Build console output (`console-terse-output`); channel map [`console-channels.md`](console-channels.md); companion [`native-toolchain-output.md`](native-toolchain-output.md); `cuppa/progress.py`; [`archive/console-report-patterns.md`](../archive/console-report-patterns.md)
- **Updated:** 2026-09-30
- **Impact:** minor — new opt-in CLI flag; default build output unchanged

## Mode note (plan vs agent)

Capture **hierarchical counts and percentages** in this document now (Phase 2 below) so Phase 1
does not paint us into a corner. **Agent mode** is enough to land that plan text. Switch to **plan
mode** only if you want a longer design session before slice B — for example weighting rules,
whether spawn completion is an acceptable proxy for “target done”, or splitting Phase 2 into its
own issue/PR.

## Why

`--minimal-output` hides toolchain noise but still prints **every command line** and full
diagnostic blocks when they appear. For large parallel builds the console becomes a wall of
`Progress( … )` descriptions and compiler invocations.

Readers familiar with CMake/Ninja-style summaries want:

- A **short coloured status line per action** (success emphasised).
- **Command lines and full tool output only on failure or warning** (or on explicit verbose).
- Cuppa progress ordering preserved (variant begin → per-target → finish).

This is **not** a CMake clone: cuppa keeps SCons graph semantics, variant scoping, and existing
`NotifyProgress` dependency chains.

**Related (separate plans):** configure-time log noise
([`build-log-hygiene.md`](build-log-hygiene.md)); version without a build
([`cuppa-info.md`](cuppa-info.md)). Those are **1.12.0** targets alongside terse Phase 1 — not
slices of this document.

## Goals

1. Add **`--terse-output`** (name settled here; not `--simple-output` — too vague).
2. On success: one line per completed tool run —
   `[ok] sconscript · variant · action file`.
3. On failure or warning: the same line with `[error]` or `[warn]`, then the command and the
   tool output (respect `--native-output` / default interpretors per companion plan).
4. Keep **`NotifyProgress` graph** unchanged — only change what `progress_action` / post-spawn
   summary prints.
5. Document vs `--minimal-output`, `--verbosity`, and CI usage.

## Non-goals (Phase 1)

- Replacing SCons `-Q` / silent mode globally.
- **Nested percentage rollup** (sconscript / variant / target) — Phase 2 below; Phase 1 must not
  block it.
- ETA or time remaining.
- Terse mode for **`--list-*` / wipe / removal reports** (those keep judgement trees).
- Suppressing cuppa `logger.error` routing notices.

## Current behaviour (baseline)

| Component | Today |
|-----------|--------|
| `NotifyProgress` | Inserts `Begin` / `Starting` / `Finished` / `End` action nodes; SCons prints `Progress( … )` when `logging.INFO` |
| `ToolchainProcessor` | Filters lines when `--minimal-output`; adds error/warning banners |
| Spawn summary | `processor.summary(returncode)` after child exits |
| `--minimal-output` | Hides non-classified lines; still shows commands via SCons |

Measure baseline line counts on `examples/minimal` and one integration fixture before claiming
improvement.

## Settled behaviour

| Event | Terse output |
|-------|----------------|
| Clean tool run | `[ok] sconscript · variant · action file`. Optional `{counts}` prefix stays empty until Phase 2 |
| Tool run fails | The command, processed output, and summary, then the `[error]` line. The status line is the summary of the failure |
| Warning in tool output | The command and warning lines, then the `[warn]` line |
| Sconstruct / sconscript begin/end | Hidden under `--terse-output`. Printed again with `--terse-output-notify-progress` |
| Configure / list actions | Unaffected — flag applies to **build/test/coverage** progress only |

### Status line

```text
[error] test/orders · gcc16_dbg_x86_64_cxx2c · link buy_sell_ladder
```

| Field | Spelling | Colour |
|-------|----------|--------|
| Status | `[ok]`, `[warn]`, or `[error]` | success / warning / error |
| Sconscript | Script path with a leading `./` removed. A trailing `/sconscript` is dropped (`./test/orders/sconscript` → `test/orders`). A named script keeps its stem (`widget/tests.sconscript` → `widget/tests`). Empty when the script is the project-root `sconscript`. Only the leaf is coloured (`orders` in `test/orders`); any leading path is subdued | subdued path, info leaf |
| Variant | `toolchain_variant_arch_abi` (`gcc16_dbg_x86_64_cxx2c`). `dbg` alone is ambiguous across sconscripts. The variant name (`dbg` / `rel` / `cov`) stays plain; the rest of the cell is subdued | subdued, variant name plain |
| Action | See the table below. Uncoloured | plain |
| File | A `·` separates the action from the path. `compile`, `compile-*`, `markdown`, and `asciidoc`: the source in the project tree, not the variant `working/` copy. Only files that exist in the source tree — products and intermediates stay basenames. A source outside the project is `~/...` when it is under the home directory (forward slashes on Linux and Windows), otherwise absolute. Never a `../` climb. The directory is subdued and the filename is emphasised. `copy`, `expand`, `render`, and a redirected `run`: `source → dest`. The source path is subdued. The destination directory is subdued and its filename is info and bold. `<working>/` and `<final>/` mark this variant's build locations. `<artifacts>/` is only this variant's folder under the artefacts root (`_artifacts/<sconscript>_<variant>/...`); any other path there is written as itself (`_artifacts/documentation/...`). A real project path has no such prefix. Link, archive, index, and a program `run` stay the product basename, emphasised | see the cell |

A compile shows the source, not the object, so `database.cpp` is not confused with another sconscript's `database.o`. Link, archive, and index show the product name, because the inputs already had their own lines. A `compile-*` label (for example `compile-scss`) shows the source the same way. `markdown` and `asciidoc` do too. `copy`, `expand`, `render`, and a redirected `run` show `source → dest`.

### How an action word is chosen

`CompileStatic` and `BuildStaticLibrary` fan out into several processes. The spawn does not carry the Cuppa method name. Spell each line in this order:

1. **Explicit label** on the product node (`node.attributes.cuppa_terse_action`), set by the method that created that one action. Do not put a label on a node that has two tool actions. A static library is both `archive` and `index`; one label would hide the second.
2. **The active toolchain** — `spell_terse_action(command, target)` on `Gcc`, `Clang`, and `cl`. Empty means "not my tool". Gcc and Clang share `cuppa/toolchains/terse_actions.py` because `gcc-ar-16` / `gcc-ranlib-16` and `llvm-ar` / `llvm-ranlib` are the same kinds of name. `cl` uses the same helper for `cl`, `lib`, and `link`.
3. **Generic fallback** — the same tool speller when the toolchain has no method, then `run`.

`run` is the fallback, not `link`. An unrecognised command used to become `link`, so `pysassc`, Python, and CMake would all look like links.

| Spelling | When |
|----------|------|
| `compile` | `-c` / `/c`, or an object target (`.o`, `.obj`, `.os`) |
| `archive` | `ar`, `lib`, `gcc-ar`, `gcc-ar-16`, `llvm-ar`, or any `*-ar` / `*-ar-<version>`, writing a `.a` / `.lib` |
| `index` | The tool name contains `ranlib` (`ranlib`, `gcc-ranlib-16`, `llvm-ranlib`). This is the second line for one `.a`. The version suffix must not win: taking only the text after the last hyphen turned `gcc-ranlib-16` into `16`, and the `.a` suffix then said `archive` |
| `link` | Compiler driver (`g++`, `g++-16`, `clang++`, `cl`, `link`) producing a program |
| `link-shared` | A `.so`, `.dylib`, or `.dll`, or `-shared` / `/dll` |
| `run` | Anything else that nobody named |

### Method labels

Toolchain children stay unlabelled. `Compile`, `CompileStatic`, `CompileShared`, `Build`, `BuildLib`, `BuildTest`, `BuildBenchmark`, `HeaderUnit`, `Module`, and `ImportModules` create objects, archives, and programs. The toolchain spells those processes.

These methods do not create an action node, so they have no status line: `BuildWith`, `BuildProfile`, `CxxProfiles`, `CxxLto`, `CxxErrorLimit`, `StdCpp`, `ReplaceFlags`, `RemoveFlags`, `Variant`, `Toolchain`, `HasToolchain`, `Use`, `HasDependency`, `TargetFrom`, `PackageDir` / `PackageBin` / `PackageLib` / `PackageVersion` / `CMakePrefixPathFor`, `Filter`, `Glob` / `RecursiveGlob`, `Modules`, `CollateCxxProfilesIndex`, `Reports`.

| Method | Label | Notes |
|--------|-------|-------|
| `CompileScss` | `compile-scss` | Source path, same as `compile` |
| `Run` | `run`, `test`, or `benchmark` | Whichever variant action is selected |
| `Test` | `test` | |
| `Benchmark` | `benchmark` | |
| `RunAndRedirectToFile` | `run` | `program → output`. A plain `Run` stays the program name |
| `CopyFiles`, `CopyFilesAs`, `StageLocationDevelop` | `copy` | `source → dest`, with `<working>`, `<final>`, or `<artifacts>` |
| `MarkdownToHtml` | `markdown` | Source path, same as `compile` |
| `AsciidocToHtml` | `asciidoc` | Source path, same as `compile` |
| `RenderJinjaTemplate` | `render` | `source → dest` |
| `ExpandTemplateFile` | `expand` | `source → dest` |
| `CreateVersion` | `version` | The generated file, not the later compile of it |
| `CMakeConfigure` | `cmake-configure` | |
| `CMakeBuild` | `cmake-build` | |
| `CMakeInstall` | `cmake-install` | |
| `DownloadExtract` | `download` | |
| `RemoveEmptyDirs` | `remove-empty` | |
| `Coverage` | `coverage` | |
| `CollateCoverageFiles` | `collate-coverage` | |
| `CollateCoverageIndex` | `coverage-index` | Not `index` — that word is the archiver |
| `PublishPackage` | `package`, then `publish` when uploading | Two nodes |
| `InstallPackage` | `install` | |

The label is stored on the product node. A spawned tool reads it when the child exits.

### Python actions

SCSS, copy, CMake, `Run`, and the other labelled methods are SCons `FunctionAction`s. They do not go through the spawn processor. SCons prints their description, then calls them, and only then knows the return value. Their own `print` and log lines appear while they run. Buffering that output globally is unsafe under `-j`, so it stays live.

`--terse-output` installs a wrapper on those actions (`enable_terse_python_actions`). Any other mode does not: the original callable runs and the wrapper is not consulted. The wrapper swaps `execfunction` after SCons has stored the action signature, so turning the flag on does not rebuild the tree.

| Result | What is printed |
|--------|-----------------|
| Success | `[ok]` line only. The SCons description stays hidden |
| Failure or exception | Whatever the action already wrote, then its description, then the `[error]` line |
| Clean child tool | Hidden. The action notes the command and its lines; a clean note is dropped |
| Child warning or error | The child command and its lines, then `[warn]` or `[error]`. A line containing `: ERROR:` is an error even when the tool exits 0. The action's return code is unchanged |
| `Install file:` / `Install directory:` | `copy`, and hidden on success. `env.Install` is wrapped so the sentence is not flushed later |
| `Progress(...)` | Still hidden. The wrapper does not touch those actions |
| Shell command (`g++`, `ar`, `ranlib`) | Unchanged spawn path: command and captured output, then the status line |

Text the action prints itself still appears as it happens. Only a child handed to `note_terse_child` is held back. `asciidoctor` does that. An unlabelled `asciidoctor` command is spelled `asciidoc`.

`None`, `0`, and any other falsy return are success, matching SCons. A truthy return or an exception is failure. `KeyboardInterrupt` and `SystemExit` propagate with no status line.

**Interaction:** `--terse-output` implies quieter success paths; it does **not** imply
`--minimal-output`. Combining both should be documented (likely: terse success lines + minimal
diagnostic filtering on failures only).

## Implementation sketch (Phase 1)

| Area | Likely touch |
|------|----------------|
| CLI | `cuppa/core/base_options.py` — `--terse-output` |
| Env | `construct.py` — `cuppa_env['terse_output']` |
| Progress | `cuppa/progress.py` — `PRINT_CMD_LINE_FUNC`; `--terse-output-notify-progress` prints the lines |
| Spawn | `output_processor.py` — buffer child lines; one success line, or reprint the command |
| Tests | Unit: stash, success, warning, failure; integration: clean compile hides the command |

**Phase 1 reporter** is the functions in `cuppa/progress.py`: `terse_counts_prefix`,
`format_terse_line`, `spell_terse_action`, `render_terse_spawn`, and `terse_print_cmd_line`.
Phase 2 fills `terse_counts_prefix()` (empty in Phase 1) and does not rewrite the status line.
Do not key human text off the `Progress(...)` description.

### Progress lines

`--terse-output` hides SCons `Progress(...)` lines. `--terse-output-notify-progress` prints
them again, so the sconscript and variant structure can be compared without editing code. The
notify flag requires `--terse-output`.

`-Q` already omits the lines: `progress_action` only builds the description when the logger is
at info. The flag matters on a normal info-level build. Parallel (`-j`) interleaves the
structure, which is why it stays opt-in.

---

## Phase 2 — hierarchical progress (counts and percentages)

### What you asked for

Example layout: 4 sconscripts (projects), 3 variants each, 38 tracked actions per
(sconscript, variant) cell — show **where we are** at each level, e.g.

```text
scripts 2/4 · variants 1/3 · actions 35/38 · overall 68%
[ok] test · gcc15_dbg_x86_64_cxx2c · compile main.cpp
```

Nested bracket intuition `[66%][33%][92%]` is useful mentally, but **do not multiply level
percentages** for an “overall” bar — levels are not independent stages. Prefer a **single honest
rollup**:

```text
overall = completed_actions / total_actions   (all active sconscript × variant cells)
```

Optional secondary fields: `scripts i/N`, `variant j/M` (within current sconscript), `actions k/T`
(within current variant cell).

### What cuppa already knows

| Level | Today | Gap |
|-------|-------|-----|
| Sconstruct | `sconstruct_begin` / `sconstruct_end` sentinels | — |
| Sconscript | `Begin` / `End` per `env['sconscript_file']` | No “2 of 4 scripts” until we count active scripts |
| Variant | `Starting` / `Finished` keyed by `parent(build_dir)` (includes sconscript segment) | No “1 of 3 variants” until we count variants for that script |
| Target / action | `NotifyProgress.add(env, nodes)` on method outputs | **No per-action completion event** — only dependency ordering |

So hierarchy **display** is feasible; **per-action completion** needs new instrumentation.

### SCons / cuppa constraints (honest)

1. **Graph is declarative.** Totals can be accumulated during `NotifyProgress.add()` once we define
   what counts as one “action” (each registered node vs each spawn — see below).
2. **Parallel builds.** Actions finish out of order; show `35/38 completed`, not “now building step
   35”.
3. **Sentinel progress nodes ≠ compile actions.** `Starting`/`Finished` bracket a variant; they do
   not fire once per object file. Per-target progress cannot reuse those events alone.
4. **Completion signal (pick in Phase 2 PR):**

   | Source | Covers | Misses |
   |--------|--------|--------|
   | **A. Spawn wrapper exit** (`output_processor`) | Compile/link/test processes cuppa spawns | Pure Python `Action`s, some installers |
   | **B. Wrap `NotifyProgress.add` + SCons `Command`/`Action` post-hooks** | Theoretically everything | Invasive; easy to miss a builder path |
   | **C. SCons task progress / `-Q` integration** | Whatever SCons counts | Fights cuppa’s custom spawn; version-dependent |

   **Recommendation:** start Phase 2 with **A + ledger populated in `add()`**, document gaps for
   non-spawn actions; revisit **B** only if gaps matter in practice.

5. **Script order.** “Project 2 of 4” follows **active `--scripts` order**, not filesystem order,
   unless we deliberately sort — state the rule in docs.

### Phase 2 slices (after Phase 1 terse lines ship)

| Slice | Deliverable |
|-------|-------------|
| F | **`ProgressLedger`** — register totals per (sconscript, variant) in `NotifyProgress.add` |
| G | **`action_done` hook** — increment on successful spawn (and optionally other hooks) |
| H | **Terse line prefix** — `scripts i/N · variant j/M · actions k/T · overall P%` |
| I | **Docs + integration** — multi-sconscript fixture; parallel build still monotonic counts |

Optional later: `--progress-format=nested|flat|overall-only`.

### Phase 1 must not foreclose Phase 2

- Terse formatting goes through **one reporter**, not ad hoc `print` in spawn and progress.
- Success lines reserve an optional **leading counts segment** (empty in Phase 1 is fine).
- Do not key human-readable progress off SCons `Progress( … )` description strings — they change.

---

## Work slices (Phase 1)

| Slice | Deliverable | Notes |
|-------|-------------|-------|
| A | Design + issue | This document |
| B | `--terse-output` flag + env | No behaviour yet; docs stub |
| C | Success one-liner | Hook finish event; colour via existing `colourise` |
| D | Failure path parity | Ensure commands + diagnostics still visible |
| E | Integration + docs | Compare before/after transcript in Antora or design note |
| F–I | Hierarchical counts / overall % | Phase 2 — see above; separate PR after Phase 1 |

## Refusal rules

| Request | Response |
|---------|----------|
| Terse as default | Refuse; opt-in |
| Terse for `--list-dependencies` trees | Refuse; reports are already structured |
| Drop `NotifyProgress` for a spinner | Refuse; graph ordering is the product |
| Hide failures to keep terse | Refuse |
| Multiply level percentages for “overall” | Refuse; use completed/total actions |
| Promise sequential “step 35 of 38” under `-j` | Refuse; counts are completion tallies |

## 1.8.0 candidacy

| Factor | Assessment |
|--------|------------|
| User value | High for large projects |
| Risk | Medium — touches progress + spawn + logging |
| Size | Phase 1 medium; Phase 2 medium+ |
| Depends on | None strictly; cleaner alongside native output plan |

**Suggested:** **1.8.0 target** — ship **Phase 1 (slices A–E)** in the 1.8.0 bundle (see ROADMAP
§1.8.0 cycle focus). **Phase 2 (F–I)** can be 1.8.0 follow-on or 1.9.0 depending on ledger/spawn
hook effort. Prefer terse Phase 1 over native output if scope is tight.

## Related

- [`colourised-doc-samples.md`](../archive/colourised-doc-samples.md) — semantic HTML for reports, not live build log.
- Scratchpad **stderr vs stdout** — validate before any global stream split.
