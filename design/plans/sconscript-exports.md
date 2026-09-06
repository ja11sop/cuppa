# Plan: Sconscript exports and shared build products

- **Status:** in progress
- **Related:** [`ROADMAP.md`](../../ROADMAP.md) — `sconscript-exports`; blocks multi-file Cuppa layouts like CMake `add_subdirectory`; pairs with [#213](https://github.com/ja11sop/cuppa/issues/213); graph/cycle vocabulary may later share helpers with [`gitlab-package-transitive.md`](gitlab-package-transitive.md) (different graph; do not force one NetworkX model)
- **Updated:** 2026-09-06
- **Impact:** minor — opt-in Export/Import ordering and `ExportShared` / `ImportShared`; flat discovery unchanged when unused

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

This is a **design side-effect**, not an accident: early cuppa projects used one sconscript per repo or per top-level folder, with libraries declared inline or via `env.BuildWith` package deps. That default has worked for well over a decade **without** relying on `Export` / `Import`.

## Two orthogonal concerns

| Concern | Role | Default today |
|---------|------|----------------|
| **Discovery** | Which `sconscript` files participate in the session | Find `sconscript` in this folder and below (`-D` / recursive walk). **Keep this.** |
| **Explicit coupling** | Sharing products / names between those scripts via `Export` / `Import` (or a Cuppa equivalent) | **Ignored.** Discovery does not backtrack exporters; invocation order is walk order only. |

Do **not** conflate “stop discovering and use an explicit `SConscript` tree” with “support Export/Import.” Most projects never need coupling; when they do, discovery stays, and coupling adds a **dependency graph** on top.

## Goals (first slices)

1. **Document** current behaviour: discovered sconscripts are siblings for discovery purposes; `Import` of non-cuppa keys fails today; why nested `SConscript(..., exports=)` double-runs.
2. **Keep** folder-and-below discovery as the default (zero migration).
3. **Add** import/export-aware resolution: when a discovered script imports a name that no exporter in the current set provides, **widen** the search (up toward the `sconstruct` root, then across the project tree) until a matching `Export` (or Cuppa export) is found — or fail clearly.
4. **Honour** an **execution graph** derived from those edges (flat / walk order when there are no imports/exports), including under parallel configure/build where order matters.
5. **Support** native SCons `Export` / `Import` where we can make them behave correctly under discovery; **also** offer a preferred Cuppa API that is clearer and less surprising; if native cannot be made reliable, Cuppa’s API still ships.

## Non-goals (initial slices)

- Turning off discovery by default, or requiring every project to list children (Direction A as the primary model).
- Full SCons `Return()` parity with arbitrary values across arbitrary depth (may revisit later).
- Replacing `location_dependency` / `package_dependency` — those already solve sharing via `env.BuildWith`.
- Auto-wiring CMake `add_subdirectory` — see [`cmake-to-cuppa-migration.md`](cmake-to-cuppa-migration.md).
- NetworkX for the sconscript graph until a second consumer proves hand-rolled DFS insufficient (same note as GitLab transitive listing).

## Settled lean (2026-09-06)

| Topic | Decision |
|-------|----------|
| Primary direction | **B — discovery stays; add import/export coupling and an execution graph.** Not “export registry only for later scripts in walk order,” and not “explicit tree only” (A) or “scoped roots only” (C) as the main story. A/C remain optional escape hatches if a spike proves useful. |
| Default discovery | Unchanged: find `sconscript` this folder and below. Decade of projects do not need Export/Import. |
| How coupling is discovered | **Scan** discovered (and, when needed, widened) sconscript sources for `Import` / `Export` (and Cuppa equivalents). Build a **dependency graph**: importer → exporter. If an `Import` is not satisfied by any script already in the discovery set, **widen** search up to the `sconstruct` root and outward until a matching export is found. |
| Execution order | Topological order from that graph. **No edges ⇒ flat** (today’s walk). Edges impose “exporter before importer.” Parallel builds must still respect that configure-time order for scripts that share names. |
| Duplicate exporters | **Review vs SCons, then choose Cuppa policy.** SCons `Export` updates a **global** dict: calls are cumulative and a second `Export` of the same name **overwrites** (last wins) — not an error. Preferable Cuppa default for *discovered* multi-exporter collisions is likely **error** (two scripts claim the same product name under discovery is almost always a mistake); confirm in spike. Scoped `SConscript(..., exports=)` locals remain a separate SCons mechanism. |
| Native vs Cuppa API | **Both tracks.** Make native `Export`/`Import` work when the scanned graph + ordered invocation can feed SCons’s pool correctly. Prefer documenting a **Cuppa API** (`env.export` / `env.import_shared` or similar — names TBD) that is obvious and less surprising. If native cannot be made trustworthy under discovery, Cuppa API is still mandatory. |
| Preferred teaching path | Point users at the Cuppa API for new layouts; keep native for SCons-literate authors and migration. |
| Existing projects | Zero migration when they never Import/Export project products. |

### Intended model (sketch)

```text
1. Discover sconscript set S (folder-and-below), as today.
2. Scan scripts in S for Import / Export (and Cuppa twins).
3. For each unsatisfied Import name:
     widen search toward sconstruct root and across the tree;
     add any newly found exporter scripts into S (or into a
     resolve-only set — spike decides whether they must also
     be “discovered” for other reasons).
4. Build execution graph G from import→export edges.
5. Detect cycles / ambiguous multi-export (per Cuppa policy).
6. Invoke each script once, in topo order (or walk order if G flat),
   with exports available to importers (native pool and/or Cuppa map).
7. Dedupe: never run the same path twice (discovery + explicit SConscript).
```

Static scan will not catch every dynamic `Import(name)` constructed at runtime; spike should bound what we promise (string-literal Imports first) and how Cuppa’s API avoids that trap.

## Design directions (historical — for contrast)

### Direction A — Explicit tree only

- Opt out of recursive discovery; root owns all `SConscript(..., exports=...)`.
- **Pros:** Matches classic SCons docs.
- **Cons:** Breaks default discovery UX; every project must list children.
- **Status:** Escape hatch only, not the primary model.

### Direction B — Discovery + import/export graph (chosen lean)

- Keep discovery.
- Scan + widen + execution graph as above.
- Cuppa preferred API + native support where feasible.
- **Pros:** Matches how Cuppa projects already work; Export/Import becomes an opt-in coupling layer.
- **Cons:** Needs a reliable scan; order and collision policy must be explicit; parallel configure must respect G.

### Direction C — Scoped discovery roots

- `cuppa.run(projects=[...])` entrypoints that nest `SConscript` themselves.
- **Pros:** No magic merging.
- **Cons:** Two mental models.
- **Status:** Possible later opt-in; not required if B’s widen search covers Capylike layouts.

## Work slices

| Slice | Deliverable | Depends on |
|-------|-------------|------------|
| `scons-export-doc` | Antora: discovery vs coupling; why `Import('capy_libs')` fails today; SCons last-wins vs Cuppa collision policy (once settled) | — |
| `scons-export-spike` | Prototype scan + widen + topo invoke; fixture (lib sconscript + `test/sconscript`); try native `Export`/`Import` and a Cuppa API sketch; settle multi-export and dynamic-Import limits | — |
| `scons-export-dedupe` | Never double-run a path (discovery + explicit `SConscript`) | spike |
| `scons-export-graph` | Execution graph as product behaviour (flat default; ordered when coupled); cycle / collision errors | spike |
| `scons-export-api` | Ship preferred Cuppa API + native path as far as spike allows + integration tests | graph, dedupe |
| `scons-export-capy` | Re-enable Boost.Capy `test/sconscript` split (external validation) | [#213](https://github.com/ja11sop/cuppa/issues/213), api |

## Open questions

- Exact Cuppa method names beyond shipped `ExportShared` / `ImportShared`.
- How much of a static scan is enough (AST vs regex vs execute-with-stubs)? Dynamic `Import(name)` remains unsupported.
- Agent / CMake migration docs: teach Cuppa API first.

## Settled (this slice)

| Topic | Decision |
|-------|----------|
| `--scripts=` + missing exporter | **Widen by default** under the sconstruct (multi-hop fixed point). |
| Refuse widen | **`--strict-sconscript-exports`** — Import must be satisfied by the already-selected set. |
| Widened scripts | Join the run set (exporters execute, not resolve-only). |
| Variant / toolchain scope | **`ExportShared` / `ImportShared` are keyed by `tool_variant_dir`** (toolchain + variant + arch + abi). Same export name under `--dbg` and `--rel` (or two toolchains) keeps distinct values. **This is a concrete reason the Cuppa API exists above native SCons `Export` / `Import`**, whose global pool is last-wins across the configure pass and cannot honour variants safely. Native `Export` is still updated best-effort for migration; product code should use `ImportShared`. |
| Graph nodes for scan/order | Script paths only (order is the same for every variant); **values** are per-variant via the Cuppa registry. |

## Progress snapshot

| Slice | Status |
|-------|--------|
| Problem validated on Boost.Capy | done (2026-08-17) |
| Lean: discovery + import/export graph (B) | settled in plan 2026-09-06 |
| `scons-export-doc` | Concepts + Building / CLI reference for widen, strict, and variant-aware Cuppa API |
| `scons-export-spike` | `sconscript_coupling` scan / multi-hop widen / topo + variant-scoped `ExportShared` / `ImportShared`; `Construct.build` wired |
| `--scripts=` + strict + clean path form | Covered by unit + integration tests |
| Variant-aware shared exports | Covered (`tool_variant_dir` scope; `--dbg --rel` integration) |
| `scons-export-dedupe` | Not started (explicit `SConscript` + discovery double-run) |
| `scons-export-capy` | Not started |
