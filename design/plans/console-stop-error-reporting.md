# Plan: Normalise StopError / options-error reporting

- **Status:** in progress
- **Related:** [`ROADMAP.md`](../../ROADMAP.md) — `console-stop-error-reporting`; [`archive/console-report-patterns.md`](../archive/console-report-patterns.md); Antora [`contributing/report-patterns.adoc`](../../docs/modules/ROOT/pages/contributing/report-patterns.adoc); cascade Options Error in [`package_cascade.py`](../../cuppa/package_managers/package_cascade.py) (`_raise_options_error`); soak follow-ons [`cascade-consume-ux-soak.md`](../archive/cascade-consume-ux-soak.md) (early option-compat, `--cascade` + `-n` did-you-mean); shared helper [`console_errors.py`](../../cuppa/utility/console_errors.py)
- **Updated:** 2026-11-09
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

Cascade’s `_raise_options_error` was the first instance. Shared home is now
`cuppa.utility.console_errors.raise_options_error`.

## Settled for the first instance (cascade `-n`)

| Piece | Choice |
|-------|--------|
| Title chip | `Options Error` |
| Tree | Headline + sibling branches (why / remedy); subdued stems |
| StopError text | `Invalid option combination (--build-and-publish-dependencies and -n/--no-exec)` |
| Where printed | `write_report_lines` → stdout (same as cascade plan trees), with a blank line after the tree |
| Why vs remedy colour | Why branch: error colour on flags / `[.sconf_temp]`. Remedy branch: **emphasised info** on the next-step flags so the positive action stands out |

## Settled (open questions from 2026-10-10)

| # | Topic | Choice |
|---|-------|--------|
| 1 | Shared home | `cuppa.utility.console_errors.raise_options_error` (+ `remedy_colour`). Cascade keeps a thin `_raise_options_error` alias |
| 2 | Title vocabulary | Always `Options Error` for operator flag mistakes. No `Configure Error` / `Cascade Error` until a second vocabulary is clearly needed |
| 3 | Which StopErrors graduate | **Surprising operator mistakes** only — incompatible flag pairs / missing required companion flags. Not every early refuse (missing toolchains, corrupt manifests, network 404, …) |
| 4 | Relationship to judgement trees | Keep a flatter why/remedy tree for option refusals. Do **not** force `_judgement_tree_lines` severity groups onto flag combos |
| 5 | stderr vs stdout | stdout via `write_report_lines` (unprefixed); critical log stays on the logging stream |
| 6 | Docs | Extend Antora Report patterns with a short “Options Error / stopping refusals” subsection |

## Settled (critical-line colouring)

| Piece | Choice |
|-------|--------|
| `StopError` / `UserError` in `log_exception` | Exception **name** in error colour; message via `highlight_values(…, as_error)` so `[values]` and bare `--flags` are error-coloured and prose stays plain |
| Other exceptions | Unchanged: whole name + message info-coloured |
| SCons re-raise line | Same highlight applied to `StopError` / `UserError` args after mask, so `scons: *** …` matches the critical line |
| Options Error trees | Still preferred for surprising flag refusals; critical-line highlighting does not replace them |

## Work slices

| ID | Deliverable | Target |
|----|-------------|--------|
| `stop-err-critical-colour` | StopError / UserError critical-line `highlight_values` | **Done** (earlier; 1.13.x / unreleased hygiene) |
| `stop-err-cascade-n` | Cascade `-n` Options Error tree (first instance) | **Done** |
| `stop-err-helper` | Extract `raise_options_error` to `console_errors.py`; settle Q1–6 | **Done** (this PR) |
| `stop-err-second-callers` | Graduate clear second callers: `--stage-package`+`--publish-package`; `--parallel=N`+`--jobs`/`-j` | **Done** (this PR) |
| `stop-err-docs` | Antora Report patterns subsection | **Done** (this PR) |
| `stop-err-check-options` | Optional method `check_options(env)` discovered like `add_options`; construct calls before SConscript; PublishPackage owns stage+publish | **Done** |
| `stop-err-cascade-early` | Extract `check_cascade_options`; PublishPackage `check_options` refuses cascade flag matrix (+ nest `-n`, update+offline) before SConscript; `maybe_run_cascade` keeps belt | **Done** |
| `stop-err-check-options-order` | Construct runs `check_options` before cascade mode banners; banners require `--cascade` so companions alone do not claim a mode | **Done** |
| `stop-err-cascade-combos` | Cascade flag matrix plain StopErrors → Options Error trees via `check_cascade_options` | **This follow-up** |
| `opt-compat-early` | More modules implement `check_options` (and core/base for parallel); optional later registry | Later — soak leftover; builds on `check_options` |

### Early refuse without construct hard-coding flags

Soak showed `--stage-package` + `--publish-package` refused only inside
`PublishPackageMethod`, after location update. Prefer:

1. The method that **introduced** the flags implements optional
   `check_options(cls, env)` (read-only `get_option`; call
   `raise_options_error` on conflict).
2. `cuppa.modules.registration.check_options("methods", env)` discovers it
   (same walk as `add_options` / `get_options`).
3. Construct calls that **after** configure/output settle and **before**
   `build()` / SConscript — no knowledge of package flag names.
4. Method `__call__` still invokes `check_options` as a belt for unit tests.

Do **not** move flag registration or nest argv forwarding. Cascade companions
registered on the same method refuse via `package_cascade.check_cascade_options`
from that hook (Options Error trees + short `StopError`). Parallel+jobs may
later grow a core `check_options`; until then it may stay as a construct-local
refuse.

## Non-goals (for now)

- A new colour meaning named `critical` (CRITICAL already uses emphasised error label)
- Converting every existing one-line StopError into an Options Error tree in one sweep
- Full declarative incompat matrix in construct (use `check_options` instead)

## Next focus

Optionally graduate location/output plain StopErrors to Options Error trees.
Optionally move parallel+jobs into a core `check_options`. Grow more module
owners only when new flag pairs appear.
