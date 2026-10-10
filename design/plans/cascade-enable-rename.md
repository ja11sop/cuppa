# Plan: Rename cascade master flag

- **Status:** done
- **Related:** [`ROADMAP.md`](../../ROADMAP.md) — `cascade-enable-rename`; shipped cascade [`package-build-publish-deps.md`](../archive/package-build-publish-deps.md) ([#297](https://github.com/ja11sop/cuppa/issues/297)); companions `--build-cascade-dependencies` / `--publish-cascade-dependencies`
- **Updated:** 2026-10-10
- **Impact:** `minor` (CLI rename / alias; behaviour unchanged)
- **PR:** [#361](https://github.com/ja11sop/cuppa/pull/361)

## Problem

`--build-and-publish-dependencies` was the **master switch** that enables package-DAG
cascade (resolve publisher trees, allow nest sessions). It does **not** mean
“you will upload.” End-state is chosen by a companion:

| Companion | Nested deps | Tip | Registry upload? |
|-----------|-------------|-----|------------------|
| `--cascade-plan` / collect / update | review / forest | usually stop | no |
| `--build-cascade-dependencies` | nest-build | tip build only | **no** |
| `--publish-cascade-dependencies` | nest-publish | tip build only | yes (deps) |
| `--publish-package` | nest-publish | tip upload too | yes |

Operators who want “build deps and consume them as-if published” correctly pass
the master enable plus `--build-cascade-dependencies`, but the old master name
implied publish. That naming stuck from the first design (cascade ≈ build
**and** publish); nest-build without upload landed later ([#339](https://github.com/ja11sop/cuppa/pull/339)).

## Settled direction

| Question | Decision |
|----------|----------|
| Primary spelling | **`--cascade`** — short master enable; matches how operators already talk (“pass `--cascade`”) |
| Old flag | **`--build-and-publish-dependencies`** is a **deprecated CLI alias** on the same dest (`cascade`); **remove in Cuppa 2.0**. Product docs: one IMPORTANT admonition only (not in main prose / samples). `--help`: short “Deprecated alias of --cascade” |
| Companions | Unchanged names and refuse rules (still require the master enable) |
| Docs / samples | Antora and generated samples use **`--cascade` only** (plus the deprecation admonition) |
| Help / refusals | Master and companions name `--cascade`; nested drop still strips the legacy spelling |
| Code | `CASCADE_OPTION = "cascade"` (dest); `CASCADE_OPTION_LEGACY` kept for nested drop / banner emphasise until 2.0 |
| Historical design plans | **Do not rewrite** archive / past CHANGELOG entries that document the old flag name |

Refuse inventing a third parallel name (`--enable-cascade`, `--cascade-dependencies`)
in the same PR — one primary + one deprecated alias is enough.

## Mental model (after)

```text
--cascade                              ≈  enable cascade machinery
--build-cascade-dependencies           ≈  nest-build, no upload   ← as-if published
--publish-cascade-dependencies         ≈  nest-upload, tip build only
--publish-package                      ≈  nest-upload + tip upload
--cascade-plan / --collect-cascade / … ≈  stop / forest companions
```

## Implementation sketch

1. Register `--cascade` (`dest=cascade`) and keep `--build-and-publish-dependencies`
   as deprecated alias on the same dest.
2. Options Error / StopError / plan finish copy use `--cascade`.
3. Antora + samples: `--cascade` only; one deprecation admonition for the old name.
4. Unit tests: primary dest `cascade`; coverage that nested argv still drops the legacy spelling.
5. No behaviour change to nest argv, skip-if-current, or tip consume vs publish.

## Non-goals

- Renaming `--build-cascade-dependencies` / `--publish-cascade-dependencies`.
- Making bare `--cascade` imply nest-build or nest-publish (still need a companion).
- Removing the long form before 2.0.
- Rewriting shipped design-archive history that named the old flag.
- Forest stem keying (still deferred on the shipped cascade plan).

## Progress

| Item | Status |
|------|--------|
| Problem / settle table | Done — this proposal |
| Implementation | Done on [#361](https://github.com/ja11sop/cuppa/pull/361) — ``--cascade`` dest + deprecated alias; nested drop both spellings |
| Product docs / samples / tests | Done — admonition-only deprecation; archive plans left historical |
| Soak / close-out | Done — naming settled as ``--cascade`` (not ``--cascade-dependencies``) |
