# Plan: terse file fields and delegated builders

- **Status:** done
- **Related:** [`terse-build-output.md`](terse-build-output.md) (Phase 1, done for 1.12.0);
  [`native-toolchain-output.md`](native-toolchain-output.md); [`console-channels.md`](console-channels.md);
  [`cmake-drive-and-package-staging.md`](cmake-drive-and-package-staging.md); Boost `b2` via
  `cuppa/dependencies/boost/boost_builder.py`; ROADMAP `console-terse-delegated`;
  Boost `-c` follow-up [`deep-clean.md`](deep-clean.md)
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
- `--deep-clean` / Boost extract `b2` vs ordinary `-c` (see follow-up below).
  Ordinary `-c` already removes `_build` and the Boost **stage**; `bin.*` and
  extract `b2` stay today. That is [`deep-clean.md`](deep-clean.md), not this plan.

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
| **Aggregate** | located product path | `link`, `link-shared`, `archive`, `package`, `publish` | Many inputs already had their own lines; the product is the news. Once `[location]` maps exist, the leaf is not enough: this variant's program is `<final>/management`, a dependency archive is `_build/<fmt>/<variant>/final/libfmt.a`. Not a transform: no object list, no `→`. Unmapped paths stay a basename. |
| **Side tool** | located product path | `index` (ranlib) | Touches an existing product; same cell as the archive line |
| **Run** | located program, or `program → output` when redirected | `run`, `test`, `benchmark` | Same dest locate as `link` so the binary matches the line that built it. `<final>/` subdued; the leaf keeps dest colouring on `run`/`benchmark` and the status badge on `test`. `test-case` uses the same muted program prefix plus the case leaf in the status colour. Unmapped stays a basename. |
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
| `link` / `link-shared` | product basename | located product (`<final>/…` or `_build/<name>/<variant>/final/…`) | Aggregate |
| `archive` | product basename | located product; only real archivers | Aggregate |
| `index` | product basename | located product (same path as the archive) | Side tool |
| `test` / `run` / `benchmark` | program / redirect | located program (`<final>/…`); redirect still `program → output` | Run |
| `cmake-configure` | `cmake.configure.complete` | e.g. `-B <build_dir>` or source tree summary | Delegated |
| `cmake-build` | `cmake.build.complete` | e.g. `-B <build_dir>` · Ninja (or generator) | Delegated |
| `cmake-install` | `cmake.install.complete` | e.g. `--prefix …` or install target | Delegated |
| `b2` | (labelled; path varies) | Boost build dir / `--prefix` style summary | Delegated |
| `package` / `publish` | package stem | located product when the dest is mapped | Aggregate |
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
delegate     0% [launch] gcc16_dbg_x86_64_cxx2c · cmake-build · -B _build/gcc16_dbg_x86_64_cxx2c --parallel 1
             → [1/75] Scanning '…/except.cpp' for CXX dependencies
             → [2/75] Scanning '…/endpoint.cpp' for CXX dependencies
             → …
             → [74/75] Linking CXX executable bench/corosio_bench
   2/  8 ·  25% [done]  gcc16_dbg_x86_64_cxx2c · cmake-build · -B _build/gcc16_dbg_x86_64_cxx2c --parallel 1
