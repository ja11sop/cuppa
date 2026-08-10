# Plan: terse build output with coloured progress (`--terse-output`)

- **Status:** proposal
- **Related:** [`ROADMAP.md`](../../ROADMAP.md) — Build console output (`console-terse-output`); companion [`native-toolchain-output.md`](native-toolchain-output.md); `cuppa/progress.py`; [`archive/console-report-patterns.md`](../archive/console-report-patterns.md)
- **Updated:** 2026-08-11
- **Impact:** minor — new opt-in CLI flag; default build output unchanged

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

## Goals

1. Add **`--terse-output`** (name settled here; not `--simple-output` — too vague).
2. On success: one line per completed build action — e.g. subdued variant + emphasised target +
   ok marker (reuse `as_notice` / `as_info` / success colour if added).
3. On failure or warning-bearing tool run: print the **command** (or `Progress` description) and
   allow tool output through (respect `--native-output` / default interpretors per companion plan).
4. Keep **`NotifyProgress` graph** unchanged — only change what `progress_action` / post-spawn
   summary prints.
5. Document vs `--minimal-output`, `--verbosity`, and CI usage.

## Non-goals

- Replacing SCons `-Q` / silent mode globally.
- Progress bars, percentages, or ETA (unless a later plan adds them).
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
| Progress node succeeds (child actions all ok) | Single line: `[ok] variant / target` (exact format TBD in PR) |
| Progress node fails | Print command/description + failure output (existing processor path) |
| Warning in tool output | Print command + warning lines (do not hide behind ok line) |
| Sconstruct / sconscript begin/end | One line each (optional suppress duplicate variant banners) |
| Configure / list actions | Unaffected — flag applies to **build/test/coverage** progress only |

**Interaction:** `--terse-output` implies quieter success paths; it does **not** imply
`--minimal-output`. Combining both should be documented (likely: terse success lines + minimal
diagnostic filtering on failures only).

## Implementation sketch

| Area | Likely touch |
|------|----------------|
| CLI | `cuppa/core/base_options.py` — `--terse-output` |
| Env | `construct.py` — `cuppa_env['terse_output']` |
| Progress | `cuppa/progress.py` — `progress_action` description or post-action hook |
| Spawn | `output_processor.py` — defer printing until summary when terse + success |
| Tests | Unit: mock progress events; integration: line-count ceiling on minimal example |

Open design choice for PR: suppress SCons's default `Progress( … )` line via quieter action
descriptions vs custom reporter registered on `NotifyProgress.call_callbacks`.

## Work slices

| Slice | Deliverable | Notes |
|-------|-------------|-------|
| A | Design + issue | This document |
| B | `--terse-output` flag + env | No behaviour yet; docs stub |
| C | Success one-liner | Hook finish event; colour via existing `colourise` |
| D | Failure path parity | Ensure commands + diagnostics still visible |
| E | Integration + docs | Compare before/after transcript in Antora or design note |

## Refusal rules

| Request | Response |
|---------|----------|
| Terse as default | Refuse; opt-in |
| Terse for `--list-dependencies` trees | Refuse; reports are already structured |
| Drop `NotifyProgress` for a spinner | Refuse; graph ordering is the product |
| Hide failures to keep terse | Refuse |

## 1.8.0 candidacy

| Factor | Assessment |
|--------|------------|
| User value | High for large projects |
| Risk | Medium — touches progress + spawn + logging |
| Size | Medium |
| Depends on | None strictly; cleaner alongside native output plan |

**Suggested:** **1.8.0** candidate; can ship after or with [`native-toolchain-output.md`](native-toolchain-output.md). If only one console item fits 1.8.0, prefer **terse** for broader audience (native output helps compiler-heavy workflows).

## Related

- [`colourised-doc-samples.md`](colourised-doc-samples.md) — semantic HTML for reports, not live build log.
- Scratchpad **stderr vs stdout** — validate before any global stream split.
