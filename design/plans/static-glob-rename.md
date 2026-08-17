# Plan: StaticGlob — rename source discovery by evaluation model

- **Status:** proposal
- **Related:** [`ROADMAP.md`](../../ROADMAP.md) — `static-glob`; [#213](https://github.com/ja11sop/cuppa/issues/213); [`cmake-to-cuppa-migration.md`](cmake-to-cuppa-migration.md)
- **Updated:** 2026-08-17
- **Impact:** minor — new names and optional cuppa `Glob` wrapper; existing `RecursiveGlob` / `GlobFiles` remain as deprecated aliases for at least one cycle

## Problem

Cuppa today exposes two **eager** Python helpers whose names describe **shape**, not **when** the file list is fixed:

| Today | Implementation | Name suggests |
|-------|----------------|---------------|
| `env.RecursiveGlob` | `os.walk` + fnmatch | “recursive glob” |
| `env.GlobFiles` | `os.listdir` + fnmatch | “glob files” |

Both snapshot the filesystem **once**, when the sconscript line runs during the initial read phase. New files under the tree do not appear until configure re-runs.

SCons **`env.Glob`** (including `**` since SCons 4) is **lazy**: directory-aware nodes that can be re-evaluated with the build graph. That is a different contract — but the current cuppa names do not help users choose.

`RecursiveGlob` originally filled a hard gap (no `**`, need to skip `_build` / dependency trees). The gap is narrower now; the **evaluation-model** distinction matters more than “recursive vs not”.

## Proposal

Introduce a pair of documented discovery options:

| API | Evaluation | Implementation direction |
|-----|------------|---------------------------|
| **`env.Glob(...)`** | Dynamic (SCons) | Document native SCons `env.Glob` / optional thin cuppa wrapper with shared path rules and default exclusions for `**` |
| **`env.StaticGlob(...)`** | Static (configure-time snapshot) | Rename/refactor today’s `RecursiveGlob` + `GlobFiles`; one method, `recursive=` (or `depth=`) instead of two names |

**Do not** silently change `RecursiveGlob` to delegate to SCons `**` — that alters when new sources appear (subtle breaking change).

### StaticGlob shape (sketch)

```python
# Was RecursiveGlob('*.cpp', start='src')
sources = env.StaticGlob('*.cpp', start='src')

# Was GlobFiles('*_test.cpp', start='tests')
tests = env.StaticGlob('*_test.cpp', start='tests', recursive=False)
```

Keep cuppa-only knobs on the static side only:

- `start=` — root of walk (see [Path vocabulary](#path-vocabulary))
- `exclude_dirs=` — directory **name** regex (default skips `_build`, dependencies root)
- `discard_pattern=` — skip subtree when marker file present

Dynamic side gets `**` and SCons directory dependencies; not `discard_pattern`.

## Path vocabulary

Users must be able to switch between dynamic and static **without rewriting path strings**.

Today path handling is split:

- **Static:** `clean_start()` / `relative_start()` in [`relative_recursive_glob.py`](../../cuppa/methods/relative_recursive_glob.py) — `start=` relative to `sconscript_dir`, optional absolutes, relpath back to `base_path` for `env.File` nodes
- **Dynamic:** SCons `#/` project-root paths, paths relative to the calling sconscript, and `env.Glob` rules — not centralized with StaticGlob

### Settled direction (proposal)

Extract a shared helper (e.g. `cuppa/paths/glob_roots.py` or extend `cuppa/utility/path.py`) used by **both** StaticGlob and any cuppa Glob wrapper:

| Input style | Meaning | Example |
|-------------|---------|---------|
| `#/…` | From project / sconstruct root | `#/src/**/*.cpp` |
| `start='src'` | Directory relative to `sconscript_dir` | `StaticGlob('*.cpp', start='src')` |
| Relative file/dir | Relative to sconscript (same as today’s `env.File('src/foo.cpp')`) | `'src/detail/a.cpp'` |
| Absolute | Allowed; documented as last resort | package / generated paths |

**Acceptance:** for a fixture tree, the **same path string** in `env.Glob('#/src/**/*.cpp')` and `env.StaticGlob('*.cpp', start='#/src')` (or equivalent) yields the same set of project-relative `File` node paths (modulo evaluation time).

Document the mapping in Antora (Methods hub + migration guide).

## Filter() and dynamic Glob

[`env.Filter`](../../cuppa/methods/filter.py) post-selects among **existing nodes** (fnmatch on `str(node)` / existence checks). It was intended to complement broad globs:

```python
# Dynamic: wide net, then cuppa filter
candidates = env.Glob('#/src/**/*.cpp')
tests = env.Filter(candidates, match='*_test.cpp', exclude='**/detail/**')
```

Follow-on work (same plan, later slice):

1. **Filter + path styles** — matching should behave consistently whether nodes came from SCons Glob or StaticGlob (today `filter_nodes` uses `str(node)`; patterns may need to match project-relative `node.path` as well as absolute `str(node)`).
2. **Filter + lazy globs** — ensure filtered SCons glob nodes remain valid dependencies (no accidental snapshot/copy).
3. **Docs** — recipe section: “dynamic Glob + Filter” vs “StaticGlob with pattern/exclude_dirs”.

StaticGlob already embeds exclude/discards; Filter remains the right tool for **dynamic** narrowing without re-walking.

## Migration

| Phase | Deliverable |
|-------|-------------|
| `static-glob-helper` | Shared path resolver; unit tests for `#/`, `start=`, sconscript-relative |
| `static-glob-add` | `env.StaticGlob`; implementation = refactor `RecursiveGlob` + `GlobFiles` |
| `static-glob-alias` | `RecursiveGlob` / `GlobFiles` call StaticGlob; one configure-time `warn_once` each with replacement hint |
| `glob-doc` | Antora: evaluation table, path vocabulary, Filter recipes |
| `glob-wrapper` (optional) | Cuppa `env.Glob` wrapper: shared paths + optional default `**` exclusions |
| `static-glob-remove` (major) | Drop aliases after deprecation window |

Internal call sites ([`build_with_location.py`](../../cuppa/build_with_location.py), tests, quickstart) migrate to `StaticGlob` in the same release as the alias.

## Settled decisions (confirm before implementation)

| Question | Options | Working bias |
|----------|---------|--------------|
| Static API name | `StaticGlob` / `SnapshotGlob` / `GlobAtConfigure` | **`StaticGlob`** — pairs naturally with dynamic `Glob` |
| Flat vs recursive | Two methods vs one flag | **One method** + `recursive=False` (replaces `GlobFiles`) |
| Dynamic API | Document SCons only vs cuppa wrapper | **Document SCons first**; add wrapper if `#/` + exclusions need one home |
| Aliases | Keep forever vs deprecate | **Deprecated aliases** ≥1 minor, remove on major |
| Path helper location | New module vs extend existing | **Shared module** consumed by StaticGlob + optional Glob wrapper |

## Progress snapshot

| Slice | Status |
|-------|--------|
| Plan | this document |
| Shared path resolver | not started |
| `StaticGlob` | not started |
| Deprecated aliases | not started |
| Filter parity | not started |
| Antora / migration matrix update | not started |

## Non-goals

- Making StaticGlob lazy (that is what SCons Glob is for).
- Reimplementing SCons `**` inside Python walk.
- Changing compile object layout ([#213](https://github.com/ja11sop/cuppa/issues/213)) — prerequisite for honest static glob docs, separate PR.

## References

- [`cuppa/methods/relative_recursive_glob.py`](../../cuppa/methods/relative_recursive_glob.py)
- [`cuppa/recursive_glob.py`](../../cuppa/recursive_glob.py)
- [`cuppa/methods/filter.py`](../../cuppa/methods/filter.py)
- Integration: [`test_glob.py`](../../tests/integration/methods/test_glob.py), [`test_flags.py`](../../tests/integration/methods/test_flags.py)
