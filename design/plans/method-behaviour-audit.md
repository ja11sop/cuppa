# Plan: Cuppa env method behaviour audit (paths, evaluation, returns)

- **Status:** proposal
- **Related:** [`ROADMAP.md`](../../ROADMAP.md) — `method-behaviour-audit`; [#213](https://github.com/ja11sop/cuppa/issues/213); [`methods-pages-split.md`](methods-pages-split.md); [`static-glob-rename.md`](static-glob-rename.md)
- **Updated:** 2026-08-17
- **Impact:** patch — behaviour fixes and shared helpers; documentation split follows in a separate docs-only stream

## Purpose

Catalogue **how cuppa `env.*` methods behave** — not just signatures — so we can fix inconsistencies
before writing per-method Antora pages. The Methods hub today lists names; readers (and agents)
need to know:

1. **What the call returns** (nodes, env, string, side-effect only).
2. **When the work is evaluated** (immediate, configure-time snapshot, build action, post-build).
3. **How output paths are named** (mirrored under `working/`, flat basename, explicit target, `final/` layout).

This plan is the **behaviour and fix** track. [`methods-pages-split.md`](methods-pages-split.md) is the
**documentation layout** track and must not run ahead of settled behaviour here.

## Prerequisite ordering

```text
method-behaviour-audit (fixes)  →  static-glob-rename (optional API)  →  methods-pages-split (docs)
```

Ship [#213](https://github.com/ja11sop/cuppa/issues/213) compile object paths first (branch
`issue/213-compile-object-paths`). Remaining slices below are follow-on PRs on the same theme.

## Classification axes

Every method family should be documented (eventually) with these columns:

| Axis | Values | Reader question |
|------|--------|-----------------|
| **Returns** | Nodes / env / str / list / None | What can I pass to `Build`, `Filter`, `Depends`? |
| **Evaluation** | Immediate / static snapshot / SCons dynamic / build action / post-build | Will a new file on disk appear without re-running configure? |
| **Output naming** | Mirror source tree / flat basename / caller target / N/A | Can two same-basename sources collide? |
| **Progress** | NotifyProgress / none | Does it show in variant Finished output? |

## Issue class A — flat intermediate targets (Compile bug family)

**Pattern:** output path uses **basename only** under a single directory, so nested sources with
the same name collide (`UserError: Multiple ways to build the same target`).

### Fixed by #213 (on branch)

Shared helper: [`object_target_for`](../../cuppa/utility/object_target.py) — targets **relative
to** `variant_dir` (`working/`), e.g. `src/detail/except.o` →
`_build/.../working/src/detail/except.o`.

| Method | Via | Status |
|--------|-----|--------|
| `Compile`, `CompileStatic`, `CompileShared` | direct | **Fixed** (#213) |
| `Build`, `BuildTest`, `BuildBenchmark` | `Compile` | **Fixed** |
| `BuildStaticLib`, `BuildSharedLib`, `BuildLib` | `Compile*` | **Fixed** |
| `Module`, `HeaderUnit` | `compile_with_modules` | **Fixed** (TU objects; BMI uses `modules/` tree) |

**Follow-on check:** `--cov` gcov layout vs mirrored objects — sanity pass after #213 lands
([`run_gcov_coverage.py`](../../cuppa/cpp/run_gcov_coverage.py) derives paths from source nodes).

### Open — same pattern, different product (flat under `final/` or output dir)

| Method | Emitter rule | Collision example | Priority |
|--------|--------------|-------------------|----------|
| `MarkdownToHtml` | `{final_dir}/{basename}.html` | `doc/a/readme.md` + `doc/b/readme.md` | Medium |
| `AsciidocToHtml` | default `{final_dir}/{basename}.html` | same | Medium |
| `RunAndRedirectToFile` | `{final_dir}/{basename}{ext}` | two programs logged to same `.out` name | Low |
| `CompileScss` | `{abspath(source)}.css` | uncommon; odd vs `working/` layout | Low |

**Proposed fix pattern:** reuse or extend `object_target_for` / a sibling
`artifact_target_for(env, source, suffix, *, root='final'|'working')` so doc/asset outputs mirror
source subdirs under the chosen root unless the caller passes an explicit target list.

## Issue class B — static vs dynamic discovery

| API | Evaluation | Notes |
|-----|------------|-------|
| SCons `env.Glob` (`**`) | **Dynamic** | Build-graph aware; new files may appear without editing sconscript |
| `RecursiveGlob`, `GlobFiles` | **Static** | Python walk/listdir at sconscript load |
| `Filter` | **Immediate** | Subset of existing nodes; pairs with dynamic Glob |

**Risk:** readers treat `RecursiveGlob` like CMake `GLOB_RECURSE` + Ninja rebuild semantics — it is
not. Rename and docs: [`static-glob-rename.md`](static-glob-rename.md).

**Filter follow-on:** ensure match patterns work consistently for nodes from static vs dynamic
discovery (`str(node)` vs `node.path` — see [`filter.py`](../../cuppa/utility/filter.py)).

## Issue class C — already path-aware (reference behaviour)

Document as the **target standard** for emitters:

| Method | Output naming |
|--------|---------------|
| `RenderJinjaTemplate` | `{final_dir}/{path_offset}/{file}` |
| `CreateVersion` | `offset_path` under `working/` |
| `CopyFiles` / `CopyFilesAs` | SCons `Install` / `InstallAs` |
| `ExpandTemplateFile` | caller-supplied target |
| `TargetFrom` | `relpath(source.path, build_dir)` (string helper, not a build action) |

## Issue class D — env / orchestration (no path collision)

No flat intermediate target bug; document evaluation only:

| Group | Methods | Returns | Evaluation |
|-------|---------|---------|------------|
| Env mutators | `StdCpp`, `ReplaceFlags`, `RemoveFlags`, `CxxProfiles`, … | env | Immediate |
| Deps | `BuildWith`, `Using`, `Toolchain` | side effects | Configure |
| Run/test drivers | `Run`, `Test`, `Coverage`, collate helpers | side effects / reports | Build / post-build |
| Packages | `PublishPackage`, `InstallPackage` | package nodes | Configure / build |

## Work slices

| ID | Deliverable | Depends on | Impact |
|----|-------------|------------|--------|
| `mba-213` | Land compile object path mirror ([#213](https://github.com/ja11sop/cuppa/issues/213)) | — | patch |
| `mba-cov-check` | Coverage integration pass after mirrored `.o` paths | `mba-213` | patch |
| `mba-artifact-paths` | Shared helper + fix Markdown/AsciiDoc/RunAndRedirect emitters | `mba-213` | patch |
| `mba-scss` | Decide SCSS output root (`working/` mirror vs beside source) | optional | patch |
| `mba-static-glob` | RecursiveGlob path vocabulary + Glob semantics | [`static-glob-rename.md`](static-glob-rename.md) | minor |
| `mba-filter` | Filter matching parity for Glob + RecursiveGlob nodes | `mba-static-glob` | patch |
| `mba-doc` | Export classification tables into Methods hub + child pages | [`methods-pages-split.md`](methods-pages-split.md) | none |

## Acceptance criteria (audit complete)

1. No cuppa method in class A left with flat-basename-only naming for nested source trees unless
   explicitly documented as intentional.
2. Classification table (this plan) reflected in Methods hub index — per [`methods-pages-split.md`](methods-pages-split.md).
3. Integration tests for at least one doc/asset emitter with duplicate basenames in different dirs.
4. Snapshot vs directory Glob documented; RecursiveGlob path roots landed;
   issue link.

## Progress snapshot

| Slice | Status |
|-------|--------|
| Audit document | this plan |
| #213 compile fix | on branch `issue/213-compile-object-paths` |
| Doc/asset flat naming | not started |
| Coverage sanity | not started |
| Methods doc split | blocked on this plan |

## Non-goals

- Full SCons API reference.
- Renaming every method for consistency in one release.
- Auto-generated docs from `add_method` registration.

## References

- Boost.Capy experiment — [`cmake-to-cuppa-migration.md`](cmake-to-cuppa-migration.md)
- Modules object stem rule — [`cxx-modules.adoc`](../../docs/modules/ROOT/pages/cxx-modules.adoc)
