# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.8.0] - unreleased

### Added

- `--artefacts-root` (default `_artefacts`; legacy `_artifacts/` kept when present): project-relative root for generated reports and
  other artefacts outside `_build/`; exposed on the construction `env` as `artefacts_root` /
  `abs_artefacts_root` (US aliases `artifacts_root` / `abs_artifacts_root`). C++ Profiles
  reports honour it (`<artefacts-root>/cxx-profiles/`).
  Coverage and test HTML still use the conventional tree until a follow-on wires them through.
- `--list-available-reports` lists built-in HTML report kinds in a judgement tree (Methods, CLI,
  toolchains by family) and which toolchains on this system can produce each; supports
  `--list-format=json`.
- `env.CollateCxxProfilesIndex()` declares Profiles session index capture from a sconscript (same
  output as `--cxx-profiles-report`; optional `destination=` and `link_style=` kwargs).
- `.cuppa-reports` manifest for C++ Profiles reports (slice D, `prof-report-manifest`): append
  JSONL entries at `sconstruct_end`; matched removal when `--clean` or `--remove-builds` runs with
  the same `--cxx-profiles-report` destination and link options.
- Profiles violation report HTML + JSON (slice C, `prof-report-html`): emit
  `cxx-profiles-index.html`, per-scope detail pages, and `cxx-profiles-index.json`
  under `_artefacts/cxx-profiles/` at `sconstruct_end` when `--cxx-profiles-report`
  is set; `--cxx-profiles-report-link-style=` (Profiles override) and `--reports-link-style=`.
- Profiles report Overview context (slice H, `prof-report-context-summary`): master-index
  **Overview** tab and top-level `context` JSON with rule concentration, zero-filled profile
  rule matrix, tier-1/tier-2 codebase metrics, `-H` parsed-file capture on report builds, and
  `--cxx-profiles-report-context=full|rules-only|off`
- Profiles report index roll-up tables expose structured `variant_display` (`common`, per-build
  `deltas[]`, `build_order`, `totals`) on by-rule and by-file rows for multi-build sessions;
  separate **Union Refs** and **Peak Refs** columns with bold total = common + deltas.
  Overview Violation totals card uses *distinct violations*, *distinct rules*, and *union references*
  with column labels `(Violations)`, `(Rules)`, `(Union Refs)`; matrices use **Union Refs**.
  Build inventory load uses **Build Refs**.
  Antora pages xref:cxx-profiles/report-introduction.adoc#reference-metrics[Report — reference metrics] and
  xref:cxx-profiles/report-by-rule.adoc[Violations By-Rule] document each aggregate.
- Profiles report index **Violations By-Build** tab: build inventory load table, sub-tabs per build id,
  and unified **By-Rule** / **By-File** tables ( **Profile** column) aggregated across all
  sconscripts for that compile inventory row. Antora:
  xref:cxx-profiles/report-by-build.adoc[Violations By-Build].
- Per-scope detail pages: one **Violations By-Rule** / **By-File** tab pair with **Profile** column
  (all profiles in the same tables); build heading `variant/tail — toolchain` matches By-Build.
  Antora: xref:cxx-profiles/report-by-sconscript.adoc[Violations By-Sconscript].
- Profiles report JSON anonymisation (slice G, `prof-report-anonymize`):
  ``python -m scripts.anonymise_profiles_report`` transforms saved
  ``cxx-profiles-index.json`` into a shareable artefact (``metadata.anonymised``,
  path rewrites, recomputed ``location_key``); ``regenerate_profiles_report --anonymised``
  skips ``by-source/`` pages and suppresses file/repo hrefs.
