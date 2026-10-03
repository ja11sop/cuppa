# Plan: terse file fields and delegated builders

- **Status:** proposal
- **Related:** [`terse-build-output.md`](terse-build-output.md) (Phase 1, done for 1.12.0);
  [`native-toolchain-output.md`](native-toolchain-output.md); [`console-channels.md`](console-channels.md);
  [`cmake-drive-and-package-staging.md`](cmake-drive-and-package-staging.md); Boost `b2` via
  `cuppa/dependencies/boost/boost_builder.py`; ROADMAP `console-terse-output` follow-on
- **Updated:** 2026-10-03
- **Impact:** minor — presentation and delegated-builder wiring under `--terse-output`; default
  transcript unchanged

## Why

Phase 1 made Cuppa-owned actions one status line. That works for a native compile graph. It is
weaker when Cuppa **delegates** a large foreign graph (CMake/Ninja, Boost `b2`) and when a status
line names only half of what the tool did.

A corosio package build under `--terse-output -Q` shows the problem clearly:

1. `cmake-configure` and `cmake-build` print the full command and every Ninja line at full
   brightness, then a Cuppa `[ok]` that is easy to miss.
2. Staging copies appear as raw `cp -f …` and are misspelled `archive` because the target ends in
   `.a`.
3. A native `compile` names only the source. CMake's own terse lines name the object
   (`Building CXX object …/foo.cpp.o`). Users who learn from CMake will expect Cuppa to say where
   the product went.

This plan settles **file-field patterns** for every action class, and a **delegated-builder**
presentation so CMake/`b2` stay under Cuppa's transcript instead of drowning it.

## Non-goals

- Pixel-perfect Ninja/CMake clone (ROADMAP `console-cmake-clone` stays out of scope).
- Terse mode for `--list-*` / wipe reports.
- Making `--native-output` a third transcript (it remains a diagnostic-body modifier).
- Changing the Phase 1 tally grammar (`N/M · P%`, `[progress]` scope begin/end).
- Hiding configure-time package download progress (that is the log/report channel, not this plan).

## Observations from the corosio soak

| What happened | Why (today) |
|---------------|-------------|
| `cmake -S …` and `cmake --build …` appear even under `-Q` on a clean run | `cuppa.utility.command.run` is a Python `FunctionAction`. Terse stashes its description, then `IncrementalSubProcess` goes through SPAWN; the next `PRINT_CMD_LINE` **flushes** the stash, so the command is reprinted before any child line |
| Every Ninja `[n/75]` line is full brightness | `command.run` writes child stdout/stderr live. It does not use `note_terse_child`, so nothing nests or mutes |
| Status line ends with `cmake.build.complete` | Stamp targets are the only node path `_file_field` sees for labelled CMake methods |
| `cp -f …/libboost_corosio.a …/working/….a` then `[ok] … · archive · libboost_corosio.a` | `spell_tool_command` treats any target ending in `.a` / `.lib` as `archive`, including `cp`. The builder never labelled the copy |
| Cuppa `[ok]` is hard to associate with the wall of Ninja lines | No bookend before the delegated run; child lines are not indented or subdued |

## Part A — File-field patterns

### Settled grammar

A status line is still:

```text
  N/M · P% [status] sconscript · variant · action · file
```

Only the **file** cell changes. The action word stays the verb. Do not invent a second verb for
"compiled into".

### Pattern table

| Pattern | File cell | When | Rationale |
|---------|-----------|------|-----------|
| **Transform** | `source → product` | `compile`, `compile-*`, `markdown`, `asciidoc`, and any one-input rewrite that yields a different artefact | Names what was read and what was written. Matches CMake/Ninja expectation without dropping the source (the Phase 1 reason for source-only was cross-sconscript `.o` confusion; `<working>/` on the product removes that) |
| **Transfer** | `source → dest` | `copy`, `move`, `expand`, `render`, Install, staging | Already settled. Location change, same kind of thing |
| **Path** | path only | `delete`, `mkdir`, `chmod` | No useful second end |
| **Aggregate** | product basename (or short product path) | `link`, `link-shared`, `archive`, `package`, `publish` | Many inputs already had their own lines; the product is the news |
| **Side tool** | product basename | `index` (ranlib) | Touches an existing product |
| **Run** | program basename, or `program → output` when redirected | `run`, `test`, `benchmark` | Already settled for redirect |
| **Delegated** | summary of the foreign job, not the stamp name | `cmake-configure`, `cmake-build`, `cmake-install`, `b2`, … | Stamps (`cmake.build.complete`) are graph glue. Show `-B` / source / install prefix instead |
| **Opaque** | omit the file cell, or a short label the method sets | rare labelled methods with no meaningful path | Prefer a method-supplied summary over a stamp |

