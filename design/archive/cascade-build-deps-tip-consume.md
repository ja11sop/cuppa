# Plan: Build-cascade tip consume from publisher-root stages

- **Status:** shipped
- **Status note:** soak 2026-10-18; reconfirmed 2026-10-19 with `--amend-cascade-manifests`
- **Related:** [`package-build-publish-deps.md`](package-build-publish-deps.md) (Q3 nest-only; tip refresh gap); [`package-develop-local.md`](package-develop-local.md) (tip → stage via `consume_develop_package_stage`); [`stage-develop-locations.md`](stage-develop-locations.md) (**working example**: nest before tip `BuildWith`); [`cascade-amend-package-manifest.md`](cascade-amend-package-manifest.md) (amend composition; tip-extract overlay is the wrong lean for this); ROADMAP **1.13.0** related
- **Updated:** 2026-10-29
- **Impact:** minor — behaviour under existing `--build-cascade-dependencies`; no new required flag
- **Follow-on:** [`cascade-consume-dependencies.md`](cascade-consume-dependencies.md) — tip bind forest stages with **no** nests

> Tip consumes **forest stages** the way develop consumes **develop stages**.
> Nest timing follows **location `--stage-develop`**: stage first, then tip
> `BuildWith` links `final/<package>/<version>/`. Do **not** mutate extracts.

## Problem

Operators use cascade in three coherent ways:

| # | Intent | Flags (sketch) | Tip consume today |
|---|--------|----------------|-------------------|
| 1 | Build and soak packages **locally** (no registry) | `--cascade --build-cascade-dependencies` | Still **extracts** — gap |
| 2 | Build, **publish**, then soak from registry | `--cascade --publish-cascade-dependencies` | Refreshed extracts (shipped) |
| 3 | No cascade — ordinary consume | (none) | Registry extracts |

`--build-cascade-dependencies` correctly nest-builds publisher trees under
`--publisher-root` (no upload). Tip still sets `_package_dir` to
`~/_cuppa/_download/…`. Nest output and tip consume never meet.

That breaks the natural reading of (1): “cascade so I can use what I built.”
Publish-cascade already couples nest work with tip use; build-deps should be
the no-upload twin.

**Not** the same as scoped `--develop` (later track): develop still means
operator `develop=` locations. This plan is **publisher-root / forest** sources
resolved via `package_source`, staged in-tree, tip-linked like develop stages.

## Settled product (2026-10-18)

| Decision | Choice |
|----------|--------|
| When tip uses forest stages | **Automatic** under `--build-cascade-dependencies`. That flag is the opt-in (symmetric with publish-cascade ⇒ tip refresh). |
| Ranking | **`--develop` wins** for packages with an active develop path. Forest-stage tip consume is for cascade members without winning develop. |
| Medium | **In-tree stage** under the forest publisher tree (`_build/…/final/<pkg>/<ver>/`). Same layout as develop. |
| Extracts | **Do not mutate** `~/_cuppa/_download`. No traveling-JSON overlay onto extracts as the product answer. |
| Missing stage after nest | **StopError** (develop-style), not silent fall-back to a stale extract. |
| Second consume flag | **Follow-on** — tip forest bind **without** nesting: [`cascade-consume-dependencies.md`](cascade-consume-dependencies.md) (`--consume-cascade-dependencies`). Not an extract fall-back. |
| Scoped develop | **Out of scope** — later (`--develop-packages` / filter). Keep global `--develop` as today. |

### Why automatic (not a second opt-in)

If you only want to publish packages, you nest-publish (or tip-publish) those
trees. If you choose **build-deps**, you are either soaking in context or using
the forest as lazy local sources — in both cases tip should consume the stages
you just built. A second “also use them” flag splits what (2) already treats as
one story.

## Working example: `--stage-develop`

Location stage-develop already solved the timing shape we want:

1. **`run_location_stage_develop(env)`** in `construct.py` — **before** tip
   sconscript / `BuildWith`.
2. Nest each candidate (leaf-first); record roots so nests are not interleaved
   with tip construction.
3. Tip `BuildWith` then **links** `final/<name>/<ver>/{include,lib}` when present
   (L3), else path-swaps.

