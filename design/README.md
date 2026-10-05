# Design notes, plans, and issue drafts

Working documents that are too long or too exploratory to live in a commit message or a GitHub
issue comment. They are **not** product documentation: the published documentation is the Antora
site under [`docs/`](../docs), and the canonical statement of what is planned is
[`ROADMAP.md`](../ROADMAP.md). A document here explains the reasoning, the measurements, and the
alternatives behind one of those roadmap entries — or, under `process/`, how the project’s own
maintainer workflow evolved.

## Layout

| Folder | Holds | Lifecycle |
|--------|-------|-----------|
| `ideas/` | Pre-plan scratch notes (not yet proposals) | Graduate into `plans/` + [`ROADMAP.md`](../ROADMAP.md), then delete the note from the scratchpad |
| `plans/` | Proposals, in-flight work, and work **done** on `master` but not yet in a named release | Stay here through merge; promote to `archive/` only at **release** when rationale is kept (else delete) |
| `issues/` | Text drafted for a GitHub issue that has not been filed yet | Delete it once the issue is filed; the issue becomes the record, and the folder is empty until the next draft |
| `archive/` | Work **shipped** in a named release whose design rationale is still cited | Keep while something references it |
| `process/` | Living maintainer process narrative (how agents and humans work this repo) | Keep and append; not a product plan |

## Index

