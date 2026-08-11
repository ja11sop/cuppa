# Plan: custom Antora UI bundle

- **Status:** proposal
- **Related:** [`ROADMAP.md`](../../ROADMAP.md) — Documentation tooling (`doc-antora-ui`); [`docs/playbook.yml`](../../docs/playbook.yml); supplemental UI [`docs/supplemental-ui/`](../../docs/supplemental-ui/); companion [`colourised-doc-samples.md`](colourised-doc-samples.md)
- **Updated:** 2026-08-11
- **Impact:** none — site presentation only (unless bundled CSS changes break CI doc build)

## Why

The published site uses Antora's **default UI bundle** from GitLab CI artifacts
(`playbook.yml` → `antora-ui-default`). It is functional but generic — navigation, typography, and
admonitions read as stock Antora.

A custom bundle (inspired by quality of Boost's docs or MkDocs Material **look**, not necessarily
their stack) would:

- Improve first impression for new users.
- Give semantic report samples ([`colourised-doc-samples.md`](colourised-doc-samples.md)) a
  coherent light-theme palette.
- Host cuppa branding in header/footer (partially started in `supplemental-ui/`).

Reference only (not drop-in): Boost UI bundle zip linked from the scratchpad — structural
differences break if copied verbatim.

## Goals

1. **Vendor a ui-bundle** under cuppa control (committed zip or build script — prefer reproducible
   build from a forked UI repo).
2. Update **`docs/playbook.yml`** to point at the local bundle; pin version in changelog when
   upgraded.
3. Preserve **Lunr search** and **Mermaid** extensions (verify after bundle swap).
4. Extend **`docs/supplemental-ui/`** for cuppa-specific CSS (report sample classes, code block
   tweaks) rather than forking entire Antora UI when possible.
5. Document local preview: `cd docs && npm ci && npm run build` unchanged for contributors.

## Non-goals

- Rewriting Antora content architecture.
- Dark mode in v1 (optional later).
- Kroki / PlantUML at site build time (scratchpad **broader diagram support** stays separate).
- Custom Mermaid theme in this plan ([`modern_mermaid`](https://github.com/gotoailab/modern_mermaid)
  is a follow-on row).

## Approach options

| Option | Pros | Cons |
|--------|------|------|
| **A. Supplemental-only** | Smallest diff; keep default bundle | Limited layout changes |
| **B. Fork `antora-ui-default`** | Full control; upstream merges possible | Maintenance |
| **C. Extract Boost-like CSS into supplemental** | Visual polish without full fork | May fight default layout |
| **D. Third-party UI (e.g. Material-inspired port)** | Best aesthetics | License + upgrade path |

**Recommendation:** start with **A + C** (supplemental CSS + header/footer already present); spike
**B** if navigation/table styling still insufficient after one iteration.

## Work slices

| Slice | Deliverable | Notes |
|-------|-------------|-------|
| A | Visual audit | Screenshots of hub, long page, admonition, table, search |
| B | Supplemental CSS pass | Typography, nav active state, `:page-pagination` |
| C | Bundle pin decision | Document in `docs/README` or contributing |
| D | CI `npm run build` green | GitHub Pages deploy unchanged |
| E | Optional Mermaid CSS vars | Coordinate with future mermaid-theme plan |

## Files

| Path | Role |
|------|------|
| `docs/playbook.yml` | `ui.bundle.url` / `snapshot` |
| `docs/supplemental-ui/css/site.css` | Add if missing; cuppa overrides |
| `docs/supplemental-ui/partials/*.hbs` | Header/footer (existing) |
| `design/plans/colourised-doc-samples.md` | Sample `.cuppa-*` classes must match site CSS |

## Refusal rules

| Request | Response |
|---------|----------|
| Network fetch of UI bundle on every CI run without pin | Refuse; pin or commit artifact |
| Break Lunr/Mermaid for aesthetics | Refuse |
| Copy Boost bundle wholesale | Refuse without license/structure review |

## 1.8.0 candidacy

| Factor | Assessment |
|--------|------------|
| User value | Medium — polish, not capability |
| Risk | Low–medium (CI doc build, Pages deploy) |
| Size | Small–medium depending on fork depth |
| Release impact | `none` |

**Suggested:** **1.8.0** optional — good **docs-only** landing early in the cycle. Pairs well with
[`methods-pages-split.md`](methods-pages-split.md) slice A (nav restructure).

## Related scratchpad items (not this plan)

- **Better Mermaid styling** — separate short plan or row under Documentation tooling when theme
  files land.
- **Structure pages folder under docs** — aligns with methods split; do together when moving pages
  into subfolders.
