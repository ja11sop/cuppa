# Plan: Antora page folders mirroring navigation

- **Status:** shipped
- **Related:** [`ROADMAP.md`](../../ROADMAP.md) — Documentation tooling (`doc-folder-layout`); hub split [`removal-options.md`](../plans/removal-options.md) §7.1 (shipped); [`methods-pages-split.md`](../plans/methods-pages-split.md) (`doc-methods-split`); std::init docs merged [#192](https://github.com/ja11sop/cuppa/pull/192)
- **Updated:** 2026-08-12
- **Impact:** none — documentation paths and xrefs only; no product behaviour

## Why

The Antora **navigation tree** already groups Dependencies, Toolchains, and C++ Profiles into
hubs with nested children. On disk, most of those children still live as **flat, prefixed files**
next to every other page (`dependencies/location.adoc`, `cxx-profiles/std-init/uninit-decl.adoc`,
`toolchains/gcc.adoc`).

Integration test pages already follow a better pattern: `pages/integration/*.adoc` matches
nav nesting and stays readable in the editor.

Problems with the flat layout:

- **Profiles scale fastest** — one designator (`std::init`) already has a hub plus eight rule-family
  pages; more designators will multiply prefixed filenames.
- **Nav ≠ filesystem** — contributors must remember prefix rules that differ per hub (`dependencies-`
  vs `toolchain-` vs `cxx-profiles-std-init-`).
- **Partial paths drift** — shared includes (for example profile attribute markers) sit beside
  unrelated partials instead of under the feature they serve.

This plan moves **child pages into folders** while keeping **hub URLs stable** where practical.

## Timing

Shipped on branch `doc-folder-layout` after [#192](https://github.com/ja11sop/cuppa/pull/192) merged
(2026-08-12).

## Goals

1. **Dependencies** — hub stays `dependencies.adoc`; children move under `dependencies/`.
2. **C++ Profiles** — hub stays `cxx-profiles.adoc`; `std::init` hub and rule pages move under
   `cxx-profiles/std-init/` (room for future designator folders).
3. **Toolchains** — hub stays `toolchains.adoc`; children move under `toolchains/` in the **same
   pass** so one hub pattern is not replaced by another flat prefix scheme.
4. Update **`nav.adoc`**, every **`xref:`**, **`include::partial$`**, and in-repo links (README,
   CHANGELOG, AGENTS hub table) in the same change.
5. **`npm run build`** in `docs/` with zero AsciiDoc warnings; spot-check published URLs on the
   preview site.

## Non-goals

- Renaming hub pages or changing product CLI/docs semantics.
- Antora **redirects** for old child URLs (no redirect extension today; accept URL churn on
  child pages — see below).
- Moving **`integration/`** pages (already folder-aligned).
- **`methods/`** split — stays on [`methods-pages-split.md`](../plans/methods-pages-split.md); optional
  to land methods folders in the same cycle or immediately after.
- Moving **`contributing/`** children (lower churn; can follow the same rule later).

## Target layout

Hub pages remain at `pages/<hub>.adoc` so top-level URLs stay familiar (`…/dependencies.html`,
`…/cxx-profiles.html`, `…/toolchains.html`).

```text
docs/modules/ROOT/pages/
  dependencies.adoc
  dependencies/
    location.adoc
    packages.adoc
    gitlab.adoc
    conan.adoc
    managing.adoc
    extending.adoc
    builtins.adoc
    builtins/
      boost.adoc
      qt.adoc
      quince.adoc

  toolchains.adoc
  toolchains/
    gcc.adoc
    clang.adoc
    msvc.adoc

  cxx-profiles.adoc
  cxx-profiles/
    std-init.adoc
    std-init/
      uninit-decl.adoc
      uninit-read.adoc
      uninit-write.adoc
      ref-to-uninit.adoc
      destroy.adoc
      constructors.adoc
      static-init.adoc
      markers.adoc

docs/modules/ROOT/partials/
  cxx-profiles/
    attribute-markers.adoc    # was cxx-profile-attribute-markers.adoc
```

### Naming conventions (settled)

| Rule | Example |
|------|---------|
| Hub at `pages/<name>.adoc` | `dependencies.adoc`, `cxx-profiles.adoc` |
| Child path mirrors nav segment | `dependencies/location.adoc` |
| Drop redundant prefix in filename | `toolchains/gcc.adoc` → `toolchains/gcc.adoc` |
| Profile designator folder | `cxx-profiles/std-init/` |
| Rule id as leaf name | `uninit-decl.adoc` (not `std-init-uninit-decl.adoc`) |
| Built-in deps optional third level | `dependencies/builtins/boost.adoc` matches nav depth |

### URL impact

| Page | Current URL (approx.) | After move |
|------|------------------------|------------|
| Dependencies hub | `/dependencies.html` | unchanged |
| Location deps | `/dependencies-location.html` | `/dependencies/location.html` |
| Toolchains hub | `/toolchains.html` | unchanged |
| GCC | `/toolchain-gcc.html` | `/toolchains/gcc.html` |
| Profiles hub | `/cxx-profiles.html` | unchanged |
| std::init hub | `/cxx-profiles-std-init.html` | `/cxx-profiles/std-init.html` |
| Rule family | `/cxx-profiles-std-init-uninit-decl.html` | `/cxx-profiles/std-init/uninit-decl.html` |

External bookmarks to **child** pages will break unless we add a redirect mechanism later.
Call that out in the PR; do not block the move on redirects.

## Work slices

| Slice | Deliverable | Notes |
|-------|-------------|-------|
| A | File moves + `nav.adoc` | `git mv`; no prose edits yet |
| B | Xref migration | Repo-wide replace `xref:dependencies/location.adoc` → `xref:dependencies/location.adoc`, etc. |
| C | Partial includes | `include::partial$cxx-profiles/attribute-markers.adoc[]` on std::init pages |
| D | Toolchains + dependencies | Same mechanical pass as profiles |
| E | Verification | `npm run build`; `rg` for stale paths; optional link check in built `_docs_build/site` |
| F | Housekeeping | Update AGENTS.md hub table, CHANGELOG (patch, docs), this plan status → shipped |

Slices A–E can land in **one PR** if the diff stays reviewable (~40 files moved, ~100 xref
touch points). Split by hub only if review asks for it.

## Migration checklist

Mechanical grep targets before merge:

```text
xref:dependencies-
xref:toolchain-
xref:cxx-profiles-std-init
include::partial$cxx-profile-attribute-markers
dependencies/location.adoc
toolchains/gcc.adoc
cxx-profiles-std-init-
```

Also scan:

- [`nav.adoc`](../../docs/modules/ROOT/nav.adoc)
- [`AGENTS.md`](../../AGENTS.md) documentation hub table
- [`CHANGELOG.md`](../../CHANGELOG.md) and [`examples/profiles/std-init-violations/README.md`](../../examples/profiles/std-init-violations/README.md) doc links
- Integration pages under `docs/modules/ROOT/pages/integration/` that xref dependencies or profiles

After moves, every std::init page should still:

- Include the attribute-markers partial from `partials/cxx-profiles/`
- Use `{cpp}` / `{cxx-a-*}` markers (no AsciiDoc `++` regressions)

## Relationship to other doc work

| Workstream | Interaction |
|------------|-------------|
| [`methods-pages-split.md`](../plans/methods-pages-split.md) | When methods children appear, place them under `pages/methods/` using the same hub-at-root rule |
| [`doc-antora-ui`](../../ROADMAP.md) | Independent; can land before or after folder layout |
| std::init content ([#192](https://github.com/ja11sop/cuppa/pull/192)) | Must merge first; this plan only relocates files |

## Refusal rules

| Request | Response |
|---------|----------|
| Move hub pages into folders (`dependencies/index.adoc`) | Refuse for this pass — breaks stable hub URLs without benefit |
| Leave toolchains flat while moving dependencies/profiles | Refuse — leaves two conventions |
| Partial xref update (nav only) | Refuse — broken builds and CI doc job |
| Add redirect extension mid-move | Defer — separate proposal unless maintainer insists |

## Verification

Local gate for the landing PR:

```sh
cd docs && npm run build
rg 'dependencies-location|toolchain-gcc|cxx-profiles-std-init-' docs modules CHANGELOG.md AGENTS.md
pytest -m unit tests/unit/test_design_index.py
```

No Python product tests required (`impact:none`).

## Progress snapshot

| Slice | Status |
|-------|--------|
| Plan drafted | done |
| Wait for #192 merge | done |
| Slice A–E (folder move PR) | done — branch `doc-folder-layout` |
| Plan → shipped | done |
