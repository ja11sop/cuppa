# Note: CI / non-interactive console progress starvation

- **Status:** proposal
- **Related:** ROADMAP `console-ci-progress`;
  [`archive/console-write-ownership.md`](../archive/console-write-ownership.md);
  [`archive/quiet-tty-heartbeat.md`](../archive/quiet-tty-heartbeat.md);
  [`archive/terse-build-action-heartbeat.md`](../archive/terse-build-action-heartbeat.md);
  [`plans/console-channels.md`](console-channels.md);
  `cuppa/__main__.py` launcher; `cuppa.utility.heartbeat.write_line`;
  `cuppa.utility.terminal` (`CUPPA_STDOUT_IS_TTY`, progress TTY);
  `cuppa.output_processor` (`IncrementalSubProcess`, `_emit_transcript`)
- **Updated:** 2026-11-16
- **Impact:** likely `patch` — restore durable progress on the captured pipe for
  non-interactive consumers; interactive TTY UX should stay as it is

## Problem

Long Cuppa builds under **CI / non-interactive** consumers (GitLab job logs,
piped runners, headless agents) can sit with **no durable console progress for
tens of minutes**, then suddenly show a completed phase — or the next
`Running: cuppa …` line — while the runner UI only shows a waiting animation.

Observed shape (normal / progress-reporting path, not “waiting for one compile”;
paths and tip names anonymised):

```text
...
variant    100% [progress] example_lib/gcc15_rel_x86_64_cxx2c · end · 14/14 actions
sconscript 100% [progress] example_lib/sconscript · end · 3 variants · 42/42 actions
sconstruct 100% [progress] /path/to/example_lib/sconstruct · end · 6 sconscripts · 3 variants · 171/171 actions
[completed] build succeeded · 171 ran
scons: done building targets.
Running: cuppa --location-match-branch=feature/example --toolchains=gcc15 --rel --dbg --cov --test --offline
<CI waiting animation — no further Cuppa lines for a long time>
```

Work is happening (compiles, links, tests). The **captured log is not updated**.
That is broken: operators must always be able to see that **each action** (or
each Cuppa progress / transcript line) is making progress. Interactive terminals
still look good; this is a **consumer / destination** failure, not a request to
undo terse chrome.

This has been seen in **normal mode** as well as `--terse-output`, and is not
necessarily brand-new — ownership / shear work may have made an older pipe-vs-TTY
split worse or more common.

## What this is *not*

| Concern | Status |
|---------|--------|
| Terse coalescing tool stdout until **one** compile/link/`Run` finishes, then emitting one `[ok]` / `[pass]` | **Intentional** and fine. That is per-action liveness, not whole-build silence. |
| Sticky `[....]` / ECG only on an interactive status row | **Intentional** interactive UX. |
| Block-buffering / holding the **entire** build (or entire next `cuppa` invocation) until exit before the CI log moves | **Broken.** Never the design. |
| Blaming `IncrementalSubProcess` for “not reading incrementally” | Misdiagnosis if durable lines never reach the **captured** stream. ISP still line-reads children; under terse, `SpawnedProcessor` buffers **per spawn** then emits — still per action. |

## Goals

1. **CI / pipe consumers always see durable progress promptly** — every
   transcript line, progress `[progress]` / `[completed]` line, mode banner,
   and terse `[ok]` / `[pass]` / `[error]` that Cuppa considers durable must
   appear on the stream the job log captures, with an explicit flush, without
   waiting for process exit.
2. **Keep interactive TTY UX** — owned progress stream, sticky captions, no
   shear / glue of `[....]` onto durable lines under the launcher pipe when the
   human console really is a TTY.
3. **One rule for “where durable goes”** keyed off the **ultimate consumer**,
   not “can we open `/dev/tty`?”.
4. **Mode-agnostic** — fix normal and terse (and quiet+TTY where durable still
   exists); do not special-case only `--terse-output`.
5. **Prove it** with unit tests and a non-interactive soak recipe that fails if
   durable lines only appear on a controlling TTY.

## Non-goals

- Redesigning terse badges, ledger math, or per-action coalesce of toolchain
  stdout.
- Removing the launcher pipe (secret masking stays).
- Dual-writing every durable line to TTY **and** pipe “to be safe” under
  interactive diverting (refused in
  [`console-write-ownership.md`](../archive/console-write-ownership.md) —
  causes OFFLINE ×2 / shear).
