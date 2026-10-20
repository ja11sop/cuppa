# Plan: Terse in-progress build action + heartbeat

- **Status:** in progress
- **Related:** [`../archive/quiet-tty-heartbeat.md`](../archive/quiet-tty-heartbeat.md); [`../archive/terse-build-output.md`](../archive/terse-build-output.md); [`../archive/terse-delegated-output.md`](../archive/terse-delegated-output.md); [`../archive/transfer-and-archive-progress.md`](../archive/transfer-and-archive-progress.md) (package compress claimed shipped in [#360](https://github.com/ja11sop/cuppa/pull/360)); [`console-channels.md`](console-channels.md); `cuppa.utility.heartbeat.operation_status`; ROADMAP Build console / **1.13.0** related polish
- **Updated:** 2026-10-20
- **Impact:** patch — TTY liveness during long toolchain actions under `--terse-output` (± `-Q`); no change to durable `[ok]` / `[error]` semantics
- **Also related:** tip `env.Run` / process monitors; cascade tip-local options → [`cascade-tip-local-options.md`](cascade-tip-local-options.md); package `create_package_archive` / nest amend compress

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
|-•-------|   → [....] test/pipelines · gcc15_dbg_x86_64_cxx2c · compiling · test/pipelines/pipeline.cpp → <working>/pipeline.o
```

Then, on success, clear/rewrite the status row and emit the usual durable
`[ok]` line.

**Parallel** (`--parallel` / `-j` / several actions at once): one status row
cannot show every job. Prefer a **generic** muted caption that is **always
rewritten** as the set of in-flight actions changes:

```text
|-•-------|   → [....] test/pipelines · … · compiling · pipeline.cpp → <working>/pipeline.o
```

Rules of thumb:

1. Maintain the set of **outstanding** (started, not yet durable) actions.
2. The status row shows **one** of them under a shared six-column badge
   `[....]` (aligns under durable `[ok]`); the action word uses the progressive
   form (`compiling`, `copying`, …). Under `-j` the row is multiplexed.
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
2. Prefer a shared **`[....]`** badge plus progressive action word (works for
   compile, link, and other actions; multiplexes cleanly under `--parallel`).
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
| Terse action start (before spawn or Python action body) | Register outstanding entry; rewrite status to `[....]` + progressive action + identity fields |
| Terse success / failure / interrupt path | Durable `[ok]` / `[error]`; unregister; rewrite status to next outstanding (or clear) |
| Pulse / idle timer (optional) | Advance the displayed outstanding member so parallel long jobs rotate |

Track outstanding actions in a small thread-safe structure (start adds, finish
removes). The **one** status row (already serialised for `-j` transcript) paints
the current cycle pick via sticky `show_info` / `operation_status`-style API.

Caption spelling should mirror durable lines so the eye can match start → finish
(action name like `compile`, paths via existing terse file-field helpers). Shared
token **`[....]`** (subdued, six columns) plus progressive action
(`compiling`, …) with durable-line colour on script / variant / file fields.
Optional later: show `N in flight` as a trailing subdued hint when `N > 1`.

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

## Soak addendum (2026-10-18) — process runs + sticky residue

Large tip soak (`--terse-output -Q --test`, postgres container helpers) also
showed:

### 1. Heartbeat / status row not cleared before process transcript

`env.Run` / `RunProcess` uses `cuppa.method_helpers.run_process.Monitor`, which
writes **directly to stdout**:

```text
Running Process [_build/.../docker-run-…]
docker run …
 = done =  Time: Wall [ … ]
```

and for readiness waits a pulse caption can remain glued to the done line:

```text
|---√-----|   → localhost:34303 - accepting connections = done =  Time: …
```

That is the quiet/terse **status row not revealed/cleared** before a non-terse
transcript write (same class as “clear before durable `[ok]`”). Any
implementation of in-progress captions must **clear (or reveal) the status row
before** `Monitor` / raw process stdout, and prefer routing those writes through
the shared transcript lock helpers.

### 2. No first-class terse form for general process actions

Under `--terse-output`, toolchain compiles already get a durable
`N/M · % [ok] … · compile · …` line, but `Run()` process helpers still emit the
verbose `Running Process […]` / `= done =` block. The durable follow-up is often
only a generic `· test · <final>/….success` (or docker stdout log), which does
not summarise the **command** the way compile summarises the tool.

**Explore (same slice or immediate follow-on):**

| Piece | Lean |
|-------|------|
| Durable line | e.g. `… [ok] · run · docker run …` / `… [ok] · run · wait-until-pg-ready` with a short product field |
| In-progress | Same `[executing...]` machinery (process is just another outstanding action) |
| `Monitor` under terse | Suppress or replace the emphasised banner + `= done =` timing block when terse is on (timing can stay subdued on the durable line or drop) |
| Label | `RunMethod` already labels terse action as `test` / `run` / `benchmark` from variant keys — keep that; improve **file/command field** spelling |

Non-goal: making docker / postgres helpers Cuppa builtins — only the console
shape when tips use `env.Run`.

### 3. Package compress / tar — no visible heartbeat (regression vs #360?)

Soak (2026-10-18), including cascade **amend** nests that retar large staged
trees: **no** transfer/alive progress is visible while `create_package_archive`
runs (`tarfile` / zip walk). The console sits on the previous durable line for
the whole compress — same “is it hung?” feel the transfer plan was meant to
kill.

That work was explicitly scoped and marked **done** in
[`../archive/transfer-and-archive-progress.md`](../archive/transfer-and-archive-progress.md)
([#360](https://github.com/ja11sop/cuppa/pull/360)): enrol
`create_package_archive` on the shared `ProgressReporter` + heartbeat engine
(muted bar under `--terse-output` ± `-Q`, overwrite on completion, then durable
terse `compress` identity via `write_terse_transfer_action`). Unit coverage
exists (`test_create_package_archive_reports_progress` with an injected
reporter).

**Investigate (do not re-litigate the product shape):**

| Suspect | Why |
|---------|-----|
| `transfer_progress_allowed()` false in nest / `-Q` | Quiet gate needs `_heartbeat_active` + alive style; nested `python -m cuppa` may not enrol the same way as tip |
| `ProgressReporter` begins but never paints | Throttle / non-TTY / ownership clear swallowing `\r` frames; nest `CUPPA_STDOUT_IS_TTY` inheritance |
| Only durable `compress` line after done | Alive+bar missing mid-flight; completion identity alone is not enough for multi-minute tar |
| Amend vs `build_package` path | Both call `create_package_archive` without forcing `show_progress=True` (rely on `_maybe_reporter`) — confirm both hit the reporter under soak flags |
| Heartbeat vs transfer confusion | Operator expects green ECG / `[executing...]`; shipped shape is muted **Compressing** transfer status — if that is absent entirely, it is a **regression / gap**, not “wrong caption” |

Cross-link: any fix may live in transfer/heartbeat enrolment rather than the
compile `[executing...]` hook — but the soak symptom is the same class of
“long action, no liveness,” so track it here until triage says otherwise.

## Progress

| Item | Status |
|------|--------|
| Soak gap captured | Done — this proposal |
| Parallel outstanding-set + cycle | Settled — rewrite on start/finish; cycle index advances on refresh (timer optional later) |
| Process `Monitor` clear + terse shape | **Done** — banner / `= done =` / argv echo suppressed under terse. Durable line: `[ok] · run · <duration> · <command>` even under `--test` (`Test()` keeps `test` / `[pass]`) |
| Toolchain `[....]` outstanding set | **Done** — `begin`/`end`/`refresh` in `cuppa.progress`; badge `[....]` + progressive verbs; durable field colour via `preserve_style`; armed from `terse_print_cmd_line`; terse `Popen2` keeps heartbeat; `[launch]` drops in-flight caption |
| Package compress / tar liveness gap | Soak noted (above) — triage vs #360 |
| Hook design / cycle cadence | Done for start/finish cycle; timer rotation deferred |
| Antora note (terse + long actions) | Done — `cli/output-and-environment.adoc` |
