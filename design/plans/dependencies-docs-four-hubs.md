# Plan: Dependencies docs — Using / Managing / Publishing / Authoring

- **Status:** done
- **Related:** [`list-deps-requires-closure.md`](list-deps-requires-closure.md) (Option A list scopes + requires samples); [`selection-filter-examples-docs.md`](selection-filter-examples-docs.md) (remove/wipe selection UX); [`package-build-publish-deps.md`](package-build-publish-deps.md) (cascade); [`archive/doc-folder-layout.md`](../archive/doc-folder-layout.md); [`removal-options.md`](removal-options.md) §7.1; [`methods-pages-split.md`](methods-pages-split.md); ROADMAP Documentation tooling (`doc-deps-four-hubs`)
- **Updated:** 2026-09-26
- **Impact:** none — Antora nav, page moves, xref updates, and docs writing conventions only; no product behaviour


## Problem

Dependency-related Antora pages are large and hard to navigate:

- **Consume** pages (location, packages, GitLab, Conan, builtins) sit flat under
  Dependencies next to Managing, with no “using” frame.
- **Publish** lives mainly in a top-level [`packages.adoc`](../../docs/modules/ROOT/pages/packages.adoc)
  (~1200 lines: cascade, amend, external CMake, Conan publish) — easy to miss from the
  Dependencies tree.
- **GitLab** mixes consume (auth, `latest`, `boost_package`) with publish-Boost-from-source
  on one page.
- A major **usability win** — building a tip application that depends on a deep GitLab
  package stack (and optionally `--develop`) **without** learning how to build or publish
  that nest — is not told as a Using story; readers bounce into cascade maintainer docs
  too early.
- Listing / Option A (`--list-scope=all` vs `resolve`, requires samples) landed under
  Managing without a clear map to Using vs Publishing.

## Goals

1. One top-level **Dependencies** hub with **four** second-level job hubs.
2. Lead with **Using** (landing + first nav child): consume and the “build without
   publishing” narrative.
3. Keep **Managing** for storage inspect / reclaim / develop health.
4. Give **Publishing** its own hub (absorb `packages.adoc` + GitLab publish slices).
5. Give **Authoring** a peer hub (factories / storage hooks / plugins) — small today,
   expected to grow.
6. Place Option A listing docs and requires samples in Managing, with Using/Publishing
   cross-links so the current list-deps work sits in the broader map.

## Non-goals

- Changing CLI or listing behaviour.
- Rewriting cascade algorithm docs from scratch (move and split; polish in later passes).
- Merging Creating+Publishing under one awkward label.
- Promoting Using / Managing / Publishing / Authoring to **top-level** nav peers (rejected:
  loses the shared map; Prefer Using-first under Dependencies).

## Settled decisions

| Topic | Decision |
|-------|----------|
| Top-level nav | Single **Dependencies** entry (not four top-level product areas). |
| Second-level hubs | **Using** · **Managing** · **Publishing** · **Authoring** (four peers). |
| Hub order | Using first in nav and on the landing page. |
| Usability story | **Using** owns “tip with complex package deps + optional `--develop` without learning cascade publish.” Mechanics stay in Publishing. |
| Publishing vs Authoring | Separate hubs. Publishing = ship artefacts / cascade / publisher trees. Authoring = invent dependency factories and storage contracts. |
| `list-publishers` | Home under **Publishing**; Managing “which listing” table keeps a row + xref. |
| `packages.adoc` | Move under Publishing (then split); retire as a Dependencies peer / lone top-level publish page. |
| GitLab page | Split consume → Using; Boost-from-source publish → Publishing. |
| Private consumers | Anonymise tip apps in tracked docs (**project A** / shape only); never paste private repo names. |

## Target nav sketch

```
* Dependencies                          ← thin chooser; Using first
** Using dependencies
*** Building with package dependencies  ← NEW: usability story (no publish required)
*** Overview (declaration / BuildWith)
*** Location dependencies
*** Package dependencies (consume hub)
*** GitLab packages (consume)
*** Conan packages (consume)
*** Built-in dependencies (+ Boost / Qt / Quince)
** Managing dependencies
*** Listing dependency trees            ← Option A scopes + requires all/resolve samples
*** Listing downloads
*** Removing, purging, and wiping
*** Develop working copies
** Publishing dependencies
*** Publishing overview
*** GitLab package publish
*** Cascading dependency publishes      ← from packages.adoc
*** Amending and external builds
*** Conan publish
*** Publisher trees                     ← list/remove/update publishers
** Authoring dependencies
*** Custom dependency factories         ← today’s extending.adoc
*** (room to grow: storage contracts, plugins, …)
```

