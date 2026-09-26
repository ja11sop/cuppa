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
| Glance | Every intent: colourised command + **Matches** against the synthetic inventory |
| Worked subset | Explain **why** (typed vs untyped, wildcards, `@`, mixed) — not a second glance |
| Command chrome | `pre.cuppa-output.cuppa-cli-example` in `.cuppa-cli-block` — flag = info, token = notice; Antora-style copy toolbox |
| Matches | Ordinary prose + monospace / `cuppa-cli-token` bullets — **not** inside the command block |
| Selectors in docs | Prefer **medium** names: `[source]`, `[gitlab]`, `[repository]`, `[conan]`, `[toolchain]`; mention short aliases once |
| Inventory | Synthetic list-dependencies HTML sample; SIZE column aligned with real samples |
| Types table | Dependency type → selector aliases from `SELECTOR_ALIASES` (+ untyped + reserved) |

## Progress snapshot

| Slice | Status |
|-------|--------|
| Types and selectors table | Done |
| Synthetic inventory + CLI partials + CSS | Done |
| Glance + Matches + worked “why” | Done (cleanup) |
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

- `docs/modules/ROOT/pages/dependencies/managing/removing.adoc`
- `docs/modules/ROOT/partials/cli-examples/*.html`
- `docs/modules/ROOT/partials/samples/selection-example-inventory.html`
- `docs/supplemental-ui/css/cuppa-output.css`, `cuppa.css`
- `docs/supplemental-ui/js/cuppa-cli-copy.js`
