# Plan: split Methods into per-method Antora pages

- **Status:** in progress
- **Related:** [`ROADMAP.md`](../../ROADMAP.md) — Documentation tooling (`doc-methods-split`); hub [`methods.adoc`](../../docs/modules/ROOT/pages/methods.adoc); [`dependencies.adoc`](../../docs/modules/ROOT/pages/dependencies.adoc) hub pattern; Phase 3 doc split [`removal-options.md`](removal-options.md) §7.1; behaviour track [`method-behaviour-audit.md`](method-behaviour-audit.md)
- **Updated:** 2026-08-30
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
- Realistic teaching for everyday `env.*` calls — whether Cuppa registered them or the build
  engine provides them — without making provenance the navigation model.

## Goals

1. Turn **`methods.adoc` into a hub** — prerequisites, progress overview, topic map, and a
   **comprehensive method index** (grouped sensibly; every name links to the Cuppa page that
   covers it when we have one, else a careful upstream link).
2. **Topic pages** by *reader job* (build, test, flags, files/install, depends, …) — not by
   whether a call is implemented in Cuppa or in SCons.
3. Document everyday engine methods Cuppa projects actually use (`Install`, `Depends`,
   `AppendUnique`, …) with the **same depth** as Cuppa-registered methods: realistic examples,
   Related methods, behaviour fields — not terse “see SCons” stubs.
4. Update **`nav.adoc`** to mirror the dependency/toolchain nesting pattern.
5. Child pages live under **`docs/modules/ROOT/pages/methods/`** (same idea as `integration/`).

## Settled — navigation and naming (2026-08-30)

| Decision | Choice |
|----------|--------|
| Page filenames | Job names only: `install.adoc`, `depends.adoc`, `flags-and-toolchain.adoc` — **no** `scons-` prefix |
| Grouping axis | What the reader is trying to do, not Cuppa vs SCons provenance |
| Flags set | `ReplaceFlags`, `RemoveFlags`, `AppendUnique`, `MergeFlags`, `Append`, … on **one** flags page with `Toolchain` |
| Install / copy | `Install` / `InstallAs` with `CopyFiles` / `CopyFilesAs` (files + install story; `install.adoc` may be the install-focused chapter or a section — prefer one coherent narrative) |
| Graph edges | `Depends`, `Requires`, `Alias` on `depends.adoc` |
| Upstream links | Optional deep links to SCons docs for completeness; **never** versioned doc URLs (they rot and confuse). Prefer Cuppa xrefs whenever we cover the method |
| Depth | Engine methods get full tutorials and realistic examples — SCons upstream is notoriously thin/contrived; we do not outsource teaching to it |
| Method names in prose | Monospace with empty parens: `` `Build()` `` — signals a method without stealing bold. Full calls (`env.Build('hello', …)`) stay in code blocks. Contrast engine builders as “vanilla SCons `Program()`” |
| Progress vs variant | Do **not** claim vanilla SCons builders lack progress on a Cuppa env — `EnvironmentMethods.add_progress_tracking` wraps them. Prefer Cuppa methods for **variant / layout / toolchain / modules**; say “vanilla `X()` will break your Cuppa builds” for that footgun |

Readers who have never heard of SCons should still find “how do I set flags?” and “how do I install files?” without a provenance taxonomy.

## Non-goals

- Duplicating the entire SCons reference.
- Auto-generating pages from `add_method` registration (manual prose stays authoritative).
- Moving integration test pages (already under `integration/`).
- Nav labels or filenames that say “SCons companions”.

## Method inventory (topic grouping)

Group related calls to avoid forty tiny pages. Cuppa-registered and engine methods share a row when
they form one job:

