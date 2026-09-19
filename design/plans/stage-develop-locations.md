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
project I am editing":

- The tip needs libraries or generated artefacts that only appear after building that project
  in its own checkout (CMake install under `final/`, staged libs, codegens, …).
- They may already have built it there — tip `--develop` is enough.
- Or they want the tip command to **ensure** that project is built (and cleaned) without
  changing directory — the same discover vs stage split packages now have.

Today the only way to get that is to leave the tip, build the location tree by hand, then return.
`--stage-develop` already names that intent for packages; extending it to **qualifying location
trees** would make one flag mean "also build my develop working copies when they are projects."

## What location `--develop` does today (unchanged by this plan's default)

| Step | Behaviour |
|------|-----------|
| Resolve | `develop_location(sconstruct_dir, develop)` |
| Build | Tip `BuildWith` / includes point at the develop tree; tip compiles those sources |
| Clean | Tip `-c` cleans the tip graph only |

## Shipped meaning (L1/L2)

Same two modes as packages, applied to location develop trees that look like **Cuppa
projects** (presence of `sconstruct` / `SConstruct`):

| Mode | Flags | Location develop with sconstruct |
|------|--------|----------------------------------|
| Discover | `--develop` | Today's swap; tip compiles the tree. No nest. |
| Stage | `--develop --stage-develop` | Nested `cuppa` session in that tree (forward tip variant/toolchain/`--parallel`/`--test`; **not** package `--stage-package`). Then tip continues with the usual develop swap. With `-c`, nest-clean those trees too. |

Location trees **without** an sconstruct stay discover-only. Package publisher-shaped
`develop=` trees still use the package nest path.

### Nested session (settled)

1. Nested `cuppa -D` via `tip_forward_args(..., project_only=True)` — no
   `--publish-package` / `--stage-package`; `--stage-develop` dropped (single-level).
2. Candidates surveyed from tip dependencies before tip sconscripts
   (`run_location_stage_develop`) so banners show real `N of M`.
3. Order today: tip `default_dependencies` declaration order, then remaining names
   sorted. Not leaf-first across develop projects.
4. Nested env sets `PYTHONUNBUFFERED=1` (tip cuppa pipes stdout).
5. Tip still uses the develop path as source/include root (L3 deferred).

## Non-goals (still)

- Changing location `--develop` alone.
- Auto-nesting on missing artefacts without `--stage-develop`.
- Nesting into non-Cuppa trees.
- Replacing cascade / package `--stage-develop` semantics.

## Soak findings (matching_facility)

| Finding | Decision |
|---------|----------|
| Banner said `1 of 1: moo` then silence | Collect-then-run + `PYTHONUNBUFFERED`. |
| Expect `1 of 13` | Survey all location develops with an sconstruct (skip package deps). |
| `--parallel` / `--test` on the tip | Forward into each nest; nests themselves stay sequential `1…N`. |
| Need cascade-style topo / plan? | Follow-on — see L4 below. |

## Follow-on: `--stage-develop-plan` and ordered stage builds (L4)

**Why:** With 13 develop projects, declaration order is a guess. If project A’s nested
build needs artefacts from B’s `_build`, nesting A before B fails or forces a second
pass. Operators also want a dry-run like `--cascade-plan` before committing wall-clock
to a full forest.

### `--stage-develop-plan`

| Requirement | Detail |
|-------------|--------|
| Flags | `--stage-develop-plan` requires `--develop` (and implies the stage-develop candidate set). Prefer **not** requiring `--stage-develop` so review is cheap — mirror `--cascade-plan` requiring the cascade flag only if that reads clearer in soak. |
| Output | Judgement-tree / table: dependency name, path, reason included (has sconstruct), order index, notes (skipped prefix-shaped / package-managed). |
| Side effects | No nested build or clean; exit after report (construct stop-before-build, same family as cascade plan/collect). |
| Exit status | Non-zero only on hard errors (e.g. missing develop path that cannot stage); warnings for odd trees stay warnings. |

### Ordered stage builds

| Requirement | Detail |
|-------------|--------|
| Goal | Leaf-first (or otherwise safe) order over the **location stage candidate** set so a nested build of A sees B’s artefacts when A’s develop tree depends on B. |
| Edge source (leaning) | For each candidate project, read that tree’s configured develop / package edges the way cascade resolves publisher deps — at minimum, tip-visible `default_dependencies` among candidates; better, survey each candidate’s own `sconstruct` dependency graph (location + package develop paths that intersect the candidate set). |
| Cycles | Report and refuse (or break with a documented tie-break), same spirit as cascade topo. |
| Interaction with plan | `--stage-develop-plan` prints the resolved order; `--stage-develop` executes it. |
| Non-goal for L4 | Parallel nested sessions (multiple develops at once) — tip `--parallel` already fans out *inside* each nest; cross-nest parallelism is a later performance slice. |

### Precedent

Reuse vocabulary and stop-before-build patterns from
[`package-build-publish-deps.md`](package-build-publish-deps.md) (`--cascade-plan`,
topo publish order, nested session banners) rather than inventing a second report shape.

## Slices

| Slice | Content | Impact |
|-------|---------|--------|
| L0 | Plan + ROADMAP | none — **shipped** |
| L1 | Nest location develops under `--stage-develop`; survey + `N of M`; unit + integration | `minor` — **this branch** (soak OK) |
| L2 | Nest `-c`; docs; unbuffered nested output | `minor` — **with L1** |
| L3 | Optional: tip prefers staged libs from location `final/` when present | `minor` — only if soak demands |
| L4 | `--stage-develop-plan` + leaf-first ordered stage builds | `minor` — **next** |

## Success criterion (L1/L2 soak) — met

- `cuppa -D --dbg --develop` — no nest.
- `cuppa -D --dbg --develop --stage-develop` — `develop stage: N location projects`, then `1 of N` … with live nested output; tip build afterward.
- `--parallel` / `--test` forward into nests; `-c --stage-develop` nest-cleans.

## Relationship to package D

| | Package publisher `develop=` | Location `develop=` with sconstruct |
|--|------------------------------|-------------------------------------|
| `--develop` | Discover package stage / fail with hint | Tip compiles develop tree |
| `--develop --stage-develop` | Nest `--stage-package`; tip links stage | Nest project build; tip still uses develop path |
| Clean without `--stage-develop` | Tip only | Tip only |
| Clean with `--stage-develop` | Nest clean | Nest clean |

One flag, two consume models, same operator story: **discover by default, stage when asked.**
