# Plan: split Methods into per-method Antora pages

- **Status:** proposal
- **Related:** [`ROADMAP.md`](../../ROADMAP.md) — Documentation tooling (`doc-methods-split`); hub [`methods.adoc`](../../docs/modules/ROOT/pages/methods.adoc); [`dependencies.adoc`](../../docs/modules/ROOT/pages/dependencies.adoc) hub pattern; Phase 3 doc split [`removal-options.md`](removal-options.md) §7.1
- **Updated:** 2026-08-11
- **Impact:** none — documentation and navigation only

## Why

[`methods.adoc`](../../docs/modules/ROOT/pages/methods.adoc) is a single long page (~540 lines)
covering progress, build, test, coverage, custom commands, modules, and packages. Dependencies
and toolchains already use a **hub + child pages** model (`dependencies.adoc` →
`dependencies-*.adoc`, `toolchains.adoc` → `toolchain-*.adoc`).

Methods are the core **`sconscript` vocabulary**. Each deserves:

- Its own URL for linking from integration tests and error messages.
- Room for parameters, examples, progress behaviour, and toolchain notes without scrolling.
- A path to document **canonical SCons helpers** used with cuppa (`env.Install`, etc.) without
  sending readers to fragmented upstream SCons docs.

## Goals

1. Turn **`methods.adoc` into a hub** — prerequisites, progress overview, method index table.
2. **Phase 1:** one Antora page per **cuppa-registered method family** (see inventory below).
3. **Phase 2:** short pages for **selected SCons methods** cuppa projects use daily, grouped under
   `methods-scons.adoc` or nested nav.
4. Update **`nav.adoc`** to mirror the dependency/toolchain nesting pattern.
5. Optional: **`docs/modules/ROOT/pages/methods/`** folder aligned with nav (same idea as
   `integration/` pages — see [`doc-folder-layout.md`](../archive/doc-folder-layout.md)).

## Non-goals

- Duplicating full SCons reference documentation.
- Auto-generating pages from `add_method` registration (manual prose stays authoritative).
- Moving integration test pages (already under `integration/`).

## Method inventory (Phase 1 grouping)

Group related registrations to avoid forty tiny pages:

| Nav group | Cuppa methods | Source module(s) |
|-----------|---------------|------------------|
| Build | `Build`, `Compile`, `CompileStatic`, `CompileShared`, `BuildLib`, `BuildStaticLib`, `BuildSharedLib` | `build.py`, `compile.py`, `build_library.py` |
| Test & run | `BuildTest`, `*Test`, `Test`, `BuildBenchmark`, `*Benchmark`, `Benchmark`, `Run` | `build_test.py`, `test.py`, `build_benchmark.py`, `benchmark.py`, `run.py` |
| Coverage | `Coverage`, `CollateCoverageFiles`, `CollateCoverageIndex` | `coverage.py` |
| C++ dialect & modules | `StdCpp`, `CxxModules`, `Modules` (deprecated), `Module`, `HeaderUnit`, `ImportModules`, `CxxProfiles`, `CxxProfilesEnforce`, `CxxDisableErrorLimit` | `stdcpp.py`, `modules.py`, `module.py`, `header_unit.py`, `import_modules.py`, `cxx_profiles.py`, `cxx_disable_error_limit.py` |
| Dependencies & profiles | `BuildWith`, `Using`, `BuildProfile` | `build_with.py`, `using.py`, `build_profile.py` |
| Flags & toolchain | `Toolchain`, `ReplaceFlags`, `RemoveFlags` | `toolchain.py`, `replace_flags.py`, `remove_flags.py` |
| Files & templates | `CopyFiles`, `CopyFilesAs`, `TargetFrom`, `ExpandTemplateFile`, `RenderJinjaTemplate`, `RecursiveGlob`, `GlobFiles`, `Filter` | respective modules |
| Docs assets | `AsciidocToHtml`, `MarkdownToHtml`, `CompileScss`, `CreateVersion`, `RunAndRedirectToFile` | respective modules |
| Packages | `PublishPackage`, `InstallPackage` | `manage_packages.py` |

Each group page: signature, when to use, minimal example, progress/NotifyProgress note, xrefs to
toolchains/modules/coverage as needed.

## Phase 2 — SCons companions (proposal)

| Page | Cover |
|------|--------|
| `methods-scons-install.adoc` | `env.Install`, `env.InstallAs`, cuppa layout under `_build/` / `final/` |
| `methods-scons-depends.adoc` | `Depends`, `Requires`, `Alias` in cuppa projects |
| `methods-scons-env.adoc` | `CPPPATH`, `LIBPATH`, when to prefer cuppa methods |

Keep each page short; link to SCons upstream for exhaustive API.

## Hub page retention

Leave on **`methods.adoc`**:

- Prerequisites
- Progress tracking and variant scoping (mermaid diagram)
- Custom commands / `--use-shell` / POSIX vs Windows spawn (or move to `methods-custom-commands.adoc` if hub stays short)
- Index table linking every child page

## Work slices

| Slice | Deliverable | Notes |
|-------|-------------|-------|
| A | Hub trim + nav skeleton | Empty child stubs with `xref` |
| B | Build + test groups | Highest traffic |
| C | Coverage + C++ groups | Link cxx-modules / cxx-profiles |
| D | Remaining groups | Files, packages, flags |
| E | Phase 2 SCons pages | Optional same cycle |
| F | Redirect grep in repo | Fix internal links to `#anchors` that moved |

## Refusal rules

| Request | Response |
|---------|----------|
| One mega-page only | Refuse; hub exists for overview |
| Generated docs without examples | Refuse |
| Rename methods in docs only | Refuse; match code |

## 1.8.0 candidacy

| Factor | Assessment |
|--------|------------|
| User value | Medium — discoverability and deep links |
| Risk | Low |
| Size | Large editorial effort; can land incrementally (slice B–C enough for 1.8.0) |
| Release impact | `none` |

**Suggested:** **1.8.0** friendly as **incremental docs PRs** (slices A–C) even while 1.8.0.dev code
work is elsewhere. Good pairing with [`antora-ui-bundle.md`](antora-ui-bundle.md) if docs cycle
gets a visible refresh.

## Folder layout (optional polish)

Mirror integration tests:

```text
docs/modules/ROOT/pages/methods/build.adoc
docs/modules/ROOT/pages/methods/test-run.adoc
…
```

Update hub xrefs to `xref:methods/build.adoc[Build methods]` when files move.
