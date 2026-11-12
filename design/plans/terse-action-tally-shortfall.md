# Note: terse action tally can finish short of N/N

- **Status:** proposal
- **Related:** [`ROADMAP.md`](../../ROADMAP.md) — `console-terse-action-tally`; [`archive/terse-build-output.md`](../archive/terse-build-output.md) (ledger / up-to-date credit); [#403](https://github.com/ja11sop/cuppa/pull/403) soak
- **Updated:** 2026-11-12
- **Impact:** `patch` (when fixed) — reminder only for now; not blocking 1.14.0

## Observed

On a tip soak with `--terse-output -Q --test --parallel`, sticky/durable shear was clean, but the closing checkpoints finished a few actions short of the planned total, for example:

```text
… · 2242/2245 actions
… reference_data … · 308/311 actions
```

Same shortfall size (3) at both the leaf variant and the sconstruct end. Nested parallel `→ [ok]` interleaving is **out of scope** here — that matches when separate actions finish under `--parallel`.

## Later

1. Reproduce on a smaller tree; compare serial vs `--parallel` and cold vs up-to-date.
2. Check whether the missing credits are nested `Execute`, nodes never visited, or a race in up-to-date / finish accounting (`NotifyProgress` / terse ledger).
3. Decide whether the fix is credit timing, registration, or accepted non-N/N with a clearer end line.

No code change until that look happens.
