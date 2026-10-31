# Note: terse heartbeat should chase, not dwell

- **Status:** proposal
- **Related:** [`ROADMAP.md`](../../ROADMAP.md) — `console-terse-heartbeat-chase`; [`quiet-tty-heartbeat.md`](../archive/quiet-tty-heartbeat.md); [`terse-build-action-heartbeat.md`](../archive/terse-build-action-heartbeat.md)
- **Updated:** 2026-10-31
- **Impact:** none until implemented (`patch` if the dwell changes)

Not part of the coverage-parallel slice. Recorded so it is not only a row inside that plan.

## What happened

A serial `cuppa --cov --test --terse-output -Q` over many short lines (coverage, collate, then copy into artefacts) held a **full heartbeat cycle on each line**. The caption sat until the animation finished, then the next line started the animation from the beginning.

Expected: the caption is chased down the terminal, and the animation **continues from where the previous line left off**.

## Where the dwell came from

Quiet-TTY and terse-action heartbeat both used a full-cycle minimum dwell (about 1.5s) before a status line was replaced. That is right for one long compile. It is wrong for a run of short actions that each complete inside that window. The wait ran when a single action's caption was visible and the durable line was written (`write_transcript` / `_write_terse_stdout`). It is not the parallel carousel (`_OUTSTANDING_DWELL_S`, about 2s), which only rotates which in-flight job is shown when more than one is outstanding.

Actions that finish before the arm delay (0.20s) never paint a caption, so they never waited. Anything that stayed up — a short coverage, collate, or copy — waited out the rest of the cycle, and the next line started the animation from the beginning.

## For now

Terse action lines clear a visible caption immediately (`dwell=False` on `_write_terse_stdout`, and on the terse spawn transcript). The parallel carousel is unchanged. Non-terse tool text and `reveal` still hold one cycle.

The chase (animation continues from where the previous line left off) is still the later change. Do not split one SCons coverage action into two terse lines to work around presentation.
