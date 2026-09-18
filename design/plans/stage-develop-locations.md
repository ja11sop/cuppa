# Plan: `--stage-develop` for location dependencies

- **Status:** proposal
- **Related:** [`ROADMAP.md`](../../ROADMAP.md) — `stage-develop-locations`; [`package-develop-local.md`](package-develop-local.md) (package half of `--stage-develop`); [`build_with_location.py`](../../cuppa/build_with_location.py); [`develop.py`](../../cuppa/develop.py)
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

`--stage-develop` without this work is a no-op for location deps (flag may be set; nothing nests).

## Proposed meaning

Keep the same two modes as packages, applied to location develop trees that look like **Cuppa
projects** (presence of `sconstruct` / `SConstruct` — same shape test as
`develop_names_a_publisher_tree`):

| Mode | Flags | Location develop with sconstruct |
|------|--------|----------------------------------|
| Discover | `--develop` | Today's swap; tip compiles the tree. No nest. |
| Stage | `--develop --stage-develop` | Nested `cuppa` session in that tree (forward tip variant/toolchain; **not** package `--stage-package` unless the nested project publishes). Then tip continues with the usual develop swap. With `-c`, nest-clean those trees too. |

Location trees **without** an sconstruct stay discover-only (nothing to nest). Passing
`--stage-develop` does not error for them — they simply do not participate (same as a
prefix-shaped package path ignoring stage).

### What the nested session builds

Open until first implementation soak, with this leaning:

1. **Default:** nested `cuppa -D` with tip-forwarded global flags (variant, toolchains, offline,
   clean) — same argv shaping family as package stage / cascade, minus package-only flags and
   tip dependency-scoped overrides.
2. **Not** implied: upload, cascade, or `--stage-package` unless the nested sconstruct's own
   `PublishPackage` graph runs as part of a normal build (as today without `--publish-package`).
3. **Success for the tip:** nested session exit 0. Tip does **not** switch to consuming a package
   stage for a location dep — it still uses the develop path as source/include root unless a
   later slice teaches location deps to prefer staged libs (out of scope here).

So for locations, "stage" means **ensure the develop project's build has run** (artefacts on
disk for whatever that project produces), not "rebind the tip to `final/<pkg>/<ver>/`."

## Why this is useful

- Tip depends on location project B; B needs a CMake configure/build (or Cuppa static libs)
  before tip's link or codegen sees outputs under B's tree.
- Operator iterates in tip; occasional `--stage-develop` rebuilds B without `cd`.
- Tip `-c --stage-develop` deep-cleans B's Cuppa `_build` / registered cleans — closing the
  same hole package D hit for package stages.

## Non-goals

- Changing location `--develop` alone (always in-tip compile).
- Making every location dep behave like a GitLab package consume.
- Auto-nesting on missing artefacts without `--stage-develop` (keep discover cheap).
- Nesting into non-Cuppa trees (no sconstruct) or inventing a second develop kwarg.
- Replacing cascade / package `--stage-develop` semantics.

## Open questions

| # | Question | Leaning |
|---|----------|---------|
| 1 | Nested default targets: full project default, or require `PublishPackage` / a named method? | Full default build first; document that projects that only build on explicit targets need a follow-on. |
| 2 | Should nested location sessions forward `--develop` (recursive stage of B's deps)? | Forward `--develop`; drop `--stage-develop` on the child (same as package nest drops tip `--stage-develop`) so recursion is one level unless the child opts in again — or never forward `--stage-develop` and document single-level only. Prefer **single-level** for v1. |
| 3 | Ordering: nest before tip sconscript read (like package consume) vs SCons Depends? | Nest during location resolve / early BuildWith, sequential, package-style — tip must not compile against a half-built B. |
| 4 | Interaction when the same path is both a package `develop=` and a location develop? | Rare; package path wins if both declare it. Call out in docs. |
| 5 | Banner copy | Reuse `develop stage` banners; say `location` in the label when not a package pin (`develop stage 1 of 1: <name>`). |

## Slices (suggested)

| Slice | Content | Impact |
|-------|---------|--------|
| L0 | Plan + ROADMAP (this document) | none |
| L1 | Qualify location develop trees with sconstruct; nest build under `--stage-develop`; drop flag on nested argv; unit + one integration fixture | `minor` |
| L2 | Nest `-c` for those trees; docs (`develop.adoc` + CLI) | `minor` / patch if L1 already documented |
| L3 | Optional: tip prefers staged libs from location `final/` when present — only if soak demands it | `minor` |

## Success criterion (soak)

A tip with a location `develop=` pointing at another Cuppa checkout:

- `cuppa -D --dbg --develop` — no nest; tip builds as today.
- `cuppa -D --dbg --develop --stage-develop` — nested session in that checkout, then tip build.
- `cuppa -D --dbg --develop --stage-develop -c` — nested clean then tip clean.

## Relationship to package D

| | Package publisher `develop=` | Location `develop=` with sconstruct |
|--|------------------------------|-------------------------------------|
| `--develop` | Discover package stage / fail with hint | Tip compiles develop tree |
| `--develop --stage-develop` | Nest `--stage-package`; tip links stage | Nest project build; tip still uses develop path |
| Clean without `--stage-develop` | Tip only | Tip only |
| Clean with `--stage-develop` | Nest clean | Nest clean |

One flag, two consume models, same operator story: **discover by default, stage when asked.**
