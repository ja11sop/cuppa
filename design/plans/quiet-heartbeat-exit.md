# Note: quiet heartbeat leaves its last line at exit

- **Status:** proposal
- **Related:** [`ROADMAP.md`](../../ROADMAP.md) — `console-quiet-heartbeat-exit`; [`quiet-tty-heartbeat.md`](../archive/quiet-tty-heartbeat.md); [`terse-heartbeat-chase.md`](terse-heartbeat-chase.md) (a different later change)
- **Updated:** 2026-10-31
- **Impact:** `patch` if exit finishes the status row

Not part of unverified-latest. Recorded so the stuck line is not only a remark on that run.

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

## Not the chase

[`terse-heartbeat-chase.md`](terse-heartbeat-chase.md) is about a terse caption continuing the animation from where the previous line left off. This is the quiet status row still being on screen when cuppa has exited, in normal output.

The coverage sentence is a result, not a progress caption. Parking it only on the transient row means exit either leaves the bar up or, if exit only erases the row, drops the sentence. A fix has to finish the row and still show that result.
