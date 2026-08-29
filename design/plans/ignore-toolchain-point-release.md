# Plan: optional toolchain point-release coarsening (variants and packages)

- **Status:** proposal
- **Related:** [`ROADMAP.md`](../../ROADMAP.md) — `tc-identity-coarsen`; package stems in [`cuppa/package_managers/gitlab.py`](../../cuppa/package_managers/gitlab.py); layout in [`cuppa/core/build_layout.py`](../../cuppa/core/build_layout.py) / [`cuppa/construct.py`](../../cuppa/construct.py) (`tool_variant_dir` vs `package_tool_variant_dir`); list-toolchains identity [`list-toolchains.md`](../archive/list-toolchains.md)
- **Updated:** 2026-08-30
- **Impact:** minor — new opt-in CLI / `cuppa.run` / configure keys; default keeps today's full toolchain identity

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

1. Let a project **opt in** to ignore point-release digits when forming **variant** paths,
   **package** identities, or **both**.
2. Keep **full identity as the default** (no behaviour change until enabled).
3. Keep **selection** and **reporting** honest: `--list-toolchains`, logs, and describe output still
   show what compiler was actually found (15.3), even when layout keys as `gcc15`.
4. Document the **compatibility risk**: coarsening asserts that point releases are interchangeable
   for that project's binaries and packages.

## Non-goals

- Changing SemVer of *software* packages Cuppa publishes (`1.2.3` product versions).
- Boost `-patched` / `-clean` package flavour identity ([`boost-updates.md`](boost-updates.md)).
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

## Proposed product shape (open options)

Prefer one clear policy object, applied in two places:

```text
toolchain identity policy:
  full          — today's behaviour (default)
  major         — drop point release in encoded names (gcc153 → gcc15)
```

### Controls (sketch — settle before implementation)

| Mechanism | Sketch |
|-----------|--------|
| CLI | `--toolchain-identity=full\|major` (name TBD) |
| `cuppa.run` / `configure.conf` | Same key; project-default for all developers |
| Scope flags (if both axes needed) | Either one switch affecting **both** variants and packages, or `--toolchain-identity-variants=` / `--toolchain-identity-packages=` (or a single enum: `full`, `major`, `major-packages-only`, …) |

**Recommendation to validate in implementation spike:** start with **one switch that coarsens both
`name()` and `package_name()` together** (simplest mental model). Add split axes only if fleets
need “coarse packages, fine-grained local `_build`” (or the reverse).

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
| Default to coarse identity | Refuse for 1.x — opt-in only |
| Coarsen without documenting ABI risk | Refuse |
| Versioned SCons-style churn of option names mid-cycle | Settle CLI vocabulary in this plan before the first PR |

## Work slices (later)

| ID | Deliverable | Notes |
|----|-------------|-------|
| `tc-id-vocab` | Settle CLI / config names and whether variants+packages share one switch | Short settled-decisions table |
| `tc-id-helper` | Shared helper: reported version → full vs coarse token (GCC/Clang/MSVC) | Unit-tested encoding |
| `tc-id-apply` | Wire into `name()` / `package_name()` or construct path composition | Honour existing `package_tool_variant_dir` split |
| `tc-id-tests` | Unit + integration: same project, full vs major, package stem + `_build` path | Multi-toolchain cell |
| `tc-id-docs` | Toolchains + Packages pages; CHANGELOG; warn about republish | Antora |
| `tc-id-migrate` | Optional notes / helpers for renaming stems (doc-only first) | Not automatic rewrite |

## Acceptance criteria

1. Default builds and package names **unchanged** without the new option.
2. With coarsening enabled, `_build` and/or package stems use major-line tokens; selecting `gcc15`
   on 15.2 and 15.3 machines can share those keys.
3. `--list-toolchains` / describe still expose the **real** compiler version.
4. Docs state the trade-off and that this is **not** Boost patched/clean or product SemVer.
5. Integration coverage for at least GCC or Clang on Linux.

## Candidacy

| Factor | Assessment |
|--------|------------|
| User value | **High** for package fleets and shared CI caches |
| Risk | Medium — identity bugs are costly; keep opt-in |
| Size | Medium (encoding + construct/package wiring + docs) |
| Release impact | `minor` |

Good follow-on after current docs/Methods work; not blocked by Methods split.
