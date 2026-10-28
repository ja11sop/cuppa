# Plan: Supported toolchain version currency

- **Status:** proposal
- **Related:** [`ROADMAP.md`](../../ROADMAP.md) — Toolchains; [`list-toolchains.md`](../archive/list-toolchains.md);
  [`list-toolchains-verbose.md`](list-toolchains-verbose.md); Antora
  [`toolchains/gcc.adoc`](../../docs/modules/ROOT/pages/toolchains/gcc.adoc) /
  [`clang.adoc`](../../docs/modules/ROOT/pages/toolchains/clang.adoc) /
  [`msvc.adoc`](../../docs/modules/ROOT/pages/toolchains/msvc.adoc);
  `cuppa/toolchains/{gcc,clang,cl}.py` `supported_versions`; CI
  [`.github/workflows/test.yml`](../../.github/workflows/test.yml)
- **Updated:** 2026-10-28
- **Impact:** patch — register new aliases / refresh docs ceilings; CI default
  bump is optional and called out separately (may be minor if runners change)

## Problem

Cuppa’s `supported_versions` lists and family Antora pages drift behind upstream
releases. Operators hit “toolchain not recognised” for a current `clang23` /
point-release alias even though the binary is on `PATH`, while docs still say
“through clang22 / gcc16”. CI may also lag the newest stable the project
actually soaks on tip machines.

## Intent

1. Periodically review **GCC**, **Clang/LLVM**, and **MSVC** against upstream
   stables and Cuppa’s registered aliases.
2. Add missing major / point-release names Cuppa’s naming rules already imply
   (e.g. `clang23`, `clang231`, …; `gcc163` when it ships).
3. Keep Antora family pages’ “through **…**” ceilings honest.
4. Decide whether the **Actions integration default** (today GCC 15 on Ubuntu)
   should move — separately from registering aliases.

## Non-goals

- Auto-chasing “latest” at runtime (`tc-dep-latest` stays out of scope).
- Dropping old aliases (grandfather forever unless a separate retirement plan).
- Expanding CI to every point release.
- Changing dialect defaults, Profiles flags, or modules policy.

## Snapshot (2026-10-28)

| Family | Cuppa ceiling (code / docs) | Upstream stable (approx.) | Gap |
|--------|-----------------------------|---------------------------|-----|
| GCC | `gcc16` / `gcc162` (docs: through **gcc16**) | 16.2.0 | Point-release aliases current; watch 16.3+ |
| Clang | `clang22` / `clang221` (docs: through **clang22**) | LLVM **23.1.4** | **Missing `clang23` / `clang231` (and siblings)** |
| MSVC | Installed VCs via SCons `_VCVER` | Host-dependent | Confirm newest VS / toolset aliases still parse |
| CI Linux gcc | Prefer **g++-15** from toolchain PPA | Tip soaks often use gcc15/16 | Optional: bump matrix to 16 when PPA/`ubuntu-latest` is easy |

## Settled lean

| Choice | Lean |
|--------|------|
| Where aliases live | Existing `supported_versions()` lists + any name→binary map already used |
| Docs | Update “through **N**” on family pages in the same change as the aliases |
| CI default | **Not automatic** with alias adds — separate checklist row; only bump when install is reliable |
| Cadence | Opportunistic (when a tip soak wants a new major) or once per minor cycle |
| Tests | Extend any unit coverage that freezes the supported set / name parsing |

## Progress

| Item | Status |
|------|--------|
| Gap captured | Done — this proposal |
| Add Clang 23 aliases + Antora ceiling | Open |
| GCC point-release check (16.3+ / 17 when present) | Open |
| MSVC / VS alias smoke on Windows CI host | Open |
| CI gcc default bump decision | Open — optional |
| Fold post-#376 consume plan → `done` | Done — this housekeeping change |
