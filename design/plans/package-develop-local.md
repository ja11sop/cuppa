# Plan: Develop a package dependency from its own source tree

- **Status:** in progress
- **Related:** [#297](https://github.com/ja11sop/cuppa/issues/297); [`ROADMAP.md`](../../ROADMAP.md) — `package-develop-local`; [`package-build-publish-deps.md`](package-build-publish-deps.md) (cascade resolution, `package_source`, `--clone-publishers`); [`issues/package-build-provenance.md`](../issues/package-build-provenance.md) (what a published package records about its own origin); [`package-download-refresh.md`](package-download-refresh.md) (same-version currency); [`develop.py`](../../cuppa/develop.py) (`configured_develop`, `survey`, `clone_develop`); [`gitlab.py`](../../cuppa/package_managers/gitlab.py) (`GitlabPackageDependency`, `_using_develop`); [`build_with_location.py`](../../cuppa/build_with_location.py) (`develop_location`)
- **Updated:** 2026-09-18
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
| `develop=` set but `--develop` absent | Configuration, not a mode switch — do **not** imply `--develop`. Reported in the cascade plan, not silently skipped in favour of `--publisher-root` or a clone. A **CLI develop override** without `--develop` is an earlier **warn** (path named on the command line that will never be used); a declared path alone stays quiet outside the plan. |
| Pins against a develop tree | Advisory: reported when the tree is elsewhere, never switched, stashed, or reset. Same rule as a reused clone. |
| Relative develop paths | Anchored to the sconstruct directory, as location develop paths already are. |
| `--clone-develop` for packages | Supported, taking the URL from `package_source` (consumer-declared, else the traveling manifest). This belongs to the develop family, not to cascade. |
| Missing path under `--clone-develop` | **pending** / note when a cloneable source is known — the mode exists to create that path. **error** only when the clone cannot succeed (no source, wrong repo already there, blocked destination). |
| Nested cascade argv | Forward the tip's global build flags; **drop** tip dependency-scoped options (`--<name>-…-develop`, `--<name>-…-package-source`, location overrides). Those are registered by the tip's sconstruct and are wrong for the child (unknown flag, and relative paths anchored to the wrong tree). Settings meant for every project travel through `~/.cuppaconfig`, which the child loads itself. |
| Console noun for the invoking package | **this package** (not "tip") in plan lines, session resume, and finish copy. Keep `tip` only as an internal/code noun where a short label helps. |
| Default publisher lookup | `<storage-root>/publishers` is searched for existing trees (same path clones write to); `--publisher-root` overrides. Matches downloads/dependencies falling back to `storage_root`. |
| Unused develop on the plan | **Warning** (pass `--develop` to make the plan executable) + **notes** for alternatives; when a publishers-forest tree already exists, a second **warning** that the plan would use it. Not an error that claims no local tree when one was configured. Day-to-day copy does not advise rewriting `package_source`. |

## Slices

| Slice | Content | Impact |
|-------|---------|--------|
| A | Anchor package develop paths to the sconstruct directory; cover `--list-develop` reporting a package develop copy | `patch` — **shipped** |
| B | Cascade honours a develop tree as a publisher tree, ranked first; refusals and plan-report visibility from the table above | `minor` — **shipped** |
| C | `--clone-develop` clones package dependencies from `package_source` | `minor` — **shipped** |
| D | Consume from a locally built package: locate the stage a publisher build produces (`final/<package>/<version>/`), a build-without-publish mode, and the refusals that stop a stale or absent stage being linked silently | `minor` |
| E | Migration for today's prefix-shaped `develop=`, once D defines the replacement | decide with D |

Slices A, B and C have shipped. A live corosio→capy soak after C found nested-argv,
clone-develop survey, unused-develop note, and package-source override defects — fixed as a
soak UX patch before slice D. Slice D is next: consuming a locally built package.

### Soak findings (post slice C)

| Finding | Decision |
|---------|----------|
| Nested publish inherited `--capy-gitlab-develop=../capy` and died (`no such option`) | Drop tip dependency options from nested argv; keep `--develop` and toolchain/variant flags. |
| Plan said `[1 note]` for unused develop but printed only the resolve error; then graded a present develop tree as "no local working tree" | Unused develop is a **warning** (pass `--develop`) plus **notes** for alternatives; not a false missing-tree error. |
| `--…-package-source=…@develop` cloned `master` | Read the CLI override in `package_source_for_dependency` the way `configured_develop` reads develop overrides — declaration/manifest alone missed the pin. |
| `--clone-develop -n` graded a missing path as *error … cannot succeed* | pending/note when clonable; error only when the clone itself cannot succeed. |
| Plan paths showed `…/corosio/../capy` | Display through `display_path` (normpath + `~`) at report time; keep lexical paths for resolution. |
| No default publisher lookup under `storage_root` | **Forgiving pattern:** `<storage-root>/publishers` is the default lookup forest (same place clones land); `--publisher-root` overrides. |
| Plan graded cloneable URL + no `--clone-publishers` as hard error | Soft-grade: **warning** (pass `--clone-publishers`) + **notes** for alternatives; real cascade still StopErrors. Footer exits 0 and names `--clone-publishers` / `--develop` when those remedies apply. |
| Plan advised rewriting filesystem `package_source` | Drop from day-to-day warn/note/footer; keep CLI `--*-package-source=` as an escape hatch. Warn primary intent, note alternatives separately. |
| Plan scrolled away from the argv that produced it | Show the command line above the tree; emphasise cascade-relevant flags. |
| Unused develop + existing publishers tree looked "green" aside from one warning | Second **warning**: plan will use the forest copy (probably not intended); note for `--publisher-root`. |
| Collect reuses forest trees without fetch | By 2b design. **`--update-publishers`** (shipped) fast-forwards clean/behind forest and `--publisher-root` trees; skips develop (use `--update-develop`). |
| No first-class way to clone/collect trees without `--publish-package` or abusing `-n` | **`--collect-cascade`** (shipped): resolve + clone/reuse publisher trees, stop before nested build/upload. Not `--publish-package -n`. |
| `--build-and-publish-dependencies --publish-package -n` died in nested configure (`ConfigureDryRunError` / `.sconf_temp`) | Full cascade **refuses** `-n`/`--no-exec` up front with an **Options Error** tree (why / remedy) then a short `StopError`; point at `--cascade-plan` / `--collect-cascade`. SCons dry-run still configures, so nested sessions cannot be a meaningful cascade dry-run. |
| Cascade `… --publish-package -c` cleaned nested + tip graphs correctly | **Works.** Clean polish **shipped**: skip invalidate/re-fetch after clean sessions; banners say **nested clean(s)** / **resuming clean**; plan intro **cleaning package** plus a note that location CMake `-B` survives unless `CMakeConfigure`/`CMakeBuild` (or an explicit `env.Clean`) registered it. Still deferred (slice 2c): positive tip confirmation when SCons skips an already-current upload. |
| After `-c`, rebuild nested capy looked “not a full rebuild” | Expected when the nested publisher leaves the location-download CMake `-B` tree in place (raw `Command` / missing `Clean`). Cuppa `working/`+`final/` were cleaned; next run still re-packages/uploads. Tip corosio looked “full” because its `-B` *was* cleaned. Operator-facing note now prints on cascade clean plans. |

### What slice B settled that this plan had not

Ranking a develop tree first is only half an answer, because the consume side reads the same
kwarg. A tip that publishes `capy` also links against it, and consume was still swapping the
develop path in as the prefix — a source tree, whose `include/` may exist and whose `lib/`
does not. The combination the slice exists to enable was therefore broken by consume.

| Question | Decision |
|----------|----------|
| Consume during a cascade | `--develop` **stands down** when the develop path is the publisher project: the dependency is consumed from the registry the nested publish has just written to. The build then behaves like a cascade without `--develop`, with the operator's tree supplying the sources. Slice D removes that registry round trip. |
| Outside a cascade | Unchanged. `develop=` is still a built prefix, so nothing that works today stops working, and slice E remains the migration. |
| What makes a develop path a publisher tree | An **sconstruct**, not `cuppa-publish.json`. A publisher build stages that manifest beside `include/` and `lib/`, so accepting it would read a built package as the project that built it. Rooted and cloned trees keep the broader test, which they cannot fail that way. |
| Scope of the local-work refusal | **Refused** for develop trees, **warned** for `--publisher-root` and cloned trees. The hazard is identical, but refusing there would stop the workflow Phase 1 shipped, so the plan report grades those as warning rows and the publish proceeds. Promoting the warning is a deliberate `major`, not a side effect of this slice. |

Publishing a dependency version that is not yet in the registry remains awkward, and is not
made worse by this slice: the tip resolves its packages while sconscripts are read, before
cascade runs, so the first publish of a new version still fails on the tip's own fetch.

Slice D is the one that makes `--develop` coherent end to end, and the one with real unknowns:
which stage a publisher build leaves behind for each publisher shape, what happens when the stage
is older than the source, and whether the nested build should run automatically or be demanded of
the operator. Those are open questions below, not settled decisions.

### What slice C settled

The plan said the URL comes from `package_source`, "consumer-declared, else the traveling
manifest", which turned out to name two things that did not exist in the shape assumed.

| Question | Decision |
|----------|----------|
| Where a consumer declares it | `package_source` is now a **declarable setting** on `package_dependency(...)`, with the usual `--<name>-<manager>-package-source=` override. Before this it lived only on a publisher's `dependencies=` edges, so a consumer that does not publish had nowhere to say it. |
| Which manifest travels | The `cuppa-publish.json` staged **beside the consumer's own sconstruct**, whose edges carry `package_source`. A *downloaded* package's manifest cannot answer this: it records that package's own dependencies' sources, never its own, so the only tree that knows where a package comes from is a tree that depends on it. Whether a published package should record its own origin is a separate question — [`issues/package-build-provenance.md`](../issues/package-build-provenance.md) — and this slice does not need it. |
| Precedence | Declaration first, staged manifest second. The declaration is what an operator can see and change. |
| Pins | A branch is honoured, a tag or revision refused, matching location dependencies — where cascade deliberately allows tags, because publishing version X from tag `vX` is the normal case and a develop copy is a branch you work on. |
| Filesystem `package_source` | Left alone. It names a tree the operator already has, so there is nothing to fetch. |
| Cascade reading the declaration | Free and worth taking: `resolve_publisher_dir` falls back to a `package_source` declared on the dependency when the publisher edge does not carry one, so a consumer does not declare the same URL twice. |

What a clone lands is the publisher's **source tree**, which consume still reads as a built
prefix outside a cascade. That is the B-to-D gap, not a slice C defect, and the develop
documentation says so rather than implying the cloned tree can be linked against.

## Open questions

Each carries the options considered so far and a leaning. A leaning is not a decision: it is
where the argument stood when the question was last looked at, recorded so the next session
argues with something rather than starting again.

### 1 and 2. Where the consumable stage lives, and whether slice D builds it

These read as two questions and behave as one. If slice D **runs the nested build** — the
machinery cascade already has, minus the upload — the stage is current by construction and the
staleness problem does not arise. If it consumes a stage the operator built earlier, cuppa needs
a freshness rule, and every cheap version of that rule (stage mtime against newest source mtime)
is wrong in the cases that matter, because it cannot see what the build would actually redo.

**Leaning:** D builds the tree. Question 1 then shrinks to locating the directory that build just
wrote, per publisher shape, rather than designing stage-freshness heuristics.

`--parallel` is not a complication under that answer. Nested runs stay sequential, as cascade
already orders them, and each one parallelises internally the way any cuppa build does.

### 3. What replaces today's prefix-shaped `develop=`

Two candidates: a distinct kwarg for the prefix meaning, or inference from the directory's
contents. Slice B has now exercised inference in anger — an `sconstruct` for a source tree
against `include/` and `lib/` for a prefix — including the trap that a publisher build stages
`cuppa-publish.json` beside the built artefacts.

**Leaning:** inference, with a note when a prefix-shaped path is detected so the older intent
stays visible. That keeps one kwarg, needs no flag day, and would drop slice E from `major` to
`minor`. A distinct kwarg remains the fallback if a consumer turns out to need the prefix meaning
explicitly.

### 4. Whether `--list-develop` should report a package develop tree differently

The argument for is that publishing from a dirty package develop tree is refused, where a dirty
location develop tree is merely noted, so the same row means something stronger.

**Leaning:** no. The refusal is a cascade-time judgement about a publish, and `--cascade-plan`
already carries it in context. Teaching the develop report a second vocabulary for one dependency
kind costs more than it explains.

### 5. Whether the warning on rooted and cloned trees should become a refusal

Settled for now as a warning (see the slice B table). Promoting it would need an override that
covers every tier rather than develop alone, and a `major` release, because it stops the
edit-locally-then-cascade workflow Phase 1 shipped.

**Leaning:** leave it. Revisit only if a rooted tree actually puts unreproducible bits in a
registry in practice, rather than in theory.

### 6. Publishing a version the registry does not have yet

The tip resolves its own packages while sconscripts are read, inside
`GitlabPackageDependency.__init__`, whereas cascade runs later from `env.PublishPackage(...)`.
Publishing version 0.4 of a dependency for the first time therefore fails on the tip's own fetch
before cascade gets a turn. Three ways out:

| Approach | What it costs |
|----------|---------------|
| Run cascade before sconscripts are read, bootstrapping from the `cuppa-publish.json` seeded beside the tip sconstruct | Needs that manifest to exist, so a first cascade in a fresh tree has nothing to read |
| Defer the package fetch to the build phase, so resolution names paths without fetching | The largest change to `gitlab.py`, and the shape that behaves best under `--parallel` |
| Let cascade mark the packages it is about to publish, so an initial `404` on exactly those is deferred rather than fatal | Contained; the failure moves to after cascade, where it is a real error if the publish did not produce the archive |

**Leaning:** the third now, the second eventually. Note that this is not a regression introduced
by slice B — it is how cascade has behaved since Phase 1 — but `--develop` makes it more visible,
because an operator with the source tree in hand reasonably expects not to need the registry.
