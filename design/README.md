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
| [`plans/coverage-performance.md`](plans/coverage-performance.md) | proposal | Where `--cov --test` time actually goes, what the A/B measurement ruled out, and the remaining suspects |
| [`plans/modules-activation.md`](plans/modules-activation.md) | proposal | Whether C++ modules should stay opt-in behind `--modules` or become opt-out, and what must land first |
| [`plans/removal-options.md`](plans/removal-options.md) | proposal | `--remove-build` / `--remove-dependencies` / `--purge-*`, listing with sizes, and renaming the storage roots |
| [`plans/scons-tool-wrapper.md`](plans/scons-tool-wrapper.md) | proposal | Wrapping an SCons Tool as a cuppa dependency instead of hand-writing a dependency class |
| [`issues/storage-roots.md`](issues/storage-roots.md) | issue draft | Rename the storage roots and add `--storage-root` (removal plan Phase 1) |
| [`issues/storage-listing-removal.md`](issues/storage-listing-removal.md) | issue draft | Listing and removal options for builds, dependencies, and downloads (Phases 2–4) |
| [`issues/develop-copies.md`](issues/develop-copies.md) | issue draft | `--list-develop` and `--update-develop` (Phase 5) |
| [`issues/artefact-removal-design.md`](issues/artefact-removal-design.md) | issue draft | Design pass for removing artefacts outside the build root (Phase 6) |
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

[`tests/unit/test_design_index.py`](../tests/unit/test_design_index.py) checks that every document
is listed in the index above, that every listed document exists with a matching status, that the
headers parse, and that relative links resolve. Adding a document without indexing it fails
`pytest -m unit`.

Private project names must not appear in anything tracked here — see the "Private projects"
section of [`AGENTS.md`](../AGENTS.md).