Package develop is the consume twin:

- `consume_develop_package_stage` → optional nest (`--stage-develop`) →
  `resolve_develop_package_stage(develop_root, …)` → tip `_package_dir` = stage.

**This plan:** same consume helper family, **`develop_root` = forest publisher
tree**; nest trigger = **`--build-cascade-dependencies`** (already nest-builds);
timing = **stage-develop’s pre-`BuildWith` batch**, not post-`[ready]` cascade
alone.

## Intent

1. Under `--cascade --build-cascade-dependencies`, nest-build the publisher DAG
   (existing companions) such that stages exist **before** tip package
   `BuildWith` binds paths — prefer the stage-develop call site pattern.
2. When tip constructs a cascade-eligible package dependency **without** winning
   develop: set `_package_dir` to
   `resolve_develop_package_stage(forest_tree, package, version, env)` (reuse).
3. Skip registry download/extract for that dep when the stage binds.
4. After tip resolve, cascade entry must **not double-nest** packages already
   staged in the pre-pass (mirror `_cuppa_location_stage_develop_roots`).
5. Publish-cascade path unchanged (nest + tip extract refresh).
6. Remove / stop relying on tip-extract traveling-JSON overlay as the soak fix
   for `lib_groups` under amend+build-deps — forest-stage tip consume supplies
   metadata and binaries together.

## Timing direction (lean)

| Approach | Role |
|----------|------|
| **Pre-`BuildWith` nest** (lean) | Under build-deps, run forest nest-build **before** tip sconscripts — same slot as `run_location_stage_develop`. Tip then discovers stages at construct time. |
| Resolve-time prefer + nest-on-miss | Fallback / complement if a package is only known after late `BuildWith`; must still unify with cascade DAG so order stays leaf-first and nests are not duplicated. |
| Post-cascade re-bind / extract overlay | **Rejected** for product (too late for `use_libs`; mutates extracts). |

### Open design points (plan before code)

1. **Graph availability pre-sconscript** — Location stage-develop surveys
   `dependencies` / `default_dependencies` registered at `cuppa.run`. Consume
   cascade today often builds the DAG **after** tip resolve from tip package
   factories. Confirm: for build-deps tips, is the DAG (direct pins +
   traveling-manifest closure via `package_source` / forest) available early
   enough to nest in the stage-develop slot? If not, define the minimal early
   resolve (registered package factories + forest stems) vs a guarded
   nest-on-miss at first `BuildWith`.
2. **Unify nest runners** — Prefer one topo walk (reuse `build_cascade_graph` /
   `run_nested_build` or stage-package argv as today for build-deps) rather than
   a parallel “stage-develop for forest” graph. Mark completed roots; later
   `maybe_run_cascade` skips them.
3. **Amend + build-deps** — Pre-pass must honour cascade-amend nest argv
   (metadata-only) the same as today’s post-pass composition.
4. **Slice F / deferred 404** — First-publish tips that defer extract until
   nested publish: build-deps has no upload; tip must bind forest stage (or
   StopError), not wait on registry.
5. **Clean (`-c`)** — Symmetry with stage-develop: tip clean under build-deps
   should not surprise-delete forest stages unless we explicitly nest-clean
   (settle with soak; default lean = leave forest stages unless nest-clean is
   part of the companion, matching current nest `-c` behaviour).

## Non-goals

- Scoped / filtered `--develop` (separate later plan).
- Tip consume from forest under **`--publish-cascade-dependencies`** via stages
  (that path refreshes extracts after upload — keep).
- Mutating or “installing into” the download extract store.
- Replacing `develop=` / `--publisher-root` ranking for cascade **resolve** of
  publisher trees (sources). This plan is tip **consume** of stages only.
- Parallel nested sessions; changing cascade plan/collect/update stop modes.

## Acceptance (draft)

1. Tip with `--cascade --build-cascade-dependencies` (no `--develop`) links
   `include/` / `lib/` / pkg-config from forest
   `_build/…/final/<package>/<version>/` for nested pins.
2. Same tip with `--develop` + package `develop=` still prefers the develop
   stage for that package.
