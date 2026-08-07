# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.5.0] - unreleased

### Added

### Changed

- Release workflow Actions buttons: **prepare** opens the `finish_release` PR; **publish**
  builds from master tip, creates the GitHub Release and tag, then waits for `pypi` approval.
  Manual `v*` tag push remains as an escape hatch. Antora **Contributing** documents the flow
  with Mermaid diagrams (`contributing.adoc` and children). See `release.txt`.

### Deprecated

### Removed

### Fixed

### Security

## [1.4.0] - 2026-08-07

### Added

- `--clone-develop` creates configured develop working copies that are missing or empty,
  cloning from the dependency's **unexpanded** git URL (no embedded tokens), checking out a
  branch that `--list-develop` will call ok, and recursing submodules. Refuses non-empty
  destinations and tag/revision pins. Compose with update:
  `cuppa -D --clone-develop --update-develop`. A `--develop` build that hits a missing path
  names this option (#138).
- `--checkout-develop-branch=NAME` switches every develop git working copy to `NAME` (use
  `current` for the consumer project's branch), creating the branch via the develop base + pull when
  needed. `--reset-develop-branch[=NAME|current|default|base]` returns copies to the develop base
  (bare / `base`), the published default (`default`), `current`, or a named branch, then
  fast-forwards where safe. `--location-base-branch` sets the develop home used by create and bare
  reset (defaults to `--location-default-branch`). Dirty or unpushed copies are left alone;
  `--list-develop` remains the check for outstanding work (#153).
- `--wipe-dependencies=name` clear-down of project-used extracts and matching downloads for the
  current selection (bypasses `storage_clean` product-only behaviour). Power tools:
  `--force-wipe-dependencies` with `[selector]name/qualifier` tokens (e.g. `[source]boost/1.8*`,
  `fmt/@11.1.1`; untyped tokens match all storage buckets) plus `--force-wipe-all-dependencies`
  and `--force-wipe-unreferenced-dependencies`. The same token grammar applies to
  `--remove-dependencies`, `--purge-dependencies`, and `--wipe-dependencies`. Removal reports nest
  **summary → type → identity → version → leaves** with removing/wiped vs remaining rollups.
  List/storage type `location` renamed to `repository` (Python `location_dependency()` unchanged).
  Partial force-wipe reports keep unmatched same-identity siblings visible. Do not combine wipe
  modes with remove or purge (#146).
- `--list-develop --list-format=json` emits structured develop-copy state for agents and scripts
  (`entries`, `would_update`, `worst_severity`, and the same context as the text banner). Text
  output is unchanged; exit status still fails when a develop path is missing (#148).
- `--list-downloads` lists cached archives under the downloads root as a hierarchical table
  (`referenced from downloads` / `unreferenced downloads`): each download file nests an `[E]`
  extract/package child. Type group is `source archives` (shared with `--list-dependencies`).
  Parent sizes and the footer count archive bytes only. `--list-format=verbose` adds LOCATION;
  `--list-format=json` includes `tree` and `entries` with `kind` `archive` or `product` (#134).
- `--purge-dependencies` / `--purge-all-dependencies` remove the same selection-scoped trees as
  `--remove-*`, then delete matching archives under the downloads root (project-used names only).
  The report nests download → `[E]` → source assets / products (`-✔-` when the extract stays).
  Leftover other-selection downloads stay. Missing archives are not a failure. Combining
  `--purge-*` with `--remove-*` is refused. Source Boost `storage_clean` still leaves the extract;
  the download file is deleted. Verify with `--list-downloads` (#134).
- `--boost-patched` selects the `patched/` Boost home (build / remove / purge).
  `--boost-patch-boost-test` remains as a deprecated alias.
- `--list-scope=all|referenced|unreferenced` filters which sections `--list-dependencies` and
  `--list-downloads` show (default `all`). Orthogonal to `--list-format`; JSON includes a
  `scope` field. Persist as `list_scope` in `~/.cuppaconfig` or `configure.conf`. Ignored by
  `--list-builds` and `--list-develop`. `--list-dependencies-scope` / `list_dependencies_scope`
  remain as a deprecated alias.
- Built-in source `boost` exposes `use_libs(libs, depends_on=[])` on the dependency instance
  returned by `env.BuildWith('boost')`, matching `boost_package` / `package_dependency` so a
  project can switch supply chains without changing sconscript call shape. It builds or reuses
  static libraries via `BoostStaticLibs` and appends them to `STATICLIBS`.
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
- `--storage-root` names the parent of the dependencies and downloads roots, so one flag moves
  cuppa's storage as a whole. `--dependencies-root` and `--downloads-root` set either root on its
  own and leave the other derived from the storage root. `--storage-root=_cuppa` keeps everything
  a build retrieves inside the project (#133).
- The dependencies and downloads roots are named at info level the first time a run retrieves
  anything, so where a build is reading from and writing to is visible in its output (#133).
- `--list-builds` reports the build root in three views and exits without building: an info-coloured
  folder total with the selected subset hung beneath it (`all N entries selected` when every entry
  matches), a toolchain → `variant/arch/abi` tree with `✓✓✓` / `-✓-` / `---` selection marks
  (ASCII `*`), and a sconscript tree with rolled-up sizes. Fully selected sconscript and toolchain
  name rows emphasise size, mark, and name in the info colour; partial and unselected rows are
  dimmed. A closing summary emphasises the selected size (info-coloured when less than the total)
  and prints an explicit `cuppa -D …` command for the selected builds present on disk (for use
  with `--remove-builds`). `--list-format=json` makes the same structures scriptable (#134).
- `--remove-builds` removes the variant subtrees that match the current toolchain and variant
  selection (the same composition the build uses), then prunes empty parents. It announces the
  removal, acts, then prints the same three views as `--list-builds` with a `REMOVED` column
  (error colour and checks for success; warning/error colour and ballots for failures, with a
  reason tree using short paths), and finishes with `Removed N entries freeing up SIZE` plus an
  explicit `cuppa -D … --list-builds` verification command. Mixed success/failure rollups use
  `✓-✗`. Dry-run (`-n`) shows the plan without deleting.
  `--remove-all-builds` removes the entire build root, with the same short-path announce styling,
  the same three REMOVED tables afterwards, and the same failure reason tree when the root cannot
  be deleted.
  Both refuse suspicious roots and symlink
  traversal and honour SCons `-n`. Neither touches artefact trees outside the build root.
  Annotated example output for `--list-builds`, `--remove-builds`, and `--remove-all-builds` is in
  the build-layout documentation (#134).
- `--list-dependencies` reports trees under the dependencies root as a ruled stdout table (size,
  type, dependency, version/branch, toolchain variant, last used, referenced / unreferenced) and
  exits without building. `type` is `gitlab`, `conan`, `location`, or `archive` (path-shape
  classification, recorded in the inventory for a future namespaced layout migration). Sizes come
  from a per-entry inventory under `<dependencies_root>/.cuppa-inventory/` (sampled during
  resolve/build with a leading `~` until listing upgrades, or exact after
  `--list-dependencies` upgrades missing/estimated entries or `--exact-sizes` forces a
  remeasure). Dependencies declare ownership through optional
  `storage_paths()`; resolve-only path discovery does not retrieve. `--list-format=json` is
  supported (#134).
- `--remove-dependencies=name1,name2` and `--remove-all-dependencies` remove selected trees under
  the dependencies root for dependencies **this project uses** (`default_dependencies` ∪ names
  from `dependencies=[…]`), using the current toolchain / variant / location-match selection.
  Auto-scanned built-ins such as `boost` are rejected unless the project names them. They announce,
  support SCons `-n`, never delete develop working copies or downloads, and finish with a
  `--list-dependencies` verification hint. Unknown or unused names print an error plus a ruled
  in-use dependency tree (same presentation as `--list-dependencies`, referenced only) so the
  removable keys are obvious. The report is a ruled tree: muted rolled-up size on the identity
  (name and package version emphasised), `LAST USED` and remove/leave status on each leaf, checks
  for successful or planned removals and ballots for failures (same marks as `--remove-builds`),
  muted leftover leaves for other selections, a short "Leaving … as shown" line, and an
  info-coloured freed-space summary. For archive deps with `storage_clean`, the identity SIZE is
  the full extract (aligned with `--list-dependencies`); products and a muted `source assets`
  leaf hang under `[E]`, and the freed-space line states the remaining archive size after product
  removal. After a live archive product clean, cuppa rewrites that extract's inventory size with
  `--exact-sizes` semantics, and the verify hint is
  `cuppa -Q -D --list-dependencies` (listing upgrades missing or estimated inventory sizes to
  exact on encounter so list and remove sizes correlate).
  Passing multiple toolchains removes each matching package
  variant. Dependencies may implement optional `storage_clean(env, selection)` to remove
  selection-scoped products while leaving the archive extract in place; source Boost cleans the
  current selection's b2 stage and matching Boost.Build toolset **variant** folders under
  `bin.<abi>`   (not the whole `bin.<abi>` tree, and not a bare toolset directory that may hold
  another variant). Bin leaves use honest Boost.Build family tags such as
  `clean/bin.c++2c [gcc-15*/debug]` (major family ± patch; cuppa minors like `gcc153` are
  not implied); stage leaves use the cuppa-precise scope
  `clean/build.c++2c [gcc153/debug/x86_64]`. Other stage/toolset products are leftovers.
  Dependencies without `storage_clean`
  still remove the whole owned tree under the dependencies root (#134).
- Optional dependency protocol `storage_clean(env, selection)` returns `None` (unsupported) or
  a result with `targets` (`{paths, label, tool_variant}`) plus `extract` (flat `paths` still
  accepted). Cuppa measures sizes per target at removal time (#134).
- Removal reports use dedicated `remove_notice` (warn / purple family) and `remove_error`
  semantics so planned or successful removals are distinct from ordinary info, while failed
  attempts stay in the error family. `--remove-builds` outcome trees use the same accents
  (checks for success, ballots for failure); failure reason trees keep ordinary error / warning
  colours (#134).
- Table padding for coloured listing cells uses visible width (ANSI ignored), so
  `--list-dependencies` columns stay aligned between referenced and unreferenced rows and the
  ruled header is not stretched by escape sequences (#134).
- `--list-dependencies` under `--develop` binds location trees under the dependencies root to the
  registry name and shows REMARK `develop` on the dependency name (branch leaves unmarked), with a
  footer pointing at `--list-develop` (#134).
- `--list-dependencies` shows expected-but-absent default dependencies as error-coloured
  `STATE` `missing` rows (size `-`) instead of only logging a resolve failure; Location soft-returns
  the expected path under resolve-only so listing can see it (aligned with GitLab packages). The
  footer reports a missing count; JSON includes `missing_count` and `state: missing`. Fixed a
  post-table crash when rendering skips (`glyphs` tuple unpack) (#134).
- `--list-dependencies` presents a hierarchical tree (referenced then unreferenced; type →
  short-name / registry identity → branch or version / toolchain children) with rolled-up sizes,
  REMARK (`in use` / `N used` when N>1 / `missing`), and short names derived from git remotes, package
  paths, and Boost archive heuristics. Missing identity rows show the configured
  `remote_location()` (URL or registry/package/version) instead of the short name; missing SIZE and
  LAST USED are `-`, and missing GitLab versions repeat the `missing` remark. Referenced section
  leads with used / potentially-stale size rollups (`N total` / `N used` / `N unused`), emphasises
  referenced dependency names (muted brackets; muted identity SIZE/LAST USED), keeps section rows
  and unreferenced group/identity names in normal colour, partitions referenced from unreferenced
  with a rule, and places `missing` only on the absent leaf. Under `--develop`, shadowed stems use
  REMARK `develop` on the identity (info-coloured like `in use`) rather than `cached` on each
  branch, with a footer pointing at `--list-develop`. Verbose LOCATION for location trees uses
  `URL@branch` on leaves; GitLab puts the registry URL on the version row and the archive
  basename on the toolchain leaf. Unspecified
  location folders show as `@`. On-disk LOCATION is available via `--list-format=verbose`;
  `--list-format=json` includes a `tree` object plus enriched flat `entries` (#134).
- Documented which listing answers which question (`--list-dependencies` vs `--list-develop` vs
  combining `--develop`), with motivating examples on the Dependencies page, and added an
  integration scenario that plants realistic git develop copies for `--list-develop` (#134).

### Changed

- The `release` workflow builds sdist and wheel, creates the GitHub Release from the CHANGELOG
  section, and publishes to PyPI via Trusted Publishing after approval on the `pypi` environment.
  Tag push and `workflow_dispatch` (existing tag) both drive it; see `release.txt`.
- Real `BuildWith` / default-dependency resolves stamp inventory `last_used` and `used_by`
  (sconstruct directory). `--list-dependencies` and remove / purge still do not (#145).
- Conan installs write `.cuppa_conan_meta.json` (fingerprint, name, `tool_variant`, settings)
  and backfill it on reuse so `--list-dependencies` can label Conan rows (#145).
- Location VCS trees use canonical `stem@<branch>` folders going forward (including the default
  branch). Existing unqualified stems are kept when they are the only copy; when both exist,
  resolve prefers the canonical folder and warns. `--list-dependencies` labels the unqualified
  row `@<default> (unqualified)` (#145).
- Dependencies documentation is split into a short hub plus location, packages, GitLab, Conan,
  built-ins / Boost / Qt / Quince, managing, and extending pages. `packages.adoc` is retitled
  toward publishing; consume material lives under Dependencies (#145).
- `--list-dependencies` upgrades missing or sampled inventory sizes to exact on encounter
  (with a subdued notice that the pass may take a while). `--exact-sizes` still forces a full
  remeasure of every tree. Archive-product remove verify hints drop the mandatory
  `--exact-sizes` flag (#134).
- Archive `--remove-dependencies` / `--purge-dependencies` reports nest products and
  `source assets` under an `[E]` extract row (`---` / `-✔-` / `✔✔✔`). Empty `bin.<abi>` husks
  with no toolset children stay on disk but are omitted from leftover rows.
- ROADMAP and the removal plan mark archive clean-by-variant done (#143) and Phase 4
  downloads/purge as next; Dependencies docs add a Boost `storage_clean` remove sample and
  document optional `storage_paths` / `storage_clean` on the Extending page (#134).
- `watch-pr` polls CI on a sparse schedule (2 minutes, then 8, then every 2 minutes) instead of
  every 30 seconds, and falls back to the sealed credential if the public API rate-limits. Pass
  `--interval` for a fixed delay, or `--auth` to start authenticated.
- `update-pr` patches an open pull request's title and/or body (and can add labels) through the
  sealed credential, so agents do not hand-roll `PATCH /pulls/{n}` response handling.
- Agent notes (`AGENTS.md`) spell out settling plan vocabulary before coding, updating plan
  progress with behaviour commits, encoding repeated chat corrections, and what to do when
  Actions shows no check runs during a forge outage.
- `cuppa/VERSION` carries a `.dev` suffix while a release is being assembled, so a build from a
  checkout between releases reports, for example, `cuppa: version 1.4.0.dev` rather than claiming
  to be the last release. Released versions are unchanged.
- Retrieved dependency trees and downloaded archives now default to `~/.cuppa/dependencies` and
  `~/.cuppa/downloads`, shared between projects. Previously dependencies went into a `_cuppa`
  folder inside each project, so the same library was retrieved again for every project that used
  it. Where a `_cuppa` folder beside your sconstruct, or a `~/_cuppa/_download` or `~/_cuppa/_cache`
  from an earlier cuppa, already exists and you have not named a root yourself, cuppa keeps using
  it and says so once, so upgrading does not trigger a re-fetch. Pass `--storage-root=_cuppa` to
  keep the previous project-local arrangement (#133).
- The environment keys are `storage_root`, `dependencies_root`, and `downloads_root`.
  `download_root` and `cache_root` remain as aliases of the resolved values, so a dependency
  plugin reading them keeps working (#133).

### Deprecated

- `--list-dependencies-scope` is deprecated in favour of `--list-scope` (same values; also
  applies to `--list-downloads`). Existing `list_dependencies_scope` conf entries still work.
- `--boost-patch-boost-test` is deprecated in favour of `--boost-patched`.
- `--download-root` and `--cache-root` are deprecated in favour of `--dependencies-root` and
  `--downloads-root`. They still choose the same roots, and cuppa names the replacement when one
  is used (#133).

### Fixed

- `git+file://` locations with a Windows drive letter and `@branch` (urlparse puts the path in
  `netloc`) now split versioning correctly, so `--clone-develop` can `ls-remote` a local origin
  on Windows (#138).
- Removal-report spacer rows use encoding-safe tree glyphs (ASCII `|` on legacy Windows
  consoles) instead of a hardcoded box-drawing pipe that raised `UnicodeEncodeError` under
  `cp1252` (#146).
- Boost archive-clean integration planting follows `Clang.name()` when
  `--clang-stdlib=libc++` is active (stage path `clangNNN-libc++`), so the
  `clang-libc++` CI cell matches remove selection (#134).
- Integration `run_cuppa` keeps the repository root on `PYTHONPATH` when tests pass
  `extra_env={"PYTHONPATH": …}` (e.g. pip-installed dependency plugins), so
  `python -m cuppa` does not fail with `No module named cuppa`.
- `--list-dependencies --list-scope=referenced` footer reports
  `N entries, X total, X referenced` instead of a useless `0B unreferenced`.
- `--list-dependencies` prints the `[D]` downloads-archive footer only under
  `--list-format=verbose`, matching where the mark appears in LOCATION.
- Conan consumer install cache fingerprints ``CONAN_HOME`` (or ``~/.conan2``) alongside
  the recipe and settings, and reinstalls when cached SConsDeps ``CPPPATH`` / ``LIBPATH``
  entries no longer exist (``BINPATH`` is ignored — Conan often lists a non-existent
  ``bin`` folder). Isolated ``CONAN_HOME`` (integration tests, CI) no longer reuses
  generator output that still points at a deleted Conan package folder.
- `--remove-dependencies` location integration tests plant OS-correct cache folder names
  (Windows MD5-shortened URL folders) so dry-run / remove resolve the same trees cuppa
  expects (#134).

- Referenced dependency-tree summaries no longer count ``missing`` leaves as
  "potentially stale" / unused. Absent expected trees get a ``missing dependencies`` /
  ``N missing`` summary row (error-coloured like other missing rows) (#134).
- `--list-dependencies` and the unknown-name remove hint print
  `Collating dependency tree...` before the walk so long inventories show progress on
  stdout (skipped for `--list-format=json`) (#134).
- `--remove-dependencies` accepts only names this project uses (`default_dependencies` ∪
  `declared_dependencies` from `dependencies=[…]`). Auto-scanned built-ins such as `boost` are no
  longer removable on a package-only sconstruct, which previously could plan deletion of a shared
  Boost extract under the dependencies root. Rejected names print a ruled in-use dependency tree
  for the current selection instead of a flat key list (#134).
- GitLab package cache keys now include the package `tool_variant` (toolchain / package variant /
  arch / ABI). A single `--toolchains=gcc,clang` run no longer reuses the first toolchain's package
  instance for the second, so `--list-dependencies` and `--remove-dependencies` resolve each
  matching extract (#134).
- Verbose `--list-dependencies` `[D]` footer no longer uses a Unicode em dash in the
  "corrupt archive" sentence. On Windows that character could not be encoded to the console
  code page after the first footer line, so the advice was missing from captured output while
  the listing still exited 0 (#134).
- Dependency listing examples in the Dependencies documentation match real table layout: full-width
  partition rules, right-aligned `SIZE`, stem-only connector rows, and current
  `--list-develop` columns. The “which listing” comparison table is AsciiDoc (`|===`), not
  Markdown (#134).
- GitLab package archive naming no longer calls Linux-only `platform.freedesktop_os_release()`
  unconditionally. On Windows and macOS it falls back to a stable OS label (`windows` / `macos`)
  so package construction — and therefore `--list-dependencies` registry LOCATION for GitLab
  packages — works outside Linux (#134).
- GitLab packages publish and prefer `.zip` on Windows (`.tar.gz` elsewhere). Download resolve
  also accepts the alternate extension so an existing `*_windows_*.tar.gz` still works until
  republished. Boost LOCATION reconstruction preserves the on-disk archive extension (`.zip` on
  Windows downloads) instead of always emitting `.tar.gz` (#134).
- `--list-dependencies` verbose LOCATION for unreferenced GitLab packages now shows the registry
  `registry/package/version` URL on each version row (matching referenced). The inventory stores
  `remote_location` when resolve knows it; sibling versions of the same package inherit that base
  with the version segment substituted when only one version was resolved. When every known GitLab
  URL shares one registry prefix, other packages on disk (e.g. never resolved by the current
  project) get `{registry}/{package}/{version}` as well (#134).
- `--list-dependencies` groups GitHub release archives under `github.com/<owner>/<repo>` with the
  tag as the version (like Boost under `boost`), and stores/shows the reconstructed download URL
  as LOCATION instead of only the encoded on-disk folder name (#134).
- Verbose `--list-dependencies` prefixes LOCATION with `[D]` when a regenerating archive exists
  under the downloads root (HTTP/Boost extracts and GitLab package tarballs). On GitLab trees the
  mark appears on toolchain archive leaves only, not on the registry URL version row. A footer
  explains the mark and that a corrupt download must be removed there - deleting only the
  dependency tree is not enough. Documented with examples on the Dependencies page and covered by
  the list-dependencies integration scenario (#134).

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

[1.5.0]: https://github.com/ja11sop/cuppa/compare/v1.4.0...HEAD
[1.4.0]: https://github.com/ja11sop/cuppa/compare/v1.3.2...v1.4.0
[1.2.0]: https://github.com/ja11sop/cuppa/compare/v1.1.3...v1.2.0
[1.1.3]: https://github.com/ja11sop/cuppa/releases/tag/v1.1.3
