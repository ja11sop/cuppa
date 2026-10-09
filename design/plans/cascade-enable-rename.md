# Plan: Rename cascade master flag

- **Status:** in progress
- **Related:** [`ROADMAP.md`](../../ROADMAP.md) — `cascade-enable-rename`; shipped cascade [`package-build-publish-deps.md`](../archive/package-build-publish-deps.md) ([#297](https://github.com/ja11sop/cuppa/issues/297)); companions `--build-cascade-dependencies` / `--publish-cascade-dependencies`
- **Updated:** 2026-10-09
- **Impact:** `minor` (CLI rename / alias; behaviour unchanged)

## Problem

`--build-and-publish-dependencies` is the **master switch** that enables package-DAG
cascade (resolve publisher trees, allow nest sessions). It does **not** mean
“you will upload.” End-state is chosen by a companion:

| Companion | Nested deps | Tip | Registry upload? |
|-----------|-------------|-----|------------------|
| `--cascade-plan` / collect / update | review / forest | usually stop | no |
| `--build-cascade-dependencies` | nest-build | tip build only | **no** |
| `--publish-cascade-dependencies` | nest-publish | tip build only | yes (deps) |
| `--publish-package` | nest-publish | tip upload too | yes |

Operators who want “build deps and consume them as-if published” correctly pass
`--build-and-publish-dependencies --build-cascade-dependencies`, but the master
name implies publish. That naming stuck from the first design (cascade ≈ build
**and** publish); nest-build without upload landed later ([#339](https://github.com/ja11sop/cuppa/pull/339)).

## Settled direction

| Question | Decision |
|----------|----------|
| Primary spelling | **`--cascade`** — short master enable; matches how operators already talk (“pass `--cascade`”) |
| Old flag | Keep **`--build-and-publish-dependencies`** as a **synonym** (same dest); no deprecation warning in 1.12.0 unless soak shows confusion remains |
| Companions | Unchanged names and refuse rules (still require the master enable) |
| Docs / samples | Prefer `--cascade` in Antora and generated samples; mention the long form once as alias |
| Help text | Master: “enable package-dependency cascade (pair with a companion action)”. Long form help notes it is an alias for `--cascade` |
| Code constant | Prefer `CASCADE_OPTION = "cascade"` (or dual registration); keep string `"build-and-publish-dependencies"` accepted via `add_option` alias / second dest |

Refuse inventing a third parallel name (`--enable-cascade`, `--cascade-dependencies`)
in the same PR — one primary + one historical synonym is enough.

## Mental model (after)

```text
--cascade                              ≈  enable cascade machinery
--build-cascade-dependencies           ≈  nest-build, no upload   ← as-if published
--publish-cascade-dependencies         ≈  nest-upload, tip build only
--publish-package                      ≈  nest-upload + tip upload
--cascade-plan / --collect-cascade / … ≈  stop / forest companions
```

## Implementation sketch

1. Register `--cascade` (and keep `--build-and-publish-dependencies`) on the same
   dest used by `cascade_enabled()` / `CASCADE_OPTION`.
2. Update Options Error / StopError / plan finish copy that hard-codes the long
   name to say `--cascade` (mention alias where refusal text lists the flag).
3. Antora + CHANGELOG: primary examples use `--cascade`; long form = synonym.
4. Unit tests: either spelling enables cascade; companions still require enable.
5. No behaviour change to nest argv, skip-if-current, or tip consume vs publish.

## Non-goals

- Renaming `--build-cascade-dependencies` / `--publish-cascade-dependencies`.
- Making bare `--cascade` imply nest-build or nest-publish (still need a companion).
- Removing the long form in 1.12.0.
- Forest stem keying (still deferred on the shipped cascade plan).

## Progress

| Item | Status |
|------|--------|
| Problem / settle table | Done — this proposal |
| Implementation | Done on this PR — ``--cascade`` + legacy synonym; nested drop both spellings |
| Docs / samples / tests | Done on this PR — Antora cascade page, refusal copy, unit coverage |
