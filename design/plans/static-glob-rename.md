# Plan: RecursiveGlob — recursive snapshot discovery (vs SCons directory Glob)

- **Status:** in progress
- **Related:** [`ROADMAP.md`](../../ROADMAP.md) — `static-glob`; [#213](https://github.com/ja11sop/cuppa/issues/213); [`cmake-to-cuppa-migration.md`](cmake-to-cuppa-migration.md)
- **Updated:** 2026-08-28
- **Impact:** minor — shared path roots + Filter path parity + `StaticGlob` as deprecated umbrella; `RecursiveGlob` / `GlobFiles` remain the primary names

## Problem

SCons **`env.Glob`** is a **directory Glob**: matches do not span `/`, and `**` is only one path segment (upstream still discussing true recursive Glob). Cuppa needs a **recursive** discovery API with exclusions for `_build` / dependency trees.

An earlier draft renamed the walk to `StaticGlob` to emphasise evaluation model (configure-time snapshot vs “dynamic” Glob). After measuring SCons behaviour, **recursion is the primary axis**; snapshot-vs-directory-Glob is secondary and low-impact under Cuppa (sconscripts re-read every normal build).

## Naming (settled)

| API | Role |
|-----|------|
| **`env.RecursiveGlob`** | Recursive configure-time tree walk — Cuppa’s stand-in for “recursive Glob” |
| **`env.GlobFiles`** | Flat configure-time listing of one directory |
| **`env.Glob`** (SCons) | Directory Glob (non-recursive) |
| **`env.StaticGlob`** | Deprecated umbrella over the same snapshot engine (`recursive=`); prefer the two names above |
| **`env.Filter`** | Narrow any node list (path forms: relative + absolute) |

Shared implementation: `snapshot_glob()` in [`relative_recursive_glob.py`](../../cuppa/methods/relative_recursive_glob.py); path roots in [`glob_roots.py`](../../cuppa/utility/glob_roots.py).

### Evaluation mismatch (named, not the method name)

| Term | Meaning |
|------|---------|
| **Configure-time snapshot** | Cuppa `RecursiveGlob` / `GlobFiles` — Python walk/listdir when the sconscript line runs |
| **SCons directory Glob** | `env.Glob` — SCons-native `File` nodes for one directory / one segment per pattern |

**Real impact (assessed):** low for typical Cuppa workflows. Both see new files on the next `cuppa` invocation because the sconscript is re-read. Differences that still matter: recursion, `exclude_dirs` / `discard_pattern`, `start=` / `#/` vocabulary, and VariantDir/Repository edge cases where SCons nodes matter more.

**Do not** implement RecursiveGlob by delegating to SCons `**` — that is not a tree walk.

## Shape

```python
sources = env.RecursiveGlob('*.cpp', start='src')
tests = env.GlobFiles('*_test.cpp', start='tests')
shallow = env.Glob('#/src/*/*.cpp')  # one nesting level only
```

Cuppa-only knobs on the snapshot side: `start=`, `exclude_dirs=`, `discard_pattern=` (recursive walk only).

## Path vocabulary

Same strings for Cuppa `start=` and SCons `#/` where possible:

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
| Primary names RecursiveGlob / GlobFiles | **done** (no deprecation) |
| StaticGlob deprecated umbrella | **done** |
| Filter path parity | **done** |
| Semantic integration matrix | **landing** — recursion vs Glob vs GlobFiles; Filter; next-invocation new file; StaticGlob warn |
| Optional true recursive SCons Glob wrapper | not started (blocked on upstream or a cuppa walk that returns Glob nodes per dir) |
| Alias removal (StaticGlob) | deferred to major |

## Non-goals

- Teaching SCons `**` as recursive.
- Making the snapshot lazy inside one sconscript read without a second call.
- Compile object layout ([#213](https://github.com/ja11sop/cuppa/issues/213)).

## References

- [`cuppa/methods/relative_recursive_glob.py`](../../cuppa/methods/relative_recursive_glob.py)
- [`cuppa/utility/glob_roots.py`](../../cuppa/utility/glob_roots.py)
- [`cuppa/recursive_glob.py`](../../cuppa/recursive_glob.py)
- Integration: [`test_glob.py`](../../tests/integration/methods/test_glob.py)
