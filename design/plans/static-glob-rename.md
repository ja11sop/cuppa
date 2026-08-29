# Plan: RecursiveGlob — recursive snapshot discovery (vs SCons directory Glob)

- **Status:** in progress
- **Related:** [`ROADMAP.md`](../../ROADMAP.md) — `static-glob`; [#213](https://github.com/ja11sop/cuppa/issues/213); [`cmake-to-cuppa-migration.md`](cmake-to-cuppa-migration.md)
- **Updated:** 2026-08-29
- **Impact:** minor — shared path roots + Filter path parity; RecursiveGlob merges `Dir.entries` + shallow Repository

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
| **Configure-time snapshot** | Cuppa `RecursiveGlob` / `GlobFiles` — walk/listdir (plus local `Dir.entries` and shallow Repository `Dir.glob` for RecursiveGlob) when the sconscript line runs |
| **SCons directory Glob** | `env.Glob` — SCons-native `File` nodes for one directory / one segment per pattern |

**Real impact (assessed):** low for typical Cuppa workflows. Both see new files on the next `cuppa` invocation because the sconscript is re-read. Differences that still matter: recursion, `exclude_dirs` / `discard_pattern`, `start=` / `#/` vocabulary, **node path forms**, and SCons FS edge cases — **Repositories** (shallow done; full recursive open) and **declared `File` nodes not on disk**.

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
| RecursiveGlob **shallow** Repository (`Dir.glob` per local dir) | **done** |
| RecursiveGlob **full** Repository (repo-only subdirectory trees) | **not started** — see below |

## Repository support

### Shallow (shipped)

For each directory that exists on the **local** disk under `start=`, RecursiveGlob calls SCons `Dir.glob(pattern)` on the corresponding node. That is the same per-directory Repository search `env.Glob` / `GlobFiles` use, so files such as `repo/src/from_repo.cpp` appear when `project/src/` exists locally.

`exclude_dirs` / `discard_pattern` still follow the local `os.walk`. Declared `File` merge (`Dir.entries`) stays separate and continues to skip Repository-backed names via `rfile()` so ghosts and repo lookups do not double-count oddly.

**Intentionally out of scope for shallow:** a subdirectory that exists **only** in a Repository (e.g. `repo/src/nested/deep.cpp` with no `project/src/nested/`) is not visited — there is no local directory for the walk to enter.

### Full recursive Repository (follow-on)

**Goal:** RecursiveGlob finds matching files under Repository-only subdirectory trees, with the same `exclude_dirs` / `discard_pattern` semantics as the local walk, returning local `File` nodes (VariantDir-safe), deduped against disk and declared merges.

**Why it is separate work:** SCons `Dir.glob` does not recurse across `/`. Shallow reuse stops at local directory names. Full parity must **union directory listings** from the local tree and each entry of `Dir.get_all_rdirs()`, recurse into names that appear only remotely, and map matches back onto the project-side node tree.

**Suggested approach:**

1. Start from `_start_dir_node` / `absolute_start`.
2. BFS/DFS of logical relative paths. At each relative path, obtain the local `Dir` (creating intermediate Dir nodes as needed for mapping) and every corresponding `get_all_rdirs()` peer.
3. Union child **directory** names from local `os.listdir` / `entries` and from each rdir’s on-disk listing (and optionally rdir `entries`).
4. Apply `exclude_dirs` to basenames; apply `discard_pattern` using the union of file names in that logical directory (local + remotes) before descending.
5. Collect matching **files** from local disk, local `entries` (declared), and each rdir (via `listdir` + `env.File` / `Dir.File`, or `rdir.glob(pattern)` at that level).
6. Dedupe with existing `_node_key` / `_source_node` / `rfile()` awareness so VariantDir build-tree nodes and Repository remotes do not inflate the list.
7. Integration fixtures: (a) shallow still green; (b) repo-only nested tree included; (c) local file shadows repo same basename; (d) `exclude_dirs` / `discard_pattern` applied to repo-only dirs; (e) Windows path forms.

**Sizing:** about one careful PR after shallow — not a redesign; builds on `get_all_rdirs`, `_merge_unique_nodes`, and the existing Repository tests. Main risk is VariantDir + dual node identity, already exercised by the declared-File work.

**Non-goals for that slice:** changing GlobFiles; teaching SCons `**` as recursive; walking Repositories when the local `start=` directory itself is missing (optional stretch — document if added).

## Non-goals

- Teaching SCons `**` as recursive.
- A released-then-removed `StaticGlob` name (never shipped).

## References

- [`cuppa/methods/relative_recursive_glob.py`](../../cuppa/methods/relative_recursive_glob.py)
- [`cuppa/utility/glob_roots.py`](../../cuppa/utility/glob_roots.py)
- Integration: [`test_glob.py`](../../tests/integration/methods/test_glob.py)
