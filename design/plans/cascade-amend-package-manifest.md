# Plan: Cascade — metadata-only amend across the nest DAG

- **Status:** in progress (on `feature/gitlab-package-lib-groups`)
- **Related:** [`../archive/package-metadata-amend.md`](../archive/package-metadata-amend.md) (tip amend shipped); [`../archive/package-build-publish-deps.md`](../archive/package-build-publish-deps.md); [`cascade-tip-local-options.md`](cascade-tip-local-options.md) (different problem: tip-local AddOption drops); `tip_forward_args` / `_NESTED_DROP_*` / `run_nested_build` in [`package_cascade.py`](../../cuppa/package_managers/package_cascade.py); ROADMAP **1.13.0** related
- **Updated:** 2026-10-18
- **Impact:** minor — new cascade companion behaviour; tip-only amend unchanged

## Problem

Shipping traveling-metadata changes across a dependency DAG (for example
`lib_groups` / `default_use_libs` on `google_cloud_cpp` and its package
predecessors) today means either:

1. **Tip-only amend** in each publisher tree by hand, or
2. **Cascade nest rebuild** (`--cascade --build-cascade-dependencies` /
   publish companions) — full acquire → build → install per nest.

Operators naturally reach for:

```text
cuppa … --cascade --build-cascade-dependencies --amend-package-manifest
```

expecting “walk the DAG, rewrite `cuppa-publish.json`, retar (and optionally
upload) — **without** multi-hour CMake”. That combination does **not** do that
today:

| Mechanism | Today |
|-----------|--------|
| `--amend-package-manifest` | Tip publisher path: skip DownloadExtract / CMake, rewrite JSON, retar |
| Nest argv | **`--amend-package-manifest` is in `_NESTED_DROP_EXACT`** — never forwarded |
| `--build-cascade-dependencies` | **Always** `run_nested_build` (full project nest; `project_only` strips publish/stage) |

So amend on the tip line is effectively ignored for nests; build-deps still
pays full rebuild cost. Soak 2026-10-18 surfaced this as a “surprise”, not a
docs typo.

## Intent

Support an explicit **cascade metadata-only** path:

1. Walk the same publisher DAG as other cascade companions.
2. Each nest rewrites traveling metadata from **that** publisher’s kwargs and
   retars (amend semantics).
3. Skip acquire / configure / build / install when the amend path can satisfy
   the graph (same as tip amend).
4. Upload only when the tip companion says so (publish cascade / tip publish),
   not merely because amend is on.
5. Keep full nest rebuild as the default when amend is **not** requested.

Non-goal: silently mixing “this leaf needs a real rebuild, that leaf is
metadata-only” without an operator signal (v1 can be all-amend or all-build).

## Why amend is nest-dropped today (keep in mind)

Likely intentional when tip amend shipped:

* Nest under `--build-cascade-dependencies` is **project_only** — no
  `--publish-package` / `--stage-package`. Amend’s useful work is inside
  `PublishPackage` → `amend_package`; a bare project nest may never hit that
  Command the way a publish nest does, or may still evaluate other always-run
  targets.
* Whole-DAG same-version overwrite is dangerous if amend were forwarded into
  `--publish-package` nests by accident.