### Compile example

Today:

```text
  25/548 ·  5% [ok]   test · gcc16_dbg_x86_64_cxx2c · compile · test/business_group_id.cpp
```

Proposed:

```text
  25/548 ·  5% [ok]   test · gcc16_dbg_x86_64_cxx2c · compile · test/business_group_id.cpp → <working>/business_group_id.o
```

Colour: source directory subdued, source filename info+bold (unchanged); `→` subdued; product
directory subdued (`<working>/`); product filename info+bold. Same transfer colouring as `copy`.

### Declined alternatives for compile

| Option | Why not |
|--------|---------|
| Product only (`business_group_id.o`) | Loses the source the reader is searching for |
| Source only (today) | Fine for Cuppa natives; weaker next to CMake's object-named lines |
| Absolute object path | Noisy; `<working>/` already scopes the cell |

### Action-by-action assessment

| Action | Today | Proposal | Pattern |
|--------|-------|----------|---------|
| `compile` | source | `source → <working>/….o` | Transform |
| `compile-scss` | source | `source → dest` (css) | Transform |
| `markdown` / `asciidoc` | source | `source → dest` (html) | Transform |
| `expand` / `render` | `source → dest` | keep | Transfer |
| `copy` / `move` / Install | `source → dest` | keep; fix mis-spelled `cp` (below) | Transfer |
| `link` / `link-shared` | product basename | keep | Aggregate |
| `archive` | product basename | keep; only real archivers | Aggregate |
| `index` | product basename | keep | Side tool |
| `test` / `run` / `benchmark` | program / redirect | keep | Run |
| `cmake-configure` | `cmake.configure.complete` | e.g. `-B <build_dir>` or source tree summary | Delegated |
| `cmake-build` | `cmake.build.complete` | e.g. `-B <build_dir>` · Ninja (or generator) | Delegated |
| `cmake-install` | `cmake.install.complete` | e.g. `--prefix …` or install target | Delegated |
| `b2` | (labelled; path varies) | Boost build dir / `--prefix` style summary | Delegated |
| `package` / `publish` | package stem | keep | Aggregate |
| `version` | generated file | keep (product) | Aggregate-ish |
| nested `Execute` `copy` | `→ … · copy · source → dest` | keep | Transfer |
| raw `cp` / `cp -f` via `command.run` | misspelled `archive` when dest is `.a` | label `copy` + Transfer field; never infer archive from suffix alone when the tool is `cp`/`copy` | Transfer |

### Speller fix (required with the copy work)

In `cuppa/toolchains/terse_actions.py`, `name.endswith(_ARCHIVE_SUFFIXES)` currently wins for any
command whose target is a `.a`, including `cp`. Order should be:

1. Explicit method label.
2. Known transfer tools (`cp`, `copy`, `install`, `mv`, …) → `copy` / `move`.
3. Archiver / ranlib / compiler heuristics (including archive suffix).
4. `run`.

## Part B — Delegated builders

A **delegated action** is a Cuppa status line whose useful work is a foreign tool's own graph
(CMake, Ninja, `b2`, …). Cuppa still owns the outer tally. The foreign tool owns the inner lines.

### Goals

1. The Cuppa line is visually primary; foreign lines are clearly subordinate.
2. On a clean run, do **not** reprint the full argv when a launch bookend already summarises the job.
3. Warnings and failures still show the command and the relevant foreign output (Phase 1 rule).
4. The same machinery serves CMake and `b2` (and later similar drivers).

### Recommended shape

