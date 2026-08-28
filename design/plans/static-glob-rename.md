# Plan: RecursiveGlob — recursive snapshot discovery (vs SCons directory Glob)

- **Status:** in progress
- **Related:** [`ROADMAP.md`](../../ROADMAP.md) — `static-glob`; [#213](https://github.com/ja11sop/cuppa/issues/213); [`cmake-to-cuppa-migration.md`](cmake-to-cuppa-migration.md)
- **Updated:** 2026-08-28
- **Impact:** minor — shared path roots + Filter path parity; honest SCons Glob docs (no new public name)

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

Shared implementation: `snapshot_glob()` in [`relative_recursive_glob.py`](../../cuppa/methods/relative_recursive_glob.py); path roots in [`glob_roots.py`](../../cuppa/utility/glob_roots.py).

### Evaluation mismatch (named, not the method name)

| Term | Meaning |
|------|---------|
| **Configure-time snapshot** | Cuppa `RecursiveGlob` / `GlobFiles` — Python walk/listdir when the sconscript line runs |
| **SCons directory Glob** | `env.Glob` — SCons-native `File` nodes for one directory / one segment per pattern |

**Real impact (assessed):** low for typical Cuppa workflows. Both see new files on the next `cuppa` invocation because the sconscript is re-read. Differences that still matter: recursion, `exclude_dirs` / `discard_pattern`, `start=` / `#/` vocabulary, **node path forms** (absolute vs project-relative), and SCons FS edge cases — **Repositories** and **declared `File` nodes not on disk** (integration tests in `test_glob.py`).

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
| Unified snapshot engine | **done** (`snapshot_glob`) |
| Filter path parity | **done** |
| Semantic integration matrix | **done** |
| GlobFiles via SCons Glob (declared Files) | **done** |
| RecursiveGlob merge of `Dir.entries` | not started (try after live-testing GlobFiles) |

## Non-goals

- Teaching SCons `**` as recursive.
- A released-then-removed `StaticGlob` name (never shipped).

## References

- [`cuppa/methods/relative_recursive_glob.py`](../../cuppa/methods/relative_recursive_glob.py)
- [`cuppa/utility/glob_roots.py`](../../cuppa/utility/glob_roots.py)
- Integration: [`test_glob.py`](../../tests/integration/methods/test_glob.py)
