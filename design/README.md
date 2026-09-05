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
| `plans/` | Proposals and design work that has not shipped | Delete when the work ships, unless the reasoning still answers questions later — then move to `archive/` |
| `issues/` | Text drafted for a GitHub issue that has not been filed yet | Delete it once the issue is filed; the issue becomes the record, and the folder is empty until the next draft |
| `archive/` | Shipped work whose design rationale is still cited from code or documentation | Keep while something references it |
| `process/` | Living maintainer process narrative (how agents and humans work this repo) | Keep and append; not a product plan |

## Index

| Document | Status | Subject |
|----------|--------|---------|
| [`plans/run-default-dependency-objects.md`](plans/run-default-dependency-objects.md) | proposal | `cuppa.run` `default_dependencies` accepts dependency objects (back-compat with strings) |
| [`archive/gitlab-package-latest.md`](archive/gitlab-package-latest.md) | shipped | GitLab `version="latest"` = registry latest; Boost package retarget; consume docs — [#271](https://github.com/ja11sop/cuppa/issues/271) / [#272](https://github.com/ja11sop/cuppa/pull/272) |
| [`archive/dependency-resolve.md`](archive/dependency-resolve.md) | shipped | BuildWith untyped resolve + type selectors; Quince `use_libs` — [#250](https://github.com/ja11sop/cuppa/issues/250) / [#270](https://github.com/ja11sop/cuppa/pull/270) |
| [`plans/boost-updates.md`](plans/boost-updates.md) | proposal | Boost source vs GitLab `boost_package` identity; #206 `use_libs`; #248/#249 runners; Quince gap → dependency-resolve |
| [`plans/shiki-syntax-highlighting.md`](plans/shiki-syntax-highlighting.md) | proposal | Build-time Shiki for Antora listings; ANSI preview only — ROADMAP `doc-shiki` |
| [`plans/coverage-performance.md`](plans/coverage-performance.md) | proposal | Where `--cov --test` time actually goes, what the A/B measurement ruled out, and the remaining suspects |
| [`plans/coverage-parallel.md`](plans/coverage-parallel.md) | in progress | What `--cov --test --parallel` can and cannot do; 1.9.1 warn + Depends; `GCOV_PREFIX` deferred — [#236](https://github.com/ja11sop/cuppa/issues/236) |
| [`plans/list-toolchains-verbose.md`](plans/list-toolchains-verbose.md) | in progress | Verbose `describe()` shipped ([#172](https://github.com/ja11sop/cuppa/issues/172) / [#170](https://github.com/ja11sop/cuppa/pull/170)); deferred table-driven init |
| [`plans/antora-ui-bundle.md`](plans/antora-ui-bundle.md) | in progress | Supplemental CSS + Boost/Material look catalogue; default bundle kept — ROADMAP `doc-antora-ui`; [#229](https://github.com/ja11sop/cuppa/issues/229) / [#228](https://github.com/ja11sop/cuppa/pull/228) |
| [`plans/methods-pages-split.md`](plans/methods-pages-split.md) | in progress | Hub + job-named `methods/*` (discovery, templates, CreateVersion, staging-files, test-reporting, …) — ROADMAP `doc-methods-split`; #234 |
| [`plans/native-toolchain-output.md`](plans/native-toolchain-output.md) | proposal | `--native-output`: passthrough native compiler colour — ROADMAP `console-native-output` |
| [`plans/terse-build-output.md`](plans/terse-build-output.md) | proposal | `--terse-output`: coloured one-line progress — ROADMAP `console-terse-output` / **1.8.0 target** |
| [`plans/build-log-hygiene.md`](plans/build-log-hygiene.md) | proposal | Configure-time log demotion + variant default message fix — ROADMAP `console-log-hygiene` |
| [`plans/cuppa-info.md`](plans/cuppa-info.md) | proposal | `cuppa --info`: version without sconstruct — ROADMAP `cli-info` |
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
| [`archive/toolchains-as-dependencies.md`](archive/toolchains-as-dependencies.md) | shipped | Fetched compilers as toolchain deps (Clang archives, GCC `.deb` / `--gcc-root=`, multi-select compare; list/force-wipe) — umbrella [#160](https://github.com/ja11sop/cuppa/issues/160); Clang [#159](https://github.com/ja11sop/cuppa/pull/159), GCC [#164](https://github.com/ja11sop/cuppa/pull/164) |
| [`archive/conan-consumer-plan.md`](archive/conan-consumer-plan.md) | shipped | Design of `conan_deps` / `conan_dependency` consumer support |
| [`archive/conan-publish-plan.md`](archive/conan-publish-plan.md) | shipped | Design of `ConanPackagePublisher` and `--publish-package` |
| [`plans/sconscript-exports.md`](plans/sconscript-exports.md) | proposal | Shared exports between discovered sconscripts; nested lib/test layout |
| [`plans/cmake-to-cuppa-migration.md`](plans/cmake-to-cuppa-migration.md) | proposal | CMake ↔ Cuppa matrix and migration phases for humans and agents |
| [`archive/recursive-glob-parity.md`](archive/recursive-glob-parity.md) | shipped | RecursiveGlob / GlobFiles / Filter parity — ROADMAP `static-glob`; [#232](https://github.com/ja11sop/cuppa/issues/232) / [#231](https://github.com/ja11sop/cuppa/pull/231) |
| [`archive/method-behaviour-audit.md`](archive/method-behaviour-audit.md) | shipped | Method returns, evaluation, paths; #213 + glob + #233 + cov nested-path; hub classification — ROADMAP `method-behaviour-audit` |
| [`plans/path-vocabulary-and-scons-nodes.md`](plans/path-vocabulary-and-scons-nodes.md) | proposal | Reuse `#/` path roots + VariantDir node helpers outside discovery — follow-on to `static-glob` |
| [`archive/ignore-toolchain-point-release.md`](archive/ignore-toolchain-point-release.md) | shipped | Point-release encoding problem (`gcc153`→`gcc15`); product shape in [`build-and-package-identity.md`](archive/build-and-package-identity.md) — ROADMAP `tc-identity-coarsen` |
| [`archive/build-and-package-identity.md`](archive/build-and-package-identity.md) | shipped | Toolchain major identity, consume matching, OS omit at publish — [#243](https://github.com/ja11sop/cuppa/issues/243) / [#242](https://github.com/ja11sop/cuppa/pull/242) / [#244](https://github.com/ja11sop/cuppa/pull/244) / [#245](https://github.com/ja11sop/cuppa/pull/245) |
| [`plans/docs-site-release-default.md`](plans/docs-site-release-default.md) | in progress | Public Antora site defaults to `/latest/` (release), `next` prerelease — ROADMAP `doc-site-release-default`; same PR as llms |
| [`plans/docs-llms-txt.md`](plans/docs-llms-txt.md) | in progress | Agent Markdown from Antora HTML (`llms.txt` / pages / `llms-full.txt`, Pandoc); default corpus `/latest/` — ROADMAP `doc-llms-txt` |

## Conventions

Filenames are kebab-case. Each document opens with a title and a three-item header:

```markdown
# Title

- **Status:** proposal
- **Related:** [`ROADMAP.md`](../../ROADMAP.md) — roadmap section or ID; GitHub issue if there is one
- **Updated:** YYYY-MM-DD
```

`Status` is one of `proposal`, `in progress`, `issue draft`, `shipped`, or `living`
(`living` is only for documents under `process/` or `ideas/`).

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