| Document | Status | Subject |
|----------|--------|---------|
| [`plans/deep-clean.md`](plans/deep-clean.md) | proposal | `--deep-clean` modifier on `-c`; cooperative `b2 --clean`; extract `b2` on ordinary `-c` as follow-up; ROADMAP `deep-clean`; [#135](https://github.com/ja11sop/cuppa/issues/135) |
| [`plans/gitlab-package-transitive.md`](plans/gitlab-package-transitive.md) | done | GitLab package A carries deps on B via `cuppa-dependency.json` (MVP on master; archive at 1.12.0) — [#279](https://github.com/ja11sop/cuppa/issues/279); follow-ons version-ranges + lib-groups |
| [`plans/gitlab-package-version-ranges.md`](plans/gitlab-package-version-ranges.md) | proposal | Soft pins (`>=1.28.0`) on package / transitive edges — follow-on to transitive MVP |
| [`plans/gitlab-package-lib-groups.md`](plans/gitlab-package-lib-groups.md) | proposal | Named `use_libs` groups + `show_*` discovery — follow-on to transitive MVP (`use_all_libs()` already shipped) |
| [`archive/list-deps-requires-closure.md`](archive/list-deps-requires-closure.md) | shipped | `--list-dependencies`: nest traveling-manifest closure under tip `requires`; Option A usage vs resolve-identity `--list-scope` |
| [`archive/dependencies-docs-four-hubs.md`](archive/dependencies-docs-four-hubs.md) | shipped | Dependencies Antora: Using / Managing / Publishing / Authoring hubs; Using-first usability story; align list-deps Option A |
| [`archive/selection-filter-examples-docs.md`](archive/selection-filter-examples-docs.md) | shipped | Remove/wipe selection docs: types table, inventory, glance Matches, worked why, CLI copy |
| [`archive/run-default-dependency-objects.md`](archive/run-default-dependency-objects.md) | shipped | `cuppa.run` `default_dependencies` accepts objects; register vs auto-apply semantics / naming |
| [`archive/gitlab-package-latest.md`](archive/gitlab-package-latest.md) | shipped | GitLab `version="latest"` = registry latest; Boost package retarget; consume docs — [#271](https://github.com/ja11sop/cuppa/issues/271) / [#272](https://github.com/ja11sop/cuppa/pull/272) |
| [`archive/dependency-resolve.md`](archive/dependency-resolve.md) | shipped | BuildWith untyped resolve + type selectors; Quince `use_libs` — [#250](https://github.com/ja11sop/cuppa/issues/250) / [#270](https://github.com/ja11sop/cuppa/pull/270) |
| [`archive/package-develop-local.md`](archive/package-develop-local.md) | shipped | Package `--develop` source-tree consume (A–D + Slice F shipped); Slice E **declined** (dual inference kept) — [#297](https://github.com/ja11sop/cuppa/issues/297) |
| [`archive/cascade-defer-404.md`](archive/cascade-defer-404.md) | shipped | Slice F tip registry 404 defer under cascade — [#316](https://github.com/ja11sop/cuppa/pull/316) / [#297](https://github.com/ja11sop/cuppa/issues/297) |
| [`archive/publish-package-parallel-side-effect.md`](archive/publish-package-parallel-side-effect.md) | shipped | `PublishPackage` archive SideEffect + CMake `--parallel N`; done on master [#319](https://github.com/ja11sop/cuppa/pull/319) — [#317](https://github.com/ja11sop/cuppa/issues/317) / [#318](https://github.com/ja11sop/cuppa/issues/318) |
| [`archive/stage-develop-locations.md`](archive/stage-develop-locations.md) | shipped | Location `--stage-develop` (L1/L2) + plan (L4) + L3 tip stage consume — on [#315](https://github.com/ja11sop/cuppa/pull/315); ROADMAP `stage-develop-locations` |
| [`issues/package-build-provenance.md`](issues/package-build-provenance.md) | issue draft | A published package records the source revisions it was built from (`built_from` in `cuppa-publish.json`); the packaging recipe's own revision is deliberately not identity — [#297](https://github.com/ja11sop/cuppa/issues/297) |
| [`plans/boost-updates.md`](plans/boost-updates.md) | proposal | Boost source vs GitLab `boost_package` identity; #206 `use_libs`; #248/#249 runners; Quince gap → dependency-resolve |
| [`plans/shiki-syntax-highlighting.md`](plans/shiki-syntax-highlighting.md) | proposal | Build-time Shiki for Antora listings; ANSI preview only — ROADMAP `doc-shiki` |
| [`plans/coverage-performance.md`](plans/coverage-performance.md) | proposal | Where `--cov --test` time actually goes, what the A/B measurement ruled out, and the remaining suspects |
| [`plans/coverage-parallel.md`](plans/coverage-parallel.md) | in progress | What `--cov --test --parallel` can and cannot do; 1.9.1 warn + Depends; `GCOV_PREFIX` deferred — [#236](https://github.com/ja11sop/cuppa/issues/236) |
| [`plans/list-toolchains-verbose.md`](plans/list-toolchains-verbose.md) | in progress | Verbose `describe()` shipped ([#172](https://github.com/ja11sop/cuppa/issues/172) / [#170](https://github.com/ja11sop/cuppa/pull/170)); deferred table-driven init |
| [`plans/antora-ui-bundle.md`](plans/antora-ui-bundle.md) | in progress | Supplemental CSS + Boost/Material look catalogue; default bundle kept — ROADMAP `doc-antora-ui`; [#229](https://github.com/ja11sop/cuppa/issues/229) / [#228](https://github.com/ja11sop/cuppa/pull/228) |
| [`plans/methods-pages-split.md`](plans/methods-pages-split.md) | in progress | Hub + job-named `methods/*` (discovery, templates, CreateVersion, staging-files, test-reporting, …) — ROADMAP `doc-methods-split`; #234 |
| [`plans/native-toolchain-output.md`](plans/native-toolchain-output.md) | done | `--native-output`: passthrough native compiler colour — ROADMAP `console-native-output` / **1.12.0** — [#354](https://github.com/ja11sop/cuppa/pull/354) |
| [`plans/terse-dependency-locations.md`](plans/terse-dependency-locations.md) | done | Nested terse `[location]` maps for deps/packages (`<dependencies>/<fmt>/…`, `<variant>`, `[prepare]`/`[ready]`) — ROADMAP `console-terse-dep-locations` / **1.12.0** — [#355](https://github.com/ja11sop/cuppa/pull/355) |
| [`plans/terse-build-output.md`](plans/terse-build-output.md) | done | `--terse-output`: coloured one-line progress — ROADMAP `console-terse-output` / **1.12.0** |
| [`plans/terse-delegated-output.md`](plans/terse-delegated-output.md) | done | Terse file-field patterns (`source → product`) and delegated builders (CMake/`b2`): `delegate … [launch]`, `[done]` close, muted `→` children, `[location]` maps — ROADMAP `console-terse-delegated` / **1.12.0** |
| [`plans/build-log-hygiene.md`](plans/build-log-hygiene.md) | done | Configure-time log demotion + variant default message fix — ROADMAP `console-log-hygiene` / **1.12.0** |
| [`plans/cuppa-info.md`](plans/cuppa-info.md) | done | `cuppa --info`: version without sconstruct — ROADMAP `cli-info` / **1.12.0** — [#350](https://github.com/ja11sop/cuppa/pull/350) |
| [`plans/cxx-profiles-report.md`](plans/cxx-profiles-report.md) | in progress | `--cxx-profiles-report`: classify/dedupe Profiles diagnostics — ROADMAP `profiles-violation-report` — **`prof-report-method-semantics`** [#203](https://github.com/ja11sop/cuppa/pull/203); **`prof-report-remote-links`** [#219](https://github.com/ja11sop/cuppa/pull/219); **`prof-report-error-limit`** [#225](https://github.com/ja11sop/cuppa/pull/225); **`prof-report-scope-filter`** [#246](https://github.com/ja11sop/cuppa/pull/246) — **1.9.0**; full **F** blocked on [#135](https://github.com/ja11sop/cuppa/issues/135) |
| [`archive/doc-folder-layout.md`](archive/doc-folder-layout.md) | shipped | Antora child pages under `dependencies/`, `cxx-profiles/`, `toolchains/` — ROADMAP `doc-folder-layout` |
| [`archive/colourised-doc-samples.md`](archive/colourised-doc-samples.md) | shipped | Semantic HTML report samples + local preview — [#252](https://github.com/ja11sop/cuppa/issues/252) / [#253](https://github.com/ja11sop/cuppa/pull/253) |
| [`archive/boost-latest-persistence.md`](archive/boost-latest-persistence.md) | shipped | Persist Boost latest (downloads-root–scoped conf); unpinned online scrape ([#201](https://github.com/ja11sop/cuppa/issues/201)); offline reuse — [#171](https://github.com/ja11sop/cuppa/issues/171) / [#170](https://github.com/ja11sop/cuppa/pull/170) |
| [`archive/list-toolchains.md`](archive/list-toolchains.md) | shipped | `--list-toolchains` ruled tree (family→version→driver→names); list-deps leaf = Cuppa session name — [#172](https://github.com/ja11sop/cuppa/issues/172) / [#170](https://github.com/ja11sop/cuppa/pull/170) |
| [`archive/download-progress.md`](archive/download-progress.md) | shipped | Shared HTTP/transfer progress (download, extract, Conan, git) — [#165](https://github.com/ja11sop/cuppa/pull/165) |
| [`plans/modules-activation.md`](plans/modules-activation.md) | proposal | Whether C++ modules should stay opt-in behind `--modules` or become opt-out, and what must land first |
| [`archive/cxx-profiles.md`](archive/cxx-profiles.md) | shipped | Opt-in C++ Profiles (`--cxx-profiles*`, enforce composition, `--cxx-disable-error-limit`, `--cxx-modules` vocabulary) — [#127](https://github.com/ja11sop/cuppa/issues/127) / [#177](https://github.com/ja11sop/cuppa/pull/177) / [#180](https://github.com/ja11sop/cuppa/pull/180) |
| [`plans/removal-options.md`](plans/removal-options.md) | in progress | Phases 1–5 + wipe + §3.7/§3.8 shipped ([#154](https://github.com/ja11sop/cuppa/pull/154)); Phase 6 artefacts [#135](https://github.com/ja11sop/cuppa/issues/135) open; next focus artefacts when that design starts |
| [`plans/scons-tool-wrapper.md`](plans/scons-tool-wrapper.md) | proposal | Wrapping an SCons Tool as a cuppa dependency instead of hand-writing a dependency class |
| [`ideas/scratchpad.md`](ideas/scratchpad.md) | living | Pre-plan product ideas; graduate to `plans/` + ROADMAP, then remove the note |
| [`process/agent-workflow-journey.md`](process/agent-workflow-journey.md) | living | How cuppa’s maintainer workflow was hardened for humans and agents (blueprint + case studies) |
| [`archive/console-report-patterns.md`](archive/console-report-patterns.md) | shipped | Judgement-tree shape, severity timing (warn before / note after), shared helpers for console reports ([#161](https://github.com/ja11sop/cuppa/issues/161)); Antora Report patterns page |
| [`plans/console-stop-error-reporting.md`](plans/console-stop-error-reporting.md) | in progress | Options Error trees + StopError critical-line `highlight_values` (error colour on `[values]` / `--flags`); extends report-patterns |
| [`plans/console-channels.md`](plans/console-channels.md) | in progress | Console channel map: log, console report, build transcript, heartbeat; `--scons-output` done ([#352](https://github.com/ja11sop/cuppa/pull/352)); `--terse-output` done ([#353](https://github.com/ja11sop/cuppa/pull/353)); `--native-output` done ([#354](https://github.com/ja11sop/cuppa/pull/354)); terse locations done ([#355](https://github.com/ja11sop/cuppa/pull/355)); heartbeat done ([#356](https://github.com/ja11sop/cuppa/pull/356)) |
| [`plans/console-mode-banners.md`](plans/console-mode-banners.md) | done | Mode banners (OFFLINE, CASCADE PLAN, …) as console reports so `-Q` does not hide them — [#351](https://github.com/ja11sop/cuppa/pull/351) |
| [`plans/quiet-tty-heartbeat.md`](plans/quiet-tty-heartbeat.md) | done | Quiet+TTY liveness: logger INFO diversion + throttle under `-Q`/`-s` on a TTY (with terse too) — [#356](https://github.com/ja11sop/cuppa/pull/356) |
| [`plans/filter-directory-warn.md`](plans/filter-directory-warn.md) | done | Drop Filter’s false-positive “probably a directory” warn for missing extensionless build products — [#358](https://github.com/ja11sop/cuppa/pull/358) |
| [`archive/toolchains-as-dependencies.md`](archive/toolchains-as-dependencies.md) | shipped | Fetched compilers as toolchain deps (Clang archives, GCC `.deb` / `--gcc-root=`, multi-select compare; list/force-wipe) — umbrella [#160](https://github.com/ja11sop/cuppa/issues/160); Clang [#159](https://github.com/ja11sop/cuppa/pull/159), GCC [#164](https://github.com/ja11sop/cuppa/pull/164) |
| [`archive/conan-consumer-plan.md`](archive/conan-consumer-plan.md) | shipped | Design of `conan_deps` / `conan_dependency` consumer support |
| [`archive/conan-publish-plan.md`](archive/conan-publish-plan.md) | shipped | Design of `ConanPackagePublisher` and `--publish-package` |
| [`archive/sconscript-exports.md`](archive/sconscript-exports.md) | shipped | Shared exports between discovered sconscripts; nested lib/test layout — [#282](https://github.com/ja11sop/cuppa/issues/282) / [#283](https://github.com/ja11sop/cuppa/pull/283) |
| [`archive/static-lib-archive-members.md`](archive/static-lib-archive-members.md) | shipped | Unique `ar` / `.lib` members when nested same-basename `.o` share one `BuildStaticLib` — [#287](https://github.com/ja11sop/cuppa/issues/287) / [#288](https://github.com/ja11sop/cuppa/pull/288); always-flatten deferred to 2.0 |
| [`plans/parallel-job-count.md`](plans/parallel-job-count.md) | proposal | Optional `--parallel=N` (affinity + job count); today’s `--parallel --jobs=N` workaround — ROADMAP `parallel-job-count` |
| [`archive/integration-parallel-local.md`](archive/integration-parallel-local.md) | shipped | Modest pytest-xdist for local integration gate (~2–3 min); HOME isolation + `local_gate` default — ROADMAP `integration-parallel-local` |
| [`archive/local-gate.md`](archive/local-gate.md) | shipped | `python -m scripts.local_gate` preflight + lint/unit/integration orchestrator for agents/humans — ROADMAP `local-gate` |
| [`archive/package-download-refresh.md`](archive/package-download-refresh.md) | shipped | Opt-in `--refresh-downloads` after same-version republish — done on master [#342](https://github.com/ja11sop/cuppa/pull/342); ROADMAP `package-download-refresh`; [#296](https://github.com/ja11sop/cuppa/issues/296) |
| [`archive/package-build-publish-deps.md`](archive/package-build-publish-deps.md) | shipped | Cascade **done on master** ([#302](https://github.com/ja11sop/cuppa/pull/302)–[#339](https://github.com/ja11sop/cuppa/pull/339)): companions incl. `--build-cascade-dependencies`, plan/collect/update, skip-if-current, `cuppa-publish.json`, list-publishers / list-location; forest stem keying deferred as future feature — ROADMAP `package-build-publish-deps`; [#297](https://github.com/ja11sop/cuppa/issues/297) |
| [`archive/package-use-libs-defaults.md`](archive/package-use-libs-defaults.md) | shipped | Shared-aware `use_libs` + package `default_use_libs` so auto-enable links small packages without `AppendUnique` — ROADMAP `package-use-libs-defaults` |
| [`archive/package-metadata-amend.md`](archive/package-metadata-amend.md) | shipped | Metadata-only amend/republish (`--amend-package-manifest`); traveling file is `cuppa-publish.json` (Phase 2d) — ROADMAP `package-metadata-amend`; [#299](https://github.com/ja11sop/cuppa/issues/299) / [#300](https://github.com/ja11sop/cuppa/pull/300) |
| [`plans/cmake-to-cuppa-migration.md`](plans/cmake-to-cuppa-migration.md) | proposal | CMake ↔ Cuppa matrix and migration phases for humans and agents |
| [`plans/cmake-drive-and-package-staging.md`](plans/cmake-drive-and-package-staging.md) | in progress | Drive CMake from publisher sconscripts (Cuppa→CMAKE_* mapping); #209 staging; accessors; deferred publish-side CLI pins (`package-publish-cli`) — ROADMAP / [#209](https://github.com/ja11sop/cuppa/issues/209) |
| [`archive/cmake-package-prefix.md`](archive/cmake-package-prefix.md) | shipped | `env.PackageBin` / `CMakePrefixPathFor`; name↔slug; bare deps; default Ninja; google-cloud-cpp prove-out soak (`cmake-pkg-cloud-soak`) — ROADMAP 1.11.0 |
| [`archive/download-extract.md`](archive/download-extract.md) | shipped | `env.DownloadExtract` + `RemoveEmptyDirs` under acquire (general, not CMake-specific) |
| [`archive/package-runtime-paths.md`](archive/package-runtime-paths.md) | shipped | GitLab `BuildWith` runtime ENV; `cmake_install_rpath_defines` / `cmake_prefix_path`; private publisher cleanup done |
| [`archive/recursive-glob-parity.md`](archive/recursive-glob-parity.md) | shipped | RecursiveGlob / GlobFiles / Filter parity — ROADMAP `static-glob`; [#232](https://github.com/ja11sop/cuppa/issues/232) / [#231](https://github.com/ja11sop/cuppa/pull/231) |
| [`archive/method-behaviour-audit.md`](archive/method-behaviour-audit.md) | shipped | Method returns, evaluation, paths; #213 + glob + #233 + cov nested-path; hub classification — ROADMAP `method-behaviour-audit` |
| [`plans/path-vocabulary-and-scons-nodes.md`](plans/path-vocabulary-and-scons-nodes.md) | proposal | Reuse `#/` path roots + VariantDir node helpers outside discovery — follow-on to `static-glob` |
| [`archive/ignore-toolchain-point-release.md`](archive/ignore-toolchain-point-release.md) | shipped | Point-release encoding problem (`gcc153`→`gcc15`); product shape in [`build-and-package-identity.md`](archive/build-and-package-identity.md) — ROADMAP `tc-identity-coarsen` |
| [`archive/build-and-package-identity.md`](archive/build-and-package-identity.md) | shipped | Toolchain major identity, consume matching, OS omit at publish — [#243](https://github.com/ja11sop/cuppa/issues/243) / [#242](https://github.com/ja11sop/cuppa/pull/242) / [#244](https://github.com/ja11sop/cuppa/pull/244) / [#245](https://github.com/ja11sop/cuppa/pull/245) |
| [`archive/docs-site-release-default.md`](archive/docs-site-release-default.md) | shipped | Public Antora site defaults to `/latest/` (release), `next` prerelease — [#238](https://github.com/ja11sop/cuppa/pull/238); ROADMAP `doc-site-release-default` |
| [`archive/docs-llms-txt.md`](archive/docs-llms-txt.md) | shipped | Agent Markdown from Antora HTML (`llms.txt` / pages / `llms-full.txt`, Pandoc); corpus on `/latest/` — [#238](https://github.com/ja11sop/cuppa/pull/238); ROADMAP `doc-llms-txt` |

## Conventions

Filenames are kebab-case. Each document opens with a title and a three-item header:

```markdown
# Title

- **Status:** proposal
- **Related:** [`ROADMAP.md`](../../ROADMAP.md) — roadmap section or ID; GitHub issue if there is one
- **Updated:** YYYY-MM-DD
```

`Status` is one of `proposal`, `in progress`, `done`, `issue draft`, `shipped`, or `living`
(`living` is only for documents under `process/` or `ideas/`).

**Done vs shipped:** `done` means the behaviour is on `master` and the plan matches the tree
(mark it on the **feature PR**). `shipped` means it is in a **named** Cuppa release — promote
`done` plans (and move kept rationale to `archive/`) in the release housekeeping pass, not in a
per-merge “cite” PR. See `AGENTS.md` § Working documents.

A document in `issues/` adds an `Impact` line naming the release impact of the work — `none`,
`patch`, `minor`, or `major`, followed by the reason:

```markdown
- **Impact:** minor — new options only; no existing build behaviour changes
```

That is the `impact:` label the resulting pull request needs, and it decides the version the work
targets. See "Versioning and changelog" in [`AGENTS.md`](../AGENTS.md).

Process documents may also carry **Maintainer** and **Privacy** lines; they still need Status /
Related / Updated and an Index row.

[`tests/unit/test_design_index.py`](../tests/unit/test_design_index.py) checks that every document
is listed in the index above, that every listed document exists with a matching status, that the
headers parse, and that relative links resolve. Adding a document without indexing it fails
`pytest -m unit`.

Private project names must not appear in anything tracked here — see the "Private projects"
section of [`AGENTS.md`](../AGENTS.md). Gitignored `*.local.md` files (for example
`INTERNAL_PROJECTS.local.md`) are never indexed and must never be committed.
