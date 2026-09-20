# Plan: `--stage-develop` for location dependencies

- **Status:** in progress
- **Related:** [`ROADMAP.md`](../../ROADMAP.md) — `stage-develop-locations`; [`package-develop-local.md`](package-develop-local.md) (package half of `--stage-develop`); [`package-build-publish-deps.md`](package-build-publish-deps.md) (cascade plan / topo precedent); [`build_with_location.py`](../../cuppa/build_with_location.py); [`develop.py`](../../cuppa/develop.py); [`location.py`](../../cuppa/location.py)
- **Updated:** 2026-09-20
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
3. **Order (nest execute):** leaf-first over edges from each candidate's `develop=` declarations
   (top-level sconstruct/sconscript) and `cuppa-publish.json` dependency names that intersect the
   **nestable** candidate set. Cycles refuse. Candidates with no edges keep a stable topo among
   isolates.
4. Nested env sets `PYTHONUNBUFFERED=1`.
5. Tip still uses the develop path as source/include root (L3 deferred).

## Soak findings (matching_facility)

| Finding | Decision |
|---------|----------|
| Banner said `1 of 1: moo` then silence | Collect-then-run + `PYTHONUNBUFFERED` (L1/L2). |
| Expect `1 of 13` | Survey all location develops with an sconstruct. |
| `--parallel` / `--test` | Forward into each nest; nests stay sequential `1…N`. |
| Need cascade-style topo / plan? | **L4** — `--stage-develop-plan` + leaf-first order. |
| Plan should show broken deps in-place | L4 UX revision — interleaved `unstaged` nodes (below). |

## L4: `--stage-develop-plan` and ordered stage builds

| Requirement | Detail |
|-------------|--------|
| Flags | `--stage-develop-plan` requires `--develop`; does **not** require `--stage-develop`. |
| Side effects | None — develop-action early exit (same family as `--list-develop`). |
| Edge source (nest) | Among nestable candidates only. |
| Execute | `--stage-develop` uses leaf-first nestable order (unchanged by plan UX). |
| Non-goal | Parallel nested sessions across develops; changing nest refuse rules via the plan alone. |

### L4 plan report UX (settled 2026-09-20)

Closer to `--cascade-plan`: every location develop stays visible; judgements hang under the
node; a footer summarises nestable vs unstaged. Nest behaviour is **unchanged** — this slice
is report-shaped.

#### Vocabulary and counts

**Staging a location develop** (the `--stage-develop` flag) means running a **nested
project build** in that checkout — the same idea as a nest under cascade, scoped to
location `develop=` trees. Report copy says **will stage** / **unstaged** so it tracks
the flag name; “nest” appears only where it clarifies the mechanism (e.g. summary
parenthetical).

| Term | Meaning |
|------|---------|
| Considered | Every tip location `develop=` (packages excluded). |
| Will stage | Path is a directory with `sconstruct` / `SConstruct` — nest-built under `--stage-develop`; gets `K of M`. |
| Unstaged | Considered but will not be nest-built — tree marker `unstaged` (not an ordinal). |

| Number | Where |
|--------|--------|
| Intro subject | All considered (e.g. `13 location projects`) |
| `[E errors][W warnings][N notes]` | Sum of nested judgements under those nodes |
| `K of M` | Will-stage only (`M` = stage count); matches execute order |
| Summary | `M` will stage / `U` unstaged (+ reasons); `--clone-develop` once if any path missing |

#### Tree order

**Leaf-first execute order** for every row that will stage (`1 of M` … `M of M` top to
bottom). Unstaged rows follow that block (still in tip declaration order among
themselves). Declaration order is not used for the nestable list — execute order is
stable, matches `--stage-develop`, and can inform a better sconstruct layout.

#### Severity map

| Situation | Marker | Severity | Nested under node | Exit |
|-----------|--------|----------|-------------------|------|
| Develop path missing | `unstaged` | **error** | Short prose: path does not exist (no per-node `--clone-develop`) | 1 |
| Path exists, no sconstruct | `unstaged` | **warning** | Not an SCons project; will not nest; tip may still use files | 0 |
| Nestable, branch neither tip nor `main`/`master` (nor configured default/base) | `K of M` | **warning** | Branch deviates from expected set (tip + preferred default emphasised; other default plain info) | 0 |
| Nestable, not a git working copy | `K of M` | **note** | Expected a repository; can proceed with path only | 0 |
| Nestable, clean / modified / ahead / behind | `K of M` | (none) | State stays in muted `(host/org/repo@branch state)` only | 0 |
| Cycle among nestables / plan without `--develop` | — | hard stop | No tree | 1 |

