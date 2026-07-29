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

- Fail configure with `StopError` when `--toolchains` matches no available toolchain instead of falling back to the platform default (#69).
- Honour project `default_variants` when only an action such as `--test` is active (#47).
- Avoid unused local typedef warnings in generated `version.cpp` when `CreateVersion` has no dependency entries (#25).

### Security

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
