# Plan: TTY liveness when info logs are quiet

- **Status:** done
- **Related:** [`ROADMAP.md`](../../ROADMAP.md) (console / quiet follow-ons); channel map [`console-channels.md`](console-channels.md); [`console-mode-banners.md`](console-mode-banners.md); [`develop.remote_check_progress`](../../cuppa/develop.py); [`Git._run_with_progress`](../../cuppa/scms/git.py); large consume-tip `-Q --cascade-plan` soak
- **Updated:** 2026-10-04
- **Impact:** `minor`
- **PR:** [#356](https://github.com/ja11sop/cuppa/pull/356)

## Problem

On a large consume tip, configure walks many Location remotes and package
lookups. With normal verbosity, `logger.info` (“Updating […]”) shows liveliness.
With SCons `-Q` (and any future “quiet configure”), those lines vanish. The
process looks hung until a stdout report (for example `--cascade-plan`) finally
prints — especially painful when the operator chose `-Q` *because* the tip is
noisy.

Existing single-line rewrite (`remote_check_progress`, git `--progress`) proves
the console pattern works, but only for a few call sites — and today those
surfaces themselves go silent under `-Q` (they gate on
`logger.isEnabledFor(INFO)`).

## Intent

Keep the console **alive** under quiet + TTY without dumping full info logs and
without scattering bespoke “if quiet: spinner” logic across the codebase.

## Candidate approaches (most → least general)

| Rank | Approach | Pros | Cons |
|------|----------|------|------|
| **1** | **Logger-level rewrite** — while quiet + TTY, divert INFO onto one subdued `\r`-rewritten status line (latest message wins, throttled). Call sites unchanged. | Always alive; no audit of every `logger.info`; consistent as new code adds info logs | Must change how `-Q` interacts with the logger (INFO is filtered today); fast chatter needs throttle; progress bars share the INFO gate |
| **2** | **Marked long events** — only waitable / network / long work participates; durable mark (`extra=`, context manager, or helper) after a codebase audit. | More precise; less flicker; can write to TTY without changing logger level | Maintenance; easy to forget marks on new slow paths |
| **3** | **Cherry-picked actions** — location update, develop fetch, cascade resolve only. | Smallest patch; reuses existing progress helpers | Piecemeal; inconsistent; new slow paths stay silent |

`remote_check_progress` / git progress remain useful **implementation details**
under any winner, not the product model by themselves.

Do **not** treat (3) as the primary long-term strategy unless evaluation shows
(1) and (2) are blocked by logger/SCons constraints; even then, document how new
slow paths get enrolled so the set does not stay arbitrary.

## Phase 0 — Evaluate and settle

### Inventory

#### 1. How `-Q` / quiet interact with logger handlers

`Construct._set_verbosity_level` (`cuppa/construct.py`):

| Flag | Cuppa logger level |
|------|--------------------|
| `-Q` (`no_progress`) | `warn` |
| `-s` / `--quiet` / `--silent` | `error` |
| `--verbosity=LEVEL` | that level (wins) |

`cuppa/log.py`: one `StreamHandler` on the `cuppa` logger (`propagate=False`).
`set_logging_level` sets **both** `root_logger` and `cuppa` logger levels.

**Consequence for approach 1:** under `-Q`, `logger.info(...)` returns before any
handler runs. A heartbeat handler alone cannot see INFO. Approach 1 therefore
requires an **INFO diversion**, not a new handler on top of today's WARN level:

1. Under quiet + TTY, keep the logger able to generate INFO records.
2. Stop the ordinary `StreamHandler` from printing multi-line INFO (filter /
   level on that handler).
3. Route INFO to a heartbeat rewrite on the controlling TTY
   (`open_progress_stream()` — same path as download / develop progress).
4. Leave WARN / ERROR / CRITICAL as normal multi-line log lines (after clearing
   the status line).

SCons' own `-Q` (no Reading/Building) is orthogonal; Cuppa does not fight it.

#### 2. Configure-time `logger.info` catalogue

Static count (AST over `cuppa/`): **154** `logger.info` call sites in **34**
modules; ~**134** are configure-adjacent (location, gitlab, construct,
configure, cascade, boost, toolchains, …).

Rough theme split (keyword heuristic, not soak timing):

| Bucket | ~Sites | Examples |
|--------|--------|----------|
| Waitable / network / long work | ~58 | `Updating […]`, `Downloading […]`, `Extracting […]`, `Checking out`, `Using package […]` (after retrieve), toolchain archive download |
| Configure chatter | ~31 | sconstruct path, configure load/save, default dependencies/profiles, branch match settings |
| Mixed / other | ~65 | staging refresh, publish create, develop stage, misc |

On a large cached tip the chatter + “Using package” burst is **fast** (many
messages in well under a second). The hung-looking case is sparse: one
`Updating [name]…` (or `Downloading…`) then seconds of network with **no further
INFO** — git/download progress is already off under `-Q`.

`--terse-output` prints `[location]` maps and action lines on stdout under
`-Q`. Heartbeat still runs with terse: it covers **gaps between** transcript
lines (long retrieve/update/delegate waits). Terse writers clear the status
line before each stdout write so the two channels do not fight.

#### 3. Existing rewrite surfaces under `-Q`

| Surface | Mechanism | Under `-Q` today |
|---------|-----------|------------------|
| `ProgressReporter` (HTTP / extract) | `\r` rewrite via `open_progress_stream()`; throttle **0.35s** | **Off** — `_maybe_reporter` defaults to `logger.isEnabledFor(INFO)` |
| `Git._run_with_progress` | subdued `\r` / `--progress` pump | **Off** — `_progress_enabled` ≡ `isEnabledFor(INFO)` |
| `remote_check_progress` | batch fetch status + clear before ACTION table | Used when caller asks; develop update path can force `progress=True` |
| Terse `[location]` / children | stdout transcript | **On** under `--terse-output` (not a heartbeat) |

Only **three** call sites gate multi-line progress on `isEnabledFor(INFO)`:
`cuppa/utility/download.py`, `cuppa/scms/git.py`, `cuppa/progress.py`
(non-terse `Progress(...)` notify). Approach 1's diversion must **re-gate** those
on an explicit “quiet console” flag so `-Q` does not resurrect full bars.

### Decision criteria (scored)

Scale: **good** / **ok** / **poor** for the product goal (alive under `-Q` on a
TTY without multi-line info).

| Criterion | (1) Logger rewrite + throttle | (2) Marked long events | (3) Cherry-pick |
|-----------|-------------------------------|-------------------------|-----------------|
| Generality | **good** — new `logger.info` participates | **ok** — only if marked | **poor** |
| Quiet honesty | **good** — if StreamHandler suppresses INFO and bars stay gated off | **good** — never touches INFO emission | **good** |
| TTY quality | **good** — with ≥0.35s throttle; clear before warn/report | **good** — fewer updates by construction | **ok** — sparse |
| SCons fit | **ok** — needs INFO diversion; does not fight SCons `-Q` itself | **good** — no logger-level change | **good** |
| Cost | **ok** — one stack change + re-gate 3 progress sites; flicker rules | **poor** — audit ~58 waitable sites + ongoing drift | **ok** short-term / **poor** long-term |
| CI / non-TTY | **good** — `open_progress_stream()` already silent without TTY | **good** | **good** |

### Spikes

#### Spike A (approach 1) — throttle simulation (done, disposable)

Simulated 35 configure messages (chatter + 20× `Using package` + waitable) with
a heartbeat handler shaped like `ProgressReporter`:

| Mode | Emitted / seen | Notes |
|------|----------------|-------|
| No throttle, 5ms pace | 35 / 35 (100%) | Unreadable flicker |
| 0.35s throttle, burst | 2 / 35 (6%) | First + flushed last; flicker gone |
| 0.35s throttle, mixed (0.5s between waitable) | 5 / 35 (14%) | Waitable lines survive |

**Flicker reduction is not wishful thinking** — the same interval Cuppa already
uses for download bars collapses bursty INFO. The hang case (sparse
`Updating…` then long network silence) keeps that line for the whole wait;
throttle does not blank it.

**Missed-phase risk** on a fully cached tip: a sub-second forest walk may show
only first/last INFO. That is acceptable — the process is not hung; heartbeat
exists for multi-second stalls.

Live soak on a large tip (`--cascade-plan -Q`, with and without network) remains
part of the **implementation** PR checklist, not a blocker for settling the
primary approach.

#### Spike B (approach 2) — coverage gap (analysis, not coded)

Marking only Location update/clone/download + one gitlab “Using package” path
covers the classic hang, but misses toolchain archive download, Boost scrape /
extract, Conan export, cascade nest publish steps, and any future retrieve.
Static catalogue shows waitable INFO already spread across **location,
gitlab, gitlab_latest, boost, toolchain_archive, conan, package_cascade**.
Approach 2's enrollment set is larger than “two call sites” and will drift.

### Settled decision

| Question | Decision |
|----------|----------|
| Primary approach | **(1) Logger-level INFO diversion** with **mandatory throttle** (~0.35s, share `ProgressReporter` / `open_progress_stream` machinery). Latest INFO wins; flush pending on quiet→loud transitions. |
| Fallback if primary fails soak | **(2) Marked long events** for the waitable catalogue — only if diversion still feels like “not quiet” after throttle, or fights an unforeseen logger/SCons interaction. Do **not** fall all the way to (3) without an enrollment rule. |
| When liveness is on | **TTY + quiet** — quiet means `-Q` / `-s` (or equivalent) forced the effective verbosity to warn/error **and** the user did not override with `--verbosity=`. Off when stdout/stderr is not a TTY (CI/pipes). |
| Mode banners / warn / error | Clear status line, then emit. Banners already use the console-report channel ([`console-mode-banners.md`](console-mode-banners.md)). |
| Clear before stdout reports | Yes — cascade plan, develop tables, Options Error trees, mode banners, and any other console report. |
| Non-TTY / CI | Silent. Colour off when `NO_COLOR` or `--raw-output`. Not a console report — see [`console-channels.md`](console-channels.md). |
| Progress bars under `-Q` | Stay **off**. Re-gate the three `isEnabledFor(INFO)` sites on an explicit quiet/heartbeat flag (or “multi-line progress allowed”), not on logger level alone once diversion keeps INFO enabled. |
| Terse overlap | **Clear before each terse stdout line** (`progress._write_terse_stdout`). Heartbeat stays on with `--terse-output` so waits between actions remain alive. |

### Implementation sketch (next PR — not this Phase 0 docs PR)

1. Introduce a small quiet-console / heartbeat controller (TTY detect + active
   flag + throttle + clear).
2. Under quiet+TTY: logger generates INFO; `StreamHandler` suppresses INFO;
   heartbeat handler rewrites subdued one-liners (strip or avoid `cuppa: … [info]`
   preamble on the status line — status is not a log line).
3. Re-gate download / git / non-terse Progress notify on “not quiet”.
4. Hook clear-before-report next to `console_report` helpers (and warn/error
   path in the log handler).
5. Unit tests: diversion on/off, throttle, clear on warn, silent without TTY.
6. Soak: large tip `-Q --cascade-plan`; offline tip; `-Q --terse-output` coexistence.

## Design checklist (after settle)

- Implement the chosen primary approach in one central place where possible.
- Mode banners and warn/error escape the status line.
- Clear the status line before stdout reports.
- Re-gate INFO-gated progress bars so `-Q` stays quiet aside from the heartbeat.
- Document quiet + TTY behaviour in Antora once behaviour is real.

## Non-goals

- Dumping full info logs under `-Q`.
- Re-prefixing nested publish output.
- Shipping a separate spinner CLI unless evaluation shows rewrite is insufficient.
- Re-enabling full git/download bars under `-Q` as a substitute for heartbeat.
- Treating `--terse-output` location maps as the heartbeat (different channel).

## Progress

| Item | Status |
|------|--------|
| Problem / candidate ranking | Done |
| Phase 0 inventory | Done |
| Phase 0 spikes A/B | Done (A simulated; B by catalogue gap analysis) |
| Settled primary approach | **(1) + throttle**; fallback (2) |
| Implementation | Done on [#356](https://github.com/ja11sop/cuppa/pull/356) — `cuppa/utility/heartbeat.py`, log diversion, construct quiet re-apply, progress re-gate, clear before terse/report/warn, Antora + unit tests |