- Profiles violation report parser groundwork ([#184](https://github.com/ja11sop/cuppa/issues/184)):
  `cuppa/cpp/cxx_profiles_report.py` parses Clang Profiles diagnostics, classifies rule
  ids, and dedupes violations per scope (slice A).
  `python -m scripts.replay_profiles_capture` replays saved build captures using
  ``Progress( … )`` scope markers.
  `python -m scripts.regenerate_profiles_report` replays a capture and rewrites HTML/JSON
  without recompiling (for template iteration). Prefer ``--from-json`` on saved
  ``cxx-profiles-index.json`` (``summary``, ``locations[]``, extended ``metadata``,
  ``schema_version: 1``).
  Capture replay strips ANSI colour sequences from ``tee`` output; the live collector hot path
  does not.
- Profiles violation capture during builds (slice B, `prof-report-collector`):
  ``--cxx-profiles-report`` activates an in-process collector wired through
  ``ToolchainProcessor`` with per-sconscript spawn scope; session summary and HTML/JSON
  at ``sconstruct_end``.
- Profiles parser layering (B½, `prof-report-parser-layers`): split inventory,
  Clang line parsing, and profile-keyed classifiers under ``cuppa/cpp/profiles_report/``;
  ``examples/profiles/std-init-violations/`` and ``std_init_golden.json`` fixtures for
  spec-driven rule capture.
- Antora: xref:cxx-profiles/std-init.adoc[std::init profile] rule-family pages with Clang
  examples; navigation under xref:cxx-profiles.adoc[C++ Profiles]. Fix ``C++ Modules`` title
  capitalisation across the site.

### Changed

- Storage and report catalogue spelling: British `artefacts_root` / `--artefacts-root` are
  canonical; US `artifacts_root` / `--artifacts-root` remain accepted aliases on the same paths.
- Profiles report anonymisation uses British spelling in module names, metadata fields
  (``metadata.anonymised``, ``anonymisation_version``), and CLI flags (``--anonymised``).
  US variants (``anonymize`` module alias, ``--anonymized``, legacy metadata keys) are still
  accepted without appearing in help text.
- Anonymised Profiles HTML regen reads index and scope headers from saved JSON ``metadata``
  (``report_project``, cleared VCS fields) instead of live git or the regen working directory.
- Violation report documentation: xref:cxx-profiles/report-introduction.adoc#sharing-anonymised[Sharing an inventory (anonymised JSON)] on Introduction; regen tables document ``--anonymised``.
- Violation report documentation: xref:cxx-profiles/report-introduction.adoc[Introduction] replaces
  shared concepts as the feature entry point (build command, ``regenerate_profiles_report``,
  JSON for CI/agents); tab guides aligned to a common structure; Overview page scoped to the
  Overview tab only.
- Profiles report index by-rule / by-file roll-ups key per-build buckets by
  `(variant_label, variant_display_tail, toolchain)` instead of variant label alone; multi-build
  rows render bold union totals with `= common` plus `+N dbg1`-style deltas when builds diverge,
  or a single total when all builds agree. By-Rule adds **Peak Refs** alongside **Union Refs**; inventory serialises per-key `row_peak` for correct union ref roll-ups.
  By-Rule file subtable adds **Build Refs** aligned with **Violating Files** lists;
  Antora pages xref:cxx-profiles/report-introduction.adoc#reference-metrics[Report — reference metrics] and
  xref:cxx-profiles/report-by-rule.adoc[Violations By-Rule] document Union Refs, Peak Refs, and Build Refs.
- Per-scope Profiles report pages omit the **Peak Refs** column (single-build view): parent and
  subtables show **Build Refs** only alongside **Union Refs**; scope inventory uses the same
  variant buckets as session roll-ups. Antora:
  xref:cxx-profiles/report-introduction.adoc#scope-metrics[scope metrics],
  xref:cxx-profiles/report-by-sconscript.adoc[By-Sconscript], and report hub
  xref:cxx-profiles/report.adoc[Violation report reading guide].
- Overview **Rule concentration** and **Profile matrices** add **Peak Refs** (with %) alongside **Union Refs**
  for correlation with index By-Rule rows. **Build inventory load** uses the **Build Refs** column label; variant
  rows sum per-scope compile inventory (`build_references`).
- Index **Violations By-Sconscript** table: separate **Rules** and **Violations** columns (replacing
  Distinct/Unique), plus **Build Refs** alongside **Union Refs**.
- Violation report Antora split: xref:cxx-profiles/report-introduction.adoc[Introduction] (generate,
  regen, JSON, Profiles/rules/violations/reference types), xref:cxx-profiles/report-by-file.adoc[By-File],
  xref:cxx-profiles/report-by-sconscript.adoc[By-Sconscript], xref:cxx-profiles/report.adoc[reading guide hub];
  Overview reference-metrics section moved to Introduction.
- `--reports-link-style=` session flag for HTML report source links (test + Profiles); shared
  helpers in ``cuppa/reports/link_style.py`` (GitHub ``/blob/``, GitLab ``/-/blob/``). Profiles
  ``--cxx-profiles-report-link-style=`` overrides the session flag.
- C++ Profiles report JSON envelope (`schema_version: 1`): top-level ``summary`` (counts +
  ``by_rule`` map), flat ``locations[]`` with stable ``location_key``, extended ``metadata``
  (``profiles_enforce``, ``variant_labels``, ``incomplete_scopes``, ``partial``), and ``doc_href``
  on rule entries (scope, rollup, and file views). Legacy bare ``scopes``/``rollup`` objects still
  load for tests and early captures.
- Antora: move dependency, toolchain, C++ Profiles, and Contributing child pages into folders
  mirroring navigation (`dependencies/`, `toolchains/`, `cxx-profiles/std-init/`, `contributing/`);
  hub URLs unchanged.
- Readable style: document PascalCase variables in `AGENTS.md`; align std::init example sources,
  Antora listings, and golden diagnostics with snake_case types/functions and property-like
  public struct members.
- Antora: apply Readable C++ style to all `[source,cpp]` listings (including
  xref:cxx-modules.adoc[C++ Modules] tutorials).
- Integration fixtures: Readable C++ naming in `tests/fixtures/modules_project/` and
  generated test sources that mirror example style.

### Deprecated

### Removed

### Fixed

- Boost default version resolution: unpinned Boost (no ``--boost-version=``) checks boost.org when
  online after any stored ``boost_latest_version`` before falling back to the compiled-in default;
  persist after download when higher. ``--boost-latest`` overrides a pinned version or forces a
  fresh scrape ([#201](https://github.com/ja11sop/cuppa/issues/201)). GitLab docs add publish/consume
  Boost package examples.
- Anonymised Profiles report regen no longer treats placeholder `metadata.sconstruct_dir`
  (`/home/user/project/widget`) as a writable path; output defaults to the input JSON directory
  unless `--report-dir=` is set.
- C++ Profiles report compile hook: TU capture wrapper accepts the SCons environment as its
  first argument (fixes `TypeError` when `--cxx-profiles-report` wraps `Compile` methods).
- C++ Profiles report builds: ``-H`` include-stack lines are captured for Overview metrics but
  no longer echoed to the console.
- C++ Profiles `.cuppa-reports` clean matching: `invocation_key` now ignores `--clean` and
  `--remove-builds` in `sys.argv` so a clean run can match the report invocation. A
  `--clean --cxx-profiles-report` configure pass removes matching manifest entries without
  activating the Profiles collector when Profiles flags are omitted (report options on the clean
  command must still match those used when the report was generated).

## [1.7.0] - 2026-08-10

### Added

- Opt-in C++ Profiles ([#127](https://github.com/ja11sop/cuppa/issues/127)): `--cxx-profiles`
  enables `-fprofiles` on Profiles-capable Clang (probed; StopError otherwise).
  `--cxx-profiles-enforce=<designators>` implies `--cxx-profiles` and either uses toolchain
  native enforce flags when present or injects `[[profiles::enforce(…)]];` via
  `-include`. `--cxx-disable-error-limit` removes the compiler diagnostic cap
  (Clang/GCC; MSVC `cl` has no supported equivalent) for full error inventories —
  useful with enforce. When a TU already has `[[profiles::enforce(…)]];`, cuppa
  merges CLI designators into that attribute in a build-tree compiler view (slice H). First smoke
  target: `std::init`. Design:
  [`design/archive/cxx-profiles.md`](design/archive/cxx-profiles.md). Antora guide:
  [`cxx-profiles.adoc`](docs/modules/ROOT/pages/cxx-profiles.adoc).

### Changed

- C++ modules CLI and methods use the `cxx-` vocabulary: `--cxx-modules` and
  `env.CxxModules()` are canonical in documentation.

### Deprecated

- `--modules` and `env.Modules()` — use `--cxx-modules` / `env.CxxModules()`; removed in
  cuppa 2.0.

### Fixed

- Force-wipe unqualified-stem hints emit matching ``name/@`` tokens instead of
  host/path forms that reported ``no leaf matches`` ([#178](https://github.com/ja11sop/cuppa/issues/178)).
  Dry-run report parents use a neutral ``related dependencies`` label (not the
  raw selector or a dumped identity list). Location stem-duplicate notices run
  only for list / remove / purge / wipe (debug log, not warn); ordinary builds
  stay quiet. ``--list-scope=compact`` omits those notices and wipe candidates
  so the tree does not advertise hidden leaves.

## [1.6.0] - 2026-08-10

### Added

- `design/ideas/scratchpad.md` holds pre-plan product ideas (living). Notes graduate into
  `design/plans/` and `ROADMAP.md`, then leave the scratchpad. `*.local.md` remains for private
  project maps only.
- Design plans: [`boost-latest-persistence.md`](design/archive/boost-latest-persistence.md) and
  [`list-toolchains.md`](design/archive/list-toolchains.md) (1.6.0 cycle; tracked as
  [#171](https://github.com/ja11sop/cuppa/issues/171) /
  [#172](https://github.com/ja11sop/cuppa/issues/172)).
- Boost latest persistence ([#171](https://github.com/ja11sop/cuppa/issues/171)): remember
  `boost_latest_version` in project `configure.conf` or `~/.cuppaconfig` according to whether
  `--downloads-root` sits under the project. Default Boost resolve prefers that stored value,
  then the compiled-in default, and does not scrape boost.org unless `--boost-latest` is passed.
  The key updates only when a higher version’s archive is present under downloads-root.
- `--list-toolchains` ([#172](https://github.com/ja11sop/cuppa/issues/172)): ruled
  **discovered** / **registered** tree (family → version → driver → name(s)), with shared-driver
  grouping, per-family and platform-default marking (platform family `(default)` only when the
  bare default name is present), inventory-backed registered SIZE/LAST USED, summary line, and
  dry-run wipe hint. Nested `--list-format=json`. `--list-dependencies` toolchain leaves show the
  Cuppa session name (`gcc17_gcc_snapshot_…`) aligned with `--toolchains=`.

### Changed

- GCC default dialect flags no longer pass `-fconcepts` / `-fcoroutines` once the chosen
  `-std=` already enables those features (GCC 11+). Extras remain only where still required:
  `-fconcepts` on GCC 8–9, `-fcoroutines` on GCC 10. Clang and MSVC were already dialect-only.
- `--list-dependencies` toolchain leaf labels use the Cuppa `--toolchains=` session name when the
  install is registered in the current session (on-disk `toolchains/<family>/<qualifier>/` layout
  unchanged).
- `--list-toolchains --list-format=verbose` hangs an info subtree under each driver: notice/yellow
  keys (`available dialects:`, `usable features:`, `stdlib choices:`, `default invocations:`,
  `c++`/`c`/`link`), normal variant names (`dbg`/`cov`/`rel`) and flag values, subdued commas
  and `<…>` placeholders. Dialects list every `-std=` name for that compiler generation
  (working-draft token before ISO alias, e.g. `c++2c` then `c++26`; Cuppa default marked).
  Usable features use dialect-inclusive shorthand (`all c++2c`, `all c++2a, coroutines`) or a
  bare gated name on older tools (`concepts`), and append `modules (experimental)` when Cuppa
  can enable modules. Qualifiers `(default)` / `(experimental)` are subdued. Invocation
  templates include `<sources>` / `<objects>` / `<static_libs>` / `<dynamic_libs>`; Cuppa
  default libraries (e.g. `-lpthread -lrt`) are listed normally before the matching
  placeholder. JSON includes the same `describe` payload on driver nodes. Horizontal rules
  span the full width of the widest content line (including verbose dialect / invocation
  rows). Toolchain classes expose `describe()` / `default_dialect()` / `usable_features()`.
- Toolchains documentation is a hub plus family pages (`toolchains/gcc.adoc`,
  `toolchains/clang.adoc`, `toolchains/msvc.adoc`) with short introductions, upstream homepage
  links, and per-flag default-invocation explanations. Hub pages include `--list-toolchains`
  text / verbose / JSON samples, a `--stdcpp` choice table (default behaviour is effectively
  `c++latest` on GCC/Clang), and JSON samples for the other `--list-format=json` list actions.
  AsciiDoc `++` / `C++` escapes so Antora no longer eats `libstdc++`, `clang++`, or dialect
  tokens.
- Listing / remove / purge doc samples (dependencies, downloads, develop, toolchains, builds —
  text and shortened `--list-format=json`) are rendered through the real CLI formatters
  (`python -m scripts.generate_doc_samples` → `docs/modules/ROOT/partials/samples/`), so tree
  stems and JSON shape stay aligned with live output. JSON examples use collapsible blocks in
  the Antora pages.
- Verbose `--list-toolchains` quotes each default-invocation template
  (`c++: "-Wall … <sources>"`); the surrounding quotes are subdued like placeholders.
- `--list-format=json` pretty-prints with 4-space indent and Allman braces (opening `[` / `{`
  on the next line for multi-line values), matching the doc samples.

### Fixed

- `--list-dependencies` unreferenced wipe hint now includes `-n` (dry-run) in the suggested
  command, matching other destructive review hints.
- Commands that warn about unused unqualified VCS stems (`stem` beside `stem@<branch>`) now also
  print the shared dry-run `--force-wipe-dependencies=name/@` recommendation (visible under
  `-Q`). `--list-dependencies` still owns that hint in its footer and merges Location-warned
  tokens with inventory-derived ones.

## [1.5.0] - 2026-08-09

### Added

- `scripts.github_helpers show-pr` (alias `fetch-pr`) prints an open pull request's title, labels,
  head/base, and body via the public GitHub API (`--json` for a stable summary). Prefer this over
  hand-rolled `GET /pulls/{n}` when agents need PR metadata. `watch-pr` pins the resolved PR
  number at start so a later checkout of another branch cannot retarget an in-flight watch.
- `--toolchain-archive=` and `--clang-root=` / `--gcc-root=` fetch or point at Clang and GCC
  installs, cache them under the downloads / dependencies roots as toolchain dependencies, and
  register non-colliding names (`clang{major}_{tag}`, `gcc{major}_{stem}`, or
  `{family}{major}_local_{hash}`) so experimental builds do not collide with distro `clang24` /
  `gcc15`. `--toolchain-archive=` accepts Clang tarballs/zips and Debian **gcc-snapshot** `.deb`
  URLs/paths (extracted with `ar` + `data.tar.*`). Archive family is taken from `clang`/`gcc` in
  the basename when present; otherwise cuppa probes archive members (staging the download under
  `toolchains/_staging/` if needed), then falls back to `.deb`→gcc / other→clang. Omitting
  `--toolchains=` selects toolchains prepared in that session. Later runs discover installs under
  `dependencies_root/toolchains/{clang,gcc}/` so you can select several at once
  (`--toolchains=gcc16_…,clang24_profiles_…`) without re-passing supply flags. External
  `--*-root=` prefixes persist a `cuppa-toolchain.json` registration (force-wipe removes the
  registration, not the external tree). After a successful archive/root session, cuppa logs the
  reuse `--toolchains=` flag at sconstruct end. List/downloads classify these as type
  `toolchain`; force-wipe accepts `[toolchain]clang/…`, `[toolchain]gcc/…`, or the session name.
  Project-scoped `--remove-` / `--purge-` / `--wipe-dependencies` do not apply. See
  `design/archive/toolchains-as-dependencies.md` and [#160](https://github.com/ja11sop/cuppa/issues/160).
  ([#127](https://github.com/ja11sop/cuppa/issues/127) `--profiles` remains a follow-on.)
- `--list-scope=compact` is a refinement of `referenced`: resolve-selected leaves only (no
  unused siblings, no unreferenced section).
- `--list-dependencies` colours unused `@<default> (unqualified)` stem duplicates (the same
  cases the location “both folders” warning calls out) with the remove accent, and prints a
  dry-run `--force-wipe-dependencies=` hint listing every such candidate. Force-wipe accepts
  `name/@` as shorthand for that unqualified stem (not `@master`). Under `--offline`, hint
  tokens whose inventory `used_by` names another project are omitted. Force-wipe `used_by`
  warnings colour only paths, nest every using project under `by N project(s):`, and explain
  when wiping an unused unqualified stem beside the canonical folder is safe. On dry-run those
  used-by notices stay warnings; after a real wipe they become past-tense notes (`wiped…`,
  `removing the copy was safe`). Paths that were already gone on a real remove/wipe become
  past-tense **notes** (`was already gone`) rather than warnings. Dependency remove/purge/wipe
  failures use the same judgement tree as builds and force-wipe (`Removed`/`Wiped N trees:` with
  severity brackets). Wipe/build judgement trees hang from a generic intro with an emphasised
  subject count and muted-or-coloured `[N errors][N warnings][N notes]` brackets (notes use info
  colour); `--list-develop` uses the same bracket shape. Repository branch rows in wipe reports
  use a single-slot mark (`✔` / `-`) rather than a triple rollup. See
  `design/archive/console-report-patterns.md` and [#161](https://github.com/ja11sop/cuppa/issues/161).
- Antora **Contributing → Report patterns** documents judgement-tree shape, warn-before /
  note-after, and shared helpers (`docs/modules/ROOT/pages/contributing/report-patterns.adoc`).

### Changed

- HTTP archive downloads (location/Boost and toolchain archives) share one transfer-progress
  reporter (`cuppa.utility.download`): bytes, total when known, percent, rate, and ETA.
  Progress prefers the controlling terminal so a rewriting line still works when the `cuppa`
  launcher pipes scons stdio for secret masking; CI without a tty keeps periodic newlines.
  Layout is `percent [=====>              ] done/total rate ETA` with fixed-width columns; with
  colour output, percent and bar glyphs are emphasised info, target size is emphasised (normal
  foreground), transferred size is info (emphasised at 100%), brackets are plain, and rate is
  subdued. Tar and zip extracts (location/Boost, GitLab package archives, toolchain archives)
  reuse the same reporter via `extract_tar_archive` / `extract_zip_archive`. GitLab generic
  package downloads use `download_file` with registry auth headers (no `wget` on PATH for the
  fetch). Conan consumer `conan install` streams stdout/stderr live instead of capturing until
  exit. Git `clone` / `fetch` (develop workflows) pass `--progress` and stream subdued progress
  to the controlling terminal when available, gated like HTTP progress to INFO or finer
  (`--verbosity=warn` and quieter stay silent). Replaces the old location-only `|=` bar. See
  `design/archive/download-progress.md`.
- Rename `_removal_error_lines` to `_judgement_tree_lines` and route `--list-develop` judgement
  bodies through it (same stem glyphs, severity headings, wrap, and value highlighting as wipe /
  remove). No intentional user-visible change; completes Phase C of the console report-patterns
  work.
- `--wipe-dependencies` emits inventory `used_by` judgement notices like force-wipe (warning on
  dry-run, past-tense note after a real wipe). Force-wipe “no inventory record” lines move into
  the judgement tree as notes (`no inventory record…` / `had no inventory record…`) instead of
  subdued pre-table text. Unmatched force-wipe tokens (and matched paths already gone) no longer
  hard-stop the whole list: other tokens still wipe, and each miss is a judgement warning on
  dry-run / note after a real wipe. Completes [#161](https://github.com/ja11sop/cuppa/issues/161)
  phases B / D / E.
- Release workflow Actions buttons: **prepare** opens the `finish_release` PR; **publish**
  builds from master tip, creates the GitHub Release and tag, then waits for `pypi` approval.
  Manual `v*` tag push remains as an escape hatch. Antora **Contributing** documents the flow
  with Mermaid diagrams (`contributing.adoc` and children). See `release.txt`.
- Tracked maintainer process narrative under `design/process/` (agent workflow journey), with
  `AGENTS.md` update rules and `.github/CODEOWNERS` review on that tree.

### Fixed

- Clang `_resolve_versioned_tool` joins the tool name onto `where_is()`'s directory again, so
  archive Clang (no in-tree `llvm-ar`) sets `AR` to `/usr/bin/llvm-ar` rather than `/usr/bin`
  and static library archives no longer fail with `Permission denied: '/usr/bin'`.
- `--list-scope=referenced` keeps unused sibling leaves under resolved identities (other Boost
  versions, other branches next to `in use`), matching the documented referenced section.
  GitLab extracts group by on-disk package folder so a registry alias such as `boost_package`
  still keeps unused `boost/<version>` siblings. `--list-scope=compact` is the short
  refinement of that view (resolve-selected leaves only). Groundwork for
  [#161](https://github.com/ja11sop/cuppa/issues/161).
- Unqualified-stem duplicate wipe tokens are recommended when a branch-qualified sibling folder
  exists even if resolve has not marked either leaf referenced. Listing also labels Windows
  MAX_PATH-hashed location stems (no `git_` prefix) as `@<default> (unqualified)` when
  `stem@<default>` sits beside them, and the integration fixture plants those hashed pairs
  with a `.git` dir so classify stays `repository`.

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

- Archive the shipped toolchains-as-dependencies design plan under `design/archive/` (umbrella
  [#160](https://github.com/ja11sop/cuppa/issues/160)); update ROADMAP, toolchains docs, and code
  citations to the new path.
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

[1.8.0]: https://github.com/ja11sop/cuppa/compare/v1.7.0...HEAD
[1.7.0]: https://github.com/ja11sop/cuppa/compare/v1.6.0...v1.7.0
[1.6.0]: https://github.com/ja11sop/cuppa/compare/v1.5.0...v1.6.0
[1.5.0]: https://github.com/ja11sop/cuppa/compare/v1.4.0...v1.5.0
[1.4.0]: https://github.com/ja11sop/cuppa/compare/v1.3.2...v1.4.0
[1.2.0]: https://github.com/ja11sop/cuppa/compare/v1.1.3...v1.2.0
[1.1.3]: https://github.com/ja11sop/cuppa/releases/tag/v1.1.3
