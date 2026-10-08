# Plan: one console write path (TTY ownership)

- **Status:** in progress
- **Related:** [`console-channels.md`](console-channels.md); [`quiet-tty-heartbeat.md`](quiet-tty-heartbeat.md); [`transfer-and-archive-progress.md`](transfer-and-archive-progress.md); [`terse-delegated-output.md`](terse-delegated-output.md); `cuppa/__main__.py` launcher; `cuppa.utility.heartbeat`
- **Updated:** 2026-10-08
- **Impact:** minor — UX / console ownership; no package format change
- **PR:** follow-on to [#360](https://github.com/ja11sop/cuppa/pull/360) (or fold into it if still open)

## Problem

Under `cuppa -Q --terse-output` (and especially nested cascade
`python -m cuppa` sessions), durable transcript lines and the quiet heartbeat
**fight for the same physical TTY row**. Soak evidence:

```text
|-----/---|              → -- Configuring done (0.1s)
|--------•|sconstruct   0% [ready] …
|---√-----|              → -- Installing: …/libopentelemetry_common.so
Running in OFFLINE mode
Running in OFFLINE mode
```

Recent #360 slices (URL fix, registry publish path, cmake Up-to-date filter,
progress-bar clear, banner dedupe) each patched a **symptom**. The soak shows
the underlying ownership model is still wrong, so each fix can look like a
no-op or can make another surface worse.

## Root cause (one sentence)

**The SCons child clears and paints the heartbeat on `/dev/tty`, but durable
transcript lines still travel `child stdout → cuppa launcher pipe → TTY`, and
the launcher never owns the status row — so a pulse can repaint between clear
and echo.**

```text
  SCons child                         cuppa launcher (__main__)
  ───────────                         ─────────────────────────
  heartbeat ──\r──► /dev/tty  ◄────── (no coordination)
  write_transcript ──► pipe  ────────► sys.stdout.write(line) ──► TTY
  write_report (diverting):
    often /dev/tty *and* pipe when CUPPA_STDOUT_IS_TTY=0
```

Nested cascade makes this worse: tip runs nested `python -m cuppa`, whose
stdout is itself a pipe. Nested `__main__` **overwrites**
`CUPPA_STDOUT_IS_TTY` from *its* `stdout.isatty()` (always false) → nested
SCons thinks the human console is non-TTY → `write_report` dual-writes TTY +
pipe → **OFFLINE ×2** even with a once-per-process banner guard.

## What the latest soak actually improved

Do not throw these out — they work on content, not ownership:

| Slice | Visible in soak? | Notes |
|-------|------------------|-------|
| **A** `https://` preserved | Yes | Registry map URL is correct |
| **B1** `<registry>/name/ver/file` publish | Yes | e.g. `→ <clearpool_io_…>/abseil-cpp/20250814.2/….tar.gz` |
| **G** Up-to-date flood gone | Yes | Abseil/c-ares install no longer dumps hundreds of paths |
| **G** `-- All targets Up-to-date` | **No** | Preamble (`[0/1] Install…`, `-- Install configuration`) marked “other”, so summary suppressed |
| **C1** clear ProgressReporter before `→` | Partial | Compress shear reduced; **ECG shear remains** (different writer) |
| **F** OFFLINE dedupe | **No** | Guard is per process; dual TTY+pipe echo is a second writer |

So the user’s “I don’t see anything improved” is fair for **readability** —
ownership still dominates — but content slices A/B1/G-suppress did land.

## Intent

One Cuppa rule for **every durable console line** under quiet+TTY:

> Clear the status row and write the line on the **same** stream, under the
> **same** lock, before any pulse may run again.

Ephemeral status (heartbeat / progress bar / cmake Up-to-date pulse) may only
paint on that stream while the idle gate says the transcript is quiet.

Non-TTY / CI stays pipe-only (no `/dev/tty`).

## Non-goals

- Redesigning terse badges / ledger math.
- Property-based resolve ensure phases.
- Killing the `cuppa` launcher pipe (secret masking stays).
- Making `-Q` dump full INFO again.

## Direction (settled sketch)

### Single owner API

Collapse call sites onto two heartbeat entry points (names indicative):

