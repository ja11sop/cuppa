# Plan: native coloured toolchain output (`--native-output`)

- **Status:** done (2026-10-04) — landed on [#354](https://github.com/ja11sop/cuppa/pull/354); promote to **shipped** and archive at the 1.12.0 release
- **Related:** [`ROADMAP.md`](../../ROADMAP.md) — Build console output (`console-native-output`); channel map [`console-channels.md`](console-channels.md); companion [`terse-build-output.md`](terse-build-output.md) / [`terse-delegated-output.md`](terse-delegated-output.md) (done on master [#353](https://github.com/ja11sop/cuppa/pull/353)); follow-on [`terse-dependency-locations.md`](terse-dependency-locations.md); [`archive/console-report-patterns.md`](../archive/console-report-patterns.md)
- **Updated:** 2026-10-04
- **Impact:** minor — new opt-in CLI flag; default build output unchanged

## Why

Cuppa historically **re-parsed** compiler and linker lines and applied its own colour vocabulary
(`ToolchainProcessor` in `cuppa/output_processor.py`, driven by per-toolchain
`output_interpretors()`). That made sense when toolchains emitted plain text.

Modern GCC, Clang, and MSVC often ship **native colour diagnostics** (`-fdiagnostics-color=always`,
`-fcolor-diagnostics`, MSVC `/diagnostics:caret`, and similar). Cuppa's layer can fight that
presentation: double colour, lost caret context, or regex misses on new diagnostic formats.

Operators who prefer the toolchain's own formatting need an explicit, documented escape hatch —
not `--raw-output`, which also disables cuppa's progress wiring and other processing.

## Goals

1. Add **`--native-output`**: prefer toolchain-native presentation for **spawned** compile/link
   commands while keeping cuppa progress nodes and non-tool actions unchanged.
2. Enable the toolchain flags that turn native colour on when `--native-output` is set (toolchain
   API, not hard-coded in one place).
3. **Passthrough mode** for stdout/stderr from spawned children: do not run lines through
   `ToolchainProcessor` re-colouring; still honour `--ignore-duplicates` where feasible without
   re-parsing meaning.
4. Document interaction with `--raw-output`, `--standard-output`, `--minimal-output`, and
   [`terse-build-output.md`](terse-build-output.md) `--terse-output`.
5. Antora: CLI reference + Methods (custom commands) cross-link.

## Non-goals

- Removing `ToolchainProcessor` or regex interpretors (default path stays cuppa-coloured).
- Native colour for **cuppa-owned reports** (`--list-builds`, wipe trees, coverage summaries).
- ANSI→HTML doc samples ([`colourised-doc-samples.md`](../archive/colourised-doc-samples.md) stays separate).
- Guaranteeing native colour on every platform (TTY detection remains the toolchain's job).

## Settled vocabulary (decide before first PR)

| Flag | Behaviour |
|------|-----------|
| *(default)* | Colourised spawn + `ToolchainProcessor` interpretors |
| `--standard-output` | Spawn processing without cuppa log colour (existing) |
| `--raw-output` | No cuppa spawn wrapper (existing) |
| **`--native-output`** | Not a transcript. On a warning or failure, in normal or terse, the toolchain's own lines pass through and Cuppa still counts them |
| `--minimal-output` | Filter to errors/warnings only (existing; applies to interpreted path today) |
| `--terse-output` | See companion plan — progress-first, not diagnostic parsing |

**Precedence:** `--native-output` is not a third transcript beside normal and terse.
It chooses how a warning or failure is drawn in either transcript: the toolchain's
own lines pass through, and Cuppa still counts them. `--raw-output` still wins over
the spawn processor. `--standard-output` disables Cuppa colour on logs and does not
imply native toolchain colour.

## Behaviour sketch

### Toolchain API

Add something like `native_output_flags( env ) → […]` on `Gcc`, `Clang`, `Cl`:

| Toolchain | Expected enable flags (initial cut) |
|-----------|-------------------------------------|
| GCC | `-fdiagnostics-color=always` when supported |
| Clang | `-fcolor-diagnostics` (or driver default when always-on) |
| MSVC | `/diagnostics:caret` where applicable; document limits |

Probe or version-gate like Profiles — do not append flags known to be rejected.

### Spawn path

In `construct.py` / `output_processor.py`:

- When `native_output` is true and not `raw_output`, install spawn that:
  - Appends `native_output_flags` to compile/link invocations (via env or wrapper).
  - Passes the toolchain line through (keep ANSI and caret/note layout).
  - Strips ANSI **only for Cuppa classification**, so `= Error N =` banners and
    `=== Errors N ===` still work when `-fdiagnostics-color=always` is set.
- **Do not** strip ANSI from the emitted body.

### `--minimal-output` interaction

Today `minimal_output` hides non error/warning **after** interpretors classify lines. With native
output, classification may be unavailable. Options (pick one in implementation PR):

| Approach | Pros | Cons |
|----------|------|------|
| A. Disable `--minimal-output` with `--native-output` (warn + ignore minimal) | Honest | Less flexible |
| B. Heuristic filter on raw lines (toolchain-specific regex) | Keeps combo | Duplicates interpretor work |
| C. Document incompatibility; refuse combo with StopError | Clearest | Stricter |

**Recommendation:** **A** for v1 — warn once, ignore `minimal_output` under native passthrough.

## Work slices

| Slice | Deliverable | Notes |
|-------|-------------|-------|
| A | Design + issue | This document (no separate issue required) |
| B | `--native-output` flag + env key | Done — `core/output_options.py`; refuse raw/scons; ignore minimal with warn |
| C | Toolchain `native_output_flags` | Done — GCC/Clang/MSVC initial mapping |
| D | Passthrough spawn branch | Done — `ToolchainProcessor(native_output=…)`; unit tests |
| E | Docs + CLI reference | Done — Antora + changelog |
| F | Integration smoke | Optional soak on gcc/clang cells before merge |

## Refusal rules

| Request | Response |
|---------|----------|
| Make `--native-output` the default | Refuse; opt-in only |
| Remove cuppa interpretors entirely | Refuse; default path unchanged |
| Re-parse native ANSI into cuppa meanings | Refuse; passthrough or nothing |
| `--native-output` on `--raw-output` | Refuse or no-op with clear message |

## 1.12.0 candidacy

| Factor | Assessment |
|--------|------------|
| User value | High for daily driver builds on modern Clang/GCC |
| Risk | Medium — spawn matrix (POSIX vs Windows, minimal/terse interaction) |
| Size | Small–medium (one flag + toolchain hooks + spawn branch) |
| Docs | Small CLI + methods note |

**Suggested:** optional **1.12.0** slice after terse (#353). Orthogonal to the transcript choice.

## Related follow-on (separate)

**stderr vs stdout split** (logging → stderr, tool primary → stdout) noted on the scratchpad —
validate current behaviour with `--verbosity=debug` before any change; not part of this plan.
