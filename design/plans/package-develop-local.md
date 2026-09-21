# Plan: Develop a package dependency from its own source tree

- **Status:** in progress
- **Related:** [#297](https://github.com/ja11sop/cuppa/issues/297); [`ROADMAP.md`](../../ROADMAP.md) — `package-develop-local`; [`package-build-publish-deps.md`](package-build-publish-deps.md) (cascade resolution, `package_source`, `--clone-publishers`); [`cascade-defer-404.md`](cascade-defer-404.md) (Slice F detail + soak); [`issues/package-build-provenance.md`](../issues/package-build-provenance.md) (what a published package records about its own origin); [`package-download-refresh.md`](package-download-refresh.md) (same-version currency); [`develop.py`](../../cuppa/develop.py) (`configured_develop`, `survey`, `clone_develop`); [`gitlab.py`](../../cuppa/package_managers/gitlab.py) (`GitlabPackageDependency`, `_using_develop`); [`build_with_location.py`](../../cuppa/build_with_location.py) (`develop_location`)
- **Updated:** 2026-09-21
- **Impact:** `minor` for the resolution, clone, local-consume (D), and first-publish defer-404 (F) slices; a distinct prefix kwarg would be `minor` unless it breaks today’s `develop=` (avoided by inference)

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
| What `--develop` + `develop=` mean for a package | **Use that working tree**: discover a local package stage under `final/<package>/<version>/` (publisher-shaped) or swap a prefix-shaped path. Opt-in **`--stage-develop`** nest-builds/cleans publisher trees. Not a second silent meaning for one kwarg — build is explicit. |
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

### Slice D settled decisions

| Question | Decision |
|----------|----------|
| Trigger (discover) | **`--develop` alone** when `develop=` names a **publisher-shaped** tree (`sconstruct` present): locate an existing stage under `final/<package>/<version>/` and link it. No nest. Missing stage → clear `StopError` naming `--stage-develop`. |
| Trigger (build/clean) | **`--develop --stage-develop`**: nest a `--stage-package` session (build + stage, no upload). With `-c`, nest-clean those trees too. Requires `--develop`. |
| Who builds | Only when `--stage-develop` is set. Nested SCons/CMake own incremental rebuild; no separate Cuppa mtime freshness rule. |
| Stage location | Matching toolchain×variant **`final/<package>/<version>/`** under the develop tree. |
| Build without upload | Nested argv uses `--stage-package` (not `--offline`). |
| Prefix-shaped `develop=` | **Inference**: `sconstruct` → publisher source; `include/`+`lib/` without sconstruct → legacy prefix swap + note. |
| Cascade + develop | Tip still consumes the local stage when present; cascade upload is independent. |
| `--list-develop` | Unchanged vocabulary. |
| Rooted/cloned dirty warn | Stay warn, not refuse. |
| First-publish registry 404 (§6) | **Slice F** (below) — not D |

## Slices

| Slice | Content | Impact |
|-------|---------|--------|
| A | Anchor package develop paths to the sconstruct directory; cover `--list-develop` reporting a package develop copy | `patch` — **shipped** |
| B | Cascade honours a develop tree as a publisher tree, ranked first; refusals and plan-report visibility from the table above | `minor` — **shipped** |
| C | `--clone-develop` clones package dependencies from `package_source` | `minor` — **shipped** |
| D | Consume from a locally built package: discover `final/<package>/<version>/` under `--develop`; opt-in `--stage-develop` for nest build + deep clean | `minor` — **shipped** in [#311](https://github.com/ja11sop/cuppa/pull/311); soak complete |
| E | Migration for today's prefix-shaped `develop=`, once D defines the replacement | `minor` (inference + note shipped with D; distinct kwarg only if needed) |
| F | First-publish: defer tip registry 404 for cascade-eligible packages until nested publish refreshes consume cache | `minor` — **shipped** in [#316](https://github.com/ja11sop/cuppa/pull/316) |

Slices A–C shipped; post-C soak UX landed in [#310](https://github.com/ja11sop/cuppa/pull/310).
**Slice D shipped** in [#311](https://github.com/ja11sop/cuppa/pull/311); soak complete. Extending `--stage-develop` to location develop trees: [`stage-develop-locations.md`](stage-develop-locations.md) (L1–L4 shipped in [#313](https://github.com/ja11sop/cuppa/pull/313) / [#315](https://github.com/ja11sop/cuppa/pull/315)).
**Slice F shipped** in [#316](https://github.com/ja11sop/cuppa/pull/316). **Slice E** (prefix migration) remains.

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
| Consume during a cascade | `--develop` on a publisher source tree **stages locally** and the tip links that stage (slice D). Cascade may still upload afterward; consume does not wait on the registry. Nested sessions fall back to registry download so develop-local does not nest recursively. |
| Outside a cascade | Unchanged. `develop=` is still a built prefix, so nothing that works today stops working, and slice E remains the migration. |
| What makes a develop path a publisher tree | An **sconstruct**, not `cuppa-publish.json`. A publisher build stages that manifest beside `include/` and `lib/`, so accepting it would read a built package as the project that built it. Rooted and cloned trees keep the broader test, which they cannot fail that way. |
| Scope of the local-work refusal | **Refused** for develop trees, **warned** for `--publisher-root` and cloned trees. The hazard is identical, but refusing there would stop the workflow Phase 1 shipped, so the plan report grades those as warning rows and the publish proceeds. Promoting the warning is a deliberate `major`, not a side effect of this slice. |

Publishing a dependency version that is not yet in the registry used to fail on the tip's
own fetch before cascade ran; that is **Slice F** (defer eligible tip 404s until after
nested publish refreshes consume cache).

Slice D is the one that makes `--develop` coherent end to end.

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

What a clone lands is the publisher's **source tree**. Slice D makes `--develop` build
that tree and consume its stage so the tip no longer links a source tree as a prefix
(or needs a registry round trip for that dependency).

## Open questions

### 1–5 — settled in slice D

See **Slice D settled decisions** above.

### 6. Publishing a version the registry does not have yet — Slice F

**Status:** **shipped** in [#316](https://github.com/ja11sop/cuppa/pull/316).

#### Why it fails today

Tip `BuildWith(default_dependencies)` runs in `init_env_for_variant` **before** the
sconscript body, so `GitlabPackageDependency.__init__` downloads **before**
`PublishPackage` → `maybe_run_cascade`. Cascade already refreshes the tip consume
cache after each nested publish; the gap is the early fatal 404.

#### Approaches considered

| Approach | What it costs |
|----------|---------------|
| Run cascade before sconscripts are read, bootstrapping from tip `cuppa-publish.json` | Needs that manifest; first cascade in a fresh tree may have nothing to read |
| Defer the package fetch to the build phase | Largest change to `gitlab.py`; best under `--parallel` eventually |
| Defer initial `404` for packages cascade will publish; fail after cascade if still missing | Contained; matches current refresh path |

#### Slice F settled decisions

| Question | Choice |
|----------|--------|
| Approach | **3 now**; approach 2 (lazy fetch) later |
| When deferral is allowed | Tip session only (`not` nested), and `--build-and-publish-dependencies` |
| Which packages | **Cascade-eligible tip deps only**: `package_source` / publisher-shaped `develop=` / tip `cuppa-publish.json` edge with a source. Registry-only deps keep today’s fatal 404 |
| Deferred behaviour | Construct the dependency; keep the usual `_package_dir`; do **not** raise; log that fetch waits on cascade |
| After cascade | Existing invalidate + re-fetch; still-missing deferred pin → `StopError` |
| Plan / collect / update-stop | Same deferral (pre-sconscript BuildWith still runs) |
| Offline | Unchanged refusal when no local archive/stage |

#### Soak (project D)

Detail and command recipes: [`cascade-defer-404.md`](cascade-defer-404.md).

Default cold-start path (not a pre-planted `--publisher-root` forest):

1. `--collect-cascade --clone-publishers` — clones into `~/.cuppa/publishers/<name>`.
   **Done (2026-09-20):** 7 of 7 tip deps collected, 7 newly cloned
   (abseil_cpp, c_ares, nlohmann_json, opentelemetry_cpp, protobuf, re2, grpc);
   nothing built or uploaded.
2. Re-run `--cascade-plan` — graph expands via each child’s `cuppa-publish.json`
   (tip-direct alone while clones are missing).
3. `--publish-package` (omit `--parallel` until [#317](https://github.com/ja11sop/cuppa/issues/317) /
   [#319](https://github.com/ja11sop/cuppa/pull/319)) — **Done (2026-09-21):** tip
   google-cloud-cpp + 7 nested publishers published; Slice F defer held.

`--publisher-root` remains a secondary shortcut when trees already exist on disk.
Nested leaf-first upload fed parents from the registry on this soak; no nested
defer expansion needed.