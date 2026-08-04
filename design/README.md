# Design notes, plans, and issue drafts

Working documents that are too long or too exploratory to live in a commit message or a GitHub
issue comment. They are **not** product documentation: the published documentation is the Antora
site under [`docs/`](../docs), and the canonical statement of what is planned is
[`ROADMAP.md`](../ROADMAP.md). A document here explains the reasoning, the measurements, and the
alternatives behind one of those roadmap entries.

## Layout

| Folder | Holds | Lifecycle |
|--------|-------|-----------|
| `plans/` | Proposals and design work that has not shipped | Delete when the work ships, unless the reasoning still answers questions later — then move to `archive/` |
| `issues/` | Text drafted for a GitHub issue that has not been filed yet | Delete once the issue is filed; the issue becomes the record, and the folder is empty until the next draft |
| `archive/` | Shipped work whose design rationale is still cited from code or documentation | Keep while something references it |

## Index

| Document | Status | Subject |
|----------|--------|---------|
| [`plans/colourised-doc-samples.md`](plans/colourised-doc-samples.md) | proposal | Capture cuppa report output as semantic HTML for Antora samples and local preview |
| [`plans/coverage-performance.md`](plans/coverage-performance.md) | proposal | Where `--cov --test` time actually goes, what the A/B measurement ruled out, and the remaining suspects |
| [`plans/modules-activation.md`](plans/modules-activation.md) | proposal | Whether C++ modules should stay opt-in behind `--modules` or become opt-out, and what must land first |
| [`plans/removal-options.md`](plans/removal-options.md) | in progress | Phases 1, 2, 5 + Phase 3 listing (#141) + Slice D removal (#142 / §4.13) + archive clean (§4.14.3 / #143) done; deferred Phase 3 polish: `used_by`, Conan meta, default-branch quirk, docs split; native `du` (§4.5.1) parked; **next** Phase 4 downloads/purge; Phases 6 / §3.7 still open — see plan progress snapshot; [#134](https://github.com/ja11sop/cuppa/issues/134) / [#135](https://github.com/ja11sop/cuppa/issues/135) |
| [`plans/scons-tool-wrapper.md`](plans/scons-tool-wrapper.md) | proposal | Wrapping an SCons Tool as a cuppa dependency instead of hand-writing a dependency class |
| [`archive/conan-consumer-plan.md`](archive/conan-consumer-plan.md) | shipped | Design of `conan_deps` / `conan_dependency` consumer support |
| [`archive/conan-publish-plan.md`](archive/conan-publish-plan.md) | shipped | Design of `ConanPackagePublisher` and `--publish-package` |

## Conventions

Filenames are kebab-case. Each document opens with a title and a three-item header:

```markdown
# Title

- **Status:** proposal
- **Related:** [`ROADMAP.md`](../../ROADMAP.md) — roadmap section or ID; GitHub issue if there is one
- **Updated:** YYYY-MM-DD
```

`Status` is one of `proposal`, `in progress`, `issue draft`, or `shipped`.

A document in `issues/` adds an `Impact` line naming the release impact of the work — `none`,
`patch`, `minor`, or `major`, followed by the reason:

```markdown
- **Impact:** minor — new options only; no existing build behaviour changes
```

That is the `impact:` label the resulting pull request needs, and it decides the version the work
targets. See "Versioning and changelog" in [`AGENTS.md`](../AGENTS.md).

[`tests/unit/test_design_index.py`](../tests/unit/test_design_index.py) checks that every document
is listed in the index above, that every listed document exists with a matching status, that the
headers parse, and that relative links resolve. Adding a document without indexing it fails
`pytest -m unit`.

Private project names must not appear in anything tracked here — see the "Private projects"
section of [`AGENTS.md`](../AGENTS.md).
