# Plan: Normalise StopError / options-error reporting

- **Status:** in progress
- **Related:** [`ROADMAP.md`](../../ROADMAP.md) — `console-stop-error-reporting`; [`archive/console-report-patterns.md`](../archive/console-report-patterns.md); Antora [`contributing/report-patterns.adoc`](../../docs/modules/ROOT/pages/contributing/report-patterns.adoc); cascade Options Error in [`package_cascade.py`](../../cuppa/package_managers/package_cascade.py) (`_raise_options_error`)
- **Updated:** 2026-09-23
- **Impact:** `patch` (presentation); possibly `minor` if a shared helper becomes public API operators rely on

## Problem

Cuppa already has a strong **judgement-tree** vocabulary for storage / develop /
wipe reports ([`console-report-patterns`](../archive/console-report-patterns.md)).
**Surprising refusals** — invalid flag combinations, configure-time StopErrors —
usually dump a long sentence into `SCons.Errors.StopError`, which then appears
only inside:

```text
cuppa: __init__: [critical] Cuppa terminated by exception [StopError: …]
```

That line is hard to scan: no tree, no highlighted flags, and the critical
logger label wraps a wall of prose. Cascade soak with
`--build-and-publish-dependencies --publish-package -n` made this obvious.

## Intent

Settle one pattern for **operator-facing option / precondition refusals**:

1. Print a short **Options Error** (or similar) report on stdout — unprefixed so
   tree glyphs survive — before raising.
2. Raise a **short** `StopError` so the critical line stays a one-line summary.
3. Colour the title chip like logger CRITICAL (`as_error_label(as_emphasised(…))`);
   highlight bare `--flags` and `[bracketed]` values in error colour; leave
   surrounding prose plain.

Cascade’s `_raise_options_error` is the first instance. This plan is to
**normalise** that approach (shared helper, when to use it, what stays a plain
StopError).

## Settled for the first instance (cascade `-n`)

| Piece | Choice |
|-------|--------|
| Title chip | `Options Error` |
| Tree | Headline + sibling branches (why / remedy); subdued stems |
| StopError text | `Invalid option combination (--build-and-publish-dependencies and -n/--no-exec)` |
| Where printed | `write_lines` → stdout (same as cascade plan trees), with a blank line after the tree |
| Why vs remedy colour | Why branch: error colour on flags / `[.sconf_temp]`. Remedy branch: **emphasised info** on the next-step flags so the positive action stands out |

## Open questions (do not implement until settled)

1. **Shared home** — Promote `_raise_options_error` to something like
   `cuppa.utility.console_errors` / `storage_actions`, or keep cascade-local until
   a second caller appears?
2. **Title vocabulary** — Always `Options Error`, or also `Configure Error` /
   `Cascade Error` by phase?
3. **Which StopErrors graduate** — Only “surprising” operator mistakes (bad flag
   combos), or every early refuse in construct / package managers?
4. **Relationship to judgement trees** — Reuse `_judgement_tree_lines` (severity
   groups) vs keep a flatter why/remedy tree for option refusals?
5. **stderr vs stdout** — Reports today prefer stdout; critical log stays on the
   logging stream. Confirm for errors that fire before construct finishes.
6. **Docs** — Extend Antora Report patterns, or a short “stopping errors” subsection?

## Non-goals (for now)

- A new colour meaning named `critical` (CRITICAL already uses emphasised error label)
- Converting every existing one-line StopError into an Options Error tree in one sweep

## Settled (critical-line colouring)

| Piece | Choice |
|-------|--------|
| `StopError` / `UserError` in `log_exception` | Exception **name** in error colour; message via `highlight_values(…, as_error)` so `[values]` and bare `--flags` are error-coloured and prose stays plain |
| Other exceptions | Unchanged: whole name + message info-coloured |
| SCons re-raise line | Same highlight applied to `StopError` / `UserError` args after mask, so `scons: *** …` matches the critical line |
| Options Error trees | Still preferred for surprising flag refusals; critical-line highlighting does not replace them |

## Next focus

When a second surprising refusal wants the Options Error tree shape, extract the helper and
answer open questions 1–4 in the same change. Until then, cascade’s `-n` instance is
the reference.