- Making `-Q` dump full INFO again.
- Fixing SCons `-j` spurious rebuilds (separate plan).

## Background (how we got here)

[`console-write-ownership.md`](../archive/console-write-ownership.md) settled:

> When ultimate console is **not** a TTY: write pipe only (CI capture). Never both.

The launcher always pipes SCons stdout/stderr and sets `CUPPA_STDOUT_IS_TTY`
from the **outer** `stdout.isatty()`. Interactive humans get `=1`; CI gets `=0`.

To stop sticky/`WRAP_OFF` shear, durable `write_line` may write on the **progress
TTY** (`/dev/tty` / inherited progress fd) when that stream `isatty()`. On
**Windows**, Actions/`CONOUT$` taught us that `isatty()` on a console device
while CI only captures the process pipe **hides** durable lines — fixed so
owned durable on Windows requires `CUPPA_STDOUT_IS_TTY=1`
(`f9b12c4d`, tests in `test_heartbeat.py`).

On **POSIX**, `_prefer_progress_tty_for_durable_unlocked()` still returns
**True** whenever the progress stream is a TTY, **even if**
`CUPPA_STDOUT_IS_TTY=0`. That optimises launcher-pipe + real human TTY (no
glue), but any CI job that can open `/dev/tty` (shell executor, some hosts,
inherited `CUPPA_PROGRESS_FD`) while the log only tails the pipe gets the same
starvation Windows already fixed.

So: “we have a controlling TTY” ≠ “the log consumer can see that TTY.”

## Hypotheses (ordered)

1. **Primary (POSIX CI + progress TTY):** `CUPPA_STDOUT_IS_TTY=0` but
   `ensure_status_row` / quiet configure arms `/dev/tty`; durable
   `write_transcript` / `write_report` ride the progress stream → job log
   silent; sticky pulses also invisible to the log.
2. **Same class, normal mode:** `_emit_transcript` and progress completion
   lines also go through `write_line` / owned path — so starvation is not
   terse-only.
3. **Secondary:** main SCons child may lack `PYTHONUNBUFFERED=1` (cascade nests
   already set it explicitly because “block-buffers without this”). Explicit
   `flush` in `write_line` should cover Cuppa-owned lines; audit any durable
   paths that still `print` / write without flush, and whether the launcher
   `LineConsumer` can stall if the child rarely emits newlines.
4. **Long single child:** one multi-hour `cmake --build` / link under terse
   correctly emits once at end of **that** spawn — distinct from whole-build
   silence; document in acceptance so soak scripts do not conflate them.
5. **Runner-specific:** GitLab UI buffering is unlikely to explain *hour-long*
   silence if Cuppa is flushing the pipe; confirm with a local
   `cuppa … | cat` / `script` reproduction before blaming the forge.

## Design space

### A. Align POSIX with Windows: outer flag gates owned durable

When `CUPPA_STDOUT_IS_TTY=0`, durable lines **always** go to the stdout pipe
(with flush), even if `/dev/tty` is open for sticky/ephemeral only.

| Pros | Cons |
|------|------|
| Matches shipped design prose; mirrors Windows CI fix | Interactive `cuppa \| tee` / odd pipes may see durable on pipe while sticky is on TTY — must re-check shear |
| Small, local change to `_prefer_progress_tty_for_durable_unlocked` | Launcher-pipe + human TTY glue risk returns unless erase-prefix / idle-gate paths still hold |

**Lean candidate** if soak shows shear still acceptable with existing
`\r`+erase prefix on pipe payloads when a progress TTY exists.

### B. Split streams by role always

- **Ephemeral** (sticky `[....]`, ECG, transfer bars): progress TTY only when
  present; else no-op or subdued pipe heartbeat policy (TBD).
- **Durable**: **always** the captured pipe when `CUPPA_STDOUT_IS_TTY=0`; when
  `=1`, owned progress TTY (current interactive behaviour).

Same as A with an explicit API comment / helper names
(`write_durable_for_consumer` vs `paint_status_row`).

### C. Dual-write when flag is 0 and progress TTY exists

Pipe for CI + TTY for a human watching the runner box.

| Pros | Cons |
|------|------|
| Both consumers see lines | Refused for interactive diverting historically; risk of doubled lines if someone tees both; more lock complexity |

Only consider if A/B cannot restore CI without reintroducing shear for the
common interactive launcher case.

### D. Stop opening `/dev/tty` when outer flag is 0