```

When a sconscript label is present on the close line, the launch line includes it too (same
field order as a status line: `sconscript · variant · action · summary`).

That opening line has to say, before a long foreign graph starts (google-cloud-cpp can run for
hours): Cuppa is handing off, and a stream of subordinate lines is about to follow. The early
draft `action … [action] …` said "action" twice and named neither the handoff nor the wait.
Corosio soak then showed that putting only the action after `[launch]` lost the variant and
made the close harder to reattach after a long muted wall.

### Naming the opening bookend

Phase 1 checkpoints use `scope · percent · [badge] · path · edge · summary`. The delegated
opener keeps the same **chrome** (padded scope word, percent, badge) but after the badge it
**mirrors the status line fields**, not a checkpoint path/edge. Association with the counted
close matters more than begin/end symmetry.

| Slot | Job |
|------|-----|
| Scope word | What kind of announcement this is (not a build-graph scope) |
| Badge | That Cuppa is commencing a long handoff, distinct from `[progress]` and from unit `[ok]` |
| Fields | Same as the close: sconscript (when present) · variant · action · summary — no `start` edge |

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
| `[start]` | Clear | Fine if there is no edge; weaker than `[launch]` for "long handoff commencing" | Acceptable alternative |
| `[launch]` | Strong — commencing something that will run | Mild redundancy with a former edge `start` | **Recommend**; drop the edge |
| `[running]` | Suggests in progress | The line is printed **before** children; "running" is slightly early | Better on a heartbeat than on the opener |

#### Close badge (delegated) and whole-build rename

| Badge | Role | Notes |
|-------|------|-------|
| `[ok]` | Ordinary unit success (compile, copy, …) | Keep for non-delegated actions |
| `[done]` | Clean close of a `[launch]` span | Signals end of a longer sequence; same six-column width as `[ok]` |
| `[warn]` / `[error]` | Delegated failure path | Unchanged |
| `[completed]` | Whole-build close (was Phase 1 `[done]`) | Frees `[done]` for delegated close; clearer than `[finished]` (clashes with Progress `finished` / `finished in-flight actions`) |

#### Combinations

| Form | Read as | Verdict |
|------|---------|---------|
| `action … [action] … · start ·` | "an action action" | Reject — redundant, uninformative |
| `delegate … [launch] … · start ·` + action only | handoff, but no variant; `start` noisy after soak | Reject after corosio soak |
| `delegate … [launch] …` + action only | shorter, still missing variant | Reject after soak |
| `delegate … [launch] …` + status fields, close `[ok]` | good association; close still looks like a unit | Acceptable smaller change |
| `delegate … [launch] …` + status fields, close `[done]` | handoff + span close; needs whole-build rename | **Recommend** |
| `delegate … [start] …` (no edge) | handoff + start in the badge | Weaker than `[launch]` |

#### Recommendation

Use:

```text
delegate     0% [launch] gcc16_dbg_x86_64_cxx2c · cmake-build · -B _build/gcc16_dbg_x86_64_cxx2c --parallel 1
             → …
   2/  8 ·  25% [done]  gcc16_dbg_x86_64_cxx2c · cmake-build · -B _build/gcc16_dbg_x86_64_cxx2c --parallel 1

[completed] build succeeded · …
```

- **`delegate`** — scope word: this line is a handoff announcement, not a sconstruct/variant
  checkpoint and not "one more ordinary action".
- **`[launch]`** — badge: Cuppa is about to start a foreign graph that may take a long time.
  Keep `[progress]` for real scope checkpoints. No `· start ·` edge (`[launch]` already implies it).
- **Fields after the badge** — mirror the counted close (`sconscript · variant · action · summary`
  when sconscript is present). Under `--parallel` the variant on `[launch]` is essential.
- **`[done]`** — clean delegated close (complement of `[launch]`). Ordinary actions stay `[ok]`.
- **`[completed]`** — whole-build close; Phase 1's `[done] build succeeded` moves here so the
  word is not overloaded.

Colour: treat `[launch]` like `[progress]` (info+bold); variant/action/summary colouring matches
the status line so the rhyme is visual as well as structural.

### Rules

| Piece | Choice | Rationale |
|-------|--------|-----------|
| Opening bookend | scope `delegate`, badge `[launch]`, status-line fields (no edge) | Names the handoff; mirrors the close for association; `[progress]` stays for scope checkpoints |
| Closing bookend | counted status line with `[done]` on clean delegated success | Span close, not a second `end` checkpoint; `[warn]`/`[error]` unchanged |
| Whole-build close | `[completed] build …` | Was `[done]`; frees `[done]` for delegated close |
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
| **F. Use `[progress]` for the launch bookend** | No new badge | Overloads scope checkpoints; `begin`/`end` pair expectation | Prefer `delegate` / `[launch]` + status fields |

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

Boost `b2` should use the same helper. Method labels `build-b2` / `b2` /
`boost-toolset` already exist; only the presentation path is missing.

### CMake-specific file cell

| Method | File / summary sketch |
|--------|------------------------|
| `cmake-configure` | `-B <build_dir>` (and maybe `-G Ninja` when not default-obvious) |
| `cmake-build` | `-B <build_dir>` |
| `cmake-install` | `--target install` / prefix when known |

Do not show `cmake.build.complete`.

### Shared tools (author override)

Some tools are built once and required by every variant (Boost bootstrap ``build-b2``,
the toolchain ``boost-toolset`` jam). Cuppa does **not** infer that from the Depends
graph. The method author who wired the call graph sets an override on the node:

```python
cuppa.progress.label_terse_action( nodes, "build-b2", shared=True )
# or shared="shared_across_variants" / another explicit string
```

Default behaviour is unchanged: launch and close show the triggering variant cell.
With ``shared``, that slot becomes the shared label instead:

```text
sconscript  0% [progress] pkg/sconscript · begin
             → [location] pkg · <boost> = _download/boost_1_86_0
