# Plan: `--skip-location-update`

- **Status:** shipped
- **Related:** [`cascade-consume-ux-soak.md`](cascade-consume-ux-soak.md)
  (`skip-resolve` sketch); [`ROADMAP.md`](../../ROADMAP.md) — was
  `cascade-skip-resolve` / cheap plan; [`cuppa/location.py`](../../cuppa/location.py)
  `retrieval_disabled_reason`; Antora
  [`cli/dependencies-and-develop.adoc`](../../docs/modules/ROOT/pages/cli/dependencies-and-develop.adoc);
  [`cli/building.adoc`](../../docs/modules/ROOT/pages/cli/building.adoc);
  done on [#379](https://github.com/ja11sop/cuppa/pull/379)
- **Updated:** 2026-10-29
- **Impact:** minor — new global flag; location retrieve/update path only

## Problem

Tip configure (including `--cascade-plan`) pays a full location fetch/update for
every git dependency even when the operator only wants to **build against the
trees already on disk**. `--offline` freezes locations **and** blocks package
downloads / other network, so it is the wrong knob for “online build, frozen
location working copies.”

Soak sketch name was `--skip-resolve`; that oversells — Cuppa still **resolves**
paths to on-disk trees; it should only skip the VCS update/fetch step.

## Settled lean

| Choice | Lean |
|--------|------|
| Name | **`--skip-location-update`** (one-shot for this run). Rejected: `--skip-resolve` (implies no resolve), `--freeze-locations` (sounds sticky/config) |
| Legal where | **Any** tip build / plan / nest (not cascade-only) |
| What is skipped | Location dependency fetch, clone, update, and remote branch/default probes |
| What stays online | GitLab package download/extract, cascade registry/publish network, PyPI version check, unrelated maintenance unless refused below |
| Missing tree | Still **fails** (same class as offline missing) — drop the flag to retrieve |
| vs `--offline` | Orthogonal; offline is broader “no remote work.” Both set → report `--offline` as the disable reason |
| Develop maintenance | **Refuse** with `--update-develop` / `--clone-develop` / `--checkout-develop-branch` / `--reset-develop-branch` |
| Nest | Cuppa-owned flag → forwarded on nest argv (not tip-local; not in nest drop list) |
| Chrome | Mode banner `Running with SKIP LOCATION UPDATE` when set and not offline |

## Progress

| Item | Status |
|------|--------|
| Naming + legality settled | Done — this plan |
| Option + `process_location_options` + conflict refusals | Done |
| `retrieval_disabled_reason` + relative remote probes | Done |
| Mode banner + Antora + CHANGELOG + ROADMAP | Done |
| Unit tests | Done |

## Out of scope

- Skipping the on-disk walk / SCM status entirely (true “cheap plan” CPU)
- Making `--offline` stop walking locations
- Auto-stashing or discarding dirty trees
