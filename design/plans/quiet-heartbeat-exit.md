# Note: quiet heartbeat leaves its last line at exit

- **Status:** done
- **Related:** [`ROADMAP.md`](../../ROADMAP.md) — `console-quiet-heartbeat-exit`; [`quiet-tty-heartbeat.md`](../archive/quiet-tty-heartbeat.md); [`terse-heartbeat-chase.md`](terse-heartbeat-chase.md) (a different later change)
- **Updated:** 2026-11-10
- **Impact:** `patch` — ships with 1.14.0 — [#393](https://github.com/ja11sop/cuppa/pull/393)

Done on master via [#393](https://github.com/ja11sop/cuppa/pull/393). Archive when 1.14.0 ships.

## What happened

Normal output, quiet, no tests:

```text
cuppa --cov --native-output --toolchains=gcc15 --normal-output -Q
```

The unverified-latest warning printed on its own line. After the build, the coverage sentence and the shell prompt shared the heartbeat row:

```text
|---√-----|  No lines of coverage (perhaps no tests were executed). Reported as 0/0 lines coveredjamie@host:~/…$
```

The bar is the quiet heartbeat. The coverage text is `logger.info` from `CoverageIndexBuilder.on_progress` at `sconstruct_end` when no lines were counted (`--cov` without `--test`).

## Why it sticks

Under `-Q` on a TTY, `cuppa.log` sends INFO to `heartbeat.show_info` and does not print a log line. `show_info` rewrites the status row and turns newlines into spaces, so the `\n` in that coverage message never reaches the terminal.

Process exit runs `restore_terminal_wrap`. That turns autowrap back on. It does not erase the status row and it does not end it with a newline. WARN and above call `heartbeat.clear()` before they print, which is why the unverified-latest warning was a clean line and this info message was not.

## Settled fix

At process exit (`finish_at_exit`, registered with `atexit` in place of bare wrap restore):

1. If an **event** INFO caption is parked (painted non-sticky `_body`, or non-sticky `_pending`), promote that text to a durable line with a trailing newline via `write_line`.
2. Sticky in-progress captions (`operation_status` / terse `[....]`) are **not** promoted — they are progress, not results. Clear them.
3. Pulse-only anchor after caption expiry (`_body == ''`) clears with no durable line.
4. Always end with wrap restore (`restore_terminal_wrap`) so a prior `?7l` cannot linger.

The coverage “no lines” sentence is a result: exit must finish the row **and** still show that sentence. Erase-only would drop it; wrap-only leaves the bar sharing the prompt.

## Not the chase

[`terse-heartbeat-chase.md`](terse-heartbeat-chase.md) is about a terse caption continuing the animation from where the previous line left off. This is the quiet status row still being on screen when cuppa has exited, in normal output.