* Tip amend was validated as a **single publisher** workflow first
  ([#299](https://github.com/ja11sop/cuppa/issues/299) / [#300](https://github.com/ja11sop/cuppa/pull/300)).

Those are constraints to design around, not reasons to refuse the use case.

## Options (explore)

### A. Forward tip `--amend-package-manifest` into nests (minimal argv change)

Remove it from `_NESTED_DROP_EXACT` / prefixes when the tip set it.

| Pros | Cons |
|------|------|
| Small diff; matches operator intuition for “flag on tip → nests see it” | Alone is **insufficient** for `--build-cascade-dependencies`: nests stay `project_only` and may not run amend/`PublishPackage` the way publish nests do |
| | Accidental forward into every nest mode if drop table is the only gate |

Lean: **necessary piece**, not a complete product.

### B. Amend-aware nest argv builder (companion-shaped)

When tip has amend **and** a cascade nest companion:

| Tip companion | Nest argv lean |
|---------------|----------------|
| `--build-cascade-dependencies` + amend | Nest with `--amend-package-manifest` **and** enough packaging surface to retar under `final/` (likely `--stage-package` or a dedicated “amend stage” so `PublishPackage` → `amend_package` runs) — **no** upload |
| `--publish-cascade-dependencies` / `--publish-package` + amend | Nest with `--amend-package-manifest` + `--publish-package` (metadata retar + upload) |
| `--cascade-plan` + amend | Plan text names “amend” vs “build” per nest |

| Pros | Cons |
|------|------|
| Matches how other cascade companions already specialize nest argv | New matrix to document and test |
| Keeps “full rebuild” vs “amend” as an explicit tip signal | Must define stage-vs-publish clearly so build-deps does not upload |

Lean: **primary direction**.

### C. Dedicated flag `--amend-cascade-manifests` (or similar)

Separate from tip-only `--amend-package-manifest` so tip-only amend never
implies DAG behaviour.

| Pros | Cons |
|------|------|
| No overload; tip amend stays single-tree | Extra flag; operators already tried composing existing flags |
| Clear Antora story | Two knobs that must stay consistent with publishers |

Lean: optional if B’s composition is ambiguous in docs; prefer **composition
first** (`--cascade` + companion + `--amend-package-manifest`) if we can make
nest behaviour obvious in the plan banner.

### D. Per-node fallback: amend if archive/stage exists, else full build

| Pros | Cons |
|------|------|
| One tip command “just works” on mixed trees | Magical; hard to explain skip vs rebuild; masks missing publishers |
| | Diverges from “opt-in metadata-only” safety story |

Lean: **defer** (maybe later “tolerant” mode). V1 = all nests amend or refuse
with a clear StopError when a nest cannot amend (no stage, no local archive,
no registry download).

### E. Tip-orchestrated amend without nested cuppa

Cascade parent downloads each pin, rewrites JSON from resolved publisher
kwargs, retars, optionally uploads — no child `sconstruct`.

| Pros | Cons |
|------|------|
| No nest option / CMake issues | Duplicates publisher kwargs outside the publisher tree; drift risk |
| | Breaks “publisher sconstruct is source of truth” |

Lean: **refuse** for v1.

## Settled lean (provisional)

1. **Compose**, do not invent a third cascade verb if we can help it:
   `--cascade` + (`--build-cascade-dependencies` \| publish companion) +
   `--amend-package-manifest`.
2. Implement via an **amend-aware nest argv** (option **B**), with **A** as the
   drop-table prerequisite (stop unconditionally dropping amend when this mode
   is active).
3. **Refuse** silent per-node rebuild fallback (**D**) and tip-orchestrated
   rewrite (**E**) for v1.
4. Nest **always nests** under amend+build-deps (like build-deps today) — no
   “pin current → skip” — because metadata rewrite is the point even when the
   registry pin exists.
5. Plan / nest banners should say **amend** (not “build”) so operators are not
   surprised.

Open: whether build-deps+amend uses `--stage-package` or a thinner “retar
only” path; whether tip consume after leaf amend still relies on existing
`payload_sha256` no-op behaviour.

## Non-goals

* Changing tip-only amend semantics when cascade is off.
* Forwarding tip-local `cuppa.add_option` flags (see
  [`cascade-tip-local-options.md`](cascade-tip-local-options.md)).
* Restaging binaries from `source_*` under amend (still forbidden).

## Acceptance (draft)

1. Documented recipe rewrites metadata across the DAG without CMake rebuilds
   when amend + cascade companion are set.
2. Nest command preview / plan shows amend (and stage vs publish) correctly.
3. Missing amend inputs → clear StopError naming the package, not a full
   rebuild surprise.
4. Unit tests cover nest argv for build-deps+amend and publish+amend.
5. Antora cascade + amend-and-external cross-links.

## Progress

| Item | Status |
|------|--------|
| Soak surprise captured | Done — this proposal |
| Options A–E | Captured; provisional lean B (+ A) **chosen** |
| Nest argv: keep amend on package nests; build-deps → stage+amend | **Done** (this PR) |
| Session / plan banners say amend | **Done** |
| Unit tests (forward / build / publish argv) | **Done** |
| Antora cascade + amend-and-external | **Done** |
| Live soak (google_cloud_cpp DAG / lib_groups) | In play |
