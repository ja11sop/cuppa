# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

### Changed

### Deprecated

### Removed

### Fixed

- Conan integration / `examples/conan_fmt_plugin`: pin fmt **12.1.0** (latest ConanCenter 12.x with Clang 21+ / libc++ fix; fmtlib/fmt#4477). Approach C warm-install passes host settings matching `CUPPA_TEST_*`.

- Conan consumer: pass `tools.build:compiler_executables` from the Cuppa toolchain so `--build=missing` uses `clang++`/`g++` matching host settings (avoids CMake picking the wrong driver from `PATH`).

- Conan publish integration: generated-recipe `requires=`, `shared=True` round-trip, and explicit `source_modules_dir=` modules staging.

### Security

## [1.3.0-dev] - planned

### Added

- Optional Conan 2 consumer via `cuppa.conan_deps` / `cuppa.conan_dependency`, using Conan's **SConsDeps** generator, settings fingerprint cache, runtime library path injection, and `env.BuildWith` integration (#29).
- Optional Conan 2 publisher via `cuppa.package_managers.conan.ConanPackagePublisher` with `env.PublishPackage` (`conan export-pkg` of Cuppa-built artefacts; upload with `--publish-package`) (#29).
- Conan publisher hardening: hand-written `conanfile=` override, `shared=` option (`-o shared=`), and generated-recipe `requires=` (#29).
- Conan publisher modules/BMI parity: stage `final/modules/` into Conan packages; `conan_deps` loads `module-map.json` via `load_packaged_modules` (#29).
- Conan integration tests (`test_conan`): generators_folder reuse, full install + build, shared-library `--test` runtime paths, pip plugin discovery, offline cache-miss failure, publish export-pkg → consumer round-trip, `conanfile=` override with transitive requires, and modules/BMI publish round-trip (skipped when Conan 2 / modules-capable toolchain unavailable).
- Example pip dependency plugin `examples/conan_fmt_plugin` registering Conan-backed `fmt` via `cuppa.dependency.plugins`.
- Example pip dependency plugin `examples/cuppa_fmt_plugin` registering `fmt` via subclassed `location_dependency` (build static lib from source).
- MSVC Conan settings mapping (`compiler.runtime` / `compiler.runtime_type`, toolset → Conan `compiler.version`).

### Changed

- Document Cuppa `cxx2c` → Conan `compiler.cppstd=26` dialect mapping and prefer `generators_folder` for CI pre-installs.
- Clarify `--propagate-env` / `--propagate-path` / `--merge-path` (shell environment for subprocesses) versus dependency-injected runtime library paths for `--test` / `--run`.
- Clang `toolchain.name()` (build tree segment) includes a non-default `--clang-stdlib=` tag (e.g. `clang21-libc++`); `package_name()` equals `name()`. Linux default `libstdc++` paths stay untagged. **Breaking for libc++ users:** clean `_build` or expect artefacts under `*-libc++` instead of the bare Clang name; compile still uses `binary()`/`clang++`, and `--toolchains=clang` is unchanged.

### Fixed

- Propagate SCons `env['ENV']` into `IncrementalSubProcess` children when `scons_env=` is passed so `--test` / `--run` honour Conan (and other) runtime library paths.
- Pin `examples/cuppa_fmt_plugin` to fmt 12.2.0 so Clang + libc++ builds (undeclared `malloc`/`free` in fmt 11.1.4; fmtlib/fmt#4477).
- `env.Toolchain(name)` resolves Clang ABI-tagged `name()` values (e.g. `clang-libc++`) as well as registry keys (`clang`), so looking up `env['toolchain'].name()` works under `--clang-stdlib=libc++`.

## [1.2.4] - 2026-07-29

### Changed

- Document parallel-safe alternatives to multi-part shell Actions (`working_dir`, `cuppa.utility.command.run` with `cwd=`) and clarify `--use-shell` as an escape hatch (#14).
- Integration tests for the custom-command / `working_dir` documentation examples (`test_custom_commands`).
- `cuppa.utility.command.run` resolves relative executables against `working_dir` and returns subprocess status to SCons.
- Docs site Mermaid diagrams use `@sntke/antora-mermaid-extension` (client-side Mermaid.js) instead of `asciidoctor-kroki`, avoiding intermittent Kroki fetch failures at site-build time.

## [1.2.3] - 2026-07-29

### Changed

- Dual-barreled methods use explicit Depends names: `build_depends_on` and `test_depends_on` on `BuildTest`; `build_depends_on` and `benchmark_depends_on` on `BuildBenchmark`. Legacy `depends_on` / `data` remain as aliases and merge when both are set (#34).
- Single-barreled `Test` / `Benchmark` / `Run` prefer `depends_on` for run-side Depends; `data` remains a legacy alias (#34).
- Methods docs document `BuildTest`, `Test`, `BuildBenchmark`, `Benchmark`, and `Run` separately, with preferred parameters listed before deprecated aliases.

## [1.2.2] - 2026-07-29

### Fixed

- Avoid unused local typedef warnings in generated `version.cpp` when `CreateVersion` has no dependency entries (#25).

## [1.2.1] - 2026-07-29

### Fixed

- Fail configure with `StopError` when `--toolchains` matches no available toolchain instead of falling back to the platform default (#69).
- Honour project `default_variants` when only an action such as `--test` is active (#47).

## [1.2.0] - 2026-07-29

### Added

- Opt-in C++20 modules via `--modules` / `env.Modules()`, with `env.Module()`, `env.HeaderUnit()`, and `env.ImportModules()`.
- Modules compile path for named modules, interface and implementation partitions, implementation units, header units (including angle-bracket forms), and `import std` / `import std.compat` where the toolchain supports them.
- Toolchain modules support for GCC 14+, LLVM Clang 16+ (Apple Clang rejected), and MSVC toolset 14.2+ (`import std` on 14.3+ with STL `std.ixx`).
- BMI packaging under `final/modules/` with `module-map.json`, consumer `ImportModules`, and GitLab package `modules/` install support (toolchain-family BMIs only).
- Line-oriented module scanner with unit tests; capability matrix and Limits in Antora docs (`cxx-modules.adoc`).
- `ROADMAP.md` for large-feature status (modules today vs planned work).
- Antora diagram support via `asciidoctor-kroki` (Mermaid diagrams in methods, build layout, testing/coverage, and modules docs).
- NotifyProgress unit tests and documentation of when methods should (and should not) attach progress.
- Unit coverage for module scanner, toolchain gates, MSVC modules helpers, libc++ `std.cppm` discovery, Boost `b2` command construction, and release-only LTO flags.
- CI modules coverage on Linux (`gcc`, `clang`+libstdc++, `clang`+libc++), Windows (`vc`), and macOS (Homebrew LLVM + libc++ slice).

### Changed

- Version bump from 1.1.3 to 1.2.0.
- LTO is release-only (`--rel`) for both GCC and Clang; debug and coverage variants no longer enable LTO.
- Clang release builds gain LTO for parity with GCC (`-flto` / `-flto=auto` by version).
- `Filter` no longer calls `NotifyProgress` (selection-only helper; progress belongs to methods that emit actions).
- `GenerateBittenReport` runs only when the test variant action is active (aligned with HTML test reports).
- Documentation and comments prefer precise wording (for example “convenience method” instead of colloquial “sugar”).
- Expanded Antora docs for toolchains, methods, modules, build layout, and testing/coverage.

### Fixed

- Boost `b2` command construction builds argv as a list (avoids `shlex` quoting failures) and passes architecture / address-model where needed.
- MSVC modules: header units, `import std`, `-Fo` object path quoting, dialect mapping (`c++23` / `c++2b` → `-std:c++latest`), toolset version aliases, and Windows path handling for module references.
- `RemoveFlags` / `ReplaceFlags` treat MSVC `-std:` flags as a dialect family so `StdCpp` replacements work.
- macOS modules builds prefer Homebrew LLVM over Apple Clang (absolute drivers / PATH handling); `import std` discovers libc++ `std.cppm` on typical Linux and Homebrew layouts.
- Object naming disambiguates `.cpp` vs `.cppm` (and related suffixes); `--clean` removes module artefacts as expected.
- Clang release LTO: emit `-ffat-lto-objects`, prefer matching `llvm-ar` / `llvm-ranlib`, and use `-fuse-ld=lld` when available so static libraries (for example `libfmt.a`) do not lose symbols to a mismatched binutils `LLVMgold` plugin.

## [1.1.3] - 2026-07-28

Baseline release on `master` before the modules work landed.
Detailed notes for 1.1.x and earlier were not maintained in this file; start recording notable changes here from 1.2.0 onward.

[Unreleased]: https://github.com/ja11sop/cuppa/compare/v1.2.0...HEAD
[1.2.0]: https://github.com/ja11sop/cuppa/compare/v1.1.3...v1.2.0
[1.1.3]: https://github.com/ja11sop/cuppa/releases/tag/v1.1.3