| Nav group | Methods (Cuppa and/or engine) | Page |
|-----------|-------------------------------|------|
| Build | `Build`, `Compile`, `CompileStatic`, `CompileShared`, `BuildLib`, `BuildStaticLib`, `BuildSharedLib` | `methods/build.adoc` |
| Test & run | `BuildTest`, `*Test`, `Test`, `BuildBenchmark`, `*Benchmark`, `Benchmark`, `Run` | `methods/test-run.adoc` |
| Coverage | `Coverage`, `CollateCoverageFiles`, `CollateCoverageIndex` | `methods/coverage.adoc` |
| C++ dialect & modules | `StdCpp`, `CxxModules`, `Modules` (deprecated), `Module`, `HeaderUnit`, `ImportModules`, `CxxProfiles`, … | `methods/cxx-dialect-and-modules.adoc` |
| Dependencies & profiles | `BuildWith`, `Using`, `BuildProfile` | `methods/dependencies-and-profiles.adoc` |
| Flags & toolchain | `Toolchain`, `ReplaceFlags`, `RemoveFlags`, **`AppendUnique`**, **`MergeFlags`**, `Append`, … | `methods/flags-and-toolchain.adoc` |
| Files, templates, install | `CopyFiles`, `CopyFilesAs`, `TargetFrom`, templates, `RecursiveGlob`, `GlobFiles`, `Filter`, **`Install`**, **`InstallAs`**, **`Glob`**, **`File`** | `methods/files-and-templates.adoc` and/or `methods/install.adoc` (split only if the page grows too large) |
| Depends | **`Depends`**, **`Requires`**, **`Alias`** | `methods/depends.adoc` |
| Docs assets | `AsciidocToHtml`, `MarkdownToHtml`, `CompileScss`, `CreateVersion`, `RunAndRedirectToFile` | `methods/docs-assets.adoc` |
| Packages | `PublishPackage`, `InstallPackage`, plus **`Command`** where publishers wrap external builds | `methods/packages.adoc` (cross-link `Command` from custom-commands if needed) |
| Custom commands | `cwd` / `--use-shell`; **`Command`** for custom actions | `methods/custom-commands.adoc` |

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

## Comprehensive method index

Somewhere on the hub (or a dedicated `methods/index.adoc` linked from the hub) maintain a
**complete** grouped list of methods readers might call — Cuppa registrations plus the engine
methods we teach. Each entry:

- Links to the Cuppa topic page when we cover it.
- Otherwise links to **unversioned** upstream documentation (no `/doc/4.x/`-style paths).
- Notes Related methods so hot paths (test → Filter → CopyFiles → coverage) stay discoverable.

## Consumer usage survey (2026-08-30)

Scanned Cuppa `sconstruct` / `sconscript` / nested `*.sconscript` files across four private
consumer trees (shape only — see local `INTERNAL_PROJECTS.local.md` for the map): a **large
multi-service Cuppa tree** (~279 scripts; includes **project A** and **project C**), a **smaller
sibling product tree** (~43; includes **project B**), a **packages / publisher tree** (~10), and
one **tree with no Cuppa sconscripts**. Counts below are call sites across that corpus (not unique
products). Use this for **Related methods**, example priority, and which engine methods to teach
first — not as a public claim about any named organisation.

### Dominant test idiom

Nearly every test sconscript repeats the same spine:

1. `BuildWith(…)` (+ often `AppendUnique` / `MergeFlags` for defines / libs)
2. `BuildTest(…)` (explicit source list; rarely recursive discovery)
3. `CopyFiles(artifacts_dir, Filter(test, ["*.log", "*.json"]))`
4. `CollateCoverageFiles` → `GenerateHtmlTestReport` → `CollateTestReportIndex` /
   `CollateCoverageIndex`

So **Related methods** on Test / Files / Coverage pages should cross-link that chain first.
`Filter` is overwhelmingly used on **test output nodes**, not on `Glob` results.

### Cuppa methods — high / medium / rare in this corpus

| Band | Methods (approx. call volume) | Doc implication |
|------|-------------------------------|-----------------|
| Hot | `CopyFiles`, `BuildWith`, `Filter`, `BuildTest`, coverage collate pair, HTML test report + index | Lead examples; hub “everyday” path |
| Common | `Build`, `Compile`, `CreateVersion`, `ExpandTemplateFile`, `Run`, `BuildBenchmark` | Binary / service scripts; keep real |
| Present | `PublishPackage` (publisher tree), `AsciidocToHtml`, `CompileScss`, `RenderJinjaTemplate`, `RemoveFlags` | Docs/assets + packages pages |
| Rare | `RecursiveGlob` (nested scenario data under one product include-tree only) | Still document; do not imply fleet-wide use |
| Absent here | `GlobFiles`, `Using`, `BuildLib` / `BuildStaticLib` / `BuildSharedLib`, standalone `Test` / `Benchmark`, `CopyFilesAs`, `TargetFrom`, `InstallPackage`, modules / Profiles method surface, `MarkdownToHtml`, `InstallAs`, `Alias` | Still document from product design + cuppa tests; invent fewer “fleet-style” examples |

`env.Glob` appears mostly in **`sconstruct`** customisation (pinning single third-party sources via
`local_sub_path`) and in a few doc/asset scripts — not as the primary test source discovery tool.

### Engine methods to teach early (same depth as Cuppa)