```text
variant     0% [progress] gcc16_dbg_x86_64_cxx2c · begin · 0/8 actions
delegate    0% [launch] cmake-build · start · -B _build/gcc16_dbg_x86_64_cxx2c · --parallel 1
             → [1/75] Scanning '…/except.cpp' for CXX dependencies
             → [2/75] Scanning '…/endpoint.cpp' for CXX dependencies
             → …
             → [74/75] Linking CXX executable bench/corosio_bench
   2/  8 · 25% [ok]   gcc16_dbg_x86_64_cxx2c · cmake-build · -B _build/gcc16_dbg_x86_64_cxx2c
```

That opening line has to say, before a long foreign graph starts (google-cloud-cpp can run for
hours): Cuppa is handing off, and a stream of subordinate lines is about to follow. The early
draft `action … [action] …` said "action" twice and named neither the handoff nor the wait.

### Naming the opening bookend

The Phase 1 checkpoint grammar is `scope · percent · [badge] · label · edge · summary`.
`sconstruct` / `sconscript` / `variant` are scopes; `[progress]` is the badge; `begin` / `end`
are edges. The delegated opener needs the same three slots, with no repeated stem.

What each slot should mean here:

| Slot | Job |
|------|-----|
| Scope word | What kind of announcement this is (not a build-graph scope) |
| Badge | That Cuppa is commencing a long handoff, distinct from `[progress]` and from `[ok]` |
| Edge | Phase of that handoff (`start`), because the close is the counted status line, not `end` |

#### Scope word candidates

| Word | Fits the slot | Risk | Notes |
|------|---------------|------|-------|
| `action` | Weak — every status line is "an action" | Collides with the tally word ("8 actions") and with a badge also saying action | Reject as scope when the badge is also action-like |
| `delegate` | Strong — Cuppa is handing the graph to a foreign tool | Slightly abstract on first sight | Matches this plan's vocabulary ("delegated builders"). Pads cleanly under `sconstruct` (10) |
| `spawn` | Mixed — process launch | Collides with Cuppa's SPAWN / `--scons-output` vocabulary | Readers may think the spawn processor changed |
| `foreign` / `external` | Clear handoff | Cold; less verb-like | Acceptable fallbacks if `delegate` feels jargon |

#### Badge candidates

| Badge | Fits the slot | Risk | Notes |
|-------|---------------|------|-------|
| `[action]` | Weak — too generic | With scope `action`, redundant; with scope `delegate`, still vague about duration | Does not say "long foreign run about to start" |
| `[spawn]` | Process-oriented | Same SPAWN collision as the scope word | Avoid |
| `[execute]` | Verb-like | Collides with SCons `env.Execute` | Avoid |
| `[command]` | Suggests argv | On the clean path we **hide** argv; the badge would promise the wrong thing | Avoid |
| `[initiate]` | Accurate | Stiff; uncommon in build UIs | Weaker than `[launch]` |
| `[start]` | Clear | Then the edge `start` doubles it (`[start] … · start ·`) | Only if the edge is dropped |
| `[launch]` | Strong — commencing something that will run | Mild overlap with edge `start` | Best badge: distinct from `[progress]`, no API collision, implies a run that may take time |
| `[running]` | Suggests in progress | The line is printed **before** children; "running" is slightly early | Better on a heartbeat than on the opener |

#### Combinations

| Form | Read as | Verdict |
|------|---------|---------|
| `action … [action] … · start ·` | "an action action" | Reject — redundant, uninformative |
| `delegate … [action] … · start ·` | handoff, but badge still vague | Better than double action; badge still weak |
| `action … [spawn] … · start ·` | Cuppa SPAWN confusion | Reject |
| `action … [execute] … · start ·` | SCons Execute confusion | Reject |
| `spawn … [action] … · start ·` | SPAWN as scope | Reject |
| `spawn … [initiate] … · start ·` | SPAWN + stiff badge | Reject |
| `action … [command] … · start ·` | implies argv will show | Reject on clean path |
| `action … [launch] … · start ·` | launch is good; scope still says little | Acceptable |
| `delegate … [launch] … · start ·` | handoff + commencing long work | **Recommend** |
| `delegate … [launch] …` (no edge) | same, shorter | Reserve if `launch` + `start` feels heavy in soak |
| `delegate … [start] …` (no edge) | handoff + start in the badge | Good alternative; loses the begin/start edge parallel |

