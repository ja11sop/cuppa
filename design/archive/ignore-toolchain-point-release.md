# Plan: optional toolchain point-release coarsening (variants and packages)

- **Status:** shipped
- **Related:** product shape [`build-and-package-identity.md`](build-and-package-identity.md); [`ROADMAP.md`](../../ROADMAP.md) — `tc-identity-coarsen`; package stems in [`cuppa/package_managers/gitlab.py`](../../cuppa/package_managers/gitlab.py); layout in [`cuppa/core/build_layout.py`](../../cuppa/core/build_layout.py) / [`cuppa/construct.py`](../../cuppa/construct.py) (`tool_variant_dir` vs `package_tool_variant_dir`); list-toolchains identity [`list-toolchains.md`](list-toolchains.md)
- **Updated:** 2026-09-02
- **Impact:** minor — see [`build-and-package-identity.md`](build-and-package-identity.md) (new-install `major`; grandfather `full` in `~/.cuppaconfig`)

## Problem

Cuppa embeds the compiler's **reported major.minor** into the toolchain session name that drives
build paths and package archives — for example GCC 15.3 → `gcc153`, Clang 21.1 → `clang211`
(plus stdlib tags such as `-libc++` where applicable). That name appears in:

| Surface | Example |
|---------|---------|
| `_build/…/<toolchain>/<variant>/<arch>/<abi>/` | `…/gcc153/dbg/x86_64/cxx2c/` |
| Flat artefact offsets | `flat_tool_variant_dir_offset` |
| GitLab package stems | `widget_debian_gcc153_rel_x86_64_cxx2c.tar.gz` |
| Package extract / cache trees | `<dependencies_root>/<tool_variant>/…` |

When a distro or toolchain archive bumps only the **point release** (15.2 → 15.3, 21.1 → 21.2),
Cuppa treats it as a **new identity**. Local `_build` trees fork; published packages no longer
match consumers; CI and developer machines churn downloads and republishes even when the ABI and
flags are effectively the same.

Family aliases (`gcc15`, `clang21`) already exist for **selection**, but once resolved, the
**layout and package identity still use the full reported name**. Users cannot choose “treat this
as gcc15 for paths and packages.”

This is a **usability** gap for long-lived package registries and multi-machine fleets more than
a correctness bug — the full identity is the safer default for reproducibility.

## Vocabulary (settled for this plan)

| Term | Meaning here |
|------|----------------|
| **Point release** | The trailing digit(s) after the language major in Cuppa's encoded name (`gcc153` → point `3`; `clang211` → point `1`). Users often say “patch”; GCC/Clang versioning is not SemVer patch, so prefer **point release** in docs. |
| **Full identity** | Today's `toolchain.name()` / `package_name()` (e.g. `gcc153`, `clang21-libc++`). |
| **Coarse identity** | Major-line identity used for layout/packages when opted in (e.g. `gcc15`, `clang21`, still honouring stdlib tags). |
| **Variants** | Build-tree `tool_variant_dir` and related `_build` / artefact path segments. |
| **Package versioning** | Package archive stems, `tool_variant()` in GitLab naming, extract dirs under the dependencies root — anything keyed by `package_name()` / `package_tool_variant_dir`. |

## Goals

1. Let a project choose to ignore point-release digits when forming **variant** paths and
   **package** identities (one switch — see umbrella plan).
2. Keep **selection** and **reporting** honest: `--list-toolchains`, logs, and describe output still
   show what compiler was actually found (15.3), even when layout keys as `gcc15`.
3. Document the **compatibility risk**: coarsening asserts that point releases are interchangeable
   for that project's binaries and packages.
4. Default / grandfather rules live in [`build-and-package-identity.md`](build-and-package-identity.md)
   (not “full forever for everyone”).

## Non-goals

- Changing SemVer of *software* packages Cuppa publishes (`1.2.3` product versions).
- Boost `-patched` / `-clean` package flavour identity ([`boost-updates.md`](../plans/boost-updates.md)).
- Auto-migrating existing `_build` or registry archives (project-local cleanup / republish).
- Hiding point releases from toolchain discovery or `--toolchains=gcc153` pins.

## Observed hooks in code today

Worth preserving in any design:

- `construct.py` already sets **`tool_variant_dir`** from `toolchain.name()` and
  **`package_tool_variant_dir`** from `toolchain.package_name()`.
- For GCC/Clang, `package_name()` currently **equals** `name()`, so the two paths stay locked.
- Coarsening can therefore diverge build layout from package stems **without** inventing a third
  path vocabulary — by teaching `name()` and/or `package_name()` (or a shared identity helper)
  about a project policy.

## Proposed product shape

**Settled in [`build-and-package-identity.md`](build-and-package-identity.md)** (do not re-open
here): `--toolchain-identity=full|major` coarsens both `name()` and `package_name()`; new installs
(no `~/.cuppaconfig`) default to `major`; existing globals without the key grandfather `full`.
That document also covers OS omit at publish and consume-time “similar package” overrides.

This file remains the **point-release encoding** problem, vocabulary, and code-hook notes.

### What must stay precise

- Actual compiler binary and reported version in diagnostics / Profiles / coverage metadata.
- Ability to **pin** `--toolchains=gcc153` for CI that needs the fine identity.
- Stdlib / ABI tags (`-libc++`, `cxx2c`, arch, `dbg`/`rel`/`cov`) — coarsening only touches the
  **version digits** in the toolchain token, not variant/arch/abi.

## Risks and refusal rules

| Risk | Mitigation |
|------|------------|
| Silent mix of 15.2 and 15.3 objects in one tree | Document; optional warn when reported version ≠ coarse key; `--clean` / remove-builds when switching policy |
| Registry already published under `gcc153` | Coarse consumers look for `gcc15_…` stems — need republish or dual-publish transition notes |
| MSVC / `vc` encoding differs | Spec identity rules per family in the spike; do not assume `major+minor` digit paste |
| “Ignore patch” misread as Cuppa package SemVer | Docs vocabulary: **toolchain point release**, not product patch |

| Request | Response |
|---------|----------|
| Silent `major` for existing `~/.cuppaconfig` without backfill | Refuse in 1.x — see umbrella plan |
| Coarsen without documenting ABI risk | Refuse |
| Versioned SCons-style churn of option names mid-cycle | Refuse — names settled in [`build-and-package-identity.md`](build-and-package-identity.md) |

## Work slices

Slice IDs and PR split live in [`build-and-package-identity.md`](build-and-package-identity.md)
(`tc-id-*`, consume overrides, OS omit). This document does not keep a second slice table.

## Acceptance criteria

See [`build-and-package-identity.md`](build-and-package-identity.md) (PR A). Encoding-specific:
`--list-toolchains` / describe still expose the **real** compiler version; coarsening only
touches version digits in the toolchain token, not variant/arch/abi/stdlib tags.

## Candidacy

| Factor | Assessment |
|--------|------------|
| User value | **High** for package fleets and shared CI caches |
| Risk | Medium — identity bugs are costly; grandfather existing globals |
| Size | Medium (encoding + construct/package wiring + docs) |
| Release impact | `minor` |

Product shape and PR split: [`build-and-package-identity.md`](build-and-package-identity.md).
