# Plan: split Methods into per-method Antora pages

- **Status:** in progress
- **Related:** [`ROADMAP.md`](../../ROADMAP.md) — Documentation tooling (`doc-methods-split`); hub [`methods.adoc`](../../docs/modules/ROOT/pages/methods.adoc); [`dependencies.adoc`](../../docs/modules/ROOT/pages/dependencies.adoc) hub pattern; Phase 3 doc split [`removal-options.md`](removal-options.md) §7.1; behaviour track [`method-behaviour-audit.md`](method-behaviour-audit.md)
- **Updated:** 2026-08-29
- **Impact:** none — documentation and navigation only

## Prerequisite — behaviour before pages

Do **not** move detailed behaviour prose onto child pages until
[`method-behaviour-audit.md`](method-behaviour-audit.md) fixes and classifications are settled
**or** explicitly deferred with issue links. Hub + nav skeleton (slice **A**) may land once
blocking audit slices are fixed or deferred.

**Settled / deferred (2026-08-29):**

| Item | State |
|------|--------|
| [#213](https://github.com/ja11sop/cuppa/issues/213) compile object paths | **Shipped** |
| `mba-static-glob` / `mba-filter` | **Shipped** — [`recursive-glob-parity.md`](../archive/recursive-glob-parity.md) / [#232](https://github.com/ja11sop/cuppa/issues/232) |
| `mba-artifact-paths` (flat `{final}/{basename}` for Markdown/AsciiDoc/RunAndRedirect) | **Deferred** — [#233](https://github.com/ja11sop/cuppa/issues/233); Docs assets pages call out collisions until fixed |
| `path-vocabulary-and-scons-nodes` | Optional parallel; not a Methods-split blocker |

**Order:**

```text
method-behaviour-audit (fixed or deferred)  →  methods-pages-split (this plan)
```

`recursive-glob-parity` is shipped; cite the archive plan from the Files group.

## Why

[`methods.adoc`](../../docs/modules/ROOT/pages/methods.adoc) is a single long page covering
progress, build, test, coverage, custom commands, modules, and packages. Dependencies and
toolchains already use a **hub + child pages** model.

Methods are the core **`sconscript` vocabulary**. Each group deserves:

- Its own URL for linking from integration tests and error messages.
- Room for parameters, examples, progress behaviour, and toolchain notes without scrolling.
- A path to document **canonical SCons helpers** used with cuppa (`env.Install`, etc.) without
  sending readers to fragmented upstream SCons docs.

## Goals

1. Turn **`methods.adoc` into a hub** — prerequisites, progress overview, method index table.
2. **Phase 1:** one Antora page per **cuppa-registered method family** (see inventory below).
3. **Phase 2:** short pages for **selected SCons methods** cuppa projects use daily, under
   `methods/scons-*.adoc`.
4. Update **`nav.adoc`** to mirror the dependency/toolchain nesting pattern.
5. Child pages live under **`docs/modules/ROOT/pages/methods/`** (same idea as `integration/`).

## Non-goals

- Duplicating full SCons reference documentation.
- Auto-generating pages from `add_method` registration (manual prose stays authoritative).
- Moving integration test pages (already under `integration/`).

## Method inventory (Phase 1 grouping)

Group related registrations to avoid forty tiny pages:

| Nav group | Cuppa methods | Page |
|-----------|---------------|------|
| Build | `Build`, `Compile`, `CompileStatic`, `CompileShared`, `BuildLib`, `BuildStaticLib`, `BuildSharedLib` | `methods/build.adoc` |
| Test & run | `BuildTest`, `*Test`, `Test`, `BuildBenchmark`, `*Benchmark`, `Benchmark`, `Run` | `methods/test-run.adoc` |
| Coverage | `Coverage`, `CollateCoverageFiles`, `CollateCoverageIndex` | `methods/coverage.adoc` |
| C++ dialect & modules | `StdCpp`, `CxxModules`, `Modules` (deprecated), `Module`, `HeaderUnit`, `ImportModules`, `CxxProfiles`, `CxxProfilesEnforce`, `CxxErrorLimit`, … | `methods/cxx-dialect-and-modules.adoc` |
| Dependencies & profiles | `BuildWith`, `Using`, `BuildProfile` | `methods/dependencies-and-profiles.adoc` |
| Flags & toolchain | `Toolchain`, `ReplaceFlags`, `RemoveFlags` | `methods/flags-and-toolchain.adoc` |
| Files & templates | `CopyFiles`, `CopyFilesAs`, `TargetFrom`, `ExpandTemplateFile`, `RenderJinjaTemplate`, `RecursiveGlob`, `GlobFiles`, `Filter` | `methods/files-and-templates.adoc` |
| Docs assets | `AsciidocToHtml`, `MarkdownToHtml`, `CompileScss`, `CreateVersion`, `RunAndRedirectToFile` | `methods/docs-assets.adoc` |
| Packages | `PublishPackage`, `InstallPackage` | `methods/packages.adoc` |
| Custom commands | `cwd` / `--use-shell` spawn notes (method-adjacent) | `methods/custom-commands.adoc` |

## Behaviour fields (every child page)

Import the classification from [`method-behaviour-audit.md`](method-behaviour-audit.md). Each method
page (or group page subsection) should state:

| Field | What to document |
|-------|------------------|
| **Returns** | Nodes, env, string, list, or side-effect only — and what callers can chain |
| **Evaluation** | Immediate / static snapshot (configure) / SCons dynamic / build action / post-build |
| **Output paths** | Mirror under `working/` or `final/`, flat basename, or caller explicit — collision notes |
| **Progress** | Participates in NotifyProgress or not |

Link to [`recursive-glob-parity.md`](../archive/recursive-glob-parity.md) from the Files group
instead of duplicating the full static/dynamic essay.

## Phase 2 — SCons companions

| Page | Cover |
|------|--------|
| `methods/scons-install.adoc` | `env.Install`, `env.InstallAs`, cuppa layout under `_build/` / `final/` |
| `methods/scons-depends.adoc` | `Depends`, `Requires`, `Alias` in cuppa projects |
| `methods/scons-env.adoc` | `CPPPATH`, `LIBPATH`, when to prefer cuppa methods |

Keep each page short; link to SCons upstream for exhaustive API.

**Preference (2026-08-29):** fold Phase 2 into the cycle **earlier** — once slice **A** (hub +
nav + stubs) exists, draft SCons companion stubs/content **before or alongside** remaining Phase 1
group migrations (not only after Files/Docs). Revisit concrete ordering after groundwork lands.

## Hub page retention

Leave on **`methods.adoc`** (target end state):

- Prerequisites
- Progress tracking and variant scoping (mermaid diagram)
- Index table linking every child page

Custom commands may stay on the hub briefly, then move to `methods/custom-commands.adoc`.

## Work slices

| Slice | Deliverable | Notes |
|-------|-------------|-------|
| **0** | Behaviour audit fixed or deferred | [#213](https://github.com/ja11sop/cuppa/issues/213) + glob parity **done**; `mba-artifact-paths` **deferred** ([#233](https://github.com/ja11sop/cuppa/issues/233)) |
| **A** | Hub map + nav skeleton + stubs | Behaviour field template on each stub; full tutorial text may still live on hub until B–D; SCons companion stubs included early |
| **B** | Build + test groups | Highest traffic; #213 semantics |
| **E′** | Phase 2 SCons companions | **Prefer early** after A (stubs first, then short prose) |
| **C** | Coverage + C++ groups | Link cxx-modules / cxx-profiles |
| **D** | Remaining groups | Files (RecursiveGlob), packages, flags, docs assets (call out flat-basename until issue fixed) |
| **F** | Redirect grep in repo | Fix internal links to `#anchors` that moved |

## Progress snapshot

| Slice | Status |
|-------|--------|
| 0 | Largely done — artifact-path emitters deferred with issue |
| A | **Done** (this groundwork) — hub topic map + `methods/*` stubs + nav; SCons companion stubs present |
| B–D, E′, F | Not started |

## Refusal rules

| Request | Response |
|---------|----------|
| One mega-page only | Refuse; hub exists for overview |
| Generated docs without examples | Refuse |
| Rename methods in docs only | Refuse; match code |

## 1.9.0 / docs candidacy

| Factor | Assessment |
|--------|------------|
| User value | Medium — discoverability and deep links |
| Risk | Low |
| Size | Large editorial effort; land incrementally |
| Release impact | `none` |

Land as **incremental docs PRs** (`impact:none`). Good pairing with
[`antora-ui-bundle.md`](antora-ui-bundle.md) if the docs cycle gets a visible refresh.

## Folder layout

```text
docs/modules/ROOT/pages/methods/build.adoc
docs/modules/ROOT/pages/methods/test-run.adoc
…
docs/modules/ROOT/pages/methods/scons-install.adoc
```

Update hub xrefs to `xref:methods/build.adoc[Build methods]` when files exist.
