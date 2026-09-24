# Plan: Mode banners as report surface (survive quiet)

- **Status:** proposal
- **Related:** [`ROADMAP.md`](../../ROADMAP.md) (console / quiet follow-ons); [`quiet-tty-heartbeat.md`](quiet-tty-heartbeat.md); cascade mode chips in [`construct.py`](../../cuppa/construct.py); Antora packages cascade plan docs
- **Updated:** 2026-09-24
- **Impact:** `patch` (presentation); possibly `minor` if a shared “always print” banner API becomes operator-facing

## Problem

Operator-facing **mode banners** — for example:

```text
Running in PACKAGE BUILD: CASCADE PLAN mode — report only; no clone, build, or publish
Running in OFFLINE mode
Running in LIST DEVELOP mode, no building will be attempted
```

are emitted with `logger.info( as_info_label( … ) )`. Under SCons `-Q` / quiet,
those lines disappear while stdout report bodies (cascade plan trees, develop
tables) still print. On a large tip, `-Q --cascade-plan` then looks like “no mode
context, then a plan” — harder to trust what Cuppa thought it was doing.

Project **B** soak made this obvious: the cascade plan body is visible under `-Q`,
but the CASCADE PLAN mode chip is not.

## Intent

Treat **mode banners** as part of the **report surface** (same family as cascade
plan finish lines and develop ACTION tables), not as routine info logs that quiet
is allowed to drop.

## Direction

1. **Inventory** call sites that announce a named mode with `as_info_label` /
   “Running in … mode” (construct develop actions, cascade plan/collect/update,
   OFFLINE, and any similar chips).
2. **Settle** which banners always print (mode chips) vs stay logger-level
   (routine progress, package “Using …”, location “Updating …”).
3. **Emit** settled mode banners via stdout / `write_lines` (or a thin helper that
   bypasses quiet) so `-Q` still shows them. Keep colour (`as_info_label`) and
   honour `--raw-output` / `NO_COLOR` the same way other report surfaces do.
4. **Document** the quiet interaction in Antora CLI / packages pages once the
   inventory is stable.
5. Coordinate with [`quiet-tty-heartbeat.md`](quiet-tty-heartbeat.md): banners must
   **escape** any TTY info-rewrite line (clear status line, then print the banner).

## Non-goals

- Turning every `logger.info` into stdout.
- Changing what `-Q` does to SCons build chatter.
- Implementing TTY heartbeat / info rewrite (separate plan).

## Progress

| Item | Status |
|------|--------|
| Problem / inventory intent | Settled in this proposal |
| Implementation | Not started |
