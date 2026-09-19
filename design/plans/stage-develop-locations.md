# Plan: `--stage-develop` for location dependencies

- **Status:** in progress
- **Related:** [`ROADMAP.md`](../../ROADMAP.md) — `stage-develop-locations`; [`package-develop-local.md`](package-develop-local.md) (package half of `--stage-develop`); [`package-build-publish-deps.md`](package-build-publish-deps.md) (cascade plan / topo precedent); [`build_with_location.py`](../../cuppa/build_with_location.py); [`develop.py`](../../cuppa/develop.py); [`location.py`](../../cuppa/location.py)
- **Updated:** 2026-09-19
- **Impact:** `minor` — new behaviour under an existing opt-in flag; location `--develop` alone unchanged

## Problem

After [`package-develop-local`](package-develop-local.md) slice D, `--stage-develop` is
**package-only**: it nest-builds publisher-shaped package `develop=` trees so the tip can
consume `final/<package>/<version>/`, and nest-cleans them with `-c`.

**Location** dependencies already have a coherent `--develop` story: swap the retrieved tree
for the operator's working copy, and the tip compiles against that copy (includes / sources in
the tip graph). There is no nest, and tip `-c` does not wipe the develop tree's own `_build`.

That leaves a useful gap. Operators often treat a location `develop=` path as "another Cuppa
project I am editing" and want the tip to nest-build those projects on demand.

## Shipped meaning (L1/L2/L4)

| Mode | Flags | Location develop with sconstruct |
|------|--------|----------------------------------|
| Discover | `--develop` | Path swap; tip compiles the tree. No nest. |
| Plan | `--develop --stage-develop-plan` | Print leaf-first nest order; exit (no build/clean). |
| Stage | `--develop --stage-develop` | Nested project build/clean in leaf-first order; tip still uses the develop path. |

### Nested session (settled)

1. Nested `cuppa -D` via `tip_forward_args(..., project_only=True)`; drop `--stage-develop` /
   `--stage-develop-plan` (single-level).
2. Survey before tip sconscripts; banners show `N of M`.
3. **Order:** leaf-first over edges from each candidate's `develop=` declarations (top-level
   sconstruct/sconscript) and `cuppa-publish.json` dependency names that intersect the
   candidate set. Cycles refuse. Candidates with no edges keep a stable topo among isolates.
4. Nested env sets `PYTHONUNBUFFERED=1`.
5. Tip still uses the develop path as source/include root (L3 deferred).

## Soak findings (matching_facility)

| Finding | Decision |
|---------|----------|
| Banner said `1 of 1: moo` then silence | Collect-then-run + `PYTHONUNBUFFERED` (L1/L2). |
| Expect `1 of 13` | Survey all location develops with an sconstruct. |
| `--parallel` / `--test` | Forward into each nest; nests stay sequential `1…N`. |
| Need cascade-style topo / plan? | **L4** — `--stage-develop-plan` + leaf-first order. |

## L4: `--stage-develop-plan` and ordered stage builds

| Requirement | Detail |
|-------------|--------|
| Flags | `--stage-develop-plan` requires `--develop`; does **not** require `--stage-develop`. |
| Output | Cascade-plan-shaped tree: `N of M`, project path, depends-on notes; skips (no sconstruct / missing path) listed after. |
| Side effects | None — develop-action early exit (same family as `--list-develop`). |
| Exit status | Non-zero on missing develop paths or cycles; notes for non-sconstruct trees stay exit 0. |
| Edge source | `develop=` in each candidate's top-level sconstruct files + publish-manifest dependency names ∩ candidates. |
| Execute | `--stage-develop` uses the same order. |
| Non-goal | Parallel nested sessions across develops. |

## Slices

| Slice | Content | Impact |
|-------|---------|--------|
| L0 | Plan + ROADMAP | none — **shipped** |
| L1 | Nest location develops; survey + `N of M` | `minor` — **shipped** in [#313](https://github.com/ja11sop/cuppa/pull/313) |
| L2 | Nest `-c`; docs; unbuffered nested output | `minor` — **shipped** with L1 in [#313](https://github.com/ja11sop/cuppa/pull/313) |
| L3 | Optional: tip prefers staged libs from location `final/` | `minor` — only if soak demands |
| L4 | `--stage-develop-plan` + leaf-first ordered stage builds | `minor` — **this branch** |

## Success criterion (L4)

- `cuppa -D --develop --stage-develop-plan` — prints leaf-first order; no nests; no `_build` under develops.
- `cuppa -D --develop --stage-develop` — nests in that same order.

## Relationship to package D

| | Package publisher `develop=` | Location `develop=` with sconstruct |
|--|------------------------------|-------------------------------------|
| `--develop` | Discover package stage / fail with hint | Tip compiles develop tree |
| `--develop --stage-develop` | Nest `--stage-package`; tip links stage | Nest project build (leaf-first); tip still uses develop path |
| `--develop --stage-develop-plan` | (n/a — package stage has no separate plan yet) | Report order; exit |
| Clean with `--stage-develop` | Nest clean | Nest clean |

One flag family, two consume models: **discover by default, stage when asked, plan when reviewing.**
