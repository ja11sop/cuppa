# Plan: Selection / filter examples for remove and wipe docs

- **Status:** done
- **Related:** [`dependencies-docs-four-hubs.md`](dependencies-docs-four-hubs.md); [`list-deps-requires-closure.md`](list-deps-requires-closure.md); ROADMAP Documentation tooling; [`removal-options.md`](removal-options.md) § tokens
- **Updated:** 2026-09-26
- **Impact:** none — documentation and supplemental CSS only

## Problem

The remove / purge / wipe glance table repeated the flag name, used internal “storage
bucket” wording, and did not show what a token selects against a concrete inventory.
Complex filters (untyped wildcards vs typed selectors, `@` stems) need Matches lists;
every example still needs a scannable table row.

## Settled approach

| Piece | Decision |
|-------|----------|
| Glance table | Keep **all** intents; columns Intent \| Example only; Intent xrefs to worked sections when present |
| Worked subset | Typed selector, untyped wildcard, typed wildcard, multi-token, location stem, unqualified `@`, mixed leaves |
| Command chrome | Colourised `pre.cuppa-output.cuppa-cli-example` only — flag = info, token = notice |
| Matches | Ordinary prose + monospace / `cuppa-cli-token` bullets — **not** inside the command block |
| Inventory | Synthetic list-dependencies HTML sample shared by worked Matches |
| Types table | Dependency type → selector aliases from `SELECTOR_ALIASES` (+ untyped + reserved) |

## Progress snapshot

| Slice | Status |
|-------|--------|
| Types and selectors table | Done |
| Synthetic inventory + CLI partials + CSS | Done |
| Glance table + worked sections | Done |
| Follow-ons (below) | Open |

## Follow-ons (not blocking)

| ID | Work | Notes |
|----|------|-------|
| `cli-example-generator` | Optional helper to emit `partials/cli-examples/*.html` from a small recipe table | Avoid hand-editing spans; only if more pages adopt the pattern |
| `cli-token-palette` | Add `--cuppa-console-token` if notice/amber collides with warnings in dark preview | Defer until visual review asks |
| `selection-inventory-regen` | If list-dependencies sample chrome changes, restyle `selection-example-inventory.html` to match | Manual HTML today |
| `more-worked-matches` | Add Matches for purge/wipe selection-scoped rows if readers still confuse them with force-wipe | Optional |
| `dry-run-collapsible` | One collapsible wipe-report shape under the wildcard worked example | Skipped in first pass |

## Files

- `docs/modules/ROOT/pages/dependencies/managing/removing.adoc`
- `docs/modules/ROOT/partials/cli-examples/*.html`
- `docs/modules/ROOT/partials/samples/selection-example-inventory.html`
- `docs/supplemental-ui/css/cuppa-output.css`
