# Plan: Persist resolved Boost “latest” across offline runs

- **Status:** shipped
- **Related:** [#171](https://github.com/ja11sop/cuppa/issues/171); [#170](https://github.com/ja11sop/cuppa/pull/170);
  [`ROADMAP.md`](../../ROADMAP.md) — Boost source and packages; [`boost-updates.md`](../plans/boost-updates.md) (patched/clean package identity — separate); [`ideas/scratchpad.md`](../ideas/scratchpad.md) (graduated)
- **Updated:** 2026-08-09
- **Impact:** minor — persisted latest version scoped with downloads-root; lazy network check; existing `--boost-latest` kept as an explicit “force latest” switch

## Why

Source Boost can resolve `latest` / `current` by scraping
https://www.boost.org/releases/latest/
([`determine_latest_boost_version`](../../cuppa/dependencies/boost/version_and_location.py)).
When offline, the same path falls back to the hard-coded
[`current_boost_release()`](../../cuppa/dependencies/boost/version_and_location.py) string
shipped in that Cuppa version.

A common CI shape breaks around Boost releases:

1. Online, parallel: download/build (picks e.g. 1.92.0 just published).
2. Offline, serial `--test`: resolve again → offline fallback → older Cuppa default
   (e.g. 1.91.0) → wrong tree under `--downloads-root` / extract homes.

`--boost-latest` already forces “use whatever is latest” and triggers a check. The gap is
**remembering a higher version that was actually downloaded**, scoped like the download cache,
and **not** scraping Boost when the project never uses Boost.

This is **not** the patched/clean GitLab package identity work in [`boost-updates.md`](../plans/boost-updates.md).

## Goals

1. Persist the remembered Boost latest version so offline runs reuse it.
2. Scope that store from **`--downloads-root`**: project-local downloads → project conf;
   shared/global downloads → global conf (same sharing as the archives).
3. Update the store automatically when a **higher** version has been **downloaded** (or is
   already present under downloads_root after this run selected it as latest).
4. Scrape / check the Boost site only when Boost is **used** on a download path, or when
   **`--boost-latest`** is passed — not on idle built-in registration for non-Boost projects.
5. Keep explicit `--boost-version=` / `--boost-location=` / `--boost-home=` authoritative.

## Non-goals

- Auto-updating Cuppa’s shipped `current_boost_release()` from the network.
- Changing GitLab `boost_package` version selection.
- A new `--boost-latest-version=` pin flag in the first slice (conf + automatic remember suffice).
- Scraping on every configure when Boost is unused.

## Today

| Piece | Behaviour |
|-------|-----------|
| `--boost-latest` | Boolean; forces version `"latest"` in `boost_location_id` |
| Default when nothing specified | Also treats version as `"latest"` → **always scrapes when Boost is constructed** |
| Online `latest`/`current` | HTML scrape → version string → archives URL |
| Offline `latest`/`current` | Log + use `current_boost_release()` (compiled-in) |
| Persistence | None |
| Surprise | Projects can see a Boost version check even when they did not intend a “latest” probe |

## Settled decisions

| Topic | Decision |
|-------|----------|
| What to persist | Full version string (e.g. `1.92.0`), key `boost_latest_version` |
| Where to persist | If `abspath(downloads_root)` is under `abspath(sconstruct_dir)` → **project** `configure.conf`; else → **`~/.cuppaconfig`**. Rationale: shared downloads root ⇒ shared remembered latest; project-only cache ⇒ project-only memory. |
| When to update | Only if the candidate version is **strictly higher** than the stored value (or none stored) **and** that version’s archive is present under `downloads_root` after this run’s resolve/fetch (fresh download **or** cache hit of the selected latest). |
| Automatic | Yes — not gated on `--boost-latest`. |
| `--boost-latest` | Explicit “use the latest, whatever that is”; **forces** a network check when online. Persistence still follows higher+present-under-downloads-root. |
| When to scrape | (1) `--boost-latest`, or (2) Boost is **actually used** and the resolve path needs the Boost site / download. **Not** on mere dependency registration for unused Boost. |
| Default without `--boost-latest` | Do **not** scrape. Prefer stored `boost_latest_version`, else `current_boost_release()`. |
| Read / resolve order | (1) explicit version / location / home → (2) `--boost-latest` → scrape then use → (3) stored value → (4) `current_boost_release()` |
| Write mechanism | Upsert one key in the chosen conf file (preserve other keys). |

## Refusal rules

- Do not persist a failed scrape’s fallback.
- Do not persist a version that was never downloaded / not present under `downloads_root`.
- Do not overwrite a stored version with a lower one.
- Do not let persistence override explicit `--boost-version=` / location / home.
- Do not scrape Boost when the built-in is registered but unused.
- Do not put secrets in the persisted value.

## Work slices

| ID | Slice | Notes |
|----|--------|-------|
| `boost-latest-scope` | Helper: downloads_root under project? → conf path | Unit-test path cases |
| `boost-latest-upsert` | Conf key upsert (project or global) | Preserve other keys |
| `boost-latest-lazy` | Stop default “nothing specified” from implying a scrape; store then compiled-in | Behaviour change + tests |
| `boost-latest-update` | After successful download / cache-present latest, update if higher | Hook near Location/Boost fetch |
| `boost-latest-flag` | `--boost-latest` forces scrape; still respects update rules | |
| `boost-latest-docs` | Dependencies / Boost: CI recipe, downloads-root scoping, flag vs automatic | Antora |
| `boost-latest-tests` | Unused Boost = no scrape; project vs global store; offline read; higher-only update | |

## Suggested first PR

`boost-latest-scope` + upsert + lazy default + update-on-download + `--boost-latest` + docs/tests.

## Progress

| ID | Status |
|----|--------|
| `boost-latest-scope` | done |
| `boost-latest-upsert` | done |
| `boost-latest-lazy` | done |
| `boost-latest-update` | done |
| `boost-latest-flag` | done |
| `boost-latest-docs` | done |
| `boost-latest-tests` | done |

## Open decisions

None — shipped in [#171](https://github.com/ja11sop/cuppa/issues/171) / [#170](https://github.com/ja11sop/cuppa/pull/170).