Folder layout (preferred): `docs/modules/ROOT/pages/dependencies/{using,managing,publishing,authoring}/…`
mirroring nav (same spirit as `doc-folder-layout`).

## Page move map (summary)

| Current | Target hub |
|---------|------------|
| `dependencies/overview.adoc`, `location.adoc`, `packages.adoc` (consume), `gitlab.adoc` (consume half), `conan.adoc` (consume), `builtins*` | **Using** |
| NEW usability page | **Using** — Building with package dependencies |
| `managing.adoc` + list-dependencies / list-downloads / removing / develop | **Managing** (paths may become `managing/…` under the hub; already nested) |
| `packages.adoc` (publish + cascade + amend + external + Conan publish) | **Publishing** (split across children) |
| GitLab “Publishing Boost from source” | **Publishing** |
| `managing/list-publishers.adoc` | **Publishing** (publisher trees) |
| `dependencies/extending.adoc` | **Authoring** |
| Top-level `packages.adoc` nav entry | Remove once Publishing hub owns it (keep URL redirects / aliases where practical) |
| CLI / Methods pages | Stay put; open with xrefs into the four hubs |

## Using — usability page (outline)

Audience: someone who wants a green build of a tip that depends on nested GitLab packages.

Cover, in user language:

1. Declare tip packages (`package_dependency` / defaults / `BuildWith`).
2. Cuppa fetches or reuses extracts under storage; traveling manifests pull closure for
   **consume** — you do not run a nest publish to compile.
3. Optional `--develop`: configured working copies can satisfy identities without registry
   round-trips (link develop Managing page for health / update).
4. When listing storage, default `--list-scope=all` shows **used** vs **unused**; point at
   Managing samples (`list-dependencies-requires` vs `-resolve`) without requiring Publishing.
5. “If you maintain or ship those packages → Publishing.” Explicitly defer cascade plan/clone
   cold-start to that hub.

Do **not** name private tip repos in the published page; use a generic tip shape or
**project A**.

## Phased migration

| Phase | Work | Done when |
|-------|------|-----------|
| **P0** | This plan + ROADMAP / AGENTS topic-map note; land on the list-deps PR or immediate follow-up | Plan indexed; settled table frozen |
| **P1** | Nav + four hub stubs; move files with stable xrefs; Dependencies landing = Using-first chooser | Nav matches sketch; builds Antora; no orphan pages |
| **P2** | NEW Using usability page; Using ↔ Managing list-deps / requires samples xrefs | Story readable without opening cascade |
| **P3** | Relocate `packages.adoc` under Publishing (single page OK at first) | No top-level Publishing orphan |
| **P4** | Split Publishing megapage + GitLab consume/publish split; re-home list-publishers | Cascade / GitLab publish / Conan publish are separate children |
| **P5** | Authoring hub + move extending; AGENTS “where topics live” table | Complete |

P1–P2 are the priority to align **current** list-deps / Option A work with the broader map.
P3–P5 can follow on the same PR if scope stays docs-only, or a docs follow-up PR.

## Alignment with list-deps requires closure (current work)

- Managing keeps **Listing dependency trees** (Option A scopes, requires HTML samples).
- Using usability page links those samples as “how storage looks for a tip with a package
  closure,” not as maintainer cascade docs.
- Publishing cascade pages link back to Managing for `--list-publishers` / list-deps when
  reclaiming publisher-adjacent storage.

## Progress snapshot

| Slice | Status |
|-------|--------|
| Settled decisions | Done — 2026-09-26 |
| Plan indexed | Done — `design/README.md` + ROADMAP `doc-deps-four-hubs` |
| P1 nav + hubs | Done — four hubs; Using/Managing/Publishing/Authoring; page moves + xref sweep |
| P2 Using usability page | Done — `dependencies/using/building-with-packages.adoc` |
| P3 relocate `packages.adoc` | Done — under `dependencies/publishing/`; top-level stub kept |
| P4 Publishing megapage / GitLab consume–publish split | Done — `gitlab` / `cascade` / `amend-and-external` / `conan` children; Boost-from-source under Publishing |
| P5 Authoring polish + AGENTS topic map | Done — topic map; placeholder strategy; remove/wipe selection examples (see [`selection-filter-examples-docs.md`](selection-filter-examples-docs.md)) |
| Next focus | None for this plan — selection-example follow-ons live on `selection-filter-examples-docs.md` |

## Impact

Documentation / nav only → changelog **none** for the product version gate; still update
AGENTS topic map and ROADMAP Documentation tooling when P1 lands.
