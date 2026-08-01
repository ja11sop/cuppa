# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.4.0] - unreleased

### Added

- `--list-develop` reports the state of every configured develop working copy — branch, upstream,
  ahead / behind as of your last fetch, and whether the tree is modified — and exits without
  building. It warns when a copy is on the wrong branch, behind, diverged, or carrying local work
  on the default branch that no other build will see, and exits non-zero when a develop path does
  not exist. The report is written to standard output rather than logged, so `--verbosity` and
  `-Q` cannot take pieces out of it and `cuppa -Q -D --list-develop` prints the report on its own.
  Severity appears in a `STATUS` column as well as in colour, so it survives `--raw-output`.
  Below the table the reasons hang from the summary line as one tree, grouped by severity with the
  worst first and counted in each heading, so reading down it is reading a work list. Long reasons
  are wrapped to the table's right edge with the stem carried down the wrapped lines. The report
  closes by naming the copies `--update-develop` would fast-forward, when there are any (#132).
- `CUPPA_CONSOLE_BACKGROUND=light` (or `dark`) tells cuppa which way to make text recede: reduced
  intensity on a dark console, grey on a light one, where dimming black text can look untouched.
  `COLORFGBG` is used where a terminal sets it, and this setting overrides it.
- `--update-develop` fetches each git develop working copy and fast-forwards only those that are
  clean and strictly behind their upstream. Modified, ahead, diverged, and detached copies are
  left alone and reported. It refuses under `--offline`, and `-n` shows the plan without changing
  anything (#132).

### Changed

- `cuppa/VERSION` carries a `.dev` suffix while a release is being assembled, so a build from a
  checkout between releases reports, for example, `cuppa: version 1.4.0.dev` rather than claiming
  to be the last release. Released versions are unchanged.

### Deprecated

### Removed

### Fixed

### Security

## [1.3.2] - 2026-07-31

### Changed

- Location retrieval failures name the option that disabled retrieval (`--offline` or `--clean`) instead of always reporting `OFFLINE` mode, so a missing download during `--clean` is no longer reported as an offline build.
- `--clean` no longer fails when a location dependency is missing from the download root. Cuppa reports it at info level and lets the clean finish, warning only when `_build/<location folder>/` holds artefacts built from that location's sources, which can no longer be described and so cannot be cleaned. `--offline` still fails as before.
- `--clean` skips `pkg-config` parsing for GitLab registry packages that are not present in the download root, reporting at info level instead of aborting the clean.

## [1.3.1] - 2026-07-31

### Fixed

- `--modules` no longer lowers the C++ dialect. The C++20 floor now consults the dialect the build would actually use — `--stdcpp` if given, otherwise the toolchain default via `abi` / `abi_flag` — so a compiler defaulting to `c++2c` keeps `c++2c`. Previously `--modules` without `--stdcpp` forced `-std=c++20` while the variant path still said `cxx2c`, which broke sources using post-C++20 library features.

- The modules dialect floor is applied by the compile that builds, declares, or imports a module instead of when each variant env is created. It no longer repeats its message once per sconscript, and no longer changes the dialect for sources that use no modules.

- Dialect ranks are ordinal: `c++98` / `c++03` no longer outrank `c++26`, so `--stdcpp=c++98 --modules` is raised to C++20 rather than silently passing the floor check.

- GCC modules builds no longer repeat `-fmodules -fmodule-mapper=…` on translation-unit compile lines. `interface_module_flags` / `consume_module_flags` now omit those flags when `modules_enable_flags` has already put them on the env, so MSVC's paired `-reference name=path` argv tokens are left alone.

## [1.3.0] - 2026-07-30

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
- Conan integration / `examples/conan_fmt_plugin`: pin fmt **12.1.0** (latest ConanCenter 12.x with Clang 21+ / libc++ fix; fmtlib/fmt#4477). Approach C warm-install passes host settings matching `CUPPA_TEST_*`.
- Conan consumer: pass `tools.build:compiler_executables` from the Cuppa toolchain so `--build=missing` uses `clang++`/`g++` matching host settings (avoids CMake picking the wrong driver from `PATH`).
- Conan publish integration: generated-recipe `requires=`, `shared=True` round-trip, and explicit `source_modules_dir=` modules staging.

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

[1.4.0]: https://github.com/ja11sop/cuppa/compare/v1.3.2...HEAD
[1.2.0]: https://github.com/ja11sop/cuppa/compare/v1.1.3...v1.2.0
[1.1.3]: https://github.com/ja11sop/cuppa/releases/tag/v1.1.3
