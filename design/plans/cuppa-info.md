# Plan: `cuppa --info` (version without a build)

- **Status:** proposal
- **Related:** [`ROADMAP.md`](../../ROADMAP.md) — CLI (`cli-info`); [`build-log-hygiene.md`](build-log-hygiene.md); `cuppa/version.py`; companion list modes (`--list-toolchains`, …)
- **Updated:** 2026-08-11
- **Impact:** minor — new opt-in CLI flag; no change to default builds

## Why

Today the installed cuppa version appears only after configure starts a normal invocation:

```text
cuppa: version: [info] cuppa: version 1.8.0.dev
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

## Settled behaviour (proposal)

| Flag | Behaviour |
|------|-----------|
| `--info` | Print cuppa version; exit **before** `sconstruct` load and toolchain registration |
| `--info` + `--offline` | Skip PyPI latest-version probe |
| `--info` + `--list-format=json` | Single JSON object on stdout (see below) |

**Registration:** `cuppa/core/base_options.py` (or a tiny `cuppa/core/info_actions.py` mirroring
list-toolchain early exits).

**Early exit hook:** in `cuppa.run()` / `construct.py` immediately after
`check_current_version( offline )` **or** a lighter `print_version_only()` that shares
`get_version()` from `cuppa/utility/version.py` — **before** `toolchain_archive.prepare()` and
`add_toolchains()`. Goal: sub-second response with no project side effects.

### Text output (default)

```text
cuppa 1.8.0.dev
```

Optional second lines (PR decision — keep minimal):

```text
scons <embedded version if cheap to read>
python <sys.version split>
```

Do **not** repeat the redundant `cuppa: version` prefix in `--info` text mode (cleaner for scripts);
normal builds keep today's log line.

### JSON output (`--list-format=json`)

```json
{
  "cuppa_version": "1.8.0.dev",
  "pypi_latest": "1.7.0",
  "offline": false
}
```

Omit `pypi_latest` when offline or probe fails silently (same as `check_current_version` today).

## Implementation sketch

| Area | Touch |
|------|--------|
| CLI | `--info` in `base_options.py` |
| Early exit | `construct.py` or `cuppa/__init__.py` `run()` before heavy configure |
| Logic | Factor shared helper from `version.py` (`report_version( offline, out, format=… )`) |
| Tests | Unit: `--info` exits 0 without mock sconstruct; JSON shape; offline skips network |
| Docs | Antora CLI reference; AGENTS.md one-liner |

**Interaction with `-D`:** `--info` should work **with or without** `-D`; no sconstruct required.
If both `--info` and `-D` are passed, `--info` wins (document precedence).

## Work slices

| Slice | Deliverable |
|-------|-------------|
| A | `--info` flag + text output + early exit |
| B | JSON + `--offline` / PyPI probe sharing |
| C | Docs + integration test |

Target: **1.8.0** — small; independent of terse / Profiles report work.

## Refusal rules

| Request | Response |
|---------|----------|
| Hijack SCons `--version` | Refuse — use `--info` |
| Load sconstruct for `--info` | Refuse — defeats the purpose |
| Hide version on normal builds | Refuse — keep configure line unless hygiene plan changes it separately |

## 1.8.0 bundle

Listed alongside [`build-log-hygiene.md`](build-log-hygiene.md), [`terse-build-output.md`](terse-build-output.md), and [`cxx-profiles-report.md`](cxx-profiles-report.md) in ROADMAP **1.8.0 focus**.

## Progress snapshot

| Slice | Status |
|-------|--------|
| Plan | **This document** |
| A — `--info` text | Not started |
| B — JSON / offline | Not started |
| C — Docs | Not started |

## Open questions

1. Include embedded **SCons** version in text/json output?
2. Should CI scripts migrate from grepping configure logs to `cuppa --info` only?
