# Plan: Optional job count on `--parallel`

- **Status:** proposal
- **Related:** [#298](https://github.com/ja11sop/cuppa/issues/298); [#318](https://github.com/ja11sop/cuppa/issues/318) (CMake serial default); [`ROADMAP.md`](../../ROADMAP.md) — CLI / build; [`cuppa/__main__.py`](../../cuppa/__main__.py) `restrict_cpus`; [`cuppa/construct.py`](../../cuppa/construct.py) parallel/`num_jobs`; [`cuppa/utility/parallelism.py`](../../cuppa/utility/parallelism.py); Antora [`cli/building.adoc`](../../docs/modules/ROOT/pages/cli/building.adoc); publish+parallel race is separate — [`publish-package-parallel-side-effect.md`](publish-package-parallel-side-effect.md) ([#317](https://github.com/ja11sop/cuppa/issues/317)); CMake/Ninja default jobs below
- **Updated:** 2026-09-21
- **Impact:** `minor` for `--parallel=N` CLI; **`patch`** for the CMake helper default below (behaviour fix)

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

### Related: no `--parallel` still saturates Ninja builds

`CMakeConfigure` defaults to **Ninja** when `ninja` is on `PATH`. `cmake_build_jobs`
today returns `None` when Cuppa `--parallel` is off, so `cmake --build` omits
`--parallel N` and CMake runs bare `ninja` — which defaults to **all CPUs**.

So omitting Cuppa `--parallel` only serialises **SCons** (`-j1`). Nested publisher
CMake builds (abseil, protobuf, grpc, …) still peg every core. That surprised the
project D cascade soak when `--parallel` was dropped to work around [#317](https://github.com/ja11sop/cuppa/issues/317).

Publisher sconscripts do **not** pass `jobs=` or bake in `-j`; the leak is in the
Cuppa CMake helpers.

## Settled: CMake / Ninja job count tracks Cuppa `--parallel`

In [`cuppa/buildsys/cmake.py`](../../cuppa/buildsys/cmake.py) `cmake_build_jobs` /
`cmake_build_args`:

| `jobs=` / Cuppa flags | Behaviour |
|----------------------|-----------|
| default (`None`), no `--parallel` | **`1`** → `cmake --build --parallel 1` |
| default (`None`), `--parallel` | **`env['job_count']`** → `cmake --build --parallel 14` (same count SCons uses after `restrict_cpus`, e.g. 16−2) |
| `jobs=False` or `0` | omit `--parallel` (escape hatch: generator default — can hog) |
| positive `int` | that count |

**Never emit bare `cmake --build --parallel`.** CMake then lets Ninja pick a
default from logical `cpu_count()` (16 on a 16-core host) even when Cuppa
affinity only allows 14 — one job per physical core plus oversubscribe.

`env['job_count']` is already affinity-aware for bare `--parallel`
([`effective_cpu_count`](../../cuppa/utility/parallelism.py) after
`restrict_cpus` in the cuppa entry point). `--parallel --jobs=N` keeps `N` as
today. CMake must receive that same integer, not “enable parallel” without a
cap.

`CMakeBuild` keeps default `jobs=None`. `CMakeInstall` keeps default
`jobs=False` (install is rarely the core hog). Call sites that want full Ninja
default without Cuppa `--parallel` must pass `jobs=False` explicitly.

Frame as a **bug fix** (`patch`): Cuppa’s `--parallel` is the parallelism
control for SCons **and** nested Ninja; both use the restricted job count.

Unit tests assert `--parallel` is always followed by an integer token. Antora
CMake / building pages note the default.

Ship this **with** [#318](https://github.com/ja11sop/cuppa/issues/318) and
[#317](https://github.com/ja11sop/cuppa/issues/317) on the same patch PR;
`--parallel=N` CLI remains [#298](https://github.com/ja11sop/cuppa/issues/298).

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
| `par-cmake-serial-default` | `cmake_build_jobs` → `1` without Cuppa `--parallel`; explicit `--parallel N` matching affinity `job_count`; tests + Antora (`patch`) — **soaked** on [#319](https://github.com/ja11sop/cuppa/pull/319) 2026-09-21 |
| `par-count-plan` | This document + design README / ROADMAP pointer |
| `par-count-settle` | Lock A vs C; `=` vs space; conflict with `--jobs` |
| `par-count-impl` | Options + wrapper + construct + tests + docs |

## Out of scope

- Changing the leave-N-cores-for-OS affinity table itself
- Making `--jobs` apply Cuppa affinity (keep SCons-native meaning)
- Coverage `--parallel` collection policy ([`coverage-parallel.md`](coverage-parallel.md))
- Forcing `CMakeInstall` onto `--parallel 1` (keeps `jobs=False` omit unless a soak shows install pegging cores)
