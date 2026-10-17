# Plan: Terse in-progress build action + heartbeat

- **Status:** proposal
- **Related:** [`../archive/quiet-tty-heartbeat.md`](../archive/quiet-tty-heartbeat.md); [`../archive/terse-build-output.md`](../archive/terse-build-output.md); [`../archive/terse-delegated-output.md`](../archive/terse-delegated-output.md); [`console-channels.md`](console-channels.md); `cuppa.utility.heartbeat.operation_status`; ROADMAP Build console / **1.13.0** related polish
- **Updated:** 2026-10-17
- **Impact:** patch — TTY liveness during long toolchain actions under `--terse-output` (± `-Q`); no change to durable `[ok]` / `[error]` semantics

## Problem

Under `--terse-output` (often with `-Q`), ordinary compile/link actions only
print a durable **`[ok]`** (or `[error]`) **when they finish**. While a
multi-minute compile runs, the last visible durable line is still the
**previous** action’s `[ok]`. There is no muted “currently compiling …” row and
no pulse/spinner tied to **this** action.

Soak observation (large tip, `--terse-output`, long `pipeline.cpp` compile):

```text
   8/  8 ·  37% [ok]   test/trades · … · compile · …/trade_from_trade_reported.cpp → <working>/….o
   … ~10 minutes with no further console cue …
   1/ 23 ·  38% [ok]   test/pipelines · … · compile · …/pipeline.cpp → <working>/pipeline.o
```

Desired shape (sketch — pulse widget + muted in-progress caption, same identity
fields as the eventual `[ok]`):

```text
|-•-------|     [compiling...] test/pipelines · gcc15_dbg_x86_64_cxx2c · test/pipelines/pipeline.cpp → <working>/pipeline.o
```

Then, on success, clear the status row and emit the usual durable `[ok]` line.

Quiet+TTY heartbeat ([`quiet-tty-heartbeat.md`](../archive/quiet-tty-heartbeat.md))
already keeps the console alive for **diverted INFO** and for **location /
retrieve** waits via `operation_status`. It does **not** arm an in-progress
caption for ordinary SCons toolchain actions (compile / link / …), which emit
no Cuppa INFO while the tool runs. So a long silent `g++` looks hung even when
heartbeat diversion is on.

## Intent

1. While a terse-eligible **build action** is in flight on a TTY, show a
   **sticky** muted in-progress caption (with pulse/spinner per
   `--quiet-heartbeat` / terse compact alive style).
2. On action completion (success or failure), clear that caption and emit the
   existing durable terse line (`[ok]` / `[error]` / …).
3. Keep non-TTY / CI silent on the status row (same rules as today’s heartbeat).
4. Do not duplicate durable transcript: in-progress is status-channel only.

## Non-goals

- Changing `[ok]` field layout, action tallies, or percent accounting.
- Replacing `--native-output` compiler dumps with the status row.
- Multi-line progress bars for compile under `-Q`.
- Per-file byte progress from the compiler (we do not have that signal).

## Direction

Reuse **`operation_status` / sticky `show_info`** (already used for git update /
clone waits) rather than inventing a second painter.

| Hook point (candidates) | Role |
|-------------------------|------|
| Terse print / action start (before spawn or Python action body) | Enter `operation_status( muted compiling… )` with sconscript · variant · action · `source → product` |
| Terse success / failure / interrupt path | Exit context → clear sticky → durable `[ok]` / `[error]` |
| Parallel `-j` | One status row already serialised; sticky caption should represent a **primary** in-flight action or a short “N compiling…” aggregate — settle in implementation (prefer: last-started action, or job-count caption when `job_count > 1`) |

Caption spelling should mirror durable lines so the eye can match start → finish
(action name like `compile`, paths via existing terse file-field helpers). Exact
token (`[compiling...]` vs `compile · …` vs subdued without brackets) is a
presentation detail — prefer subdued, not a second success badge.

### Mode matrix (draft)

| Mode | In-progress caption |
|------|---------------------|
| `--terse-output` + TTY | Yes (arm status row via `ensure_status_row` if not already diverting) |
| `--terse-output` + `-Q` + TTY | Yes (same row as quiet heartbeat) |
| `--terse-output` + pipe / CI | No status row |
| Normal output (not terse) | Out of scope for this plan (SCons/cmd lines already show activity unless `-s`) |
| `--quiet-heartbeat=off` | No pulse; decide whether a static muted caption is still worth it (lean: off with heartbeat off) |

## Open questions

1. **`-j` / `--parallel`:** last-started sticky vs aggregate “N actions in flight”.
2. **Python actions / non-spawn** (e.g. some Cuppa builders): same enter/exit hooks?
3. **Delegated builders** (CMake / `b2`): they already have `[launch]` / children —
   avoid double captions; prefer extending those bookends only if gaps remain.
4. **Idle after finish:** ensure sticky release does not leave a stale compiling
   caption when the next action is slow to start (clear on durable write is
   enough if every action uses the context manager).

## Progress

| Item | Status |
|------|--------|
| Soak gap captured | Done — this proposal |
| Hook design / `-j` settle | Starting |
| Implementation | Not started |
| Antora note (terse + long actions) | With implementation |
