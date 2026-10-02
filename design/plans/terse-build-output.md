# Plan: terse build output with coloured progress (`--terse-output`)

- **Status:** done
- **Related:** [`ROADMAP.md`](../../ROADMAP.md) — Build console output (`console-terse-output`); channel map [`console-channels.md`](console-channels.md); companion [`native-toolchain-output.md`](native-toolchain-output.md); `cuppa/progress.py`; [`archive/console-report-patterns.md`](../archive/console-report-patterns.md)
- **Updated:** 2026-10-02
- **Impact:** minor — new opt-in CLI flag; default build output unchanged

## Mode note (plan vs agent)

The flag, the status line, and the tally are done together on [#353](https://github.com/ja11sop/cuppa/pull/353).
One action is one status line that is not a child of another. The prefix is that line's
sconscript and variant (`35/38`) and one overall percent. Up-to-date actions count as already
done. A `scripts i/N · variants j/M` position was declined: it does not survive `-j`.

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
([`cuppa-info.md`](cuppa-info.md)). Those are **1.12.0** targets alongside this flag — not
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

## Non-goals

- Replacing SCons `-Q` / silent mode globally.
- A `scripts i/N · variants j/M` position, or multiplying those level percentages. The cell
  fraction and the whole-build percent are done with the flag. That position sketch is not.
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
| Clean tool run | `35/38 · 68% [ok] sconscript · variant · action file`. The fraction is this sconscript and variant. The percent is the whole build. Actions SCons has already found up to date are included in both |
| Tool run fails | The command, processed output, and summary, then the `[error]` line. The status line is the summary of the failure |
| Warning in tool output | The command and warning lines, then the `[warn]` line |
| Sconstruct / sconscript begin/end | Printed, as without the flag. `-Q` omits them |
| Configure / list actions | Unaffected — flag applies to **build/test/coverage** progress only |

The percent is actions accounted for in this process, out of the actions that are going to
run. It starts at zero every run. A line that still has to run adds one when it prints. A
node SCons finds already built adds its remaining actions when it is visited, and that visit
does not print. With `--parallel`, the first lines show a low percent when the workers are
still on nodes that need building, and a high percent when they reach nodes left built by the
previous run. A later run therefore does not open at the previous percent. If most of the
graph is already built, those workers are likely to count it quickly. If little is built, the
opening lines can stay near zero until the walk reaches the built nodes. The closing
`reached` line is that same ratio once the jobs have returned.

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
| File | A `·` separates the action from the path. `compile`, `compile-*`, `markdown`, and `asciidoc`: the source in the project tree, not the variant `working/` copy. Only files that exist in the source tree — products and intermediates stay basenames. A source outside the project is `~/...` when it is under the home directory (forward slashes on Linux and Windows), otherwise absolute. Never a `../` climb. The directory is subdued and the filename is info and bold. `copy`, `expand`, `render`, and a redirected `run`: `source → dest`. The source path is subdued. The destination directory is subdued and its filename is info and bold. `<working>/` and `<final>/` mark this variant's build locations. `<artifacts>/` is this variant's artefact location: the flat folder `_artifacts/<sconscript>_<variant>/...`, or a report path whose variant offset is `gcc16_dbg_x86_64_cxx2c/<sconscript>` even when a prefix such as `test/` sits in front. Any other path under the artefacts root is written as itself (`_artifacts/documentation/...`). A real project path has no such prefix. Link, archive, index, and a program `run` stay the product basename, emphasised | see the cell |

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
| SCons builder | Named from the command. `tar` and `gtar` are `tar`. `zip` and `zip_builder(...)` are `zip`. `Textfile` and `Substfile` are both `text`, because both print `Creating '...'`. `CopyAs` and `CopyTo` (`Copy file(s):`) are `copy`. `jar`, `javac`, `javah`, `rmic`, `m4`, `swig`, `rpcgen`, `latex`, `pdflatex`, `tex`, `pdftex`, `dvips`, `dvipdf`, `gs`, `bibtex`, `biber`, and `makeindex` use that tool's name. `flex` is `lex`, `bison` is `yacc`, and `rpmbuild` is `rpm`. This is decided before `-c`, so `tar -c` is not a compile |

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
| Failure or exception | Whatever the action already wrote, then its description, then the `[error]` line. SCons' default `Name([...])` dump is not that description. A test names the program, not its log |
| Clean child tool | Hidden. The action notes the command and its lines; a clean note is dropped |
| Child warning or error | The child command and its lines, then `[warn]` or `[error]`. A line containing `: ERROR:` is an error even when the tool exits 0. The action's return code is unchanged |
| `Install file:` / `Install directory:` | `copy`, and hidden on success. `env.Install` is wrapped so the sentence is not flushed later |
| `Execute(...)` | A `→` line, not in the action total. `copy` and `move` show `source → dest`. `delete`, `mkdir`, and `chmod` show the path. Anything else is `run`, and the command is printed only on failure. `Touch` stays hidden. The caller's description is not also printed |
| `Execute(Touch(...))` | Hidden. The caller keeps its own status line |
| `Progress(...)` | Printed as usual. The wrapper does not add a status line. `-Q` omits the description |
| Shell command (`g++`, `ar`, `ranlib`) | Unchanged spawn path: command and captured output, then the status line |
| Ctrl-C | One subdued `interrupted — finishing in-flight actions...` line. Tasks already running are left to finish, and those lines look the same as any other status line. No new tasks are started. When they have finished: `finished in-flight actions`, then `[interrupted] reached 57%: 1280/2245 · 80 ran · 1200 up to date`. That close is printed when the job runner returns. `-Q` never writes SCons's own `scons: Build interrupted.` line, so that text is not the cue. The fraction is actions completed against the actions that were going to run. `[interrupted]` is notice, not an error. A second Ctrl-C prints `aborted` and stops what is still running, with no closing line. The per-job `Error -2` list is dropped |
| Before the first action | One subdued line: `3 sconscripts · 1 variant · 13465 actions`. A variant is the build cell, counted once however many sconscripts use it |
| Successful build | `[done] build succeeded · 820 ran · 12645 up to date · 842 test cases · 36 nested`. Zero clauses are omitted. `nested` is every uncounted `Execute` line. Test cases come from the roll-up, including cases that were not printed. A no-op build is `[done] build up to date · 13465 actions`. No whole-build timer. Nothing is added on failure or Ctrl-C |

Text the action prints itself still appears as it happens. Only a child handed to `note_terse_child` is held back. `asciidoctor` does that. An unlabelled `asciidoctor` command is spelled `asciidoc`.

### Tests

A test binary keeps one roll-up line: `[pass|fail|skip|xfail|xpass] sconscript · variant · test · duration · binary — 11/12 cases, 40/52 assertions, 1 failed`. The roll-up status and the binary name are quiet badges: the same colour as a highlight, without the bold bright background. A `test-case` uses the same status text in the status colour, not a badge, and colours only the case leaf. The duration is subdued (`4 ms`, `1.2 s`, `12 s`). Passing fractions stay plain. Only non-zero extras follow, in the status colour (`1 failed`, `1 aborted`, `1 skipped`, `1 xfailed`). On a roll-up, no assertion total is a notice badge: `no assertions`. The yellow is the notice colour, not the bright highlight. On a `test-case` the same words are a bold notice, not a label. Status tokens share a six-column field, so `[ok]` lines up with `[pass]`, `[warn]`, `[fail]`, and `[skip]`. `[error]`, `[xfail]`, and `[xpass]` run one column past it.

A binary with several cases prints a failing case before that roll-up: assertion text, then `→ [fail] … · test-case · duration · binary/case — 1/3 assertions`. A leading `→` means the line is not in the action total. A nested `copy` or `move` uses it too. Only the case leaf is coloured. Passing cases stay hidden unless `--show-test-cases` is set. That flag requires `--terse-output`. A Cuppa test that is one executable is only the roll-up, and it says `no assertions` rather than `1/1`. `run` and `benchmark` stay `[ok]`.

`None`, `0`, and any other falsy return are success, matching SCons. A truthy return or an exception is failure. `KeyboardInterrupt` and `SystemExit` propagate with no status line.

**Interaction:** `--terse-output` implies quieter success paths; it does **not** imply
`--minimal-output`. Combined with it, a clean run is still one line, and failure output is
filtered to errors and warnings. That is documented on the output page.

## Implementation sketch

| Area | Likely touch |
|------|----------------|
| CLI | `cuppa/core/base_options.py` — `--terse-output` |
| Env | `construct.py` — `cuppa_env['terse_output']` |
| Progress | `cuppa/progress.py` — `PRINT_CMD_LINE_FUNC` prints `Progress(...)` and stashes tool commands |
| Spawn | `output_processor.py` — buffer child lines; one success line, or reprint the command |
| Tests | Unit: stash, success, warning, failure; integration: clean compile hides the command |

The reporter is the functions in `cuppa/progress.py`: `terse_counts_prefix`,
`format_terse_line`, `spell_terse_action`, `render_terse_spawn`, and `terse_print_cmd_line`.
`terse_counts_prefix()` is the cell tally and overall percent. It does not rewrite the rest of the status line.
Do not key human text off the `Progress(...)` description.

### Progress lines

`Progress(...)` lines are printed. `-Q` omits them: `progress_action` only builds the
description when the logger is at info. Parallel (`-j`) interleaves that structure with the
status lines, as it does without `--terse-output`.

---

## Counting (done with the flag)

The tally once queued here as a later slice is done in [#353](https://github.com/ja11sop/cuppa/pull/353)
with `--terse-output`. It is not a follow-on.

- One action is one status line that stands alone: compile, link, archive, index, a top-level copy, a test roll-up. A status line that is not in that total leads with `→`, whether or not a parent line is visible. That covers a `test-case` and a nested `copy` or `move`. The caller of the nested copy still counts as one. `[done]` is not an action and is not a status line, so it has no arrow.
- Several targets that share an executor count once. Archive and index are two slots, because they are two status lines.
- The total is the actions reachable from the targets being built. Anything SCons decides is up to date is already done, not missing. A walk that finds nothing keeps the full set, so a failed lookup does not show an empty tally.
- The prefix is ` 19/182 · 10%`. The subdued fraction is this sconscript and variant, so two scripts show different totals. The plain-coloured percent is completed actions over total actions for the whole build. Counts reserve three digits and the percent two (` 25/ 56 · 10%`); past 999 or 99 they grow. A `→` line is indented so its `[status]` stays in that column. Do not print "which script we are in". Under `-j` the numbers only increase.
- No ETA, and no tally on `[done]`.
- The ledger registers each executor when `NotifyProgress.add` records the node. Spawn exits and Python actions both move it. Up-to-date nodes are credited when SCons visits them and skips them. That visit prints nothing. Nested copies and `test-case` lines do not count.

A sketch of `scripts 2/4 · variants 1/3 · actions 35/38 · overall 68%` does not survive `-j`, so it was not built. Level percentages are not multiplied. There is no `--progress-format`.

---

## Work slices

| Slice | Deliverable | Notes |
|-------|-------------|-------|
| A | Design + issue | This document |
| B | `--terse-output` flag + env | Done in [#353](https://github.com/ja11sop/cuppa/pull/353) |
| C | Success one-liner | Done in #353 |
| D | Failure path parity | Done in #353 |
| E | Integration + docs | Done in #353 |
| F–I | Cell fraction and overall percent | Done in #353. Not the `scripts i/N · variants j/M` sketch |

## Refusal rules

| Request | Response |
|---------|----------|
| Terse as default | Refuse; opt-in |
| Terse for `--list-dependencies` trees | Refuse; reports are already structured |
| Drop `NotifyProgress` for a spinner | Refuse; graph ordering is the product |
| Hide failures to keep terse | Refuse |
| Multiply level percentages for “overall” | Refuse; use completed/total actions |
| Promise sequential “step 35 of 38” under `-j` | Refuse; counts are completion tallies |

## Release

The console bundle slipped from the original 1.8.0 candidacy. The flag and the tally are done
for 1.12.0 on [#353](https://github.com/ja11sop/cuppa/pull/353). Mark this plan **shipped** and
move it to `design/archive/` when 1.12.0 is released.

## Related

- [`colourised-doc-samples.md`](../archive/colourised-doc-samples.md) — semantic HTML for reports, not live build log.
- Scratchpad **stderr vs stdout** — validate before any global stream split.
