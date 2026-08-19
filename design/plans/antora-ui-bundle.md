# Plan: custom Antora UI bundle

- **Status:** in progress
- **Related:** [`ROADMAP.md`](../../ROADMAP.md) — Documentation tooling (`doc-antora-ui`); [`docs/playbook.yml`](../../docs/playbook.yml); supplemental UI [`docs/supplemental-ui/`](../../docs/supplemental-ui/); companion [`colourised-doc-samples.md`](colourised-doc-samples.md)
- **Updated:** 2026-08-19
- **Impact:** none — site presentation only (unless a UI change breaks the docs CI build)

## Why

The published site uses Antora's **default UI bundle** from GitLab CI artifacts
(`playbook.yml` → `antora-ui-default`). It is functional but generic — navigation, typography, and
admonitions read as stock Antora.

A custom look (inspired by Boost docs or MkDocs Material **appearance**, not their stack) would:

- Improve first impression for new users.
- Give semantic report samples ([`colourised-doc-samples.md`](colourised-doc-samples.md)) a
  coherent light-theme palette.
- Host cuppa branding in header/footer (started in `supplemental-ui/` partials).

Reference only (not drop-in): a Boost UI bundle zip — structural differences break if copied
verbatim. MkDocs Material is MIT; still copy **ideas**, not class names or whole stylesheets.

## Issue timing

**Do not file a GitHub issue until the pick-list below is the acceptance bar.** ROADMAP
`doc-antora-ui` plus this plan already track the workstream. A vague “make the docs prettier”
issue would not help review.

