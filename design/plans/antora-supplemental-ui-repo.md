# Note: extract Antora supplemental UI into a shareable repo

- **Status:** proposal
- **Related:** ROADMAP `doc-antora-supplemental-ui-repo`;
  [`antora-ui-bundle.md`](antora-ui-bundle.md) (keep default bundle; polish via supplemental);
  [`archive/colourised-doc-samples.md`](../archive/colourised-doc-samples.md);
  [`shiki-syntax-highlighting.md`](shiki-syntax-highlighting.md);
  [`docs/supplemental-ui/`](../../docs/supplemental-ui/);
  [`docs/playbook.yml`](../../docs/playbook.yml)
- **Updated:** 2026-11-14
- **Impact:** `none` for Cuppa product/CLI; docs CI / playbook wiring only. Other repos
  consume the shared overlay as their own docs dependency.

## Why

Cuppa’s published docs keep Antora’s **default UI bundle** and layer polish through
`docs/supplemental-ui/` (settled in [`antora-ui-bundle.md`](antora-ui-bundle.md)):

| Area | Examples in-tree today |
|------|-------------------------|
| Palettes | `css/cuppa-palette-*.css` (cup-of-tea, harbour, forest, aubergine) + toolbar cycle |
| Layout / UX “candy” | article width steps, grab-pan / edge fades, scroll panels, search recess tokens |
| Console samples | `cuppa-output.css`, CLI copy helper |
| Chrome partials | header/footer, head-styles overlay, edit-page → width/palette controls |
| Branding | Cuppa mark / wordmark, Cuppa-specific header copy |

That candy and UX are useful **beyond Cuppa**. Sister projects should reuse the machinery
(palette switcher, width control, scroll panels, output sample CSS patterns, head-styles
overlay rule) while supplying **their own** brand marks, header/footer, and theme tokens —
without reinventing the supplemental stack or forking `antora-ui-default`.

## Goals

1. **Shared supplemental overlay repo** — versioned, documented, consumable from any Antora
   playbook via `ui.supplemental_files` (git URL, release archive, or npm/git subtree — settle
   in implementation).
2. **Clear split** between **reusable UX** and **per-site theme/brand**.
3. **Cuppa keeps first-class themes** — cup-of-tea (and siblings) remain available; Cuppa’s
   playbook points at the shared overlay + a thin Cuppa brand/theme layer (in-repo or a
   `themes/cuppa` package path in the shared repo).
4. **Preserve Antora constraints** already settled: do not replace `site.css`; no partial
   `ui.yml` unless the full descriptor is copied; pin default bundle URL when `ui-pin` lands.
5. **Migration path** for this repo — playbook change, CI green, no visual regression on
   key pages (nav, tables, admonitions, console samples, palette cycle).

## Non-goals

- Forking or replacing `antora-ui-default` (still deferred per `antora-ui-bundle.md` unless
  supplemental truly cannot reach a chrome need).
- Shipping Cuppa CLI behaviour or PyPI artifacts from the UI repo.
- Forcing every consumer onto Cuppa palettes.
- Rewriting Antora content architecture or Mermaid/Lunr choices (consumers keep their own
  playbook extensions).

## Proposed package split

| Layer | Lives in shared repo? | Contents (draft) |
|-------|----------------------|------------------|
| **Core overlay** | Yes | `head-styles.hbs` pattern (keep `site.css`, link palette + component sheets); palette switcher + width JS; scroll-panels; shared component CSS that is brand-agnostic (`cuppa.css` renamed to something neutral, e.g. `site-overlay.css`); output/sample CSS patterns without Cuppa naming where practical |
| **Theme packs** | Yes (optional packs) | Token files (`*-palette-*.css`) — Cuppa’s four palettes as the first pack; other projects add `acme-palette-*.css` |
| **Brand partials** | **Consumer repo** (or optional pack) | `header-content.hbs`, `footer-content.hbs`, marks/wordmarks, site title strings |
| **Playbook** | Consumer | `ui.bundle.url`, `supplemental_files` → shared core (+ theme) + local brand dir |