#### Recommendation

Use:

```text
delegate    0% [launch] cmake-build · start · -B _build/gcc16_dbg_x86_64_cxx2c · --parallel 1
```

- **`delegate`** — scope word: this line is a handoff announcement, not a sconstruct/variant
  checkpoint and not "one more ordinary action".
- **`[launch]`** — badge: Cuppa is about to start a foreign graph that may take a long time.
  Keep `[progress]` for real scope checkpoints.
- **`start`** — edge: opening phase; the counted `[ok]` / `[warn]` / `[error]` is the close.
  If soak finds `launch` + `start` noisy, drop the edge and keep `[launch]` only.

Colour: treat like a progress checkpoint — subdued scope word, plain percent, info+bold badge
(or notice if we want launch to feel more urgent than progress; default to the same treatment as
`[progress]` unless soak says otherwise).

### Rules

| Piece | Choice | Rationale |
|-------|--------|-----------|
| Opening bookend | scope `delegate`, badge `[launch]`, edge `start` | Names the handoff and the long commence; no repeated stem; `[progress]` stays for sconstruct/sconscript/variant |
| Closing bookend | the ordinary counted status line | Already in the tally; do not add a second end checkpoint |
| Child lines | lead with the same `→` indent as nested `Execute` / `test-case` | One visual language for "not in the Cuppa action total" |
| Child line body | subdued (muted) text | Subservient to Cuppa chrome; still readable |
| Child status badge | optional; default **off** for Ninja progress | Ninja already has `[n/N]`. A Cuppa `[ok]` on every scan line is noise. Reserve a badge for classified warn/error lines if we filter later |
| Clean argv | hidden when the launch bookend was printed | The bookend carries `-B`, generator, jobs. Failure still reprints argv |
| Cuppa `Executing […]` info log | stays a log line; `-Q` already hides it | Do not promote it into the transcript |

### Options considered (presentation shape)

| Option | Pros | Cons | Verdict |
|--------|------|------|---------|
| **A. Launch bookend + muted `→` children + counted close** (above) | Clear ownership; reuses `→` indent; works for CMake and `b2`; names the long handoff | Needs `command.run` (and b2 runner) to cooperate with terse | **Recommend** |
| **B. Only mute children; no launch bookend** | Smaller change | Association still weak; argv still appears via SPAWN flush; no warning before a multi-hour `cmake --build` | Not enough |
| **C. Indent without mute** | Less colour risk | Still fights Cuppa chrome on a busy dark/light console | Weaker than A |
| **D. Hide all foreign lines unless warn/error** | Quietest | Users lose the only progress signal during a long `cmake --build` | Refuse as default; could be a later opt-in |
| **E. Parse Ninja into Cuppa status lines** (`→ [ok] compile · …`) | Familiar Cuppa grammar | Fragile; fights `--native-output`; out of scope (`console-cmake-clone`) | Refuse |
| **F. Use `[progress]` for the launch bookend** | No new badge | Overloads scope checkpoints; `begin`/`end` pair expectation | Prefer `delegate` / `[launch]` / `start` |

### Wiring (`command.run` and friends)

Today `cuppa.utility.command.run`:

- logs `Executing […]` at info,
- streams every child line with `sys.stdout.write` / `sys.stderr.write`,
- does not call `note_terse_child`,
- triggers the SPAWN/`PRINT_CMD_LINE` stash flush that reprints argv.

Under `--terse-output` it should:

1. Announce the delegated launch bookend (method supplies the summary string).
2. Buffer or stream child lines through a terse helper that prefixes `→` and mutes.
3. On completion, let the existing Python-action wrapper print the counted status line.
4. On warn/error, reprint argv, then the (muted) child body, then `[warn]`/`[error]`.
5. Avoid the stash-flush reprint of argv on the clean path (either do not stash the full argv when
   a launch bookend was emitted, or consume it without `_write_command`).

