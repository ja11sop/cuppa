# Plan: Selection / filter examples for remove and wipe docs

- **Status:** done
- **Related:** [`dependencies-docs-four-hubs.md`](dependencies-docs-four-hubs.md); [`list-deps-requires-closure.md`](list-deps-requires-closure.md); ROADMAP Documentation tooling; [`removal-options.md`](removal-options.md) § tokens
- **Updated:** 2026-09-26
- **Impact:** none — documentation and supplemental CSS/JS only

## Problem

The remove / wipe glance table repeated the flag name, used internal “storage
bucket” wording, and did not show what a token selects against a concrete inventory.
Complex filters (untyped wildcards vs typed selectors, `@` stems) need Matches lists;
every example still needs a scannable intent + command + confirmation.

## Settled approach

| Piece | Decision |
|-------|----------|
| Glance | **Table** Intent \| Example; Example = colourised command + Matches against shared inventory |
| Worked examples | Descriptive `===` headings under Worked examples (linked from glance; no global Example N); section intro embeds the shared inventory |
| Alternate inventory | When the shared inventory cannot succeed (e.g. source `boost` unused), the example shows its own inventory first |
| Naming | Qualify **used** / **unused** / **project-used**; **active context** = toolchain/variant/location-match flags (not token **selectors**) |
| Two reclaim paths | remove→purge→wipe = context-scoped ladder; force-wipe = everyday list-tree reclaim outside a matching project build |
| Wipe samples | Synthetic dry-run HTML for wipe GitLab, wipe source Boost, and force-wipe wildcard / multi / stem / `@` / mixed |
| Command chrome | `pre.cuppa-output.cuppa-cli-example` in `.cuppa-cli-block` — flag = info, token = notice; copy toolbox; wrap on whitespace + `<wbr>` after `=`/`,` |
| Selectors in docs | Prefer **medium** names: `[source]`, `[gitlab]`, `[repository]`, `[conan]`, `[toolchain]` |

## Progress snapshot

| Slice | Status |
|-------|--------|
| Types and selectors table | Done |
| Synthetic inventory + CLI partials + CSS | Done |
| Glance + Matches + worked “why” | Done |
| Descriptive worked examples + alt inventories + wipe samples | Done |
| Context vs list-tree reclaim framing; inventory in Worked examples intros | Done |
| Copy toolbox on CLI blocks | Done |
| Follow-ons (below) | Open |

## Follow-ons (not blocking)

| ID | Work | Notes |
|----|------|-------|
| `cli-example-generator` | Optional helper to emit `partials/cli-examples/*.html` from a small recipe table | Avoid hand-editing spans |
| `cli-token-palette` | Add `--cuppa-console-token` if notice/amber collides with warnings in dark preview | Defer until visual review asks |
| `selection-inventory-regen` | If list-dependencies sample chrome changes, restyle inventory HTML to match | Manual HTML today |
| `more-worked-matches` | Extra “why” for purge/wipe selection-scoped rows | Optional |
| `dry-run-collapsible` | One collapsible wipe-report shape under a wildcard example | Skipped |
| `h4-heading-theme` | Keep watching h4 accent-bar treatment across palettes | Landed initial fix in `cuppa.css` |

## Files

- `docs/modules/ROOT/pages/dependencies/managing/reclaiming.adoc` (hub: tokens, flag family, glance)
- `docs/modules/ROOT/pages/dependencies/managing/removing.adoc`
- `docs/modules/ROOT/pages/dependencies/managing/purging.adoc`
- `docs/modules/ROOT/pages/dependencies/managing/wiping.adoc`
- `docs/modules/ROOT/pages/dependencies/managing/force-wiping.adoc`
- `docs/modules/ROOT/partials/cli-examples/*.html`
- `docs/modules/ROOT/partials/samples/selection-example-inventory.html`
- `docs/supplemental-ui/css/cuppa-output.css`, `cuppa.css`
- `docs/supplemental-ui/js/cuppa-cli-copy.js`
