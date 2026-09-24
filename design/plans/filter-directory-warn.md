# Plan: Filter “probably a directory” warn hygiene

- **Status:** proposal
- **Related:** [`cuppa/utility/filter.py`](../../cuppa/utility/filter.py) (`_node_exists_as_file`); [`archive/recursive-glob-parity.md`](../archive/recursive-glob-parity.md) (Filter path forms); project **B** soak under `--cascade-plan -Q`
- **Updated:** 2026-09-24
- **Impact:** `patch` (log severity / heuristic; Filter match behaviour should stay the same)

## Problem

`filter_nodes` warns when a matched node’s path does not exist yet and has no
file extension:

```text
cuppa: filter: [warn] filtered node is probably a directory […/_build/…/final/<program>]
```

Project **B** soak under `--cascade-plan -Q` hit this on an extensionless Program
under `final/` that had not been built yet.

The heuristic assumes “no extension + missing on disk ⇒ directory”. That is often
wrong for Cuppa **Program** targets (and similar extensionless artefacts) that
have not been built yet. Configure still evaluates Filter while reading
sconscripts, including under `--cascade-plan`, so the warn shows up on dry runs
where nothing is wrong.

There is no operator mitigation — only “ignore it” — which fails the bar for a
**warn**: either something is likely wrong with a clear fix, or the message
should not be a warn.

A second message, `filtered node is a directory […]`, fires when the path
**exists** and `isdir`; that case is more honest and can stay (or move to
debug) once the false-positive path is fixed.

## Intent

Only warn from Filter when the situation is **actionable** or clearly erroneous.
Do not warn for not-yet-built extensionless file targets.

## Direction

1. **Stop warning** on the “does not exist + no extension” branch (return
   `False` quietly, or `logger.debug` / `trace` if a breadcrumb is still useful
   while debugging Filter patterns).
2. Keep excluding directories from file match lists when `os.path.isdir` is true
   (existing behaviour). Optionally demote the “is a directory” warn to debug if
   it is also noise in practice.
3. Unit test: Filter of a missing extensionless path under a `_build/.../final/`
   style string does **not** emit warn; an existing directory still does not
   enter the filtered file list.
4. Non-goal: changing which nodes match when the path is a real file; only the
   log surface and the false-positive heuristic.

## Progress

| Item | Status |
|------|--------|
| Problem / intent | Settled in this proposal |
| Implementation | Not started |
