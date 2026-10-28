# Plan: Terse in-progress build action + heartbeat

- **Status:** done
- **Status note:** shipped on [#375](https://github.com/ja11sop/cuppa/pull/375)
- **Related:** [`../archive/quiet-tty-heartbeat.md`](../archive/quiet-tty-heartbeat.md); [`../archive/terse-build-output.md`](../archive/terse-build-output.md); [`../archive/terse-delegated-output.md`](../archive/terse-delegated-output.md); [`../archive/transfer-and-archive-progress.md`](../archive/transfer-and-archive-progress.md) (package compress claimed shipped in [#360](https://github.com/ja11sop/cuppa/pull/360)); [`console-channels.md`](console-channels.md); `cuppa.utility.heartbeat.operation_status`; ROADMAP Build console / **1.13.0** related polish
- **Updated:** 2026-10-28
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
cannot show every job. Multiplex with a muted job count (right-aligned on the
arrow column) and embed the 1-based display index in the badge:

```text
|--------•|   5 [...3] test/pipelines · … · compiling · pipeline.cpp → <working>/pipeline.o
```

Single in-flight job keeps the arrow:

```text
|--------•|   → [....] test/pipelines · … · compiling · pipeline.cpp → <working>/pipeline.o
```

Rules of thumb:

1. Maintain the set of **outstanding** (started, not yet durable) actions.
2. The status row shows **one** of them under a shared six-column badge
   (`[....]` alone, or `[...k]` when `N > 1`); the action word uses the
   progressive form (`compiling`, `copying`, …). Under `-j` the row is
   multiplexed with muted `N` replacing `→`.
3. When an action completes and writes its durable `[ok]` / `[error]`, remove
   it from the set and **immediately rewrite** the status row to another
   outstanding action (if any).
4. **Cycle** the displayed member through the outstanding set on a dwell timer
   (~2s) and on each completion / start so long-running siblings each get
   airtime — not “stuck forever on the last-started job.”
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

1. ~~**Cycle cadence** under `-j`~~ — **Settled:** dwell timer (~2s) plus
   rewrite on start/finish; badge embeds 1-based index; muted job count replaces
   `→` when `N > 1` (`5 [...3]`; single job keeps `→ [....]`).
2. **Python actions / non-spawn** (e.g. some Cuppa builders): same register /
   unregister hooks?
3. ~~**Delegated builders** (CMake / `b2`)~~ — **Deferred.** See below.
4. **Idle after empty set:** clear sticky when outstanding is empty (do not leave
   a stale `[executing...]` between waves). — Done with outstanding refresh.

## Settled (parallel)

Under `--parallel` / `-j`, **do not** pin the status row to “last started”
forever. Keep an outstanding set; show one member under `[....]` / `[...k]`;
**cycle** through the set on a dwell timer and as actions complete; rewrite
after each durable terse line so the console always reflects something still
running. Shape: `→ [....]` when alone; `N [...k]` (muted count, right-aligned
on the arrow column; badge dots + 1-based index) when multiplexing.

## Delegated CMake / `b2` (deferred)

CMake and `b2` already print a durable `[launch]` bookend and then stream
muted child lines. `write_terse_launch` drops any stash-time `[....]` so the
status row does not carry a second caption beside that bookend. That is the
in-flight cue for those builders. Do not add another `[....]` (or a parallel
`N [...k]` row) for the delegated span unless a soak shows a long silent gap
with `[launch]` already printed and no muted children moving.

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

**Settled (2026-10-23, [#375](https://github.com/ja11sop/cuppa/pull/375)).**
Durable process lines are action `run` (duration + command summary), and
in-flight process actions use the same `[....]` outstanding set as toolchain
spawns. Python callables and `env.Execute` are wrapped so they enter and
leave that set.

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

**Triage (2026-10-20):** Yes — this was the nest TTY / progress-fd gap, not a
missing `[....]` hook. Cascade nests lose `/dev/tty` under `start_new_session`;
tip now keeps an open progress fd and forwards `CUPPA_PROGRESS_FD` + `pass_fds`
(POSIX). That landed with cascade tip-consume (see CHANGELOG “Cascade nested
compress/upload progress”). Re-soak amend compress under `--terse-output` ±
`-Q`; only reopen if the muted **Compressing** bar is still absent.

## Progress

| Item | Status |
|------|--------|
| Soak gap captured | Done — this proposal |
| Parallel outstanding-set + cycle | Settled — rewrite on start/finish; cycle index advances on refresh (timer optional later) |
| Process `Monitor` clear + terse shape | **Done** — banner / `= done =` / argv echo suppressed under terse. Durable line: `[ok] · run · <duration> · <command>` even under `--test` (`Test()` keeps `test` / `[pass]`) |
| Toolchain `[....]` outstanding set | **Done** — `begin`/`end`/`refresh` in `cuppa.progress`; badge `[....]` + progressive verbs; durable field colour via `preserve_style`; armed from `terse_print_cmd_line`; terse `Popen2` keeps heartbeat; `[launch]` drops in-flight caption |
| Parallel `N [...k]` + dwell rotate | **Done** — single job `→ [....]`; multiplex muted count on arrow column + `[...k]` badge; ~2s dwell timer |
| Execute(Copy) outstanding leak | **Done** — nested `Execute` armed `[....]` via `PRINT_CMD_LINE` but never ended (no SPAWN finish); finished copies stayed in the set and looked “queued”. Wrap now drops nested key and restores parent |
| Deferred `[....]` arm (fast actions) | **Done** — pending set + ~0.2s arm delay (idle-gate order); end before arm → durable line only |
| Sticky chase vs busy transcript | **Done** — sticky bypasses idle gate; `write_transcript` preserves + restores sticky after each durable line so fast `[ok]` cannot starve armed long jobs |
| Stable carousel index | **Done** — retain display key across repaint/append; removal lands on successor slot; dwell timer alone advances, and repaint does **not** restart that ~2s timer |
| Status glued to `scons: ***` | **Done** — terse stdout/stderr filter clears the status row before non-interrupt writes |
| `[....]` glued to shell prompt on Ctrl-C | **Done** — interrupt announce drops the outstanding set and blanks the status row; begin/refresh/promote refuse afterward so cleanup `[ok]` cannot chase the caption onto the prompt ([#376](https://github.com/ja11sop/cuppa/pull/376)) |
| Progress / location maps after `[interrupted]` | **Done** — close waits for `Jobs.run`; Progress / location after announce skipped (noise beside `[stopped]`) (this PR; ordering supersedes hide-after-close from [#380](https://github.com/ja11sop/cuppa/pull/380)) |
| Per-job `[stopped]` on Ctrl-C | **Done** — notice `[stopped]` with in-flight progressive chrome (`compiling`); drain before close (this PR) |
| Package compress / tar liveness gap | **Same root cause as nest TTY** — fixed via tip `CUPPA_PROGRESS_FD` + `pass_fds` (cascade tip-consume / [#373](https://github.com/ja11sop/cuppa/pull/373) CHANGELOG); path-only `CUPPA_PROGRESS_TTY` reopen was insufficient after nest `start_new_session`. Re-soak only if muted Compressing bar still missing |
| Hook design / cycle cadence | Done — start/finish + dwell timer |
| Antora note (terse + long actions) | Done — `cli/output-and-environment.adoc` |
| Delegated CMake / `b2` extra `[....]` | **Deferred** — `[launch]` already drops the in-flight caption; muted children are the mid-flight cue. Do not add a second `[....]` unless a soak shows a silent gap beside `[launch]` |

## Soak addendum (2026-10-28) — interrupt stop confirmation + close ordering

Under `--terse-output` ± `-Q` / `--parallel`, first Ctrl-C `SIGINT`s remembered
build children. Desired drain shape:

```text
interrupted — stopping in-flight actions...
   2/  6 ·  60% [stopped]  test/trades · … · compiling · …
   1/  4 ·  61% [stopped]  test/filters · … · compiling · …
stopped in-flight actions
[interrupted] reached 61%: 43/70 · 2 ran · 41 up to date
```

| Piece | Choice |
|-------|--------|
| Badge | `[stopped]` — notice; same verb as `stopping…` / `stopped in-flight actions` |
| Verb / file | In-flight progressive chrome (`compiling`, muted-bold pending product) — not done-form `compile` |
| Width | Wider than six columns; pad is a no-op so the word reads in full |
| When | SIGINT returncode on spawn + Python-action finish |
| Close | **`Jobs.run` finally only** — never on mid-drain SCons `Build interrupted.` |
| Maps | Skip Progress / location after announce — `[stopped]` is the drain value |
| Argv | Not reprinted — stop is confirmation, not a failure transcript |
| Bare `· run` | Serial soak showed nameless `[ok] · run` after close — **bug**, not hide. Fall back to stashed command when node summary missing / `.success` only (this PR) |
| Stale `N/M` on cleanup | **Open** — post-`[interrupted]` `docker stop` often shows the same cell `N/M` as the `[stopped]` compile (credit failed). Do **not** paper over with `→`. See soak note below |

### Serial soak — why `docker stop` reuses `14/34` (2026-10-28)

Observed order:

```text
  14/ 34 ·  14% [stopped] … · compiling · event_processor.cpp → …
stopped in-flight actions
[interrupted] reached 14%: …
  14/ 34 ·  14% [ok]   … · run · docker stop <id>   # same tally, no bump
```

**Timing:** `[interrupted]` is printed from `Jobs.run`'s finally
(`build_children`). Anything after that line is **not** an in-flight BuildTask
drain — it is post-job teardown (tip `atexit` / `env.Execute` after SCons
returns / similar). Cuppa still paints a durable `run` line if that teardown
goes through `Run` / `_TersePythonCallable` / `format_terse_line(..., count=True)`.

**Credit path:** `_account_and_prefix` → `credit_and_prefix` looks up the finish
`target` (and `_current_action_nodes`) in `_progress_ledger._nodes`. On miss or
`remaining == 0` it returns `credited=False` but still returns the **current**
cell prefix (`_prefix_unlocked`) — so the line looks like “another 14/34”
without bumping `done`.

Likely causes (need tip soak / instrumentation to pick one):

1. **Out-of-band Execute** — cleanup never was a BuildTask; node id not in the
   ledger (or empty target). Still paints `count=True` with stale prefix.
2. **Narrowed away** — `NotifyProgress.add` registered the stop `Run` at parse,
   then `narrow_progress_ledger` dropped it because it was not reachable from
   the requested roots; teardown still runs it.
3. **Already spent** — same executor/node credited earlier (unlikely for a
   distinct AlwaysBuild stop, but check shared executors).
4. **AlwaysBuild + force_test** — stop `Run` is among the 34, but after
   interrupt SCons does not schedule it; tip invokes it manually after return.

**Options (do not “hide” the number):**

| Option | Idea | Trade-off |
|--------|------|-----------|
| **Diagnose** | Temporary reason on failed credit: `missing` / `spent` / `empty-target` (test or `--info`) | Find which of 1–4 before product change |
| **Match + credit** | If node is in ledger with `remaining > 0`, ensure finish targets are the registered nodes (AlwaysBuild wrap order, `remember_terse_action_target`) → honest `15/34` | Fixes 3/partial 4 only when it really is a graph action that still runs |
| **Keep in ledger** | Exclude cleanup `Run`s from narrow, or `Depends` them so they stay reachable | Fixes 2; tip must declare cleanup as part of the graph |
| **Run cleanups before close** | Tip/cuppa teardown that must paint runs *before* `write_terse_interrupt_finish` | Hard without a registry of cleanups; changes interrupt bookend timing |
| **Phase-name cleanup** | After `_interrupt_finished`, paint `· cleanup · docker stop` (or keep `run`) **without** build `N/M` — not nested `→`, not a fake tally | Honest if teardown is intentionally out-of-band; does not pretend it was action 15 |
| **Late-register** | On failed credit after close, `register` + credit so total grows (`15/35`) | Distorts the planned `34`; usually wrong for atexit |

**Rejected:** map failed credit → nested `→` (hides the bug; user soak 2026-10-28).

**Next:** instrument failed credit (option Diagnose) against this tip’s postgres
stop hook; then choose Match+credit / Keep-in-ledger vs Phase-name cleanup.

**Diagnose (this PR):** after the interrupt **close** (`_interrupt_finished`),
a failed `count=True` credit prints one subdued stdout line:

```text
terse-credit: miss=missing · interrupt=closed · ledger=34 · cell=14/34 · 14% · target=… · cmd=docker stop …
```

`miss` is `empty-target` / `missing` / `spent`. Re-soak the serial postgres
Ctrl-C case and paste that line.
