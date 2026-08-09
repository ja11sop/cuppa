# Plan: `--list-toolchains`

- **Status:** in progress
- **Related:** [`ROADMAP.md`](../../ROADMAP.md) — Toolchains as dependencies; shipped design
  [`archive/toolchains-as-dependencies.md`](../archive/toolchains-as-dependencies.md); [#160](https://github.com/ja11sop/cuppa/issues/160); [`ideas/scratchpad.md`](../ideas/scratchpad.md) (graduated); console patterns
  [`archive/console-report-patterns.md`](../archive/console-report-patterns.md)
- **Updated:** 2026-08-09
- **Impact:** minor — inventory CLI + list-deps leaf label alignment for toolchain session names

## Why

After [#160](https://github.com/ja11sop/cuppa/issues/160), Cuppa can download, register, discover,
and force-wipe Clang/GCC toolchain dependencies. Operators need an inventory that answers:

- Which toolchains will Cuppa offer on this machine?
- Which came from PATH / distro discovery vs `--toolchain-archive=` / `--*-root=`?
- Where is the actual `g++` / `clang++` binary?
- Which Cuppa names (`--toolchains=`) share a driver?

`--list-dependencies` alone is not enough: it omits PATH compilers and does not emphasise driver
paths. A first slice shipped a flat table; smoke testing showed it should match the existing
ruled hierarchical reports instead.

## Goals

1. `--list-toolchains` exits without building (same family as other `--list-*` actions).
2. Two sections: **discovered** and **registered** (normal typeface section labels).
3. Hierarchical tree: family → version → driver → one or more Cuppa names.
4. Styling follows established tree principles (glyphs, subdued stems/paths, emphasised family /
   version, info+emphasised default).
5. `--list-format=json` mirrors the same hierarchy.
6. Align `--list-dependencies` toolchain **leaf labels** with the Cuppa session name used for
   `--toolchains=` (keep on-disk folder layout).
7. Make clear force-wipe applies only to Registered / managed installs.

## Non-goals

- Changing on-disk `toolchains/<family>/<qualifier>/` layout.
- Changing `toolchain_name()` / breaking existing `--toolchains=gcc17_…` pins.
- Implementing SIZE / LAST USED tracking for PATH-discovered toolchains in this slice
  (placeholders only; follow-up may record when Cuppa executes a discovered toolchain).
- MSVC coverage or MSVC-as-archive.
- `--list-toolchains` performing downloads or updates.

## Today (after first slice / #170)

| Piece | Behaviour |
|-------|-----------|
| `--list-toolchains` | Flat NAME/FAMILY/VERSION/DRIVER/STORAGE table; Discovered vs Registered |
| PATH aliases | Multiple env keys (`gcc`, `gcc15`, `gcc153`) can share one driver |
| Registered Cuppa name | `toolchain_name(family, major, qualifier)` → e.g. `gcc17_gcc_snapshot_…` |
| `--list-dependencies` leaf | Shows on-disk **qualifier** only (`gcc_snapshot_…`), not the session name |
| Force-wipe | Already accepts session id via `parse_registered_toolchain_name` |

## Settled decisions

| Topic | Decision |
|-------|----------|
| Flag | `--list-toolchains` |
| Section titles | **discovered** and **registered** (terse; normal typeface) |
| Tree shape | section → family → version → driver → name(s). A driver has one or more names. |
| Dual listing | PATH `gcc15` and managed `gcc15_…` appear in **both** sections when both exist |
| Default mark | Name equal to `platform.default_toolchain()` gets ` (default)`; that name and its parent **version** row use info+emphasised |
| Family / version colour | Family: emphasised, normal colour. Version: emphasised; info+emphasised when it owns the default name |
| Name colour | Normal; default name info+emphasised |
| Driver path | `storage.display_path()` (home → `~`); subdued |
| SIZE / LAST USED (this slice) | Discovered: `--` / untracked placeholders. Registered: inventory size/mtime under `_toolchain_dep_root` when available, else `--`. Values attach to **name** leaves (not drivers) for future PATH tracking |
| JSON | Nested sections/families/versions/drivers/names |
| Name alignment | **Option A:** keep folder layout; `--list-dependencies` toolchain leaf label becomes the Cuppa session name (`gcc17_gcc_snapshot_…`). Wipe tokens continue to accept qualifier and session id |
| Wipe messaging | Registered only |

## Refusal rules

- Do not invent wipe for PATH-discovered toolchains.
- Do not require network access for listing.
- Do not print secrets from environment into the table.
- Do not rename existing extract directories to match session names.
- Do not invent SIZE/LAST USED for PATH compilers until a real inventory path exists.

## Work slices

| ID | Slice | Notes |
|----|--------|-------|
| `list-tc-tree-model` | Pure model: group rows by section → family → version → driver → names; mark default | Unit-testable; replaces flat-only model |
| `list-tc-tree-render` | Ruled tree text: glyphs, colours, `display_path`, SIZE/LAST USED placeholders | Match `dependency_tree` / `storage_actions` patterns |
| `list-tc-json-nested` | Nested JSON matching the tree | Update unit tests |
| `list-tc-deps-leaf` | list-deps toolchain leaf label = Cuppa session name; keep path/qualifier for matching | Tests for display + wipe still matching |
| `list-tc-docs` | Update `toolchains.adoc` / CLI reference examples to the tree | |
| `list-tc-follow-inventory` | (later) Record size/last-used when Cuppa runs a discovered toolchain | Out of this PR |

## Suggested next PR

`list-tc-tree-model` + `list-tc-tree-render` + `list-tc-json-nested` + `list-tc-deps-leaf` + docs/tests
on the open 1.6.0 branch (follow-on to #170).

## Progress

| ID | Status |
|----|--------|
| `list-tc-model` (flat) | done (superseded by tree model) |
| `list-tc-cli` (flat table) | done (superseded by tree render) |
| `list-tc-json` (flat sections) | done (superseded by nested JSON) |
| `list-tc-docs` (first pass) | done (refreshed for tree) |
| `list-tc-tests` (flat) | done (rewritten for tree) |
| `list-tc-tree-model` | done |
| `list-tc-tree-render` | done |
| `list-tc-json-nested` | done |
| `list-tc-deps-leaf` | done |
| `list-tc-docs` (tree) | done |
| `list-tc-follow-inventory` | deferred |

## Open decisions

None — proceed to implementation when ready.