3. Missing stage after nest → clear StopError naming package and forest root.
4. Extracts under the download root are unchanged by the soak.
5. `use_libs` / `lib_groups` expand from nest-stage traveling metadata without
   extract overlay.
6. Nests are not run twice (pre-pass + post-`[ready]`).
7. Unit tests: path bind under build-deps; develop ranking; skip double-nest;
   missing-stage StopError.
8. Antora: cascade companions table + develop cross-link; note symmetry with
   publish-cascade tip refresh.

## Progress

| Item | Status |
|------|--------|
| Product settle (auto, ranking, no extract mutate) | Done |
| Timing lean = stage-develop pre-`BuildWith` | Done |
| Early graph vs nest-on-miss open points | Lean: early `run_build_cascade_stages` + nest-on-miss |
| Implementation | **Done** on this PR — `run_build_cascade_stages`, `consume_build_cascade_package_stage`, tip bind, skip double-nest |
| Revert / retire tip-extract overlay | **Done** — build-deps nest loop no longer overlays extracts |
| Antora + unit tests | **Done** |
| Soak: boost missing from early graph (floating `_version`) | **Fixed** — `_edges_from_consume_tip` runs `default_version` so `boost_package` / `latest` enter the early DAG (9 packages again) |
| Soak: tip linked wrong-toolchain stage (`gcc16` into `gcc15`) | **Fixed** — `resolve_develop_package_stage(..., match_toolchain=True)`; dbg→rel same toolchain OK; different toolchain refused |
| Live soak (**project F** / `kms` group) | **Succeeded** (9 nests, forest bind, `kms` group expand, link OK) — follow-ups below |
| Soak: tip preferred stale `dbg` abseil over nest-amended `rel` | **Fixed** — when tip variant ≠ `rel`, prefer nest-default `rel` first |
| Nested progress lost TTY (normal newline spam; terse mute missing) | **Fixed** — tip `pass_fds` + `CUPPA_PROGRESS_FD` (path reopen alone was insufficient) |

### Soak corrections (2026-10-18)

1. **`boost_package` is a GitLab package** on this tip (registry / publisher
   forest), not “outside the cascade walk.” Missing from the 9→8 nest plan was
   a **regression**: early `run_build_cascade_stages` seeded edges before tip
   `default_version`, skipped `_version is None`, then
   `cascade_ran_for_tip` blocked the post-pass that formerly included
   remembered `1.92`.
2. **Wrong toolchain×variant bind is a bug**, not flexibility. Nest-default
   `--rel` under tip `--dbg` for the **same** toolchain is expected. Silently
   accepting another toolchain (e.g. `gcc16/rel` into `gcc15/dbg`) is not.
3. Successful **project F** soak (`kms` group expand) proved forest tip consume + group expand.
   Residual: tip bound `abseil` from `_build/gcc15/dbg/…` (stale) while nest
   amended `rel` — prefer nest-default `rel` when both exist.
4. **Nested progress must stay TTY when the tip is interactive.** Losing
   `/dev/tty` under nest `start_new_session` is a bug: normal mode fell into
   CI newline percent lines; terse mode stayed silent (no muted bar). Product:
   cascade nests keep tip TTY progress via an inherited open fd
   (`CUPPA_PROGRESS_FD` + `pass_fds`). Path-only `CUPPA_PROGRESS_TTY` reopen
   was tried first and still produced newline spam under soak.

## Implementation sketch (non-binding)

1. Add `run_build_cascade_stages(env)` (name TBD) called from `construct.py`
   next to `run_location_stage_develop`, gated on build-deps (+ cascade enable
   rules already in force).
2. Reuse cascade graph + nest-build; record staged publisher roots.
3. In `GitlabPackageDependency` construct (parallel to
   `_develop_is_publisher_source`): if build-deps and forest tree known and no
   winning develop → `resolve_develop_package_stage(forest_root, …)` → bind
   `_package_dir`; skip download when stage present; StopError when nest was
   expected and stage missing.
4. `maybe_run_cascade` under build-deps: skip nodes already staged in the
   pre-pass (still run plan banners / deferred-fetch audit as needed).
5. Drop tip-extract overlay path introduced for amend+build-deps soak.
6. Docs + unit tests.
