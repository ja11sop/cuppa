# Cuppa roadmap

Living roadmap for **large features** in the cuppa repository.
Use this document to see what is shipped today, what is planned next, and what is explicitly out of scope.

**Audience:** maintainers and AI agents working on cuppa.
**Canonical product docs:** [https://ja11sop.github.io/cuppa/](https://ja11sop.github.io/cuppa/) under `docs/`.
**Agent notes:** [`AGENTS.md`](AGENTS.md).
**Release notes:** [`CHANGELOG.md`](CHANGELOG.md) (Keep a Changelog; SemVer via `cuppa/VERSION`).
**Design notes behind these entries:** [`design/README.md`](design/README.md).

When code and this roadmap disagree on *current* behaviour, **code and the Antora docs are authoritative**; update this file in the same change.

**As of:** 2026-08-10

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

Opt-in via `--cxx-modules` / `env.CxxModules()` (`--modules` / `env.Modules()` deprecated until cuppa 2.0).
Whether activation should become automatic (with `--cxx-modules` / `--no-modules` as overrides) is
worked out in [`design/plans/modules-activation.md`](design/plans/modules-activation.md).
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
| C++20 dialect floor | Yes | Yes | Yes | n/a | Honours the toolchain default (never lowers a dialect) and applies at the compile that uses modules |
| Product label | Opt-in | Opt-in | Opt-in | Rejected | Graduated from “experimental” in CLI help |
| CLI / methods | `--cxx-modules` / `env.CxxModules()` canonical; `--modules` / `env.Modules()` deprecated (2.0) | Yes | Yes | Yes | n/a | [#180](https://github.com/ja11sop/cuppa/pull/180) |

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
| `mod-scan-preamble` | Stop scanning a source at the end of its preamble | High | `scan_file` reads whole files today; prerequisite for any always-on scanning |
| `mod-scan-cache` | Cache scan results per path / mtime / size | High | Same sources are scanned by every `Compile` call that lists them |
| `mod-activate-evidence` | Activate the modules path on module sources / `Module` / `HeaderUnit` / `ImportModules` rather than a global flag, with `--modules` / `--no-modules` as overrides | Medium | Gated on read-phase timing; see [`design/plans/modules-activation.md`](design/plans/modules-activation.md) |
| `mod-gcc-flag-scope` | Give GCC `-fmodules` / `-fmodule-mapper=` to the compiles that need them instead of every TU | Medium | The only always-on compiler flag change among the three toolchains |
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
| `modules-default` | Routing every project through the modules compile path | Superseded by `mod-activate-evidence`: activate where there is evidence of modules, rather than for all builds |
| `apple-emulation` | Emulating Apple Clang modules without vendor support | Prefer fail-clearly |

Boost / package-registry packaging work is tracked separately from modules — see
[Boost source and packages](#boost-source-and-packages).

---

## C++ Profiles

Opt-in WG21 / experimental-Clang **Profiles** via `--cxx-profiles` / `--cxx-profiles-enforce=`
and `env.CxxProfiles()` / `env.CxxProfilesEnforce()`. Requires a Profiles-capable Clang archive
(`--toolchain-archive=` / `--clang-root=`). User guide:
[`docs/modules/ROOT/pages/cxx-profiles.adoc`](docs/modules/ROOT/pages/cxx-profiles.adoc).
Design (shipped): [`design/archive/cxx-profiles.md`](design/archive/cxx-profiles.md).
Umbrella: [#127](https://github.com/ja11sop/cuppa/issues/127) ([#177](https://github.com/ja11sop/cuppa/pull/177), [#180](https://github.com/ja11sop/cuppa/pull/180)).

### Today

| Capability | Status |
|------------|--------|
| `--cxx-profiles` → `-fprofiles` (probed; StopError when unsupported) | Yes |
| `--cxx-profiles-enforce=` (native flags or `-include` inject; source composition) | Yes |
| `--cxx-disable-error-limit` (Clang/GCC; MSVC `cl` has no supported flag) | Yes |
| Smoke designator `std::init` on Alliance Clang | Yes |
| Integration smoke + unsupported-toolchain failure | Yes |

**Key implementation files**

- `cuppa/methods/cxx_profiles.py`, `cuppa/methods/cxx_disable_error_limit.py`
- `cuppa/cpp/cxx_profiles.py`
- `cuppa/toolchains/{clang,gcc,cl}.py` — `profiles_*` and `disable_error_limit_flags`
- `tests/unit/test_cxx_profiles_method.py`, `tests/unit/test_cxx_vocabulary.py`
- `tests/integration/methods/test_cxx_profiles.py`

### Planned / potential

| ID | Work | Priority | Notes |
|----|------|----------|-------|
| `profiles-designators` | Additional profile names as Alliance Clang / WG21 stabilise | Medium | Cuppa passes opaque strings through |
| `profiles-native-enforce` | Wire `profiles_enforce_flags` when a compiler adds native enforce flags | Low | Hook exists; `-include` fallback remains |
| `profiles-carve-outs` | Build policy to skip session enforce on selected paths | Low | Separate from source attributes |
| `profiles-modules-require` | Import-site `profiles::require` with the modules graph | Later | No session-wide CLI |

### Out of scope (C++ Profiles)

| ID | Item | Reason |
|----|------|--------|
| `profiles-default` | Auto-enable Profiles on every Clang | Opt-in only |
| `profiles-require-cli` | Session `--cxx-profiles-require=` / `--cxx-profiles-suppress=` | Wrong locus for a cuppa CLI |
| `profiles-invent-flags` | Required native `-fprofile-enforce` before it exists | Map when real; inject until then |

---

## Boost source and packages

Goal: source `boost` and GitLab `boost_package` stay interchangeable at the sconscript
(`use_libs`) while patch status is an honest identity — especially for prebuilt packages, which
are patched by default.

Design: [`design/plans/boost-updates.md`](design/plans/boost-updates.md).

### Today

| Capability | Status |
|------------|--------|
| Source `--boost-patched` selects `patched/` vs `clean/` under one extract | Yes (alias `--boost-patch-boost-test`) |
| Source remove/purge is selection-scoped per home | Yes ([#144](https://github.com/ja11sop/cuppa/pull/144)) |
| `boost_package.define(..., patched=True)` default | Yes — compile define + `patched_test()` only |
| Package archive / extract / version distinguish patched vs clean | No — same `boost` + `1.91` + tool variant |
| Package `use_libs` passes `patched_test=` into library deps | No |
| Persist Boost latest for offline reuse (`boost_latest_version`, downloads-root–scoped) | Yes — [#171](https://github.com/ja11sop/cuppa/issues/171) / [#170](https://github.com/ja11sop/cuppa/pull/170); design [`boost-latest-persistence.md`](design/archive/boost-latest-persistence.md) |

### Planned / potential

| ID | Work | Priority | Notes |
|----|------|----------|-------|
| `boost-latest-persist` | Persist higher downloaded latest; offline reads stored then compiled-in; scrape only with `--boost-latest` | High | Done — [#171](https://github.com/ja11sop/cuppa/issues/171) / [#170](https://github.com/ja11sop/cuppa/pull/170) |
| `boost-pkg-version` | Canonical version `{base}-patched` / `{base}-clean`; publisher + resolve + `package_id` | High | Visible qualifier; avoids extract collision |
| `boost-pkg-compat` | Patched resolve falls back to unadorned `{base}`; clean does not | High | Existing registry tarballs are patched and unnamed |
| `boost-pkg-use-libs` | Package `use_libs` passes `patched_test=` | High | Parity with source Boost |
| `boost-pkg-docs` | Document opposite defaults (source clean / package patched) and identity | Medium | `packages.adoc` / `dependencies.adoc` |
| `boost-pkg-flag` | Optional: `--boost-patched` selects among declared package flavours | Later | Not required if a project only consumes patched packages |

### Out of scope (Boost)

| ID | Item | Reason |
|----|------|--------|
| `boost-pkg-as-source-homes` | Two homes under one GitLab extract | Packages are whole prebuilt trees, not b2 stage layouts |
| `boost-src-two-downloads` | Separate tarballs for source clean vs patched | One upstream archive; patch is applied after extract |

---

## SCons Tool dependencies (#27)

Goal: make it trivial to wrap an existing **SCons Tool** so it appears as a normal Cuppa dependency (`env.BuildWith('…')`), with variants, toolchains, methods, and **pip-installable** discovery via `cuppa.dependency.plugins`.

In-tree references today: [`cuppa/dependencies/build_with_qt4.py`](cuppa/dependencies/build_with_qt4.py) and [`build_with_qt5.py`](cuppa/dependencies/build_with_qt5.py) — each detects an install, then calls `SCons.Script.Tool('qtN', toolpath=[…])(env)` inside `__call__`.

### Today

| Capability | Status |
|------------|--------|
| Hand-written Tool-backed deps (Qt4/Qt5) | Yes |
| `cuppa.dependency.plugins` entry points | Yes (construct loads them) |
| Generic Tool → dependency factory | No |
| Documented pip packaging for Tool wrappers | No |

### Planned / potential

| ID | Work | Priority | Notes |
|----|------|----------|-------|
| `scons-tool-dep` | Public `scons_tool_dependency(...)` (or equivalent) factory: name, Tool id, toolpath/location, prepare/after hooks; registers via `add_dependency` | High | Extract the Qt pattern without requiring Qt-specific detection in the core facility |
| `scons-tool-pip` | Docs + minimal example package: `setup.cfg` / `pyproject.toml` entry point under `cuppa.dependency.plugins`; install via `requirements.txt` | High | Same discovery path as other Cuppa plugins |
| `scons-tool-tests` | Unit test with a tiny fake Tool; optional integration smoke | High | No Qt install required in CI |
| `scons-tool-qt-migrate` | Optionally refactor in-tree Qt4/Qt5 onto the facility | Later | Keep Qt-specific pkg-config / `QTnDIR` detection as hooks, not in the generic core |

### Out of scope (SCons Tools)

| ID | Item | Reason |
|----|------|--------|
| `rewrite-tools` | Rewriting upstream SCons Tools as Cuppa-native code | Wrappers should consume Tools as-is |
| `auto-toolpath-scan` | Scanning the whole system for arbitrary Tools without declaration | Explicit name + toolpath/location keeps builds reproducible |

Tracked as GitHub issue [#27](https://github.com/ja11sop/cuppa/issues/27).

---

## Conan consumer integration (#29)

Goal: optional **Conan 2 consumer** support so projects can pull mainstream packages (fmt, OpenSSL, …) and apply them through `env.BuildWith`, without making Conan Cuppa’s orchestrator or replacing location/GitLab package deps.

Detailed exploration, trade-offs, and API sketches: [`design/archive/conan-consumer-plan.md`](design/archive/conan-consumer-plan.md) (consumer), [`design/archive/conan-publish-plan.md`](design/archive/conan-publish-plan.md) (producer).

### Today

| Capability | Status |
|------------|--------|
| `location_dependency` / git-style deps | Yes |
| GitLab `package_dependency` | Yes |
| Conan install → Cuppa env flags | Yes (optional; `conan_deps` / SConsDeps) |
| Conan export-pkg / upload of Cuppa-built libs | Yes (optional; `ConanPackagePublisher`) |
| Conan modules/BMI (`modules/` + `module-map.json`) | Yes (optional; parity with GitLab generic) |

### Planned / potential

| ID | Work | Priority | Notes |
|----|------|----------|-------|
| `conan-spike` | Spike **SConsDeps** + `MergeFlags` + fmt hello (no pkg-config on happy path) | Done | Evidence locked generator for Phase 1 |
| `conan-consume` | `conan_deps` / `conan_dependency`; fingerprint cache + lock; runtime ENV; `BuildWith` | Done | Consumer only; Conan 2 + SConsDeps (`cuppa/build_with_conan.py`) |
| `conan-reuse` | Consume pre-run `conan install` output folder (`generators_folder`) | Done | Covered by MVP + `test_conan` integration |
| `conan-json` | Custom CuppaDeps/JSON only if SConsDeps proves insufficient | Later | Not on critical path |
| `conan-pkgconfig` | Document PkgConfigDeps as optional fallback | Later | Not MVP default |
| `conan-docs-pip` | Docs + example pip plugin (`examples/conan_fmt_plugin`) | Done | Entry point `cuppa.dependency.plugins`; covered by `test_conan` |
| `conan-integration` | Linux integration: install / generators_folder / shared `--test` / plugin / offline miss / publish | Done | `test_conan.py`; Linux CI installs Conan 2 |
| `conan-publish-spike` | Spike Cuppa-build → `export-pkg` → local-cache consumer round-trip | Done | Producer path evidence |
| `conan-publish` | `ConanPackagePublisher` + `PublishPackage`; settings; upload via `--publish-package` | Done | See [`design/archive/conan-publish-plan.md`](design/archive/conan-publish-plan.md) |
| `conan-publish-recipe` | Hand-written `conanfile=` override; `shared=`; generated `requires=` | Done | Components still deferred; see `conan-components` below |
| `conan-publish-modules` | Stage Cuppa `modules/` + BMI map in Conan packages; consumer `load_packaged_modules` | Done | Parity with GitLab generic `modules/` path |
| `conan-components` | First-class multi-target packages via `cpp_info.components` | Later | Flat `cpp_info.libs` covers single-target packages today; GitHub [#125](https://github.com/ja11sop/cuppa/issues/125) |
| `conan-windows-ci` | Install Conan 2 on the Windows job so `test_conan.py` runs under MSVC instead of skipping | Later | Needs a proven MSVC Conan profile; GitHub [#126](https://github.com/ja11sop/cuppa/issues/126) |

### Out of scope (Conan)

| ID | Item | Reason |
|----|------|--------|
| `conan-orchestrator` | Conan as primary build driver / required dependency manager | Cuppa stays the orchestrator |
| `conan1` | First-class Conan 1.x | Conan 2 only unless a thin shim appears later |
| `conancenter-vendor` | Hosting/mirroring ConanCenter inside Cuppa | Not a package host |
| `conan-cross-mvp` | Build vs host profiles / cross in Phase 1 | Host-only MVP |
| `conan-tool-requires` | `tool_requires` / codegen plugins in MVP | Document limitation; later |
| `conan-create-build` | `conan create` with `build()` invoking Cuppa/SCons | Fights orchestrator stance; use export-pkg |

Tracked as GitHub issue [#29](https://github.com/ja11sop/cuppa/issues/29).

---

## Coverage reporting and performance

Goal: keep the multi-toolchain coverage reports (per test, by sconscript, by source) while
making `--cov --test` cheap enough to run routinely on large codebases.

Measurements, analysis of the current implementation, and the ordered list of candidate changes:
[`design/plans/coverage-performance.md`](design/plans/coverage-performance.md).

### Today

| Capability | Status |
|------------|--------|
| Per-test gcovr HTML + JSON (GCC and Clang) | Yes |
| By-sconscript and master indexes, toolchains compared side by side | Yes |
| By-source union across tests (JSON preferred, HTML fallback) | Yes, always on |
| Per-phase timing of a coverage run | No |

**Measured, 2026-07-31** — a header-heavy consumer project (**project A**: 38 test sconscripts,
362 single-source test binaries, 545 headers), `--cov --test --offline` after a clean
`--cov --parallel` build: **8m32** without by-source, **7m43** with it. By-source is not the
bottleneck on that project; the earlier suspicion that it caused a 40 → 70 minute regression on
another project is unconfirmed.

### Planned / potential

| ID | Work | Priority | Notes |
|----|------|----------|-------|
| `cov-timing` | Opt-in per-phase timing (gcov, gcovr, union, page writing, collation) | High | Nothing else should be optimised before this exists |
| `cov-once-per-test` | Run gcovr once per test binary instead of once per source file | High | `run_suite` is called inside the per-source loop in `_run_gcov`; an N× multiplier on multi-source tests |
| `cov-version-cache` | Cache the gcovr version instead of probing per report | Low | One subprocess per report today |
| `cov-union-once` | Share one union per toolchain between sconscript indexes and the master index | Medium | Same JSON is parsed at least twice per build |
| `cov-html-optional` | Make gcovr `--html-details` opt-in, with by-source as the browsing UI | Medium | Detail pages scale with tests × covered files and embed CSS each |
| `cov-union-incremental` | Cache the union on JSON mtime / size and skip unchanged work | Medium | Biggest win on repeat runs |
| `cov-branch-index` | Group branches by line once rather than scanning per line | Low | Removes an O(lines × branches) scan |
| `cov-second-project-ab` | Repeat the A/B measurement on the project the regression was reported from (**project B**) | High | Fewer, larger test binaries and much longer coverage runs than project A |

### Out of scope (coverage)

| ID | Item | Reason |
|----|------|--------|
| `cov-by-source-flag` | A permanent flag to disable by-source reporting | Measurement does not support it; make the report cheap instead. The temporary `--cov-by-source` used for the experiment has been reverted |
| `cov-msvc` | Coverage on MSVC | gcov-based; GCC and Clang only |

---

## Storage roots, listing, and removal

Goal: make the storage cuppa owns — the build tree, retrieved dependencies, cached downloads, and
local working copies used by `--develop` — something you can see and manage through cuppa, rather
than through `rm -rf` on paths you had to work out yourself.

The design, including the naming rationale, the safety model, and the sizing and inventory
mechanics: [`design/plans/removal-options.md`](design/plans/removal-options.md).

### Today

| Capability | Status |
|------------|--------|
| `--clean` removes the current variant's build outputs | Yes |
| `--list-develop` / `--update-develop` for the working copies `--develop` builds against | Yes — [#132](https://github.com/ja11sop/cuppa/issues/132); `--list-format=json` for develop — [#148](https://github.com/ja11sop/cuppa/issues/148) |
| `--clone-develop` / `--checkout-develop-branch` / `--reset-develop-branch` / `--location-base-branch` | Yes — [#154](https://github.com/ja11sop/cuppa/pull/154) (closes [#138](https://github.com/ja11sop/cuppa/issues/138) / [#153](https://github.com/ja11sop/cuppa/issues/153)) |
| Shared storage under `~/.cuppa`, named `--dependencies-root` / `--downloads-root`, with `--storage-root` to move both | Yes — [#133](https://github.com/ja11sop/cuppa/issues/133) / [#139](https://github.com/ja11sop/cuppa/pull/139) |
| Remove a whole build tree, a dependency, or a stale download | Builds: `--remove-builds` / `--remove-all-builds` ([#134](https://github.com/ja11sop/cuppa/issues/134) / [#140](https://github.com/ja11sop/cuppa/pull/140)); dependencies: `--remove-dependencies` / `--remove-all-dependencies` ([#142](https://github.com/ja11sop/cuppa/pull/142)), with selection-scoped archive product clean via `storage_clean` ([#143](https://github.com/ja11sop/cuppa/pull/143)); downloads: `--purge-dependencies` / `--purge-all-dependencies` ([#144](https://github.com/ja11sop/cuppa/pull/144)); clear-down: `--wipe-dependencies` / `--force-wipe-dependencies` / `--force-wipe-all-dependencies` / `--force-wipe-unreferenced-dependencies` ([#146](https://github.com/ja11sop/cuppa/issues/146) / [#150](https://github.com/ja11sop/cuppa/pull/150)) |
| See what is stored, where, and how large it is | Builds: `--list-builds` ([#140](https://github.com/ja11sop/cuppa/pull/140)); dependencies: `--list-dependencies` ([#141](https://github.com/ja11sop/cuppa/pull/141)), with lazy exact size upgrade ([#143](https://github.com/ja11sop/cuppa/pull/143)); downloads: `--list-downloads` ([#144](https://github.com/ja11sop/cuppa/pull/144)), filterable with `--list-scope` (`compact` + referenced sibling rules on [#161](https://github.com/ja11sop/cuppa/issues/161)) |

### Planned / potential

| ID | Work | Priority | Notes |
|----|------|----------|-------|
| `storage-listing-removal` | `--list-*`, `--remove-*`, `--purge-*`, `--wipe-*` for builds, dependencies, and downloads | Medium | Umbrella [#134](https://github.com/ja11sop/cuppa/issues/134) closed by [#144](https://github.com/ja11sop/cuppa/pull/144). Builds #140; list-deps #141; remove #142; archive clean #143; Phase 4 list-downloads + purge #144. Phase 3 polish [#145](https://github.com/ja11sop/cuppa/issues/145). Wipe [#146](https://github.com/ja11sop/cuppa/issues/146) closed by [#150](https://github.com/ja11sop/cuppa/pull/150). Remaining from this family: [#135](https://github.com/ja11sop/cuppa/issues/135) (artefacts). |
| `artefact-removal` | Decide how to remove artefacts written outside the build root | Low | Design pass first; `--remove-builds` deliberately stops at `_build`. GitHub [#135](https://github.com/ja11sop/cuppa/issues/135) |
| `console-report-patterns` | Document and keep judgement-tree / severity-timing rules for contributors and agents | Low | Issue [#161](https://github.com/ja11sop/cuppa/issues/161) closed by B/D/E follow-on; Antora [`contributing-report-patterns.adoc`](docs/modules/ROOT/pages/contributing-report-patterns.adoc); design [`console-report-patterns.md`](design/archive/console-report-patterns.md) |

### Out of scope (storage)

| ID | Item | Reason |
|----|------|--------|
| `storage-gc` | Automatic eviction of unused downloads | Deleting without being asked is the wrong default; listing plus explicit removal first |
| `storage-build-root` | Moving `build_root` under `--storage-root` | Build outputs stay project-relative and reviewable beside the sources |

---

## Toolchains as dependencies

Goal: fetched compilers behave like other cuppa dependencies — download once, extract under the
storage roots, register a stable non-colliding name for `--toolchains=` / `_build`, and list /
force-wipe with the same grammar as location and package trees.

Design (shipped): [`design/archive/toolchains-as-dependencies.md`](design/archive/toolchains-as-dependencies.md).
Umbrella: [#160](https://github.com/ja11sop/cuppa/issues/160) (Clang [#159](https://github.com/ja11sop/cuppa/pull/159), GCC [#164](https://github.com/ja11sop/cuppa/pull/164)).
C++ Profiles are a separate roadmap section — see [C++ Profiles](#c-profiles).

### Today

| Capability | Status |
|------------|--------|
| `--toolchain-archive=` / `--clang-root=` for Clang | Yes ([#160](https://github.com/ja11sop/cuppa/issues/160)) |
| `--gcc-root=` + `--toolchain-archive=` `.deb` for gcc-snapshot | Yes ([#160](https://github.com/ja11sop/cuppa/issues/160)) |
| Register `clang{major}_{tag}` / `gcc{major}_{stem}` (or `_local_{hash}`); auto-select when `--toolchains=` omitted | Yes |
| Discover cached installs under `dependencies_root/toolchains/{clang,gcc}/`; multi-select compare | Yes |
| External `--*-root=` persists registration (`cuppa-toolchain.json`) | Yes |
| List as type `toolchain`; force-wipe `[toolchain]…`; project remove/purge/wipe N/A | Yes |
| Shared transfer progress (HTTP download, extract, Conan stream, git `--progress`) | Yes ([#165](https://github.com/ja11sop/cuppa/pull/165); plan [`download-progress.md`](design/archive/download-progress.md)) |
| `--list-toolchains` (Discovered vs Registered, driver paths, JSON) | Yes — [#172](https://github.com/ja11sop/cuppa/issues/172) / [#170](https://github.com/ja11sop/cuppa/pull/170); design [`list-toolchains.md`](design/archive/list-toolchains.md) |
| `--list-toolchains --list-format=verbose` + `describe()` | Yes — [#172](https://github.com/ja11sop/cuppa/issues/172) / [#170](https://github.com/ja11sop/cuppa/pull/170); design [`list-toolchains-verbose.md`](design/plans/list-toolchains-verbose.md) |
| Toolchains hub + GCC / Clang / MSVC family pages | Yes — [#172](https://github.com/ja11sop/cuppa/issues/172) / [#170](https://github.com/ja11sop/cuppa/pull/170) |

### Planned / potential

| ID | Work | Priority | Notes |
|----|------|----------|-------|
| `list-toolchains` | `--list-toolchains` inventory; Discovered vs Registered; driver + storage paths; JSON; verbose `describe()` | High | Done — [#172](https://github.com/ja11sop/cuppa/issues/172) / [#170](https://github.com/ja11sop/cuppa/pull/170) |
| `list-tc-flag-tables` | Table-driven GCC/Clang/Cl init shared with `describe()` | Low | Deferred; see [`list-toolchains-verbose.md`](design/plans/list-toolchains-verbose.md) |
| `tc-dep-url-sugar` | Optional URL token in `--toolchains=` | Low | Keep `--toolchain-archive=` as explicit supply |
| `tc-dep-actions` | Authenticated Actions artifact URLs | Low | After public HTTPS / file path is solid |
| `tc-dep-msvc` | MSVC archive / layout as toolchain dep | Low | Separate driver; not gcc-snapshot |

### Out of scope (toolchains-as-deps)

| ID | Item | Reason |
|----|------|--------|
| `tc-dep-latest` | Auto “latest Profiles release” | Pinning and reviewability matter more than chasing HEAD |

---

## Future feature sections

Add new `##` headings here as larger efforts start, for example:

- Additional toolchains or platforms

Each new section should follow the same shape: **Today** → **Planned / potential** → **Out of scope**.

---

## Documentation tooling

### Today

| Capability | Status |
|------------|--------|
| Antora site under `docs/` with Mermaid and Lunr | Yes |
| Plain-text examples of report output in AsciiDoc | Yes — e.g. build-layout listing/removal samples |
| Terminal colour via colorama meanings (`as_error`, `as_info`, …) | Yes |

### Planned / potential

| ID | Work | Priority | Notes |
|----|------|----------|-------|
| `doc-output-samples` | Capture report output as semantic HTML for Antora and local preview | Low | Prefer meaning→CSS over ANSI scrape. [`design/plans/colourised-doc-samples.md`](design/plans/colourised-doc-samples.md) |

### Out of scope (docs tooling)

| ID | Item | Reason |
|----|------|--------|
| `doc-ansi-only` | Rely solely on ANSI→HTML for committed samples | Terminal palette and light/dark subdued handling make samples drift |
