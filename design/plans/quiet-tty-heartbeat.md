# Plan: TTY liveness when info logs are quiet

- **Status:** proposal
- **Related:** [`ROADMAP.md`](../../ROADMAP.md) (console / quiet follow-ons); [`console-mode-banners.md`](console-mode-banners.md); [`develop.remote_check_progress`](../../cuppa/develop.py); [`Git._run_with_progress`](../../cuppa/scms/git.py); project **B** `-Q --cascade-plan` soak
- **Updated:** 2026-09-24
- **Impact:** `minor` when a quiet+TTY liveness surface ships; `none` while proposal-only / evaluating

## Problem

On a large consume tip, configure walks many Location remotes and package
lookups. With normal verbosity, `logger.info` (“Updating […]”) shows liveliness.
With SCons `-Q` (and any future “quiet configure”), those lines vanish. The
process looks hung until a stdout report (for example `--cascade-plan`) finally
prints — especially painful when the operator chose `-Q` *because* the tip is
noisy.

Existing single-line rewrite (`remote_check_progress`, git `--progress`) proves
the console pattern works, but only for a few call sites.

## Intent

Keep the console **alive** under quiet + TTY without dumping full info logs and
without scattering bespoke “if quiet: spinner” logic across the codebase.

**Which mechanism** (logger rewrite vs marked long events vs a small set of
actions) is **not settled yet**. Generality is a strong bias, not a product
decision. This plan’s first delivery is an **evaluation** that picks one primary
approach with written criteria and evidence.

## Candidate approaches (most → least general)

| Rank | Approach | Pros | Cons |
|------|----------|------|------|
| **1** | **Logger-level rewrite** — while quiet + TTY, mute normal multi-line info emission and fold **all** info records onto one subdued `\r`-rewritten status line (latest message wins, or a short rolling summary). One place in the logging / console stack; call sites unchanged. | Always alive; no audit of every `logger.info`; consistent as new code adds info logs | Fast chatter may flicker; need clear rules for warn/error and mode banners; may fight SCons quiet |
| **2** | **Marked long events** — only info that represents waitable / network / long work participates; durable mark (`extra=`, context manager, or helper) after a codebase audit. | More precise; less flicker | Maintenance; easy to forget marks on new slow paths |
| **3** | **Cherry-picked actions** — location update, develop fetch, cascade resolve only. | Smallest patch; reuses existing progress helpers | Piecemeal; inconsistent; new slow paths stay silent |

`remote_check_progress` / git progress remain useful **implementation details**
under any winner, not the product model by themselves.

Do **not** treat (3) as the primary long-term strategy unless evaluation shows
(1) and (2) are blocked by logger/SCons constraints; even then, document how new
slow paths get enrolled so the set does not stay arbitrary.

## Phase 0 — Evaluate and settle (before implementation)

Goal: choose **one primary approach** (and optional fallback) with enough
evidence that a later implementation PR does not reopen the ranking.

### Inventory (read-only)

1. How cuppa and SCons `-Q` / quiet interact with logger handlers (who writes
   where; can a cuppa handler see INFO when SCons quiet is on?).
2. Rough catalogue of configure-time `logger.info` on a large tip (project **B**
   or a fixture of similar width): count, rate, themes (location update, gitlab
   using package, construct, …).
3. Existing rewrite surfaces (`remote_check_progress`, git `--progress`, download
   bars) and whether they already run under `-Q`.

### Decision criteria (score each approach)

| Criterion | What “good” looks like |
|-----------|------------------------|
| Generality | New slow paths stay alive without a one-off patch |
| Quiet honesty | Does not reintroduce full multi-line info under `-Q` |
| TTY quality | Readable single line; warn/error and mode banners escape cleanly |
| SCons fit | Works with real `-Q` without fighting SCons’ own quiet |
| Cost | Implementation + ongoing maintenance (marks, audits, call-site drift) |
| CI / non-TTY | Silent; no progress spam |

### Spikes (small, disposable)

- **Spike A (approach 1):** temporary logging handler that, on TTY + quiet,
  rewrites the latest INFO onto one subdued line; run project **B**
  `--cascade-plan -Q` and note flicker / missed phases / handler conflicts.
- **Spike B (approach 2):** mark only Location update + one gitlab “Using
  package” path; same soak; note coverage gaps vs A.
- Record outcomes in this plan (short “Evaluation notes” section); **then** fill
  the settled-decision table below.

### Settled decision (fill after Phase 0 — currently open)

| Question | Decision |
|----------|----------|
| Primary approach | **Open** — (1), (2), or hybrid after spikes |
| Fallback if primary fails soak | **Open** |
| When liveness is on | **Open** — TTY + quiet only vs whenever INFO is suppressed |
| Mode banners / warn / error | Must escape rewrite (clear status line, then emit); coordinate [`console-mode-banners.md`](console-mode-banners.md) |
| Clear before stdout reports | Yes — cascade plan, develop tables, Options Error trees |
| Non-TTY / CI | Silent |
| `NO_COLOR` / `--raw-output` | Honour like other report surfaces |

Until that table is filled, **do not** start a product implementation PR.

## Design checklist (after settle)

- Implement the chosen primary approach in one central place where possible.
- Mode banners and warn/error escape the status line.
- Clear the status line before stdout reports.
- Document quiet + TTY behaviour in Antora once behaviour is real.

## Non-goals

- Dumping full info logs under `-Q`.
- Re-prefixing nested publish output.
- Shipping a separate spinner CLI unless evaluation shows rewrite is insufficient.
- Prematurely locking the product to approach (1) without Phase 0 evidence.

## Progress

| Item | Status |
|------|--------|
| Problem / candidate ranking | Done (this proposal) |
| Phase 0 inventory | Not started |
| Phase 0 spikes A/B | Not started |
| Settled primary approach | **Open** |
| Implementation | Blocked on settle |
