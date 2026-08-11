# Plan: configure-time build log hygiene

- **Status:** proposal
- **Related:** [`ROADMAP.md`](../../ROADMAP.md) — Build console output (`console-log-hygiene`); shipped [`archive/list-toolchains.md`](../archive/list-toolchains.md); companion [`terse-build-output.md`](terse-build-output.md) (action-time output — **not** this plan); [`cuppa-info.md`](cuppa-info.md)
- **Updated:** 2026-08-11
- **Impact:** patch — log levels and message text only; default behaviour unchanged at `--verbosity=info` for most lines **except** the demoted messages (quieter normal builds)

## Why

Normal `cuppa -D --dbg` configure still prints long **info** blocks before any compile action:

```text
cuppa: toolchain_archive: [info] Registered toolchain [clang24_profiles_2026_08_07_27] from […] at […] (clang 24.0)
cuppa: construct: [info] available toolchains are ['gcc95', 'gcc9', …, 'clang']
cuppa: construct: [info] No active variants specified so toolchain defaults of ['dbg':'<cuppa.variants.dbg.Dbg object at 0x…>', 'rel':'<…>'] being used.
```

Problems:

1. **Registered toolchain** — one line per archive entry; useful once while debugging registration, noise on every build now that **`--list-toolchains`** exists ([#172](https://github.com/ja11sop/cuppa/issues/172)).
2. **available toolchains are […]** — dumps every registered name; same information as `cuppa --list-toolchains` in a structured tree.
3. **Variant defaults line** — **`colour_items` on a dict** stringifies values (`str(Dbg object)`), not variant **names** (`dbg`, `rel`). Same bug pattern on **Default build actions** when `active_actions` is a dict.

[`terse-build-output.md`](terse-build-output.md) addresses **per-action** success/failure lines during build/test; it does **not** cover configure-time registration spam. Keep this as a **separate plan** so log hygiene ships even if terse Phase 2 slips, and so demotions are not tied to `--terse-output`.

## Goals

1. **Demote** archive registration + full toolchain name list to **`logger.debug`** (still visible with `--verbosity=debug`).
2. **Fix** variant/action default messages to print **sorted variant/action names** only.
3. Optionally **one** concise **info** line when defaults apply, e.g. `Using variant defaults: dbg, rel` — TBD in PR (may stay debug-only if terse configure line is enough).
4. Document where to discover toolchains (`--list-toolchains`) and variants (`--help` / project `default_variants`).

## Non-goals

- Terse **`Progress( … )`** / spawn output (see [`terse-build-output.md`](terse-build-output.md)).
- Demoting **warnings**, **errors**, or **list/wipe judgement trees**.
- Hiding **`cuppa: version …`** (see [`cuppa-info.md`](cuppa-info.md) for version without a build).
- Demoting VCS / branch / offline banners in this slice (separate follow-on if needed).

## Settled changes (proposal)

| Location | Today | Proposed |
|----------|-------|----------|
| `cuppa/toolchains/toolchain_archive.py` — `Registered toolchain […]` | `logger.info` | `logger.debug` |
| `cuppa/construct.py` — `available toolchains are […]` | `logger.info` | `logger.debug` |
| `cuppa/construct.py` — `Default build variants of …` / `No active variants …` | `colour_items(active_variants)` on **dict** | `colour_items(sorted(active_variants.keys()), as_info)` |
| `cuppa/construct.py` — `Default build actions of …` | `colour_items(active_actions)` on **dict** | `colour_items(sorted(active_actions.keys()), as_info)` |

**Trace parity:** existing `logger.trace( "supported toolchains …" )` in `add_toolchains` stays.

## Implementation sketch

| Area | Touch |
|------|--------|
| Toolchain archive | `_register_clang_entries` / `_register_gcc_entries` log level |
| Construct | `add_toolchains`, variant/action default info lines |
| Tests | Unit: mock logger; assert debug vs info; assert default-variant message contains `dbg` not `Dbg object` |
| Docs | Antora CLI / troubleshooting — “see `--list-toolchains`”; CHANGELOG under `[1.8.0]` |

No new CLI flags required.

## Work slices

| Slice | Deliverable |
|-------|-------------|
| A | Demote registration + available-toolchains list to debug |
| B | Fix dict formatting on variant/action default lines + unit tests |
| C | Docs + CHANGELOG |

Target: **1.8.0** — small patch; land early in the cycle alongside [`terse-build-output.md`](terse-build-output.md) Phase 1.

## Refusal rules

| Request | Response |
|---------|----------|
| Gate demotions behind `--terse-output` | Refuse — hygiene helps all builds |
| Remove `--list-toolchains` because logs are quieter | Refuse — list is the structured inventory |
| Demote build failures to debug | Refuse |

## 1.8.0 bundle

Part of the maintainer **1.8.0 console focus** with:

- [`terse-build-output.md`](terse-build-output.md) — Phase 1 (`--terse-output`)
- [`cxx-profiles-report.md`](cxx-profiles-report.md) — slices A–D
- [`cuppa-info.md`](cuppa-info.md) — `--info`

[`native-toolchain-output.md`](native-toolchain-output.md) remains optional for 1.8.0 if scope is tight.

## Progress snapshot

| Slice | Status |
|-------|--------|
| Plan | **This document** |
| A — Demote logs | Not started |
| B — Fix dict messages | Not started |
| C — Docs | Not started |
