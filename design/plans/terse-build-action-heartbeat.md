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

**Serial** (one action in flight):

```text
|-•-------|     [executing...] test/pipelines · gcc15_dbg_x86_64_cxx2c · compile · test/pipelines/pipeline.cpp → <working>/pipeline.o
```

Then, on success, clear/rewrite the status row and emit the usual durable
`[ok]` line.

**Parallel** (`--parallel` / `-j` / several actions at once): one status row
cannot show every job. Prefer a **generic** muted caption that is **always
rewritten** as the set of in-flight actions changes:

```text
|-•-------|     [executing...] test/pipelines · … · compile · pipeline.cpp → <working>/pipeline.o
```

Rules of thumb:

1. Maintain the set of **outstanding** (started, not yet durable) actions.
2. The status row shows **one** of them under a shared token such as
   `[executing...]` (not a per-tool `[compiling...]` — under `-j` the row is
   multiplexed).
3. When an action completes and writes its durable `[ok]` / `[error]`, remove
   it from the set and **immediately rewrite** the status row to another
   outstanding action (if any).
4. **Cycle** the displayed member through the outstanding set on a timer (or
   on each completion / start) so long-running siblings each get airtime while
   others finish — not “stuck forever on the last-started job.”
5. When the set is empty, clear the sticky caption (idle / between waves).

Quiet+TTY heartbeat ([`quiet-tty-heartbeat.md`](../archive/quiet-tty-heartbeat.md))
already keeps the console alive for **diverted INFO** and for **location /
retrieve** waits via `operation_status`. It does **not** arm an in-progress
caption for ordinary SCons toolchain actions (compile / link / …), which emit
no Cuppa INFO while the tool runs. So a long silent `g++` looks hung even when
heartbeat diversion is on.

## Intent

1. While one or more terse-eligible **build actions** are in flight on a TTY,
   show a **sticky** muted in-progress caption (with pulse/spinner per
   `--quiet-heartbeat` / terse compact alive style).
2. Prefer a shared **`[executing...]`** token (works for compile, link, and
   other actions; multiplexes cleanly under `--parallel`).
3. On each action completion, emit the existing durable terse line, drop that
   action from the outstanding set, and rewrite the status row to another
   outstanding member (cycling the display across the live set).
4. Keep non-TTY / CI silent on the status row (same rules as today’s heartbeat).
5. Do not duplicate durable transcript: in-progress is status-channel only.

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
| Terse action start (before spawn or Python action body) | Register outstanding entry; rewrite status to `[executing…]` + identity fields |
| Terse success / failure / interrupt path | Durable `[ok]` / `[error]`; unregister; rewrite status to next outstanding (or clear) |
| Pulse / idle timer (optional) | Advance the displayed outstanding member so parallel long jobs rotate |

Track outstanding actions in a small thread-safe structure (start adds, finish
removes). The **one** status row (already serialised for `-j` transcript) paints
the current cycle pick via sticky `show_info` / `operation_status`-style API.

Caption spelling should mirror durable lines so the eye can match start → finish
(action name like `compile`, paths via existing terse file-field helpers). Shared
token **`[executing...]`** (subdued), not a second success badge. Optional later:
show `N in flight` as a trailing subdued hint when `N > 1`.

### Mode matrix (draft)

| Mode | In-progress caption |
|------|---------------------|
| `--terse-output` + TTY | Yes (arm status row via `ensure_status_row` if not already diverting) |
| `--terse-output` + `-Q` + TTY | Yes (same row as quiet heartbeat) |
| `--terse-output` + pipe / CI | No status row |
| Normal output (not terse) | Out of scope for this plan (SCons/cmd lines already show activity unless `-s`) |
| `--quiet-heartbeat=off` | No pulse; decide whether a static muted caption is still worth it (lean: off with heartbeat off) |

## Open questions

1. **Cycle cadence** under `-j`: rewrite only on start/finish vs also on a
   heartbeat tick (e.g. every full pulse cycle) so two long compiles rotate
   without waiting for a third completion.
2. **Python actions / non-spawn** (e.g. some Cuppa builders): same register /
   unregister hooks?
3. **Delegated builders** (CMake / `b2`): they already have `[launch]` / children —
   avoid double captions; prefer extending those bookends only if gaps remain.
4. **Idle after empty set:** clear sticky when outstanding is empty (do not leave
   a stale `[executing...]` between waves).

## Settled (parallel)

Under `--parallel` / `-j`, **do not** pin the status row to “last started”
forever. Keep an outstanding set; show one member under `[executing...]`;
**cycle** through the set as actions complete (and optionally on a timer);
rewrite after each durable terse line so the console always reflects something
still running.

## Progress

| Item | Status |
|------|--------|
| Soak gap captured | Done — this proposal |
| Parallel outstanding-set + cycle | Settled direction (above) |
| Hook design / cycle cadence | Starting |
| Implementation | Not started |
| Antora note (terse + long actions) | With implementation |