delegate     0% [launch] pkg · shared_across_variants · build-b2 · <boost>/b2
             → Building Boost.Build engine
             → [ok] pkg · shared_across_variants · copy · <boost>/tools/build/src/engine/b2 → <boost>/b2
   1/  8 ·   3% [done]  pkg · shared_across_variants · build-b2 · <boost>/b2
```

The file cell is the extract product (``paths="product"``). The engine-tree copy is an
uncounted nested ``copy`` and must **not** call ``note_terse_status_emitted``, or the
counted ``[done]`` is skipped. Colour: ``shared`` plain (like ``dbg`` in a cell);
``_across_variants`` subdued. Sconscript (when present) is unchanged. Per-variant ``b2``
library builds do not set this flag. ``boost-toolset`` is also
``shared_across_variants``; if the ``._jam`` already exists, SCons treats it as up to
date and there is no status line.

### Location maps

Begin checkpoints print named roots so later ``<token>/`` file cells can be decoded:

```text
variant     0% [progress] test/orders/gcc16_dbg_x86_64_cxx2c · begin
             → [location] test/orders · gcc16_dbg_x86_64_cxx2c · <working> = _build/test/orders/gcc16/dbg/x86_64/cxx2c/working
             → [location] test/orders · gcc16_dbg_x86_64_cxx2c · <final> = _build/test/orders/gcc16/dbg/x86_64/cxx2c/final
             → [location] test/orders · gcc16_dbg_x86_64_cxx2c · <artefacts> = _artifacts
