# Plan: `--list-toolchains`

- **Status:** proposal
- **Related:** [`ROADMAP.md`](../../ROADMAP.md) — Toolchains as dependencies; shipped design
  [`archive/toolchains-as-dependencies.md`](../archive/toolchains-as-dependencies.md); [#160](https://github.com/ja11sop/cuppa/issues/160); [`ideas/scratchpad.md`](../ideas/scratchpad.md) (graduated)
- **Updated:** 2026-08-09
- **Impact:** minor — new inventory CLI; no change to how toolchains are selected for builds

## Why

After [#160](https://github.com/ja11sop/cuppa/issues/160), Cuppa can download, register, discover,
and force-wipe Clang/GCC toolchain dependencies. There is still no dedicated inventory command
analogous to `--list-dependencies` / `--list-builds` that answers:

- Which toolchains will Cuppa offer on this machine?
- Which came from PATH / distro discovery vs `--toolchain-archive=` / `--*-root=`?
- Where is the actual `g++` / `clang++` binary?

Users who call the driver outside Cuppa (IDE, scripts, `compile_commands`) need the path.
Operators who manage `dependencies_root/toolchains/` need a list before wipe.

## Goals

1. Add `--list-toolchains` that exits without building (same family as other `--list-*` actions).
2. Show **two sections** (exact headings TBD — settle vocabulary before coding):
   - Automatically discovered (PATH / toolchain class probes).
   - Manually registered / managed (archive extracts and external `--*-root=` registrations under
     `dependencies_root/toolchains/{clang,gcc}/`, including `cuppa-toolchain.json` externals).
3. For each row: Cuppa name (for `--toolchains=`), family, version/major where known, **absolute
   driver path**, and storage path when managed.
4. Make clear that **force-wipe / removal of toolchain deps applies only to the managed
   section** (already true for `[toolchain]…`; the list must not imply PATH compilers are wiped).
5. Optional `--list-format=json` for agents, consistent with other list commands.

## Non-goals

- Changing discovery or registration rules from the shipped toolchain-deps work.
- Implementing MSVC coverage or MSVC-as-archive (separate roadmap rows).
- `--list-toolchains` performing downloads or updates.
- Replacing `--toolchains=` selection UX.

## Today

| Piece | Behaviour |
|-------|-----------|
| PATH / versioned drivers | Toolchain classes (`gcc`, `clang`, …) probe and register supported names |
| `--toolchain-archive=` / `--clang-root=` / `--gcc-root=` | Prepare + register non-colliding names; persist externals |
| `discover_cached` | Re-registers installs under `dependencies_root/toolchains/{clang,gcc}/` |
| `--list-dependencies` | Can show type `toolchain` rows for managed installs |
| Dedicated toolchain inventory | No |

`--list-dependencies` is not enough: it does not surface PATH-discovered compilers or emphasise
driver paths for day-to-day toolchain ops.

## Settled decisions (propose)

| Topic | Decision |
|-------|----------|
| Flag | `--list-toolchains` (parallel naming to `--list-dependencies` / `--list-builds`) |
| Section names | Prefer **discovered** vs **registered** (or **managed**) in the first draft; avoid vague “automatic” alone. Final strings in CLI help + docs in the same PR as behaviour |
| Row identity | Cuppa toolchain name as the primary key (what you pass to `--toolchains=`) |
| Driver path | Absolute path to the C++ driver Cuppa would use (`g++` / `clang++` / …) |
| Sort | Group by section; within section sort by name |
| JSON | `--list-format=json` emits sections + rows; stable field names for agents |
| Interaction with build | Listing only; mutually exclusive with build like other list actions |
| Wipe messaging | Footer or column note: managed rows may be force-wiped with `[toolchain]…`; discovered PATH rows are not Cuppa-owned |

## Refusal rules

- Do not invent wipe for PATH-discovered toolchains.
- Do not require network access for listing.
- Do not print secrets from environment into the table.

## Work slices

| ID | Slice | Notes |
|----|--------|-------|
| `list-tc-model` | Pure report model: classify registered vs discovered; gather name, family, version, driver, storage | Unit-testable without full Construct |
| `list-tc-cli` | Wire `--list-toolchains` + text table; exit before build | Match console report patterns where cheap |
| `list-tc-json` | `--list-format=json` | Same PR if small |
| `list-tc-docs` | `toolchains.adoc` + CLI reference | Examples with archive + PATH |
| `list-tc-tests` | Unit + light integration (plant a fake registered prefix) | |

## Suggested first PR

`list-tc-model` + `list-tc-cli` + docs; JSON in the same PR if the table shape is stable.

## Open decisions (confirm before coding)

1. Exact section titles (“Discovered” / “Registered” vs longer phrases).
2. Whether distro `gcc15` that also has a managed `gcc15_…` snapshot appears in **both**
   sections (yes — different Cuppa names and paths) or is coalesced (no — keep both rows).
