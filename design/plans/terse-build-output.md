# Plan: terse build output with coloured progress (`--terse-output`)

- **Status:** proposal
- **Related:** [`ROADMAP.md`](../../ROADMAP.md) — Build console output (`console-terse-output`); companion [`native-toolchain-output.md`](native-toolchain-output.md); `cuppa/progress.py`; [`archive/console-report-patterns.md`](../archive/console-report-patterns.md)
- **Updated:** 2026-08-11
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
([`cuppa-info.md`](cuppa-info.md)). Those are **1.8.0** targets alongside terse Phase 1 — not
slices of this document.

## Goals

1. Add **`--terse-output`** (name settled here; not `--simple-output` — too vague).
2. On success: one line per completed build action — e.g. subdued variant + emphasised target +
   ok marker (reuse `as_notice` / `as_info` / success colour if added).
3. On failure or warning-bearing tool run: print the **command** (or `Progress` description) and
   allow tool output through (respect `--native-output` / default interpretors per companion plan).
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

## Settled behaviour (proposal)

| Event | Terse output |
|-------|----------------|
| Progress node succeeds (child actions all ok) | Single line: optional `{counts}` prefix + `[ok] variant / target` (exact format TBD in PR) |
| Progress node fails | Print command/description + failure output (existing processor path) |
| Warning in tool output | Print command + warning lines (do not hide behind ok line) |
| Sconstruct / sconscript begin/end | One line each (optional suppress duplicate variant banners) |
| Configure / list actions | Unaffected — flag applies to **build/test/coverage** progress only |

**Interaction:** `--terse-output` implies quieter success paths; it does **not** imply
`--minimal-output`. Combining both should be documented (likely: terse success lines + minimal
diagnostic filtering on failures only).

## Implementation sketch (Phase 1)

| Area | Likely touch |
|------|----------------|
| CLI | `cuppa/core/base_options.py` — `--terse-output` |
| Env | `construct.py` — `cuppa_env['terse_output']` |
| Progress | `cuppa/progress.py` — **`ProgressReporter`** facade + `NotifyProgress.call_callbacks` |
| Spawn | `output_processor.py` — defer printing until summary when terse + success |
| Tests | Unit: mock progress events; integration: line-count ceiling on minimal example |

**Phase 1 hook for Phase 2:** introduce a small reporter API (name TBD in PR) that Phase 1 calls
from existing events only (`sconstruct_begin`, `begin`, `started`, `finished`, spawn success).
Phase 2 adds denominators and `action_done` without rewriting terse formatting twice.

Open design choice for PR: suppress SCons's default `Progress( … )` line via quieter action
descriptions vs custom reporter registered on `NotifyProgress.call_callbacks`.

---

## Phase 2 — hierarchical progress (counts and percentages)

### What you asked for

Example layout: 4 sconscripts (projects), 3 variants each, 38 tracked actions per
(sconscript, variant) cell — show **where we are** at each level, e.g.

```text
scripts 2/4 · variants 1/3 · actions 35/38 · overall 68%
[ok] test/sconscript · gcc15_dbg_x86_64_cxx2c · compile main.cpp
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
