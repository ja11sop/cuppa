# Plan: Develop a package dependency from its own source tree

- **Status:** proposal
- **Related:** [#297](https://github.com/ja11sop/cuppa/issues/297); [`ROADMAP.md`](../../ROADMAP.md) — `package-develop-local`; [`package-build-publish-deps.md`](package-build-publish-deps.md) (cascade resolution, `package_source`, `--clone-publishers`); [`package-download-refresh.md`](package-download-refresh.md) (same-version currency); [`develop.py`](../../cuppa/develop.py) (`configured_develop`, `survey`, `clone_develop`); [`gitlab.py`](../../cuppa/package_managers/gitlab.py) (`GitlabPackageDependency`, `_using_develop`); [`build_with_location.py`](../../cuppa/build_with_location.py) (`develop_location`)
- **Updated:** 2026-09-16
- **Impact:** `minor` for the resolution and clone slices; the consume change is `major` if it repurposes today's `develop=`, which §6 exists to avoid

## Problem

`--develop` on a **location** dependency is coherent: it swaps a retrieved tree for the
operator's working copy, and the build then compiles that copy. `--develop` on a **package**
dependency is three mechanisms disagreeing about what the develop path *is*:

| Mechanism | Treats a package's `develop=` as | Evidence |
|-----------|----------------------------------|----------|
| Consume (`GitlabPackageDependency`) | A **built prefix**: `_package_dir = _develop`, then `include/` and `lib/` under it, and download / extract skipped entirely | `gitlab.py` `_using_develop` |
| `--list-develop` | A **git working copy**: `configured_develop()` reads `_develop` off package dependencies and `survey()` asks `inspect()` for branch, upstream, and dirty state | `develop.py` `configured_develop` / `survey` |
| `--clone-develop` | A working copy it can never fill: `clone_source_for_dependency` returns a URL-less source for anything without `location_id`, so a package dependency is permanently *leave alone: no URL* | `develop.py` `clone_source_for_dependency` |

Two of the three already mean "the repository I work in", which is what an operator declaring
`develop = "../../google/protobuf"` intends. The prefix reading is the outlier, and the missing
URL that stops `--clone-develop` is exactly what `package_source` now supplies — from the
consumer's own declaration, or from the traveling `cuppa-publish.json`.

Two smaller defects found while confirming the above:

- A package develop path was only `~`-expanded (`configured_develop`, and `gitlab.py` when it
  swaps). It was never anchored to the sconstruct directory the way a location develop path is
  (`develop_location( sconstruct_dir, develop )`), so the natural relative form
  `develop = "../../google/protobuf"` resolved against the process working directory. **Fixed in
  slice A**: both sites now resolve through `develop_location`, whose docstring already required
  it of anything reporting on develop copies. The join stays lexical, as it is for location
  develop paths — `normpath` is lexical too and would resolve a symlinked parent to the wrong
  directory.
- `storage_paths()` already files a develop-mode package under `'develop'` rather than as a
  dependency tree, so listing and removal already expect a hand-managed location.

## Why this is not just a cascade resolution rule

If `develop=` names a source tree, consume cannot link against it: a repository is not a prefix.
So `--develop` for a package has to mean what it means for a location — *use my copy* — which
implies **build that tree locally and consume what it produced**. That is cascade without the
registry round trip, and it is a better inner loop than cascade offers today: no upload, no
consume-cache invalidation, no re-download.

That also makes it a different feature from
[`package-build-publish-deps.md`](package-build-publish-deps.md), which exists to *publish*.
Cascade's job is to get a registry into the right state; this plan's job is to keep a registry out
of the loop entirely.

## Where develop sits among the three tiers

Cascade will have three ways to find a publisher tree, and they answer different questions:

| Tier | For | Scope |
|------|-----|-------|
| `develop=` on the dependency | Map onto a tree the operator already has and intends to work in | Only dependencies the consumer authored — in practice the top of the stack |
| `--publisher-root` | A forest convention covering many trees the operator curates | Dependencies the consumer never declared |
| `--clone-publishers` | Cold start: nothing local yet | Anything with a `package_source` URL |

`develop=` is the most precise and ranks first. It cannot replace the other two: a dependency
discovered from a downloaded manifest is never named in the consumer's sconstruct, so it cannot
carry a `develop=`, and deep stacks are made of exactly those.

## Settled decisions

| Question | Decision |
|----------|----------|
| What `--develop` + `develop=` mean for a package | **Build that tree locally and consume what it produced.** The same promise as a location dependency, rather than a second meaning for one kwarg. |
| Relationship to cascade | Complementary, not a replacement. Cascade ranks a develop tree **above** `--publisher-root` lookup and above cloning, and never clones a dependency that has a develop path — `--clone-develop` owns filling those. |
| Publishing from a develop tree | **Refused** when the copy is dirty, ahead, or diverged, because the result is a registry version nobody can reproduce. `develop.py`'s `inspect()` already computes that state. An explicit override flag, not a warning in a log. |
| A develop path that is a prefix, not a publisher tree | An error naming both meanings, so an operator who set the old-style path learns what changed instead of reading "no sconstruct". |
| `develop=` set but `--develop` absent | Reported in the cascade plan, not silently skipped in favour of `--publisher-root` or a clone. |
| Pins against a develop tree | Advisory: reported when the tree is elsewhere, never switched, stashed, or reset. Same rule as a reused clone. |
| Relative develop paths | Anchored to the sconstruct directory, as location develop paths already are. |
| `--clone-develop` for packages | Supported, taking the URL from `package_source` (consumer-declared, else the traveling manifest). This belongs to the develop family, not to cascade. |

## Slices

| Slice | Content | Impact |
|-------|---------|--------|
| A | Anchor package develop paths to the sconstruct directory; cover `--list-develop` reporting a package develop copy | `patch` — **shipped** |
| B | Cascade honours a develop tree as a publisher tree, ranked first; refusals and plan-report visibility from the table above | `minor` |
| C | `--clone-develop` clones package dependencies from `package_source` | `minor` |
| D | Consume from a locally built package: locate the stage a publisher build produces (`final/<package>/<version>/`), a build-without-publish mode, and the refusals that stop a stale or absent stage being linked silently | `minor` |
| E | Migration for today's prefix-shaped `develop=`, once D defines the replacement | decide with D |

Slice A has shipped. Slice B is next: cascade honouring a develop tree as a publisher tree.

Slice D is the one that makes `--develop` coherent end to end, and the one with real unknowns:
which stage a publisher build leaves behind for each publisher shape, what happens when the stage
is older than the source, and whether the nested build should run automatically or be demanded of
the operator. Those are open questions, not settled decisions.

## Open questions

1. Where the consumable stage lives for each publisher shape, and how a stale stage is detected
   rather than linked.
2. Whether slice D builds the develop tree automatically under `--develop`, or refuses until the
   operator has built it, and how that interacts with `--parallel`.
3. What replaces today's prefix-shaped `develop=` — a distinct kwarg, or inference from the
   directory's contents — and whether any consumer relies on the current behaviour.
4. Whether `--list-develop` should report a package develop tree differently from a location one,
   given that publishing from a dirty one is refused rather than merely noted.
