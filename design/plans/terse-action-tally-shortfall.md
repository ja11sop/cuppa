# Note: terse action tally can finish short of N/N

- **Status:** in progress
- **Related:** [`ROADMAP.md`](../../ROADMAP.md) — `console-terse-action-tally`; [`archive/terse-build-output.md`](../archive/terse-build-output.md) (ledger / up-to-date credit); `_ProgressLedger` in `cuppa/progress.py`; [#403](https://github.com/ja11sop/cuppa/pull/403) soak
- **Updated:** 2026-11-13
- **Impact:** `patch` — candidate polish for 1.14.0

## Observed (tip soak)

On a tip soak with `--terse-output -Q --test --parallel` (and again after clean full rebuild), sticky/durable shear was clean, but closing checkpoints finished a few actions short of the planned total:

```text
… · 2242/2245 actions
… test/reference_data … · 308/311 actions
terse-tally-dump: 0 uncredited executors
[completed] build succeeded · 2242 ran · …
```

Same shortfall size (**3**) at that leaf cell and at sconstruct end. Nested parallel `→ [ok]` interleaving is **out of scope** — that matches when separate actions finish under `--parallel`.

### Missing display numbers are not the shortfall

After `test-report`, CollateTestReportIndex runs nested `env.Execute(Copy)` lines:

```text
   5/  8 · … test-report · <final>/protocol.report.html
              → [ok]   … copy · …report.html → …
              → [ok]   … copy · …report-summary.json → …
   7/  8 · … copy · …report.json → …
```

The skipped `6/8` is **silent credit**: nested copies set `status_emitted`, so the parent Python action still `credit_and_prefix(+1)` without printing its own counted line. Those slots are in `done`. That pattern is **not** the `2242/2245` / `308/311` desync.

### Why the first dump said little

`CUPPA_TERSE_TALLY_DUMP` only walked live `_nodes` for `remaining > 0`. The soak shape was **every live entry fully credited** (`remaining_sum == 0`) while `_total` / cell `total` stayed inflated — so the dump correctly reported `0 uncredited` and could not name the phantoms. Integrity / orphan reporting is required.

## Root cause

`register_terse_actions` keys executors by `id(executor)` (or `id(node)` fallback). When the same File node is re-notified under a **new** executor (builder replace — e.g. a sconscript listing the same `BuildTest` name twice), tip behaviour was:

1. Write a **new** ledger entry and `total += slots` again.
2. Remap `_nodes[id(node)]` to the new entry.
3. Leave the old entry only in `_executors` (orphaned from `_nodes`).

Credits hit the live entry → `remaining == 0` on everything dump could see. `_total` still included the orphaned slots → close as `N-k/N` with matching cell Δ.

`keep_reachable` used to return early when the reachability walk found nothing **without** `_rebuild_totals()`, which preserved that inflation even when orphans could have been dropped by recomputing from `_nodes`.

Arithmetic check for the leaf: unique test names × (compile + link + test + three log/report copies) plus report collate work ≈ **308** real actions; **+3** matches one remapped three-slot test (object / program / test) left as phantoms.

## Fix (this PR)

1. **Reuse** the existing `_nodes` entry when the same node is registered under a new executor id (remap `_executors`, do not `total +=` again unless slots grow).
2. **`keep_reachable`** always prune `_executors` to live entries and `_rebuild_totals()` (including when the walk finds nothing / leaves the full set).
3. **Reconcile** before terse end / finished checkpoints so late remaps cannot print `N-k/N`.
4. **Dump** prints integrity (`done`/`total`/`remaining_sum`/`orphans`/`cell_shortfalls`) before the uncredited list.

Out of scope: nested `→ [ok]` order under `-j`; `[completed]` clause wording; shear / WRAP_OFF (fixed on [#403](https://github.com/ja11sop/cuppa/pull/403)); consumer sconscript duplicate names (call-site hygiene — cuppa must still tally correctly).

## Reproduce / verify

Serial vs `--parallel`; cold vs mostly up-to-date; with/without `--test`. With `CUPPA_TERSE_TALLY_DUMP=1`, expect integrity `done == total`, `orphans=0`, `0 uncredited`, and end lines `N/N`.