**Naming:** avoid hard-coding `cuppa` in shared core file names once extracted (`cuppa-doc-palette.js`
→ `doc-palette.js`, etc.). Keep a compatibility note for one release if Cuppa still references
old paths via thin wrappers.

## Consumption sketch

```yaml
# consumer playbook.yml (illustrative)
ui:
  bundle:
    url: https://gitlab.com/antora/antora-ui-default/-/jobs/artifacts/…/ui-bundle.zip?job=bundle-stable
    snapshot: true
  supplemental_files:
  - ./node_modules/@org/antora-supplemental-ui/overlay   # shared candy
  - ./node_modules/@org/antora-supplemental-ui/themes/cuppa  # or ./docs/brand
  - ./docs/brand   # header/footer/marks only
```

Exact install mechanism (npm package vs git submodule vs release zip) is an open decision —
prefer whatever docs CI already understands and pins reproducibly.

## Relationship to `antora-ui-bundle.md`

| Concern | Owner plan |
|---------|------------|
| Keep default bundle; overlay rules; palette catalogue; Cuppa visual acceptance | [`antora-ui-bundle.md`](antora-ui-bundle.md) |
| Extract overlay to a **multi-repo product**; brand/theme split; consumer playbook recipe | **This plan** |
| Remaining `ui-pin` | Still on `antora-ui-bundle.md` / ROADMAP `doc-antora-ui` — do pinning before or with the extract so consumers inherit a pinned recipe |

When this ships, update `antora-ui-bundle.md` paths to the shared repo (or mark the in-tree
`docs/supplemental-ui/` as a vendored pin / submodule checkout).

## Risks

| Risk | Mitigation |
|------|------------|
| Dual maintenance during move | Single source of truth ASAP; Cuppa CI builds from the shared pin |
| Breaking Cuppa Pages on extract | Visual checklist + docs workflow before deleting in-tree copies |
| Consumers override wrong layer | README: brand vs theme vs core; example playbooks |
| Antora supplemental merge order | Document file precedence; avoid duplicate partial names across layers |
| License / attribution for embedded Material SVG masks | Carry NOTICE into the shared repo |

## Recommended slices

| Id | Work | Outcome |
|----|------|---------|
| `sui-inventory` | Classify every file under `docs/supplemental-ui/` as core / theme / brand | Settled table in this plan |
| `sui-repo-bootstrap` | Create repo, LICENSE (match Cuppa BSL or choose MIT for wider docs reuse — **product call**), README, example playbook | Empty consumer can build |
| `sui-move-core` | Move candy + rename neutral identifiers; Cuppa playbook consumes pin | Cuppa CI green |
| `sui-theme-cuppa` | Cuppa palettes as a theme pack | Toolbar cycle unchanged |
| `sui-brand-cuppa` | Header/footer/marks stay in cuppa or as `themes/cuppa/brand` | Pages look the same |
| `sui-docs` | Antora contributing note: how to depend on the overlay | Other projects can copy the recipe |
| `sui-second-consumer` | Optional: wire one sister docs site | Proves the split |

## Open questions

1. **License** for the shared UI repo — keep Boost Software License 1.0 vs MIT for easier
   adoption outside Boost-shaped projects?
2. **Distribution** — GitHub repo + release zip, npm under `@ja11sop/…`, or both?
3. **Repo name** — `antora-supplemental-ui`, `docs-supplemental-ui`, something org-neutral?
4. Should Cuppa palettes live in the shared repo (as the reference theme pack) or only in
   cuppa until a second consumer appears?
5. Submodule vs package pin in cuppa’s `docs/` — which is less painful for Pages CI?

## Progress

| Slice | Status |
|-------|--------|
| Problem / split / risks | **This plan** |
| File inventory (core vs theme vs brand) | Todo |
| Repo bootstrap + Cuppa playbook pin | Todo |
| Second consumer proof | Todo (optional) |
