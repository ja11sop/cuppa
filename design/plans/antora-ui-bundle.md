# Plan: custom Antora UI bundle

- **Status:** in progress
- **Related:** [`ROADMAP.md`](../../ROADMAP.md) — Documentation tooling (`doc-antora-ui`); [`docs/playbook.yml`](../../docs/playbook.yml); supplemental UI [`docs/supplemental-ui/`](../../docs/supplemental-ui/); companions [`colourised-doc-samples.md`](colourised-doc-samples.md), [`shiki-syntax-highlighting.md`](shiki-syntax-highlighting.md)
- **Updated:** 2026-08-25
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
- A dark-mode *toggle* in v1 (palettes already follow `prefers-color-scheme`).
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
| Colour tokens | One brand + semantic status | **Keep** | Complete semantic contract in a named `cuppa-palette-*.css` file; six palettes (cup-of-tea, mint-tea, fine-bone-china, harbour, forest, aubergine), each with a `prefers-color-scheme: dark` override; later `.cuppa-error` sample classes |
| Sidebar current page | Stronger active marker | **Keep** | High value, small CSS |
| Admonitions | Boxed MkDocs-style heading + quieter body | **Adapt** | Semantic border/glow; compact tinted heading with a masked Material icon and label/title; page-colour body at a smaller type size; do not change AsciiDoc HTML |
| Expandable examples | Tinted collapsed disclosure | **Adapt** | Same callout chrome as admonitions (border, radius, glow, heading-strip height); flask mark, right-aligned plus/minus control, and progressive native-details transition |
| Tables | Header background, optional zebra | **Adapt** | Header + tighter cell padding first; no sticky columns in v1. Column ratios are content, not CSS: the bundle sets `table-layout: fixed`, so every table declares `cols` sized from its own cells, with repeated families held to one ratio |
| Pagination | Clear prev/next | **Adapt** | Style existing `.pagination` |
| Navbar | Compact brand colour | **Adapt** | Tint/border only; keep overlay markup |
| Navbar brand marks | Project / registry icons | **Adapt** | GitHub and PyPI links carry inline SVG marks (Simple Icons paths, CC0) that inherit `currentColor`; text labels stay for the mobile menu |
| Code blocks | Title bar, quieter chrome | **Adapt** | Quieter frame and a smaller monospace scale (`--cuppa-code-size*`); highlight.js tokens untouched in this UI pass; token theming and line numbers are [`shiki-syntax-highlighting.md`](shiki-syntax-highlighting.md) (`doc-shiki`). Wide listing/console samples: horizontal scroll only, inset edge fades + shadows inside the frame border, click-drag pan with clamp + edge pulse at limits |
| Fonts / icon packs | Material icons, extra webfonts | **Skip** | Weight and self-hosting. Cherry-picked Material paths (Apache 2.0) are embedded as `--cuppa-icon-*` data-URI masks in `cuppa.css`, so semantic and disclosure marks inherit palette colour without a pack or extra request; the two navbar marks stay inline in the header partial |
| Dark mode | Material default | **Adapt** | Palette files follow `prefers-color-scheme`; a navbar toggle remains deferred |
| Card / grid landing | Material cards | **Skip** | Needs content rewrite |
| Search modal | Material overlay search | **Skip** | Lunr field stays in the navbar |
| Sticky table first column | Dense comparison tables | **Skip** for v1 | Easy to break overflow |

## How to add CSS

