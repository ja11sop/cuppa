# Cuppa roadmap

Living roadmap for **large features** in the cuppa repository.
Use this document to see what is shipped today, what is planned next, and what is explicitly out of scope.

**Audience:** maintainers and AI agents working on cuppa.
**Canonical product docs:** [https://ja11sop.github.io/cuppa/](https://ja11sop.github.io/cuppa/) under `docs/`.
**Agent notes:** [`AGENTS.md`](AGENTS.md).
**Release notes:** [`CHANGELOG.md`](CHANGELOG.md) (Keep a Changelog; SemVer via `cuppa/VERSION`).

When code and this roadmap disagree on *current* behaviour, **code and the Antora docs are authoritative**; update this file in the same change.

**As of:** 2026-07-29

---

## How to use this document

| Section | Purpose |
|---------|---------|
| Feature sections below | One major product area each |
| **Today** | Shipped capability (matrix or summary) |
| **Planned / potential** | Follow-on work, vendor waits, deferred items |
| **Out of scope** | Explicit non-goals so agents do not re-open them without intent |

Add new top-level `##` sections when starting other large efforts (for example packages, coverage UX, or new toolchain families). Keep each section self-contained: matrix of today, then planned work with short IDs.

---

## C++20 modules

Opt-in via `--modules` / `env.Modules()`.
User guide and Limits: `docs/modules/ROOT/pages/cxx-modules.adoc`.
Integration scenarios: `docs/modules/ROOT/pages/integration/test-modules.adoc`.
Companion canvas (optional): Cursor canvas `cxx-modules-status`.

### Today

| Feature | GCC | LLVM Clang | MSVC | Apple Clang | Notes |
|---------|-----|------------|------|-------------|-------|
| Named modules | Yes (14+) | Yes (16+) | Yes (toolset 14.2+ / `vc142+`) | No | Apple Clang fails clearly under `--modules`; use Homebrew LLVM on macOS |
| Interface / implementation partitions | Yes | Yes | Yes | No | MSVC uses `-interface` / `-internalPartition` as appropriate |
| Implementation units (`module M;`) | Yes | Yes | Yes | No | Ordinary objects consuming the primary BMI |
| Header units (`HeaderUnit`, `import "…"`, `import <…>`) | Yes | Yes | Yes | No | Spelling must match the declared form |
| `import std` / `import std.compat` | Yes (15+) | Yes (18+ + libc++) | Yes (14.3+ + `std.ixx`) | No | Dialect floor raised to C++23; `std` before `std.compat` |
| Private module fragments (`module :private;`) | No | Yes | n/a | No | GCC still unimplemented |
| Shared libraries with module interfaces | Yes | Yes | Yes | No | MSVC still needs ordinary DLL export (`__declspec(dllexport)` / `.def`) |
| Package BMI install + `ImportModules` | Yes | Yes | Yes | No | Toolchain-family BMIs only (`.gcm` / `.pcm` / `.ifc`); no cross-toolchain reuse |
| `--cov --modules` | Yes | Yes | No | No | MSVC coverage instrumentation not supported |
| `.ixx` interface suffix | Yes | Yes | Yes | No | Smoke-tested via `MODULE_SOURCE_SUFFIXES` |
| `env.Module` convenience method | Yes | Yes | Yes | No | Delegates to `Compile` / modules compile path |
| Product label | Opt-in | Opt-in | Opt-in | Rejected | Graduated from “experimental” in CLI help |

**CI coverage**

- Linux: full modules suite × `gcc`, `clang`+libstdc++, `clang`+libc++
- Windows: full integration with `CUPPA_TEST_TOOLCHAIN=vc`
- macOS: Homebrew LLVM + libc++ — named modules, header units, `Module` method, partitions, implementation units, `.ixx`, packaging, `import std`

**Key implementation files**

- `cuppa/cpp/module_scanner.py`, `cuppa/cpp/cxx_modules.py`
- `cuppa/toolchains/{gcc,clang,cl,cxx_modules_support}.py`
- `cuppa/methods/{modules,module,header_unit,import_modules}.py`
- `tests/unit/test_module_scanner.py`, `tests/integration/methods/test_modules.py`

**Scanner today:** line-oriented import/export detection with unit tests. It does **not** call `clang-scan-deps`. Macros / `#if` that invent imports remain an explicit Limit.

### Planned / potential

| ID | Work | Priority | Notes |
|----|------|----------|-------|
| `scan-deps` | Optional `clang-scan-deps` (or P1689) dependency backend | Medium | Flag or auto-detect; keep line scanner as fallback. Substantial: driver discovery, JSON graph merge, fallback path |
| `gcc-private` | Private module fragments on GCC | Later | Re-enable / unskip tests when GCC implements the feature |
| `apple-clang` | Apple Clang modules support | Later | Revisit only if Apple ships a usable scanner and reliable BMI flags |

### Stabilize / leave alone unless regressing

- GCC module mapper and Clang `-fmodule-output` paths
- BMI install under `final/modules/` + `module-map.json`
- Fail-on-too-old-toolchain policy for Linux modules integration tests
- Absolute `CXX` / `CC` + PATH prepend for Homebrew LLVM on macOS
- MSVC `c++23` / `c++2b` → `-std:c++latest` mapping where toolsets ignore `-std:c++23`

### Out of scope (modules)

| ID | Item | Reason |
|----|------|--------|
| `cross-bmi` | Cross-toolchain BMI packages | BMI formats are vendor-specific |
| `modules-default` | Making modules the default build path | Remain opt-in via `--modules` / `env.Modules()` |
| `apple-emulation` | Emulating Apple Clang modules without vendor support | Prefer fail-clearly |

Boost / package-registry packaging work is tracked separately from modules.

---

## Future feature sections

Add new `##` headings here as larger efforts start, for example:

- Packages / GitLab registry UX
- Coverage reporting and multi-toolchain indexes
- Additional toolchains or platforms

Each new section should follow the same shape: **Today** → **Planned / potential** → **Out of scope**.
