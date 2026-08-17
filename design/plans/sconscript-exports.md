# Plan: Sconscript exports and shared build products

- **Status:** proposal
- **Related:** [`ROADMAP.md`](../../ROADMAP.md) — `sconscript-exports`; blocks multi-file Cuppa layouts like CMake `add_subdirectory`; pairs with [#213](https://github.com/ja11sop/cuppa/issues/213)
- **Updated:** 2026-08-17

## Problem

Cuppa discovers **every** `sconscript` under the launch directory and invokes each with the same per-variant `env`, but **without** SCons `exports=` from a parent script ([`construct.py`](../../cuppa/construct.py) `call_project_sconscript_files` → `SCons.Script.SConscript(..., exports=sconscript_exports)` where `sconscript_exports` is only the standard cuppa keys: `env`, `build_root`, …).

A natural CMake-shaped layout:

```text
sconstruct
sconscript          # libraries
test/sconscript     # imports capy_libs from parent
```

does not work:

```python
# test/sconscript
Import('env', 'capy_libs')   # Import of non-existent variable 'capy_libs'
```

Manual `SConscript('test/sconscript', exports=[...])` inside a root sconscript **also fails** today because Cuppa **still auto-discovers** `test/sconscript` and runs it a second time without exports.

This is a **design side-effect**, not an accident: early cuppa projects used one sconscript per repo or per top-level folder, with libraries declared inline or via `env.BuildWith` package deps.

## Goals (exploration — first slice)

1. **Document current behaviour** in Antora (`concepts.adoc` or `methods.adoc`): discovered sconscripts are siblings, not a tree with inherited exports.
2. **Choose a direction** for enabling CMake-like decomposition without duplicate invocation.
3. **Spike** the smallest API that unblocks a real consumer (Boost.Capy Cuppa sketch): shared static libs built once, tests in `test/sconscript`.

## Non-goals (initial slice)

- Full SCons `Return()` parity with arbitrary values across arbitrary depth.
- Replacing `location_dependency` / `package_dependency` — those already solve sharing via `env.BuildWith`.
- Auto-wiring CMake `add_subdirectory` — see [`cmake-to-cuppa-migration.md`](cmake-to-cuppa-migration.md).

## Settled decisions (to confirm before implementation)

| Question | Options | Working bias |
|----------|---------|--------------|
| Discovery vs explicit tree | (A) Only run sconscripts reached from explicit `SConscript()` calls; (B) discovery + optional `exports` registry; (C) discovery with parent path hints | **B or C** — keep `-D` descent ergonomics, add export map |
| Export surface | SCons `Export()` / `Import()` only vs cuppa `env.export('name', nodes)` | Start with **SCons-native** where possible |
| Duplicate invocation | Skip auto-discovery when a path was already loaded with exports | **Yes** — required for nested layout |
| Default | Single root sconscript remains valid | **Unchanged** — zero migration for existing projects |

## Design directions (to compare in spike)

### Direction A — Explicit tree only

- Turn off recursive sconscript discovery when `sconstruct` sets `cuppa.run(discover_sconscripts=False)` or equivalent.
- Root `sconscript` owns all `SConscript('test/sconscript', exports=...)`.
- **Pros:** Matches SCons docs; predictable.
- **Cons:** Breaks `--scripts=` / default discovery UX; every project must list children.

### Direction B — Export registry on `env`

- Root sconscript: `env.export('capy_libs', [lib_a, lib_b])`.
- Cuppa merges exported names into `sconscript_exports` for **later** discovered scripts (discovery order = tree walk order).
- Child: `Import('env', 'capy_libs')` or `env.import_shared('capy_libs')`.
- **Pros:** Minimal change to discovery; fits cuppa's `env` methods style.
- **Cons:** Order-dependent; needs clear rules when exports collide.

### Direction C — Scoped discovery roots

- `cuppa.run(projects=['sconscript'])` — only listed entrypoints; entrypoints call nested `SConscript` themselves.
- Keeps today’s default discovery for legacy repos via opt-out flag.
- **Pros:** No magic export merging.
- **Cons:** Two mental models (discovered vs rooted).

## Work slices

| Slice | Deliverable | Depends on |
|-------|-------------|------------|
| `scons-export-doc` | Antora: how discovery works; why `Import('capy_libs')` fails today | — |
| `scons-export-spike` | Choose A/B/C; prototype in a fixture (lib sconscript + test sconscript) | — |
| `scons-export-dedupe` | Do not double-run a sconscript path (explicit + discovery) | spike |
| `scons-export-api` | Ship chosen API + integration test | dedupe |
| `scons-export-capy` | Re-enable Boost.Capy `test/sconscript` split (external validation) | [#213](https://github.com/ja11sop/cuppa/issues/213) |

## Open questions

- Should exports be variant-scoped automatically (they must be — lib nodes are per variant)?
- Interaction with `--scripts=` filtering: do exports from a skipped parent still exist?
- How do agents discover the pattern? → tie-in with CMake migration guide.

## Progress snapshot

| Slice | Status |
|-------|--------|
| Problem validated on Boost.Capy | done (2026-08-17) |
| Plan | this document |
| Implementation | not started |
