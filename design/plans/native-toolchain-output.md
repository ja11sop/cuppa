# Plan: native coloured toolchain output (`--native-output`)

- **Status:** proposal
- **Related:** [`ROADMAP.md`](../../ROADMAP.md) — Build console output (`console-native-output`); companion [`terse-build-output.md`](terse-build-output.md); [`archive/console-report-patterns.md`](../archive/console-report-patterns.md); issue to file when work starts
- **Updated:** 2026-08-11
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
- ANSI→HTML doc samples ([`colourised-doc-samples.md`](colourised-doc-samples.md) stays separate).
- Guaranteeing native colour on every platform (TTY detection remains the toolchain's job).

## Settled vocabulary (decide before first PR)

| Flag | Behaviour |
|------|-----------|
| *(default)* | Colourised spawn + `ToolchainProcessor` interpretors |
| `--standard-output` | Spawn processing without cuppa log colour (existing) |
| `--raw-output` | No cuppa spawn wrapper (existing) |
| **`--native-output`** | Spawn wrapper stays; child gets native-colour flags; lines pass through uninterpreted |
| `--minimal-output` | Filter to errors/warnings only (existing; applies to interpreted path today) |
| `--terse-output` | See companion plan — progress-first, not diagnostic parsing |

**Precedence (proposal):** `--raw-output` wins over everything. Among cuppa spawn modes:
`--native-output` and default colourisation are mutually exclusive; `--standard-output` disables
cuppa colour on logs but does not imply native toolchain colour unless documented otherwise.

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
  - Uses `IncrementalSubProcess` / Windows pipe path but **`processor=None`** passthrough
    (or a no-op processor that only applies duplicate filtering on raw lines if cheap).
- **Do not** strip ANSI from child output.

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
| A | Design + issue | This document; file umbrella issue |
| B | `--native-output` flag + env key | `base_options.py`, `construct._set_output_format` |
| C | Toolchain `native_output_flags` | GCC/Clang/MSVC initial mapping |
| D | Passthrough spawn branch | `output_processor.py`; tests with fake toolchain lines |
| E | Docs + CLI reference | Interactions with other output flags |
| F | Integration smoke | Build with `--native-output` on gcc and clang cells |

## Refusal rules

| Request | Response |
|---------|----------|
| Make `--native-output` the default | Refuse; opt-in only |
| Remove cuppa interpretors entirely | Refuse; default path unchanged |
| Re-parse native ANSI into cuppa meanings | Refuse; passthrough or nothing |
| `--native-output` on `--raw-output` | Refuse or no-op with clear message |

## 1.8.0 candidacy

| Factor | Assessment |
|--------|------------|
| User value | High for daily driver builds on modern Clang/GCC |
| Risk | Medium — spawn matrix (POSIX vs Windows, minimal/terse interaction) |
| Size | Small–medium (one flag + toolchain hooks + spawn branch) |
| Docs | Small CLI + methods note |

**Suggested:** strong **1.8.0** candidate as slice B–E; pair with [`terse-build-output.md`](terse-build-output.md) only if progress work lands in the same cycle (orthogonal but same console area).

## Related follow-on (separate)

**stderr vs stdout split** (logging → stderr, tool primary → stdout) noted on the scratchpad —
validate current behaviour with `--verbosity=debug` before any change; not part of this plan.
