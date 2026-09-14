# Plan: Optional job count on `--parallel`

- **Status:** proposal
- **Related:** [`ROADMAP.md`](../../ROADMAP.md) — CLI / build; [`cuppa/__main__.py`](../../cuppa/__main__.py) `restrict_cpus`; [`cuppa/construct.py`](../../cuppa/construct.py) parallel/`num_jobs`; [`cuppa/utility/parallelism.py`](../../cuppa/utility/parallelism.py); Antora [`cli/building.adoc`](../../docs/modules/ROOT/pages/cli/building.adoc)
- **Updated:** 2026-09-14
- **Impact:** `minor` (CLI shape change for an existing flag)

## Problem

Today:

| Flag | Affinity (wrapper) | Job count |
|------|--------------------|-----------|
| `--parallel` | Yes (`restrict_cpus`, leave cores for OS) | Auto = `effective_cpu_count()` after affinity |
| `--jobs=N` / `-j N` | **No** | Exactly `N` |
| `--parallel --jobs=N` | Yes | Exactly `N` (works; awkward to discover) |

Soak publishers often want **affinity + a lower job count** (e.g. 12 on a 16-core host
that would auto to 14). Documenting `--parallel --jobs=12` works, but:

- `--jobs` is an SCons flag; `--j` is ambiguous (`--jobs` vs `--just-print`)
- Operators reasonably expect Cuppa’s `--parallel` to accept a count

## Intent

Make “run parallel with affinity, but at most N jobs” a first-class Cuppa spelling,
without breaking bare `--parallel` or plain `--jobs=N`.

## Naming / shape options

| Option | Example | Pros | Cons |
|--------|---------|------|------|
| **A. Optional value on `--parallel`** | `--parallel` / `--parallel=12` | One flag; matches mental model | SCons `AddOption` + optional nargs needs care; help text clarity |
| **B. Document combo only** | `--parallel --jobs=12` | Zero code | Discoverability; two-flag story forever |
| **C. Cuppa `--parallel-jobs=N`** | `--parallel-jobs=12` | Clear; implies affinity + count | Third parallel-related flag; easy to forget bare `--parallel` |
| **D. `--parallel` requires count** | always `--parallel=N` | Unambiguous | Breaks every existing `--parallel` invocation (**refuse**) |

**Provisional preference:** **A** — `--parallel` remains a boolean *presence* for
affinity; an optional integer sets `num_jobs` (and thus `CMakeBuild --parallel N`).
Bare `--parallel` keeps today’s auto count.

Spellings to support if A:

- `--parallel=12` (preferred in docs)
- Possibly `--parallel 12` if SCons option parsing allows without eating the next argv token wrongly

Refuse shipping `--parallel 12` if it steals a target name; prefer `=` form only.

## Semantics (sketch for A)

```text
--parallel          → affinity + job_count = effective_cpu_count()
--parallel=N        → affinity + job_count = N  (N >= 1)
--jobs=N            → no Cuppa affinity; job_count = N  (unchanged)
--parallel --jobs=M → affinity + job_count = M  (unchanged; M wins over auto)
--parallel=N --jobs=M → settle: last-wins or error; prefer **error** if both set
```

Cap policy (open): if `N > effective_cpu_count()` after affinity, either clamp with a
notice or honour N (SCons can oversubscribe). Provisional: **honour N**, warn once if
`N > affinity size`.

## Implementation touchpoints

1. `cuppa/core/base_options.py` — change `--parallel` from `store_true` to optional int
   (or add a parallel dest that accepts both; keep `env['parallel']` truthy when set).
2. `cuppa/__main__.py` — treat any argv token matching `--parallel` / `--parallel=*` as
   affinity trigger (today: exact `'--parallel' in args_list`).
3. `cuppa/construct.py` — if parallel count provided, `SetOption('num_jobs', N)`; else
   existing auto path when `num_jobs==1 and parallel`.
4. Antora `cli/building.adoc` + AGENTS preferred flags; unit tests for parsing.

## Work slices

| ID | Deliverable |
|----|-------------|
| `par-count-plan` | This document + design README / ROADMAP pointer |
| `par-count-settle` | Lock A vs C; `=` vs space; conflict with `--jobs` |
| `par-count-impl` | Options + wrapper + construct + tests + docs |

## Out of scope

- Changing the leave-N-cores-for-OS affinity table itself
- Making `--jobs` apply Cuppa affinity (keep SCons-native meaning)
- Coverage `--parallel` collection policy ([`coverage-parallel.md`](coverage-parallel.md))
