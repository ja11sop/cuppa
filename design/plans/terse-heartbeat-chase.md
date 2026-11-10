# Note: terse heartbeat should chase, not dwell

- **Status:** done
- **Related:** [`ROADMAP.md`](../../ROADMAP.md) — `console-terse-heartbeat-chase`; [`quiet-tty-heartbeat.md`](../archive/quiet-tty-heartbeat.md); [`terse-build-action-heartbeat.md`](../archive/terse-build-action-heartbeat.md)
- **Updated:** 2026-11-10
- **Impact:** `patch` — ships with 1.14.0 — [#395](https://github.com/ja11sop/cuppa/pull/395)

Done on master via [#395](https://github.com/ja11sop/cuppa/pull/395). Archive when 1.14.0 ships. Dwell was already off; this slice preserved ECG phase across sticky chase-back.

## What happened

A serial `cuppa --cov --test --terse-output -Q` over many short lines (coverage, collate, then copy into artefacts) held a **full heartbeat cycle on each line**. The caption sat until the animation finished, then the next line started the animation from the beginning.

Expected: the caption is chased down the terminal, and the animation **continues from where the previous line left off**.

## Where the dwell came from

Quiet-TTY and terse-action heartbeat both used a full-cycle minimum dwell (about 1.5s) before a status line was replaced. That is right for one long compile. It is wrong for a run of short actions that each complete inside that window. The wait ran when a single action's caption was visible and the durable line was written (`write_transcript` / `_write_terse_stdout`). It is not the parallel carousel (`_OUTSTANDING_DWELL_S`, about 2s), which only rotates which in-flight job is shown when more than one is outstanding.

Actions that finish before the arm delay (0.20s) never paint a caption, so they never waited. Anything that stayed up — a short coverage, collate, or copy — waited out the rest of the cycle, and the next line started the animation from the beginning.

## Dwell: done

Terse action lines clear a visible caption immediately (`dwell=False` on `_write_terse_stdout`, and on the terse spawn transcript). The parallel carousel is unchanged. Non-terse tool text and `reveal` still hold one cycle. Do not split one SCons coverage action into two terse lines to work around presentation.

## Chase: settled

Dwell is off; the remaining gap is **phase**. `_clear_unlocked` always zeroed `_spin`, and `_flush_unlocked` zeroed it again on a new row after clear. Sticky chase-back after a durable `[ok]` therefore restarted the ECG at rest every time.

Settled behaviour:

1. When a durable write clears the row **and** immediately restores a sticky heartbeat caption (`keep_pending` sticky chase), **preserve `_spin`** across clear → restore so consecutive heartbeat lines continue the animation.
2. Ordinary clears (warn/report, non-chase leave-the-row) still reset `_spin` to rest so a mid-beat does not resume after a real gap.
3. Same-row caption rewrites (already keep `_spin`) stay as they are.

Ownership: clear decides whether the cycle resets; flush on a new row does not force rest when spin was preserved for chase.