Supplemental files **replace** a bundle file when the relative path matches
([Antora supplemental UI](https://docs.antora.org/antora/latest/playbook/ui-supplemental-files/)).

**Do not** add `docs/supplemental-ui/css/site.css`. That path is the default bundle stylesheet;
replacing it drops all Antora layout CSS.

Add **new** paths and two links after the bundle stylesheet:

| Path | Role |
|------|------|
| `docs/supplemental-ui/css/cuppa-palette-*.css` | Selected semantic colour contract (one file linked at a time) |
| `docs/supplemental-ui/css/cuppa.css` | Colour-independent component overrides |
| `docs/supplemental-ui/partials/head-styles.hbs` | Overlay: keep `site.css`, then load the selected palette and `cuppa.css` |

`head-styles.hbs` **does** replace the bundle partial, so the overlay must still load `site.css`.
Do not add a supplemental `ui.yml` unless you copy the bundle descriptor in full — it also
replaces.

To compare palettes, change the palette filename in `head-styles.hbs`, rebuild, and reload:

- `cuppa-palette-cup-of-tea.css` — cup of tea (currently selected)
- `cuppa-palette-mint-tea.css` — mint tea
- `cuppa-palette-fine-bone-china.css` — fine bone china
- `cuppa-palette-harbour.css` — harbour
- `cuppa-palette-forest.css` — forest
- `cuppa-palette-aubergine.css` — aubergine

Each file defines the same token names, including page/text/surface colours,
`--cuppa-table` / `--cuppa-table-surface`, and `color-scheme: light dark`. Dark values
live in a `prefers-color-scheme: dark` block in the same file, so a future toggle can
flip scheme without rewriting component selectors.

Header/footer overlays already in tree:

- `docs/supplemental-ui/partials/header-content.hbs`
- `docs/supplemental-ui/partials/footer-content.hbs`

Removing a piece of bundle chrome works the same way: overlay the partial that renders it with
one that renders nothing. `docs/supplemental-ui/partials/edit-this-page.hbs` does that for the
toolbar edit link. A playbook `edit_url: false` is not enough, because the bundle partial links
`page.fileUri` for a worktree build before it considers `page.editUrl`.

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

### Progress snapshot (2026-08-21)

| Id | Status |
|----|--------|
| `ui-audit` | **Shipped** — catalogue and overlay rules in [#227](https://github.com/ja11sop/cuppa/pull/227) |
| `ui-css` | **On branch `docs/antora-ui-css`** — navbar/nav; article type scale; compact tables; admonitions; disclosures; code scale; pagination; separate palette contract. Review passes: nav labels retain uniform alignment while brand-colour carets sit fully outside highlights; the current-page rule marks leaf items only, since a caret already marks a parent; tables drop vertical rules for a tinted heading band opened and closed by a `--cuppa-table` rule; GitHub/PyPI marks; smaller body and monospace scales; edit-page link removed; subtree parent/overview links are distinct; visible `C++` notation normalised through AsciiDoc attributes; chevrons inside pagination buttons; inline code uses a translucent ink wash (`--cuppa-code-tint`, with an opaque fallback) in every context, so it darkens the surface behind it rather than laying grey over a tinted heading; admonition table cells stack inside one semantic outer border/glow, with compact headings, locally embedded Material SVG marks, and heading-strip tokens that shift mark and label independently (per type where a glyph needs it) so both the generic label and an explicit title share one alignment; independently coloured expandable examples share that callout chrome and pair a flask mark with a right-aligned plus/minus control and progressive transition; six palettes (cup-of-tea, mint-tea, fine-bone-china, harbour, forest, aubergine) each carry light and `prefers-color-scheme: dark`; navbar uses `background-clip: padding-box` so Chromium does not paint a band of navbar colour below the accent border; every table declares a `cols` ratio measured from its own content, because the bundle's `table-layout: fixed` applies Antora's equal split literally, and repeated families (toolchain flag tables, Methods reference tables) are held to one ratio across sibling pages; the dense CLI reference is split into an introductory hub and seven task pages, with option/value tables and a curated SCons subset |
| `ui-pin` | **Next** — keep separate until a stable default-bundle artifact or vendoring route is selected |
| `ui-ci` | Local Antora build passes; verify Pages CI on the CSS pull request |
| `ui-fork-spike` | Deferred pending review of the supplemental pass |

## Files

| Path | Role |
|------|------|
| `docs/playbook.yml` | `ui.bundle.url` / `snapshot`; `supplemental_files` |
| `docs/supplemental-ui/css/cuppa-palette-*.css` | Named palettes: cup-of-tea, mint-tea, fine-bone-china, harbour, forest, aubergine; each file is the full light+dark token contract |
| `docs/supplemental-ui/css/cuppa.css` | Colour-independent component overrides |
| `docs/supplemental-ui/partials/head-styles.hbs` | Base, selected-palette, and component stylesheet links |
| `docs/supplemental-ui/partials/header-content.hbs` | Navbar overlay, including the inline GitHub / PyPI marks |
| `docs/supplemental-ui/partials/footer-content.hbs` | Footer overlay (existing) |
| `docs/supplemental-ui/js/cuppa-scroll-panels.js` | Wide listing scroll affordances and click-drag pan |
| `docs/supplemental-ui/partials/edit-this-page.hbs` | Empty overlay that removes the toolbar edit link |
| `docs/modules/ROOT/pages/contributing.adoc` | Pin + preview notes when `ui-pin` lands |
| `design/plans/colourised-doc-samples.md` | Sample classes follow `--cuppa-*` tokens |

## Refusal rules

| Request | Response |
|---------|----------|
| Network fetch of UI bundle on every CI run without pin | Refuse; pin or commit artifact |
| Break Lunr/Mermaid for aesthetics | Refuse |
| Copy Boost bundle or Material CSS wholesale | Refuse |
| Replace `css/site.css` or `ui.yml` without copying bundle contents | Refuse |
| Dark-mode toggle / search modal / webfonts in v1 | Refuse; palettes already follow `prefers-color-scheme` |

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