File an **`impact:none`** issue when opening the first CSS pull request (or immediately after
this catalogue lands, if a number is useful for the PR body). The issue should quote the
**keep / adapt** rows and the overlay rule in [§How to add CSS](#how-to-add-css), not invent a
second design.

## Goals (this iteration)

1. **Keep the default Antora UI bundle**; polish via `docs/supplemental-ui/` (header/footer already
   present).
2. **Pin** `ui.bundle.url` (job/commit or vendored zip) so CI does not float on `HEAD`.
3. Preserve **Lunr search** and **Mermaid** (re-check after CSS and after any pin).
4. Document local preview: `cd docs && npm ci && npm run build` unchanged for contributors.
5. Leave a **fork of `antora-ui-default`** until one supplemental CSS pass is still insufficient.

Vendoring a full custom bundle remains a later option if supplemental CSS cannot reach nav chrome
or table layout.

## Non-goals

- Rewriting Antora content architecture.
- Dark mode in v1 (optional later).
- Kroki / PlantUML at site build time.
- Custom Mermaid theme ([`doc-mermaid-theme`](../../ROADMAP.md) is a follow-on row).
- Copying Boost or Material CSS wholesale.
- Replacing `css/site.css` from the default bundle (see [§How to add CSS](#how-to-add-css)).

## Approach (settled for v1)

| Id | Option | Use now? |
|----|--------|-----------|
| `approach-supplemental` | Keep default bundle; overlay files | **Yes** |
| `approach-extract-look` | Steal visual *ideas* into cuppa CSS | **Yes** — via the catalogue, not a file dump |
| `approach-fork` | Fork `antora-ui-default` | **Not yet** — spike only if nav/tables still fail after one CSS pass |
| `approach-third-party` | Material-inspired Antora port | **No** for v1 — license + upgrade path |

Header and footer Handlebars already overlay the bundle. There is **no** supplemental CSS file
yet.

## Current pain (default UI + this site)

Drawn from the live site and typical Antora-default pages (hub, CLI, Profiles, toolchain tables).
Re-check against a local `npm run build` before the CSS PR.

| Area | What readers see today | Why it matters |
|------|------------------------|----------------|
| Navbar | Stock grey bar; title “Cuppa Documentation”; useful links already in the overlay | Brand is text-only; little hierarchy vs GitHub/PyPI |
| Sidebar | Default `.nav-list`; current page marker is easy to miss | Nested Dependencies / Toolchains / Profiles trees are hard to scan |
| Measure | Article column is wide on large screens | Long tutorial and CLI pages fatigue |
| Type scale | Headings close to body size | Hubs and deep pages feel the same |
| Admonitions | AsciiDoc `admonitionblock` nested tables | Note/warning look like leftover layout, not callouts |
| Tables | Default borders; wide matrices wrap awkwardly | CLI reference and toolchain grids are core pages |
| Code | Default highlight.js chrome | Fine; not the first lever |
| Pagination | `:page-pagination:` is on; styling is stock | Next/prev exists but does not read as a guide |
| Search | Lunr in the navbar | Keep behaviour; do not restyle into a modal in v1 |
| Samples | Plain `[source,text]` report listings | Colourised samples need tokens from this work later |

Audit pages for the CSS PR (same six every time):

1. Hub — `index.adoc`
2. Long tutorial — `quickstart.adoc` or `cxx-profiles.adoc`
3. Dense tables — `cli-reference.adoc`, `toolchains.adoc`
4. Admonitions + listings — contributing / install
5. Nested nav — Dependencies or C++ Profiles children
6. Search + pagination on a mid-tree page

## Catalogue: Boost / Material ideas → Antora

Sources are **look references**, not dependencies. Map each idea onto Antora classes
(`.navbar`, `.nav-menu`, `.nav-item.is-current-page`, `#toc`, `.doc`, `.admonitionblock`,
`.listingblock`, `.pagination`) — never MkDocs `md-*` or Boost-bundle selectors.

| Element | Cue (Boost-like / Material) | Decision | Notes |
|---------|-----------------------------|----------|--------|
| Page measure / line length | Constrained content column | **Keep** | `max-width` on `.doc`; do not shrink the sidebar |
| Type scale | Distinct H1–H3, quieter body | **Keep** | CSS variables on headings in `.doc` |
| Colour tokens | One brand + semantic status | **Keep** | Light-theme `--cuppa-*`; later `.cuppa-error` etc. for samples |
| Sidebar current page | Stronger active marker | **Keep** | High value, small CSS |
| Admonitions | Left accent bar, muted fill | **Adapt** | Style `.admonitionblock` / `.title`; do not change AsciiDoc HTML |
| Tables | Header background, optional zebra | **Adapt** | Header + tighter cell padding first; no sticky columns in v1 |
| Pagination | Clear prev/next | **Adapt** | Style existing `.pagination` |
| Navbar | Compact brand colour | **Adapt** | Tint/border only; keep overlay markup |
| Code blocks | Title bar, quieter chrome | **Defer** | After type/nav; do not fight highlight.js yet |
| Fonts / icon packs | Material icons, extra webfonts | **Skip** | Weight and self-hosting; system / bundle fonts |
| Dark mode | Material default | **Skip** | Plan non-goal |
| Card / grid landing | Material cards | **Skip** | Needs content rewrite |
| Search modal | Material overlay search | **Skip** | Lunr field stays in the navbar |
| Sticky table first column | Dense comparison tables | **Skip** for v1 | Easy to break overflow |

## How to add CSS

Supplemental files **replace** a bundle file when the relative path matches
([Antora supplemental UI](https://docs.antora.org/antora/latest/playbook/ui-supplemental-files/)).

**Do not** add `docs/supplemental-ui/css/site.css`. That path is the default bundle stylesheet;
replacing it drops all Antora layout CSS.

Add a **new** path and a second `<link>`:

| Path | Role |
|------|------|
| `docs/supplemental-ui/css/cuppa.css` | Cuppa tokens + overrides (new path → added) |
| `docs/supplemental-ui/partials/head-styles.hbs` | Overlay: keep `{{{uiRootPath}}}/css/site.css`, then link `cuppa.css` |

`head-styles.hbs` **does** replace the bundle partial, so the overlay must still load `site.css`.
Do not add a supplemental `ui.yml` unless you copy the bundle descriptor in full — it also
replaces.

Header/footer overlays already in tree:

- `docs/supplemental-ui/partials/header-content.hbs`
- `docs/supplemental-ui/partials/footer-content.hbs`

## Work slices

| Id | Deliverable | Notes |
|----|-------------|-------|
| `ui-audit` | Pain table + catalogue (this section) | Re-verify with local build before CSS |
| `ui-pin` | Pin `ui.bundle.url` (not `HEAD`) | Parallel hygiene; document in contributing |
| `ui-css` | `cuppa.css` + `head-styles.hbs` | Only **Keep** / **Adapt** rows; six audit pages |
| `ui-ci` | `docs` `npm run build` green | GitHub Pages deploy unchanged |
| `ui-fork-spike` | Optional | Only if `ui-css` cannot reach nav/tables |
| `ui-samples-tokens` | `--cuppa-*` used by colourised samples | Coordinate with `colourised-doc-samples.md` |
| `ui-mermaid` | Optional CSS vars | `doc-mermaid-theme` — not this PR |

**First implementation PR:** `ui-css` (+ `ui-pin` in the same PR if small). `ui-audit` is this
plan update.

## Files

| Path | Role |
|------|------|
| `docs/playbook.yml` | `ui.bundle.url` / `snapshot`; `supplemental_files` |
| `docs/supplemental-ui/css/cuppa.css` | Overrides (to add) |
| `docs/supplemental-ui/partials/head-styles.hbs` | Extra stylesheet link (to add) |
| `docs/supplemental-ui/partials/*.hbs` | Header/footer (existing) |
| `docs/modules/ROOT/pages/contributing.adoc` | Pin + preview notes when `ui-pin` lands |
| `design/plans/colourised-doc-samples.md` | Sample classes follow `--cuppa-*` tokens |

## Refusal rules

| Request | Response |
|---------|----------|
| Network fetch of UI bundle on every CI run without pin | Refuse; pin or commit artifact |
| Break Lunr/Mermaid for aesthetics | Refuse |
| Copy Boost bundle or Material CSS wholesale | Refuse |
| Replace `css/site.css` or `ui.yml` without copying bundle contents | Refuse |
| Dark mode / search modal / webfonts in v1 | Refuse; catalogue **Skip** |

## Release

| Factor | Assessment |
|--------|------------|
| User value | Medium — polish, not capability |
| Risk | Low (supplemental CSS); medium if forking |
| Size | Small for `ui-css` |
| Release impact | `none` |

**1.8.0** shipped without this. Fine as **docs-only** in **1.9.0**. Independent of
[`methods-pages-split.md`](methods-pages-split.md) (that plan still wants a behaviour audit
first).

## Related (not this plan)

- **Better Mermaid styling** — `doc-mermaid-theme` after tokens exist.
- **Colourised report samples** — uses tokens from `ui-css`; no sample HTML in the first CSS PR.
- **Page folder layout** — shipped; [`archive/doc-folder-layout.md`](../archive/doc-folder-layout.md).