No status row in CI at all; everything on the pipe.

| Pros | Cons |
|------|------|
| Simple mental model for CI | Loses any future “alive” cue on pipe; may be right for v1 of this fix |

Compatible with A/B: ephemeral may no-op when flag is 0.

### E. Launcher protocol (second FD / framed events)

Parent owns the human TTY; child only writes structured events on the pipe.

| Pros | Cons |
|------|------|
| Clean long-term | Explicitly deferred in write-ownership; too large for this bugfix |

### F. Buffering hygiene pass (orthogonal, cheap)

- Set `PYTHONUNBUFFERED=1` (or line-buffer stdout) on the main SCons child in
  `__main__.run_scons`, matching cascade nests.
- Audit durable call sites for missing `flush`.
- Does **not** fix lines written only to `/dev/tty`, but hardens the pipe path.

## Proposed direction (lean)

1. **Treat `CUPPA_STDOUT_IS_TTY` as the durable-consumer flag** (already the
   nested-cascade contract). If `0`, durable transcript/report/progress
   completion lines go to **stdout pipe only**, with flush — **POSIX and
   Windows**. Progress TTY may still exist for ephemeral sticky when a human
   is somehow attached, but must not own durable lines in that mode.
2. **Keep owned durable on the progress TTY only when `CUPPA_STDOUT_IS_TTY=1`**
   (interactive ultimate console), preserving today’s good terminal UX and
   anti-shear locking.
3. **Harden pipe path (F)** on the main launcher child.
4. **Do not** dual-write as the default fix.
5. **Document** the distinction: per-action terse coalesce vs CI starvation.

Revisit C only if interactive launcher soak regresses glue that the erase-prefix
/ idle-gate path cannot absorb after (1).

## Acceptance

- Unit: extend `test_heartbeat.py` so **POSIX** with `CUPPA_STDOUT_IS_TTY=0` and
  a TTY-like progress stream puts durable `[ok]` / transcript on the **pipe**,
  not only on the progress stream (symmetric to the existing Windows test).
- Unit: interactive flag `=1` still prefers owned progress TTY (no shear
  regression tests removed).
- Manual / tip soak: `CUPPA_STDOUT_IS_TTY=0 cuppa --terse-output … 2>&1 | cat`
  (and a normal-mode run) shows durable lines **while** the build runs, not only
  at exit; a second back-to-back `cuppa` in one script shows the next
  invocation’s early lines without an hour gap.
- GitLab (or equivalent) job log for a multi-variant build updates throughout;
  sticky absence in the log is OK; durable silence is not.
- Public prose: no private tip names in the plan/ROADMAP; soak recipes stay
  generic.

## Implementation sketch (when we leave proposal)

1. Change `_prefer_progress_tty_for_durable_unlocked` (or replace with an
   explicit `durable_on_owned_stream()`) so owned durable requires
   `_outer_stdout_is_tty()` on **all** platforms.
2. Retune / replace
   `test_write_transcript_owned_when_progress_tty_despite_pipe_flag` — that test
   currently **encodes** the POSIX CI footgun; flip expectation to pipe-when-flag-0
   and keep a separate test for flag-1 owned path.
3. Optional: when flag is 0, skip arming progress TTY for compact terse
   (`ensure_status_row`) so we do not paint invisible sticky (D-lite).
4. `__main__.run_scons`: propagate `PYTHONUNBUFFERED=1` (or equivalent).
5. Soak + CHANGELOG under 1.15.0; Antora note only if operators need a
   documented `CUPPA_STDOUT_IS_TTY` / CI expectation.

## Open questions

1. Does the failing GitLab runner actually have a usable `/dev/tty` or progress
   fd during the hung phase? (One-line diagnostic in a job would confirm
   hypothesis 1 quickly.)
2. After forcing pipe durable with flag 0, does interactive `cuppa | tee logfile`
   glue return? If yes, is tee an accepted trade-off or do we need a third
   signal (“human TTY separate from stdout”)?
3. Should progress `[progress]` lines under normal mode take any path that
   bypasses `write_line` today?
4. Quiet `-Q` without terse: any remaining diverting durable that still skips
   the pipe when flag is 0?

## Progress

| Item | Status |
|------|--------|
| CI soak symptom + mode clarification | Done — this document |
| Root-cause review vs write-ownership / Windows pipe fix | Done — proposal |
| Implementation | Not started |
