# Note: terse action tally can finish short of N/N

- **Status:** in progress
- **Related:** [`ROADMAP.md`](../../ROADMAP.md) — `console-terse-action-tally`; [`archive/terse-build-output.md`](../archive/terse-build-output.md) (ledger / up-to-date credit); `_ProgressLedger` in `cuppa/progress.py`; [#403](https://github.com/ja11sop/cuppa/pull/403) soak
- **Updated:** 2026-11-12
- **Impact:** `patch` — candidate polish for 1.14.0 if a small fix lands; otherwise ship 1.14.0 without it

## Observed

On a tip soak with `--terse-output -Q --test --parallel`, sticky/durable shear was clean, but the closing checkpoints finished a few actions short of the planned total, for example:

```text
… · 2242/2245 actions
… <one sconscript/variant cell> … · 308/311 actions
```

Same shortfall size (**3**) at both that leaf cell and the sconstruct end. Nested parallel `→ [ok]` interleaving is **out of scope** here — that matches when separate actions finish under `--parallel`.

## What that shortfall means

`_ProgressLedger` registers **slots per executor** when `NotifyProgress.add` sees a target (`register_terse_actions`). Credits move only through:

| Path | Effect |
|------|--------|
| Spawn / Python status line | `credit_and_prefix(..., count=True)` → **+1** slot |
| `BuildTask.make_ready` when SCons state is up-to-date | `credit_all_remaining(node)` → **all** remaining on that executor |
| First terse begin checkpoint | `credit_currently_up_to_date()` lookahead once (same all-remaining when `is_up_to_date()`) |

End checkpoints **sample** `done`/`total`; they do not sweep remaining. `Finished` / `sconstruct_end` already `Depends`/`Requires` the notified targets, so a lasting `done < total` is not “end printed too early while work was still running” in the usual progress graph — it is **registered slots that never received a credit**.

The matching Δ at the leaf cell (308/311) and sconstruct (2242/2245) is the useful constraint: the three missing credits sit in that **one cell**. The global tally is not independently wrong; it is that cell’s residual.

So at close, three slots under that cell still had `remaining > 0`. Not a percent-rounding artefact, and not nested `Execute` / `test-case` lines (those are deliberately off the action total).

## Likely buckets (ordered for investigation)

1. **Multi-slot under-credit** — `_action_slots` / `_slots_in` walks the executor action list (including `ListAction` children) and counts every leaf. Each status line only credits **one** slot. If the list is wider than the spawn/Python exits that actually print (or one leaf never runs and never becomes `up_to_date` in `make_ready`), residual slots stick. Archive+index (=2) is covered by unit tests when both exits happen; three leftovers could be three such gaps or one executor with `slots >= 3`.

2. **Registered but never visited** — node counted at `NotifyProgress.add` and kept by `keep_reachable`, yet `BuildTask.make_ready` never sees it (and nothing spawns). Unusual if `Finished` truly `Depends` that target; still worth checking for side-effect / alias / replaced-node cases where the depended node is not the registered id.

3. **Credit miss on visit** — `make_ready` or spawn runs, but `_nodes.get(id(node))` misses (node identity churn) and `credit_and_prefix`’s `target` / `_current_action_nodes()` fallback also misses. Leaves `remaining` untouched while the build still “completed”.

4. **`--parallel` as amplifier, not root** — ledger updates are lock-guarded; a pure race that drops credits is unlikely. Parallel changes visit/finish interleaving and which nodes look current at lookahead time. Serial vs parallel soaks still matter to classify.

Out of scope for the bug hunt: nested `→ [ok]` order under `-j`; `[completed]` clauses (`ran` / `up to date` / `nested`); shear / WRAP_OFF (fixed on [#403](https://github.com/ja11sop/cuppa/pull/403)).

## Approach on this PR

1. **Sanitize / deepen the plan** (this doc) — public wording only.
2. **Instrument** — expose uncredited ledger entries and dump them at `sconstruct_end` under a narrow debug path (or once when `remaining > 0`) so a tip soak names the three slots.
3. **Classify and fix** if the dump points at a small contract bug (slots vs exits, visit miss).
4. **Else** leave the reminder, merge what is safe, and ship 1.14.0 without waiting on a deep dig.

## Reproduce matrix (tip)

Serial vs `--parallel`; cold vs mostly up-to-date; with/without `--test`. Confirm Δ stays in one cell. Prefer a smaller selection when possible so the dump is short.
