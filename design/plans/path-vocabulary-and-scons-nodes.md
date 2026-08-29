# Plan: Shared path vocabulary and SCons node helpers

- **Status:** proposal
- **Related:** [`ROADMAP.md`](../../ROADMAP.md) — follow-on to `static-glob`; [`recursive-glob-parity.md`](recursive-glob-parity.md); [#232](https://github.com/ja11sop/cuppa/issues/232); [#231](https://github.com/ja11sop/cuppa/pull/231)
- **Updated:** 2026-08-29
- **Impact:** patch — internal reuse / small call-site cleanups; no new discovery API

## Problem

RecursiveGlob / GlobFiles work in [#231](https://github.com/ja11sop/cuppa/pull/231) introduced solid helpers for Cuppa’s `#/` / sconscript-relative path dialect and for VariantDir-safe SCons node identity (`srcnode`, `rfile`, `isinstance(Dir)`). Most of that logic still lives as private functions beside discovery. Other methods reinvent thin slices (for example coverage `#` clean patterns, `CopyFiles` destination `#` checks) or will keep tripping on absolute-vs-relative node forms.

## Settled decisions

| Decision | Choice |
|----------|--------|
| Reuse RecursiveGlob’s **Repository / `Dir.entries` tree walk** in other methods | **No** — discovery stays in RecursiveGlob / GlobFiles; Compile and friends consume node lists |
| Share **path vocabulary** (`#/` / sconscript-relative / absolute) | **Yes** — widen `cuppa.utility.glob_roots` (or rename to a neutral module) |
| Share **node identity** helpers (`srcnode` / `rfile` / dir class check / dedupe key) | **Yes** — small `cuppa.utility.scons_nodes` (name TBD) when a second call site needs them |
| Push Repository search into Compile / Copy / etc. | **No** — callers keep discovering via RecursiveGlob / GlobFiles / Glob |

## Catalogue (from #231)

| Helper | Today | Reuse candidates |
|--------|-------|------------------|
| `resolve_glob_start` / `relative_glob_start` / `#` strip | `glob_roots.py` | Coverage `#` clean patterns; `CopyFiles` destinations; any future “project path” API |
| `_start_dir_node` | private on discovery | Only if another API needs VariantDir-safe `Dir` for a resolved start |
| `_source_node` / `_node_key` / `_is_dir_node` / `_is_mergeable_declared_file` | private on discovery | Filter edge cases; `object_target_for` if absolute/`srcnode` bugs return; any list dedupe of File nodes |
| `_files_from_dir_entries` / `_files_from_repository_tree` | private on discovery | **Keep private** — no second discovery consumer |
| `_node_path_forms` | `filter.py` | Already shared for Filter; leave unless path-form matching spreads |

## Phases

### Phase A — Path vocabulary (preferred first)

1. Public (or clearly documented) resolve helper for a single path string with the same `#/` / sconscript-relative / absolute rules as `resolve_glob_start` (may be a thin wrapper that does not require a `start=` sentinel).
2. Replace one-off `#` joins in coverage clean handling and align `CopyFiles` destination `#` handling with that helper.
3. Unit tests stay in `test_glob_roots.py` (extend); no behaviour change for RecursiveGlob.

### Phase B — SCons node helpers (when needed)

1. Extract `_source_node`, `_node_key`, `_is_dir_node` (and only what call sites need) to `cuppa.utility.scons_nodes`.
2. Point RecursiveGlob at the shared module; optionally Filter / `object_target_for` if a concrete bug or duplication appears.
3. Move or mirror the existing fakes from `test_relative_recursive_glob.py` into unit tests for the new module.

### Non-goals

- A second public recursive discovery API.
- Teaching other methods to walk Repositories themselves.
- Broad refactor of Jinja / variables / modules path rebasing (different “outside build dir” problem).

## Progress snapshot

| Slice | Status |
|-------|--------|
| Assessment vs RecursiveGlob helpers | **done** (chat / this plan) |
| Phase A path vocabulary | not started |
| Phase B scons_nodes extract | not started (optional / demand-driven) |

## References

- [`cuppa/utility/glob_roots.py`](../../cuppa/utility/glob_roots.py)
- [`cuppa/methods/relative_recursive_glob.py`](../../cuppa/methods/relative_recursive_glob.py)
- [`cuppa/utility/filter.py`](../../cuppa/utility/filter.py)
- Parent discovery plan: [`recursive-glob-parity.md`](recursive-glob-parity.md)