```

``<working>``, ``<final>``, and ``<artefacts>`` come from the env on **variant** begin.
Authors add extras with ``label_terse_location(env, "boost", path)`` (default scope
**sconscript**). Grammar: ``→ [location] [sconscript ·] [variant ·] <token> = path``.
``[location]`` is bold muted grey (vocabulary chrome, not a status colour,
not action ink, not info+bold). Identity fields reattach the line when
``-j`` splits it from ``[progress]``. Sconscript-scoped
maps omit the variant cell. Path colour matches the parent checkpoint: sconscript
leaf info, ``dbg`` / ``rel`` / ``cov`` plain, last component info+bold. Not inferred from
``_download``. End checkpoints do not repeat the maps.

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
| A | Design + index + ROADMAP row | Done |
| B | File-field Transform for `compile` / `compile-*` / `markdown` / `asciidoc` | Done |
| C | Speller: `cp`/`copy` before archive-suffix heuristic | Done |
| D | Label staging copies (CMake package path + any `command.run` cp) | Done |
| E | Delegated launch bookend (`delegate … [launch]` + status fields) + muted `→` child stream helper | Done |
| F | CMake summaries on configure/build/install status lines | Done |
| G | Boost `b2` on the same helper | Done |
| H | Docs: output page patterns + delegated section | Done (Antora + changelog; not shipped until 1.12.0) |
| I | Soak tweak: launch mirrors close fields; clean close `[done]`; whole-build `[completed]` | Done |
| J | `shared_across_variants` author override for build-wide tools | Done |
| K | Location maps + extract `b2` as `paths=product` + uncounted copy | Done; Boost `-c`/`b2` is [`deep-clean.md`](deep-clean.md) |

## Refusal rules

| Request | Response |
|---------|----------|
| Parse every Ninja line into Cuppa `[ok] compile` | Refuse; fragile and out of scope |
| Hide all CMake/Ninja lines by default | Refuse; long builds need a pulse |
| Reuse `[progress]` + `begin`/`end` for delegated jobs | Refuse; reserve that for scope checkpoints |
| Scope `action` with badge `[action]` | Refuse; redundant and silent about the long handoff |
| Make transform `source → product` the default outside `--terse-output` | Refuse; only the terse file cell changes |
| Infer `archive` from a `.a` target for any tool | Refuse; that is the bug being fixed |
| Turn `link` / `archive` into `objects → product` | Refuse; aggregate stays product-only; locate the dest |
| Print `<final>/libfmt.a` for a dependency archive | Refuse; that token is this sconscript's final dir |
| Infer “shared across variants” from Depends | Refuse; author sets `label_terse_action(..., shared=True)` |
| Infer `<boost>` (or other tokens) by sniffing `_download` folder names | Refuse; structured registration only — see [`terse-dependency-locations.md`](terse-dependency-locations.md) |
| Register Boost `bin.*` as a terse location | Refuse; ordinary `-c` does not wipe it |
| Change `env.NoClean(b2)` / cooperative library clean in this plan | Refuse; follow-up on [`deep-clean.md`](deep-clean.md) |

## Success criteria

1. A clean `cmake-build` under `--terse-output -Q` shows
   `delegate … [launch] <variant> · cmake-build · …`, muted indented Ninja lines, and one
   counted `[done]` — without a leading raw `cmake --build …` argv. When sconscript is on
   the close line, it is on the launch line too.
2. Staging libraries show as `copy` with `source → dest`, never as `archive` from `cp`.
3. A native `compile` shows `source → <working>/….o` and still closes with `[ok]`.
4. Boost `b2` uses the same delegated presentation (library builds per variant;
   bootstrap `BuildB2` with `shared_across_variants`, extract product
   ``<boost>/b2``, uncounted nested copy).
5. Failure still prints argv and enough foreign output to diagnose (`[warn]` / `[error]`).
6. A successful whole build ends with `[completed] build succeeded` (not `[done]`).
7. Variant begin prints ``→ [location]`` maps for ``<working>`` / ``<final>`` /
   ``<artefacts>`` with sconscript · variant; Boost registers ``<boost>`` on
   sconscript begin (no variant cell).

## Follow-up (not this plan)

Nested dependency location maps (`<dependencies>/<fmt>/…`, shared `<variant>`,
structured registration from dependency `_name`) are tracked on
[`terse-dependency-locations.md`](terse-dependency-locations.md).

Boost `-c` vs extract `b2` vs library `bin.*` is tracked on
[`deep-clean.md`](deep-clean.md). Today `env.NoClean(b2)` leaves the bootstrap
binary, so the next build does not rebuild `b2` if it exists. That is the right
**build** default and the wrong **clean** default: Cuppa built that file, so
ordinary `-c` should remove it (CMake `-B` parity), and a cooperative
`b2 --clean` for the **current variants** is the library-side match — not a
`--deep-clean` wipe of the whole `bin.*` tree. Coarse Boost.Build toolset
folders make the latter risky. Leave `NoClean(b2)` until that follow-up.

## Related

- Phase 1 terse grammar and checkpoints: [`terse-build-output.md`](terse-build-output.md)
- Channel map: [`console-channels.md`](console-channels.md)
- Native diagnostic modifier: [`native-toolchain-output.md`](native-toolchain-output.md)
- Dependency location maps: [`terse-dependency-locations.md`](terse-dependency-locations.md)
- CMake drive / package staging: [`cmake-drive-and-package-staging.md`](cmake-drive-and-package-staging.md)
- Boost `-c` / extract `b2` / `bin.*`: [`deep-clean.md`](deep-clean.md)
