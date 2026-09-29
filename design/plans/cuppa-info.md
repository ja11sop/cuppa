# Plan: `cuppa --info` (version without a build)

- **Status:** in progress
- **Related:** [`ROADMAP.md`](../../ROADMAP.md) — CLI (`cli-info`); [`build-log-hygiene.md`](build-log-hygiene.md); `cuppa/version.py`; companion list modes (`--list-toolchains`, …)
- **Updated:** 2026-09-29
- **Impact:** minor — new opt-in CLI flag; no change to default builds

## Why

Today the installed cuppa version appears only after configure starts a normal invocation:

```text
cuppa: version: [info] cuppa: version 1.12.0.dev
```

That line comes from `check_current_version()` in `cuppa/version.py`, called from
`cuppa/construct.py` **after** options load, storage paths, and often toolchain archive
registration — far too late for scripts and agents that only need **“which cuppa is this?”**

**`--version`** is owned by **SCons** (compiler/build tool version strings), not cuppa’s package
version. A cuppa-specific flag avoids fighting SCons semantics.

## Goals

1. Add **`--info`** — print cuppa version (and a small fixed fact block) then **exit 0** without
   loading the project `sconstruct` or attempting a build.
2. Keep **`check_current_version()`** on normal builds (unchanged line for log familiarity).
3. Honour **`--offline`** for the optional PyPI “newer version available” check (same as today).
4. Optional machine-readable output aligned with other list modes (see §Output shapes).

## Non-goals

- Replacing `pip show cuppa` or packaging metadata queries.
- Printing the full SCons help tree.
- `--version` alias on cuppa (reserved / ambiguous with SCons).
- Full environment dump (`--dump` already exists for configure debugging).

## Settled behaviour

| Flag | Behaviour |
|------|-----------|
| `--info` | Print cuppa version; exit **before** `sconstruct` load and toolchain registration |
| `--info` + `--offline` | Skip PyPI latest-version probe |
| `--info` + `--list-format=json` | Single JSON object on stdout (see below) |

**Primary path:** `cuppa/__main__.py` handles `--info` in the wrapper **before** spawning
SCons — works with or without `-D`, no project required.

**Fallback:** `cuppa/core/base_options.py` registers `--info`; `construct.py` exits after
reading offline / list-format if someone invokes `scons --info` through a loaded
sconstruct (still loads the file, but skips toolchain registration).

### Text output (default)

```text
cuppa 1.12.0.dev
```

Do **not** repeat the redundant `cuppa: version` prefix in `--info` text mode (cleaner for scripts);
normal builds keep today's log line. No embedded SCons / Python lines in this cut (keep minimal).

### JSON output (`--list-format=json`)

```json
{
  "cuppa_version": "1.12.0.dev",
  "offline": false,
  "pypi_latest": "1.11.0"
}
```

Omit `pypi_latest` when offline or probe fails silently (same as `check_current_version` today).

## Implementation sketch

| Area | Touch |
|------|--------|
| CLI | `--info` in `base_options.py` |
| Wrapper early exit | `cuppa/__main__.py` before `run_scons` |
| Logic | `report_info` / `probe_pypi_latest` in `version.py` |
| Fallback | `construct.py` after offline option |
| Tests | Unit: argv helpers, text/JSON, offline skip, wrapper exit without scons |
| Docs | Antora inspect CLI; AGENTS.md preferred invocation |

## Work slices

| Slice | Deliverable |
|-------|-------------|
| A | `--info` flag + text output + wrapper early exit |
| B | JSON + `--offline` / PyPI probe sharing |
| C | Docs + unit tests |

Target: **1.12.0**.

## Refusal rules

| Request | Response |
|---------|----------|
| Hijack SCons `--version` | Refuse — use `--info` |
| Load sconstruct for `--info` (wrapper path) | Refuse — defeats the purpose |
| Hide version on normal builds | Refuse — keep configure line unless hygiene plan changes it separately |

## 1.12.0 console bundle

Listed alongside [`build-log-hygiene.md`](build-log-hygiene.md) and
[`terse-build-output.md`](terse-build-output.md).

## Progress snapshot

| Slice | Status |
|-------|--------|
| Plan | **This document** |
| A — `--info` text | **This PR** |
| B — JSON / offline | **This PR** |
| C — Docs | **This PR** |

## Open questions

1. Include embedded **SCons** version in text/json output? — **Deferred** (keep minimal).
2. Should CI scripts migrate from grepping configure logs to `cuppa --info` only? — encouraged in docs; not forced.
