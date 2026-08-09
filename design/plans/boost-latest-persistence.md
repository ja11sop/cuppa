# Plan: Persist resolved Boost “latest” across offline runs

- **Status:** proposal
- **Related:** [`ROADMAP.md`](../../ROADMAP.md) — Boost source and packages; [`boost-updates.md`](boost-updates.md) (patched/clean package identity — separate); [`ideas/scratchpad.md`](../ideas/scratchpad.md) (graduated)
- **Updated:** 2026-08-09
- **Impact:** minor — new persisted config key and offline resolve behaviour; existing `--boost-latest` / explicit `--boost-version=` keep working

## Why

Source Boost can resolve `latest` / `current` by scraping
https://www.boost.org/releases/latest/ when online
([`determine_latest_boost_version`](../../cuppa/dependencies/boost/version_and_location.py)).
When offline, the same path falls back to the hard-coded
[`current_boost_release()`](../../cuppa/dependencies/boost/version_and_location.py) string
shipped in that Cuppa version.

A common CI shape breaks around Boost releases:

1. Online, parallel: download/build with “latest” (picks e.g. 1.92.0 just published).
2. Offline, serial `--test`: resolve “latest” again → offline fallback → older Cuppa default
   (e.g. 1.91.0) → wrong tree under `--downloads-root` / extract homes.

`--boost-latest` already exists as a boolean; the gap is **remembering the version discovered
online** so offline runs reuse it.

This is **not** the patched/clean GitLab package identity work in [`boost-updates.md`](boost-updates.md).

## Goals

1. After a successful online resolve of Boost `latest`/`current`, persist that version string.
2. When offline (or when the scrape fails), prefer the persisted value over
   `current_boost_release()` whenever the caller asked for latest/current.
3. Keep explicit `--boost-version=` / `--boost-location=` / `--boost-home=` authoritative.
4. Document the online→offline CI pattern and how persistence makes it safe.

## Non-goals

- Auto-updating Cuppa’s shipped `current_boost_release()` string from the network (the
  hard-coded default remains a last resort / documentation of “what this Cuppa knew at release”).
- Changing GitLab `boost_package` version selection.
- Replacing `--boost-latest` with a required version flag for all users.
- Scraping on every cold start when an explicit version is already set.

## Today

| Piece | Behaviour |
|-------|-----------|
| `--boost-latest` | Boolean; contributes to `boost_location_id` as version `"latest"` |
| Default when nothing specified | Also treats version as `"latest"` |
| Online `latest`/`current` | HTML scrape → version string → SourceForge/archives URL |
| Offline `latest`/`current` | Log + use `current_boost_release()` (compiled-in) |
| Persistence | None for the scraped value |

## Settled decisions (propose)

| Topic | Decision |
|-------|----------|
| What to persist | The **resolved full version** string from a successful online scrape (e.g. `1.92.0`), not a boolean |
| Config key | `boost_latest_version` (name TBD in implementation if an existing conf key fits better) |
| Where written | Prefer **global** `~/.cuppaconfig` so all projects share one “last seen latest”; optionally also project `configure.conf` if write helpers already scope that way — pick one primary in the first slice and document it |
| When written | Only after a **successful** online determine; never overwrite with the offline fallback |
| Offline read order | (1) explicit version/location/home → (2) persisted `boost_latest_version` if asking for latest → (3) `current_boost_release()` |
| CLI surface | Keep `--boost-latest`. Optional later: `--boost-latest-version=X.Y.Z` to pin/override without editing conf by hand |
| Bump of shipped default | Still a maintainer task when cutting Cuppa releases; persistence is the user-facing fix for the CI race |

## Refusal rules

- Do not persist a failed scrape’s fallback as if it were freshly discovered.
- Do not let persistence override an explicit `--boost-version=` / location / home.
- Do not put registry tokens or private URLs in the persisted value (version string only).

## Work slices

| ID | Slice | Notes |
|----|--------|-------|
| `boost-latest-persist-write` | On successful online resolve, write `boost_latest_version` via existing conf helpers | Unit-test with mocked scrape |
| `boost-latest-persist-read` | Offline / failed-scrape path reads persistence before `current_boost_release()` | Integration: plant conf, `--offline`, assert URL/home |
| `boost-latest-docs` | Dependencies / Boost docs: online then offline CI recipe | Antora |
| `boost-latest-pin-cli` | Optional `--boost-latest-version=` | Later if hand-editing conf is awkward |

## Suggested first PR

`boost-latest-persist-write` + `boost-latest-persist-read` + docs.

## Open decisions (confirm before coding)

1. Global-only vs project-level conf (or write-through both).
2. Whether a successful scrape that finds the **same** version as `current_boost_release()` still
   writes the key (yes — makes offline deterministic even when Cuppa’s default is current).