Off-branch is a counted warning on a **nestable** node. No-sconstruct is **unstaged** + warning.
Do not conflate them.

#### Node chrome

- Command banner: emphasise `--stage-develop-plan` (info/bold) like `--develop`.
- Tip preamble: this project’s name + muted `(host/org/repo@branch …)` with the tip
  **branch** emphasised info (it anchors later off-branch warnings); one line on
  considered vs will-stage / unstaged counts.
- Parenthetical: observed checkout (`host/org/repo@branch state`); missing trees use
  `wants host/org/repo` from configured `location=` (keep a trailing `@` / `@rev` when the
  sconstruct declares it). Same short-name style throughout.
- Off-branch: warning colour on the branch token **and** a nested warning judgement.
  Expected-branch prose lists tip first (emphasised info), then the tip repo’s
  default from local `origin/HEAD` when known (else `--location-default-branch` /
  `master`, also emphasised info), then the other of `main`/`master` as plain info —
  e.g. `(feature_1 or master or main)` when the tip is on `feature_1` and default is
  `master`.
- `project […]` path in info; breathing stubs as today.
- `depends on […]`: edges among the **full considered name set** (including unstaged). Nestable
  names info; unstaged names coloured by that dependency’s severity (missing → error,
  no-sconstruct → warning). Plain words/brackets/commas; wrap between names.
- Unstaged nodes: cascade-style nested severity group (`1 error` / `1 warning`); no depends-on
  when the tree is missing (nothing to observe).

#### Footer

```
└── Stage plan summary
    ├── M projects will stage under --stage-develop (nested project build)
    └── U unstaged:
        │
        ├── name [path]
        …
        └── Use --clone-develop to obtain missing projects   # only if any missing
```

Replace the old `--stage-develop-plan: N planned; nothing was built…` chip with this summary; keep
a one-line “nothing was built or cleaned” note if useful beside the summary.

#### Explicit non-goals (this UX slice)

- Refusing `--stage-develop` nests for off-branch checkouts (plan warns only).
- Promoting `modified` / `N behind` into counted notes.
- Package develops in this tree (still the package stage path).

## Slices

| Slice | Content | Impact |
|-------|---------|--------|
| L0 | Plan + ROADMAP | none — **shipped** |
| L1 | Nest location develops; survey + `N of M` | `minor` — **shipped** in [#313](https://github.com/ja11sop/cuppa/pull/313) |
| L2 | Nest `-c`; docs; unbuffered nested output | `minor` — **shipped** with L1 in [#313](https://github.com/ja11sop/cuppa/pull/313) |
| L3 | Optional: tip prefers staged libs from location `final/` | `minor` — only if soak demands |
| L4 | `--stage-develop-plan` + leaf-first ordered stage builds | `minor` — **this branch** / [#315](https://github.com/ja11sop/cuppa/pull/315) |
| L4b | Plan report UX: execute-order tree, `unstaged` judgements, stage=nest vocab | `minor` — **this branch** |

## Success criterion (L4)

- `cuppa -D --develop --stage-develop-plan` — prints the plan; no nests; no `_build` under develops.
- `cuppa -D --develop --stage-develop` — nests nestable trees in leaf-first order.
- Plan shows every considered location develop; unstaged stay visible; `[E]/W]/N]` matches nested judgements.

## Relationship to package D

| | Package publisher `develop=` | Location `develop=` with sconstruct |
|--|------------------------------|-------------------------------------|
| `--develop` | Discover package stage / fail with hint | Tip compiles develop tree |
| `--develop --stage-develop` | Nest `--stage-package`; tip links stage | Nest project build (leaf-first); tip still uses develop path |
| `--develop --stage-develop-plan` | (n/a — package stage has no separate plan yet) | Report order + unstaged judgements; exit |
| Clean with `--stage-develop` | Nest clean | Nest clean |

One flag family, two consume models: **discover by default, stage when asked, plan when reviewing.**