| Priority | API | Observed role | Lives with |
|----------|-----|---------------|------------|
| 1 | `AppendUnique`, `MergeFlags` | Everywhere beside `BuildWith` | Flags page |
| 2 | `Requires` | Order packaging copies after `Build` / `CreateVersion` | Depends page |
| 3 | `Depends` | Test graph edges (DB scripts, wait/update nodes) | Depends page |
| 4 | `Install` | Package staging; occasional `final/` assets | Install / files narrative |
| 5 | `Command` | Publisher tree: wrap external CMake steps | Packages / custom commands |
| 6 | `Glob`, `File` | Dep sources; `#/` assets; templates | Files page |
| 7 | `AlwaysBuild`, `Clean` | Force regenerate / clean staged dirs | Brief sections on depends or packages |
| Low | `InstallAs`, `Alias`, … | Unused in corpus | Short “when you need it” on the job page |

### Example / Related-methods checklist (when migrating pages)

- Test page: Related → `Filter`, `CopyFiles`, coverage collate, HTML reports, `BuildWith`
- Files page: Related → `Filter` on test outputs; `RecursiveGlob`; `Glob` / `File`; `Install`
- Build page: Related → `Compile`, `CreateVersion`, `Requires` + `CopyFiles` for packaging
- Flags page: Related → `BuildWith`, `ReplaceFlags` / `RemoveFlags` / `AppendUnique` / `MergeFlags`
- Packages page: Related → `Install`, `Command`, `Depends` / `Requires`, `PublishPackage`

## Hub page retention

Leave on **`methods.adoc`** (target end state):

- Prerequisites
- Progress tracking and variant scoping (mermaid diagram)
- Topic map + **comprehensive method index**
- Optional short “how Cuppa relates to the build engine” without making engine provenance the nav axis

Custom commands may stay on the hub briefly, then move to `methods/custom-commands.adoc`.

## Work slices

| Slice | Deliverable | Notes |
|-------|-------------|-------|
| **0** | Behaviour audit fixed or deferred | [#213](https://github.com/ja11sop/cuppa/issues/213) + glob parity **done**; `mba-artifact-paths` **deferred** ([#233](https://github.com/ja11sop/cuppa/issues/233)) |
| **A** | Hub map + nav skeleton + stubs | Job-named pages; no `scons-*` filenames |
| **B** | Build + test groups | **Done** — #213 semantics; everyday Filter/CopyFiles pattern on test page |
| **E′** | Flags / depends / install depth | **Done** — full tutorials; unversioned production upstream links |
| **C** | Coverage + C++ groups | **Done** — baseline topic pages |
| **D** | Remaining groups | **Done** — files, packages, docs assets, custom commands, deps |
| **F** | Redirect grep + method index | **Partial** — hub method index landed; keep fixing moved anchors as needed |

## Progress snapshot

| Slice | Status |
|-------|--------|
| 0 | Largely done — artifact-path emitters deferred with issue |
| A | **Done** — hub topic map + job-named stubs (no `scons-*`); flags page owns AppendUnique/MergeFlags |
| E′ | **Done** — flags / depends / install tutorials |
| C–D | **Done** — remaining topic baselines migrated off the hub |
| F | **Partial** — hub <<method-index>> present; continue anchor cleanup |
| Consumer survey | **Done** (2026-08-30) |
| Naming / grouping settled | **Done** — job pages, flags coalesce, full engine depth |
| B–D, E′, F | Not started |

## Refusal rules

| Request | Response |
|---------|----------|
| One mega-page only | Refuse; hub exists for overview |
| Generated docs without examples | Refuse |
| Rename methods in docs only | Refuse; match code |
| Terse “see SCons docs” for engine methods we teach | Refuse; teach with realistic Cuppa-project examples |
| Versioned upstream SCons doc URLs | Refuse; unversioned links only |

## 1.9.0 / docs candidacy

| Factor | Assessment |
|--------|------------|
| User value | Medium — discoverability and deep links |
| Risk | Low |
| Size | Large editorial effort; land incrementally |
| Release impact | `none` |

Land as **incremental docs commits** on one PR until Methods topic pages have a **baseline**
(merge only when the live site would not show empty stubs). Good pairing afterward with
[`docs-site-release-default.md`](docs-site-release-default.md) (visitors default to **released**
docs) and [`docs-llms-txt.md`](docs-llms-txt.md) (agent Markdown / `llms.txt`), and with
[`antora-ui-bundle.md`](antora-ui-bundle.md) if the docs cycle gets a visible refresh.

## Folder layout

```text
docs/modules/ROOT/pages/methods/build.adoc
docs/modules/ROOT/pages/methods/test-run.adoc
docs/modules/ROOT/pages/methods/flags-and-toolchain.adoc
docs/modules/ROOT/pages/methods/install.adoc
docs/modules/ROOT/pages/methods/depends.adoc
…
```

Update hub xrefs to `xref:methods/build.adoc[Build methods]` when files exist.