Boost `b2` should use the same helper. Method labels `b2` / `boost-toolset` already exist; only
the presentation path is missing.

### CMake-specific file cell

| Method | File / summary sketch |
|--------|------------------------|
| `cmake-configure` | `-B <build_dir>` (and maybe `-G Ninja` when not default-obvious) |
| `cmake-build` | `-B <build_dir>` |
| `cmake-install` | `--target install` / prefix when known |

Do not show `cmake.build.complete`.

### Staging copies after CMake

Publisher sconscripts / package helpers that shell out to `cp -f` must either:

- use `env.Install` / `Copy` / labelled `Command` with `label_terse_action(..., "copy")` and
  `paths="transfer"`, or
- go through a small Cuppa helper that does that labelling.

Then the line becomes:

```text
   3/  8 · 38% [ok]   gcc16_dbg_x86_64_cxx2c · copy · <cmake-build>/libboost_corosio.a → <working>/libboost_corosio.a
```

instead of a raw `cp` and a false `archive`.

## Part C — Interaction with other controls

| Control | Interaction |
|---------|-------------|
| `--terse-output` | Required for launch bookends, muted children, transform file fields |
| `--normal-output` / default | Unchanged full commands and child streams |
| `--minimal-output` | Still filters Cuppa-classified diagnostics; foreign muted lines that are not classified stay as progress unless we later add a foreign filter |
| `--native-output` (planned) | Applies to **Cuppa-spawned toolchain** diagnostics. A delegated CMake/Ninja body is already "native" in the sense of passthrough; do not re-colour it. Muting/indent still apply under terse |
| `-Q` | Hides info logs; transcript bookends and muted children stay |
| `--terse-output-show-actions` | May still append the raw SCons action on the **counted** close line; not on every child line |

## Work slices

| Slice | Deliverable | Notes |
|-------|-------------|-------|
| A | Design + index + ROADMAP row | This document |
| B | File-field Transform for `compile` / `compile-*` / `markdown` / `asciidoc` | Unit tests on `_file_field`; docs table |
| C | Speller: `cp`/`copy` before archive-suffix heuristic | Fixes false `archive` |
| D | Label staging copies (CMake package path + any `command.run` cp) | Integration soak on a package publisher |
| E | Delegated launch bookend (`delegate … [launch] … · start ·`) + muted `→` child stream helper | `progress.py` + `command.run` |
| F | CMake summaries on configure/build/install status lines | Drop stamp filenames |
| G | Boost `b2` on the same helper | Parity with CMake |
| H | Docs: output page patterns + delegated section | Antora + changelog for the release that ships it |

## Refusal rules

| Request | Response |
|---------|----------|
| Parse every Ninja line into Cuppa `[ok] compile` | Refuse; fragile and out of scope |
| Hide all CMake/Ninja lines by default | Refuse; long builds need a pulse |
| Reuse `[progress]` + `begin`/`end` for delegated jobs | Refuse; reserve that for scope checkpoints |
| Scope `action` with badge `[action]` | Refuse; redundant and silent about the long handoff |
| Make transform `source → product` the default outside `--terse-output` | Refuse; only the terse file cell changes |
| Infer `archive` from a `.a` target for any tool | Refuse; that is the bug being fixed |

## Success criteria

1. A clean `cmake-build` under `--terse-output -Q` shows
   `delegate … [launch] … · start ·`, muted indented Ninja lines, and one counted `[ok]` —
   without a leading raw `cmake --build …` argv.
2. Staging libraries show as `copy` with `source → dest`, never as `archive` from `cp`.
3. A native `compile` shows `source → <working>/….o`.
4. Boost `b2` uses the same delegated presentation.
5. Failure still prints argv and enough foreign output to diagnose.

## Related

- Phase 1 terse grammar and checkpoints: [`terse-build-output.md`](terse-build-output.md)
- Channel map: [`console-channels.md`](console-channels.md)
- Native diagnostic modifier: [`native-toolchain-output.md`](native-toolchain-output.md)
- CMake drive / package staging: [`cmake-drive-and-package-staging.md`](cmake-drive-and-package-staging.md)