| API | Role |
|-----|------|
| `heartbeat.write_line(text)` | Durable transcript **and** console report — clear status, write, mark idle gate |
| `heartbeat.status(message)` / pulse / `ProgressReporter` | Ephemeral rewrite only; never a durable newline |

`progress._write_terse_stdout`, `write_report_lines`, mode banners, and muted
cmake children all call `write_line`. No direct `sys.stdout.write` for product
lines while diverting.

### Interactive diverting: write on the heartbeat stream

Today `write_report` already prefers `/dev/tty` when diverting. **`write_transcript` must do the same** when the ultimate console is a TTY:

1. Under lock: erase status row on `_stream`.
2. Write the durable line + `\n` on `_stream` (not the pipe).
3. Mark transcript idle gate; arm pulse only after idle.

When ultimate console is **not** a TTY: write pipe only (CI capture). Never both.

### Propagate ultimate TTY through nested cuppa

In `__main__.run_scons`, do **not** clobber an inherited `CUPPA_STDOUT_IS_TTY`
set by an outer interactive launcher. Nested cascade then keeps `=1`,
`write_report` stops dual-writing, OFFLINE ×2 disappears without relying on
dedupe (dedupe remains a belt-and-braces for same-process double Construct).

### ProgressReporter / operation_status

Enrol on the same stream + lock as heartbeat (already partially true).
`clear_active_progress` stays, but becomes redundant for shear once durable
lines never leave the owned stream.

### Cmake Up-to-date summary (content follow-on, after ownership)

Treat install **preamble** as neither work nor uptodate:

- Pulse/suppress `-- Up-to-date:`
- Durable: `-- Installing:`, errors, ninja build lines, `ninja: no work to do.`
- Ignore for “other”: `[0/1] Install the project…`, `-- Install configuration:…`, blanks
- If any `-- Up-to-date:` seen and zero `-- Installing:` → emit `-- All targets Up-to-date`

### Cascade bookend (product, separate small slice)

Tip still jumps `prepare` → plan with no `[ready]`. Nest handoffs are in:
blank after plan → tip `[cascade] … · begin · N packages` → first nest
`entering` → nest banners → `parent session` + exiting|entering between
nests → `cascade sessions complete` banner → blank → tip
`[cascade] … · end · …`.

Tip begin/end use the tip pin (no `<token>`) so they stay distinct from nest
enter/exit. `[ready]` after tip prepare→plan remains open.

## Implementation lean

1. **Prove the race in a unit test** — fake TTY stream + pipe echo thread:
   pulse between clear and echo → glued line; owned-stream write → clean.
2. **Unify `write_transcript` with `write_report` stream choice** (one helper).
3. **Preserve `CUPPA_STDOUT_IS_TTY` across nested `__main__`**.
4. **Route terse / report / muted children only through `write_line`**.
5. **Retune cmake summary** (preamble vs Installing).
6. Soak the same google_cloud_cpp offline cascade under `-Q --terse-output`.

## Refusal rules

| Request | Response |
|---------|----------|
| Another ad-hoc `hb.clear()` before one more call site | Refuse — enrol on `write_line` instead |
| Dual-write TTY + pipe “so CI and interactive both work” while diverting | Refuse — choose by ultimate TTY flag, never both |
| Fix OFFLINE ×2 only with a bigger dedupe set | Refuse — fix nested TTY flag / dual-write |
| Rewrite the launcher protocol (JSON frames, second FD) in this slice | Defer — owned-stream write is enough for 1.12.0 |

## Progress

| Item | Status |
|------|--------|
| Soak diagnosis vs #360 slices | Done — this document |
| Owned-stream `write_line` | Done on this PR — `heartbeat.write_line`; transcript + report share it |
| Nested `CUPPA_STDOUT_IS_TTY` preserve | Done on this PR — `resolve_cuppa_stdout_is_tty` in `__main__` |
| Cmake preamble-aware summary | Done on this PR — preamble does not block `-- All targets Up-to-date` |
| Cascade tip bookend (E) | Done for nest handoffs + tip ``begin``/``end`` twins (after complete banner); tip prepare→plan ``[ready]`` still open |
| Cascade Ctrl-C process-tree kill | Done — ``_run_nested_cuppa`` + ``terminate_process_tree`` |
| First Ctrl-C forwards stop to delegates | Done — ``interrupt_build_children`` (``SIGINT``) on first stop; ``SIGTERM`` on second |
