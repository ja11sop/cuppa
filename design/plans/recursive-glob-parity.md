# Plan: Glob / RecursiveGlob parity

- **Status:** in progress
- **Related:** [`ROADMAP.md`](../../ROADMAP.md) — `static-glob`; [#232](https://github.com/ja11sop/cuppa/issues/232); [#213](https://github.com/ja11sop/cuppa/issues/213); [`cmake-to-cuppa-migration.md`](cmake-to-cuppa-migration.md); follow-on [`path-vocabulary-and-scons-nodes.md`](path-vocabulary-and-scons-nodes.md); landing [#231](https://github.com/ja11sop/cuppa/pull/231)
- **Updated:** 2026-08-29
- **Impact:** minor — shared path roots + Filter path parity; RecursiveGlob merges `Dir.entries` + full Repository trees

## Problem

SCons **`env.Glob`** is a **directory Glob**: matches do not span `/`, and `**` is only one path segment (upstream still discussing true recursive Glob). Cuppa needs a **recursive** discovery API with exclusions for `_build` / dependency trees.

**Recursion is the primary axis.** Snapshot-vs-directory-Glob is secondary and low-impact under Cuppa (sconscripts re-read every normal build).

## Naming (settled)

| API | Role |
|-----|------|
| **`env.RecursiveGlob`** | Recursive configure-time tree walk — Cuppa’s stand-in for “recursive Glob” |
| **`env.GlobFiles`** | Single-directory discovery via SCons `Glob` after Cuppa `start=` / `#/` (declared `File`s, Repositories) |
| **`env.Glob`** (SCons) | Directory Glob (non-recursive) |
| **`env.Filter`** | Narrow any node list (path forms: relative + absolute) |

Shared implementation: disk walk + merges in [`relative_recursive_glob.py`](../../cuppa/methods/relative_recursive_glob.py); path roots in [`glob_roots.py`](../../cuppa/utility/glob_roots.py).

### Evaluation mismatch (named, not the method name)

| Term | Meaning |
|------|---------|
| **Configure-time snapshot** | Cuppa `RecursiveGlob` / `GlobFiles` — walk/listdir (plus local `Dir.entries` and Repository `Dir.glob` for RecursiveGlob) when the sconscript line runs |
| **SCons directory Glob** | `env.Glob` — SCons-native `File` nodes for one directory / one segment per pattern |

**Real impact (assessed):** low for typical Cuppa workflows. Both see new files on the next `cuppa` invocation because the sconscript is re-read. Differences that still matter: recursion, `exclude_dirs` / `discard_pattern`, `start=` / `#/` vocabulary, **node path forms**, and SCons FS edge cases — **Repositories** and **declared `File` nodes not on disk**.

**Do not** implement RecursiveGlob by delegating to SCons `**` — that is not a tree walk.

## Shape

```python
sources = env.RecursiveGlob('*.cpp', start='src')
tests = env.GlobFiles('*_test.cpp', start='tests')
shallow = env.Glob('#/src/*/*.cpp')  # one nesting level only
```

## Path vocabulary

| Input | Meaning |
|-------|---------|
| `#/…` / `#…` | Project / sconstruct root |
| `start='src'` | Relative to calling sconscript |
| Absolute | Last resort |

## Progress snapshot

| Slice | Status |
|-------|--------|
| Shared path resolver | **done** |
| Unified snapshot engine | **done** (`cuppa.recursive_glob` + merges) |
| Filter path parity | **done** |
| Semantic integration matrix | **done** |
| GlobFiles via SCons Glob (declared Files) | **done** |
| RecursiveGlob merge of `Dir.entries` | **done** |
| RecursiveGlob **shallow** Repository (`Dir.glob` per local dir) | **done** (superseded by full walk) |
| RecursiveGlob **full** Repository (repo-only subdirectory trees) | **done** |

**Follow-on (not this plan):** reuse `#/` path vocabulary and VariantDir node helpers outside discovery — [`path-vocabulary-and-scons-nodes.md`](path-vocabulary-and-scons-nodes.md). Do **not** share the Repository / `Dir.entries` tree walk with other methods.

## Repository support

### Shipped behaviour

RecursiveGlob merges three sources, then dedupes by source abspath:

1. Local disk walk (`cuppa.recursive_glob`) with `exclude_dirs` / `discard_pattern`
2. Declared `File` nodes from `Dir.entries` (including nested declared-only dirs; skips Repository-backed names via `rfile()`)
3. **Repository tree walk** — at each logical directory (union of local disk, local `entries`, and `get_all_rdirs()` peers), call SCons `Dir.glob(pattern)` and recurse into child directory basenames from that union

So `repo/src/from_repo.cpp` appears when `project/src/` exists locally, and `repo/src/nested/deep.cpp` appears even when `project/src/nested/` does not.

`exclude_dirs` / `discard_pattern` for the Repository walk use the **union** of local and remote basenames at each logical path (so a `CMakeLists.txt` only in the repo still discards that logical subdirectory).

Local basename shadows a Repository copy once (no duplicate nodes).

### Corner cases considered (full walk)

| Case | Handling |
|------|----------|
| Repo-only nested dirs | Union child names from `get_all_rdirs()` peers; `Dir(name)` maps to local node tree; `Dir.glob` finds remotes |
| Local file shadows repo same basename | `_merge_unique_nodes` / `_node_key` via `srcnode()` |
| `exclude_dirs` / `discard` on repo-only dirs | Applied to unioned basenames before descend / before glob |
| VariantDir dual nodes | Prefer sconscript-relative `Dir`; dedupe on source abspath |
| Multiple Repositories | `get_all_rdirs()` + `Dir.glob` already search all peers |
| Cycles / revisit | `visited` set of logical relative paths |
| Local `start=` missing | Walk still starts from `start_dir`; remote listdir via peers (optional stretch kept) |
| Declared ghosts vs repo | Separate `Dir.entries` merge; `rfile()` filter avoids treating repo lookups as ghosts |

### Historical note

An earlier **shallow** slice only called `Dir.glob` for directories that existed on local disk. The full walk replaces that helper; shallow behaviour remains as a subset of the same tests.

## Non-goals

- Teaching SCons `**` as recursive.
- A released-then-removed `StaticGlob` name (never shipped).
- Changing GlobFiles (already Repository-complete via SCons `Glob`).

## References

- [`cuppa/methods/relative_recursive_glob.py`](../../cuppa/methods/relative_recursive_glob.py)
- [`cuppa/utility/glob_roots.py`](../../cuppa/utility/glob_roots.py)
- Integration: [`test_glob.py`](../../tests/integration/methods/test_glob.py)
