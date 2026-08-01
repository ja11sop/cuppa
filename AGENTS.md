---
name: Cuppa build system
description: Guidance for AI agents working on the cuppa repository or using cuppa in consumer projects
---

# Cuppa — agent notes

Cuppa is a SCons extension for C++ builds. This repository is the **cuppa package itself**. Consumer projects call `import cuppa` / `cuppa.run()` from their own `sconstruct`.

**Roadmap (large features, current vs planned):** [`ROADMAP.md`](ROADMAP.md) — start here for C++20 modules status and follow-on work; other major areas will be added as sections.
**Release notes:** [`CHANGELOG.md`](CHANGELOG.md) — Keep a Changelog / SemVer; write entries into the open section as you work (see [Versioning and changelog](#versioning-and-changelog)).
**Design notes, plans, issue drafts:** [`design/README.md`](design/README.md) — the index; read it before writing a new plan, in case one already exists.

## Versioning and changelog

`cuppa/VERSION` names the version being assembled, with a `.dev` suffix while it is open —
`1.4.0.dev` becomes `1.4.0` at release. `CHANGELOG.md` carries exactly one open section,
`## [X.Y.Z] - unreleased`, at the top, and dated sections below it.

The version is chosen when a workstream starts, from what it does to the public surface —
the CLI flags, the `env.*` methods, `cuppa.run()` arguments, and configuration file keys:

| Change | Impact | Version |
|--------|--------|---------|
| New option, method, or behaviour a project can opt into | `minor` | `X.Y+1.0` |
| Fix, message, docs, tests, or internal refactor | `patch` | `X.Y.Z+1` |
| Removed or repurposed option, changed default a project depends on | `major` | `X+1.0.0` |
| No release impact at all (CI, design documents) | `none` | unchanged |

Two commands do the mechanical work; do not hand-edit the version or the section headings:

```sh
python -m scripts.start_release 1.4.0 # first commit of a workstream: open the cycle
python -m scripts.finish_release      # release: date the section, drop .dev, close the link
```

Write entries under the open section as each change lands, not in a sweep at the end.

Three checks keep this honest, all sharing `scripts/changelog.py` so they cannot disagree:

- `tests/unit/test_version_and_changelog.py` — the version and the changelog describe the same
  release, one open section at the top, sections descend, recent versions have compare links.
- The `version` job on pull requests — the target version is at least what the pull request's
  `impact:` label implies, and the open section has entries. Every pull request needs exactly one
  `impact:none`, `impact:patch`, `impact:minor`, or `impact:major` label.
- The `release` workflow on a `v*` tag — no `.dev`, the section is dated and non-empty, and the
  tag matches `cuppa/VERSION`.

A patch-sized pull request landing inside an open minor cycle is fine: the gate asks for *at
least* the implied version, so `1.4.0.dev` satisfies a `patch` label. Raising the target
mid-cycle (a `major` arrives) is a `start_release` call on that branch.

## Working documents

Long-form plans, measurements, and unfiled issue text live under `design/`, never in the
repository root and never in `docs/` (that tree is the published Antora site):

- `design/plans/` — proposals that have not shipped. Delete a plan when its work ships, unless
  the reasoning is still cited from code or docs, in which case move it to `design/archive/`.
- `design/issues/` — text drafted for a GitHub issue. Delete it once the issue is filed.
- `design/archive/` — shipped work whose rationale something still references.

Filenames are kebab-case. Every document opens with a `Status` / `Related` / `Updated` header,
and must be added to the Index table in `design/README.md`; `tests/unit/test_design_index.py`
fails otherwise. Statuses are `proposal`, `in progress`, `issue draft`, or `shipped`. An issue
draft also carries an `Impact` line — the release impact of the work, which becomes the pull
request's `impact:` label and decides the version it targets.

`ROADMAP.md` remains the canonical statement of what is planned — a design document explains the
reasoning behind a roadmap entry and links back to it, rather than duplicating it.

## Private projects — never name them here

This repository is public. Cuppa is developed against private consumer projects, and their
names must not appear in anything tracked here — no private repository, group, host,
dependency, or package names, and no personal absolute paths (`/home/<user>/…`).

That applies to code, tests, docs, `CHANGELOG.md`, `ROADMAP.md`, and plan documents, including
pasted build output. Instead:

- Refer to a consumer project by a stable label (**project A**, **project B**) plus the part
  that is technically relevant — its shape: file counts, test style, run times.
- Use the existing generic fixtures for dependency and package names (`widget`,
  `https://example.com/org/widget.git`, `gitlab.example`) and `/home/user/…` for paths.
- Public references are fine: OSS libraries, published articles, the company website.

`design/INTERNAL_PROJECTS.local.md` maps those labels back to the real projects. It is gitignored
(`*.local.md`). Read it when you need to know which project a label means, and update it
whenever you introduce a new anonymised reference — but never copy a name out of it into a
tracked file.

## Commit messages

**No trailers.** A commit message ends with its last paragraph — no `Co-authored-by`, no
`Signed-off-by`, no generated-by or tool attribution lines, and nothing appended by a client.
The history records what changed and why; who or what typed it is the author field's job, and
trailers naming tools date the history and add a line of noise to every `git log`.

That means `git commit` is never invoked with `--trailer`, and a `Co-authored-by:` line is
never written into the message body either. An agent committing here passes the message with
`-m` or `-F` and nothing else.

Otherwise, follow the shape already in the log:

- A subject line that names the change, in the imperative, without a full stop.
- A blank line, then prose explaining **why** the change was needed and what it now does. Wrap
  at roughly 72 characters, and use bullets for a change with several distinct parts.
- Reference issues in prose (`Groundwork for #132`), not as a trailer.
- One coherent change per commit; split unrelated work rather than describing two things at once.

## GitHub access

Cuppa is a public repository, so anything that only reads it — issue lists, issue bodies, pull
request state — needs no credential at all. Use the public API anonymously and do not ask for a
token. A token is only for **writing**: filing or editing issues, applying labels, commenting on
pull requests.

Having one is optional. If you want an agent to write on your behalf, set it up as follows; tokens
are personal, so mint your own rather than reusing anyone else's, and what an agent did stays
attributable to you while revoking it affects nobody else. Agents: when no credential is present,
that is not a blocker — say what needs filing, labelling, or commenting, and leave it to the
person.

### Creating the token

On GitHub, under **Settings → Developer settings → Personal access tokens → Fine-grained tokens**,
create a token with:

- **Repository access:** only the cuppa repository — your fork if you work from one.
- **Permissions:** *Issues* read and write, *Pull requests* read and write, *Metadata* read-only.
  Grant nothing else. Without *Contents* or *Workflows* write, the worst an agent can do is
  reversible, visible noise on issues and pull requests; it cannot touch code, branches, or CI.
- **Expiry:** short. Thirty days or less, so a value that escapes has a deadline.

Copy the value once, into the next step. Do not paste it into a chat, a file in the working tree,
or a shell command.

### Storing it

Seal it with the helper, which encrypts it to your machine's TPM and writes
`~/.config/cuppa/github-token.cred` — outside the working tree, so it cannot be committed:

```sh
python -m scripts.github_api seal
```

The paste is not echoed. The command verifies that the sealed credential reads back correctly and
makes one authenticated call before reporting success, so a truncated paste fails now rather than
at the next write. Rotating later is the same command.

This needs `systemd-creds` and a TPM, which most current Linux systems have. Without them, seal
fails and the helper falls back to `GITHUB_TOKEN` from the environment, with a warning — usable,
but it gives up the protection described below, so prefer a keyring or another sealed store if you
work on a machine with no TPM.

### Using it

One helper reads the credential into the calling process, never into the environment:

```sh
python -m scripts.github_api GET /repos/ja11sop/cuppa/issues/132
```

```python
from scripts.github_api import GitHub
GitHub().request( 'POST', '/repos/ja11sop/cuppa/issues/132/labels', { 'labels': [ 'bug' ] } )
```

Be clear about what sealing buys. It makes the stored file meaningless anywhere else — in a backup,
a synced folder, or a pasted diff. It does **not** stop a process running as you from asking the
helper for the token, because unattended decryption means the helper answers whoever asks. That
residual risk is what the narrow permissions and the short expiry are for. So: never
`export GITHUB_TOKEN`, never echo the value, and never pass it on a command line, where the command
text lands in shell history and terminal logs.

Every call prints how long the token has left, and warns loudly under three days. Rotate when it
says so, or immediately if a value was ever printed, pasted, or committed. A TPM clear or a move to
another machine makes the sealed file unreadable; that is a two-minute recovery, not a lockout —
mint a new token and seal it again.

## Preferred invocation

```sh
cuppa -D --dbg
cuppa -D --dbg --test --show-test-output
cuppa -D --rel
cuppa -D --cov --test
cuppa -D --toolchains=gcc,clang
cuppa -D --scripts=path/to/sconscript
cuppa -D --list-develop
cuppa -D --update-develop
```

`cuppa` wraps `scons`, appends `--cuppa-mode`, masks `*TOKEN*` env values in output, and may restrict CPU affinity with `--parallel`.

Equivalent: `scons -D …` when the project's `sconstruct` already imports cuppa.

**Important:** standalone `cuppa --help` shows SCons help only. Cuppa options are SCons `AddOption` flags registered when `cuppa.run()` runs. Inspect options from a real project, or read `docs/modules/ROOT/pages/cli-reference.adoc` / [CLI reference](https://ja11sop.github.io/cuppa/cuppa/cli-reference.html).

## Defaults (do not invent older paths)

| Purpose | Default |
|---------|---------|
| Build root | `_build` |
| Storage root | `~/.cuppa` |
| Dependencies root | `~/.cuppa/dependencies` (`--dependencies-root`, was `--download-root`) |
| Downloads root | `~/.cuppa/downloads` (`--downloads-root`, was `--cache-root`) |
| Project conf | `configure.conf` |
| Global conf | `~/.cuppaconfig` |

## Flags agents should default to

- `--offline` — after the first fetch in a session; skips PyPI version check and remote location updates
- `--develop` — when using configured local develop paths for location/package deps
- `--parallel` — for compile-only speed; avoid when diagnosing failures or often when running tests/coverage
- `--verbosity=exception` or `--verbosity=debug` — when configure/sconscript load fails

**Coverage:** always pass both `--cov` and `--test`. `--cov` alone does not run tests.

## Where to change behaviour in this repo

| Area | Path |
|------|------|
| Public API | `cuppa/__init__.py` (`run`, `location_dependency`, `package_dependency`, `profile`) |
| Orchestration | `cuppa/construct.py` |
| CLI options | `cuppa/core/base_options.py`, `storage_options.py`, `location_options.py`, `cuppa/configure.py` |
| Methods | `cuppa/methods/` |
| Variants / actions | `cuppa/variants/` |
| Toolchains | `cuppa/toolchains/` (`gcc.py`, `clang.py`, `cl.py` — MSVC/`vc` on Windows; coverage is GCC/Clang only) |
| Dependencies | `cuppa/dependencies/`, `cuppa/build_with_location.py` |
| Packages | `cuppa/build_with_package.py`, `cuppa/package_managers/`, `cuppa/packages/` |
| Coverage | `cuppa/cpp/run_gcov_coverage.py`, `cuppa/methods/coverage.py` |
| C++ modules | `cuppa/cpp/module_scanner.py`, `cuppa/cpp/cxx_modules.py`, `cuppa/methods/modules.py`, `cuppa/methods/header_unit.py`, toolchain helpers in `gcc.py` / `clang.py` / `cl.py` (named modules, partitions, header units, `import std` where supported; see `docs/modules/ROOT/pages/cxx-modules.adoc`) |
| Console entry | `cuppa/__main__.py` |

Module auto-registration: `cuppa/modules/registration.py` loads classes exposing `add_options` / `add_to_env` under methods, dependencies, profiles, variants, toolchains, project_generators.

Plugins (setuptools): `cuppa.method.plugins`, `cuppa.profile.plugins`, `cuppa.dependency.plugins`.

## Validating changes to cuppa

```sh
flake8 cuppa
pylint -E cuppa
pytest -m unit
pytest -m integration   # requires a C++ compiler (g++ preferred)
# Optionally force the toolchain used by integration helpers:
# CUPPA_TEST_TOOLCHAIN=clang pytest -m integration
# CUPPA_TEST_TOOLCHAIN=clang CUPPA_TEST_ARGS='--clang-stdlib=libc++' pytest -m integration
# CUPPA_TEST_TOOLCHAIN=clang CUPPA_TEST_ARGS='--clang-stdlib=libstdc++' pytest -m integration
# CUPPA_TEST_TOOLCHAIN=vc pytest -m integration   # Windows + MSVC
```

Unit tests under `tests/unit/` cover foundations (`location`, `build_with_*`, `configure`, `registration`, construct helpers, `CuppaEnvironment`) with mocked SCons/filesystem — no compiler or network. Prefer adding unit cases there for parsing, precedence, and edge cases before new integration scenarios.

Lint config: [`.flake8`](.flake8) and [`.pylintrc`](.pylintrc). Full settings and rationale for contributors/agents: [`docs/modules/ROOT/pages/linting.adoc`](docs/modules/ROOT/pages/linting.adoc). Keep the gate error-focused — do not broaden to style warnings without intent.

CI runs the integration suite once per Linux cell via `CUPPA_TEST_TOOLCHAIN` / `CUPPA_TEST_ARGS`:
`gcc`, `clang` + `--clang-stdlib=libstdc++`, and `clang` + `--clang-stdlib=libc++`, plus once on `windows-latest` with MSVC (`vc`), and a macOS modules job that installs **Homebrew LLVM** Clang + libc++ (Apple/Xcode Clang is not modules-capable — no `clang-scan-deps`; see `docs/modules/ROOT/pages/cxx-modules.adoc` § macOS). The macOS job covers named modules, header units, partitions, packaging, and `import std` (not the full Linux matrix).
Linux CI installs **g++-15** (via `ppa:ubuntu-toolchain-r/test` + `update-alternatives`) **only on the gcc integration job**.
Each Linux integration job also `pip install`s **Conan 2** (`conan>=2,<3`) and runs `conan profile detect --force` so `tests/integration/methods/test_conan.py` runs instead of skipping; Conan is not a cuppa runtime dependency and is not required for the unit job.
The clang jobs install the newest available Clang from [apt.llvm.org](https://apt.llvm.org/) (tried newest-first), select it with `update-alternatives`, and install matching libc++ so both stdlib cells (and `import std`) can run. The libstdc++ cell uses the distro libstdc++ — do not install a newer GCC on those jobs.
Modules integration tests prefer that job’s default compiler family alias and only probe versioned drivers if the default is below the modules floor; they **fail** on too-old GCC/Clang (and on Apple Clang) rather than skipping.

Integration scenarios (with generated `sconstruct` / `sconscript` and expectations) are documented on the Antora site under **Integration tests** (`docs/modules/ROOT/pages/integration-tests.adoc` and `docs/modules/ROOT/pages/integration/`).

Smoke-test with the minimal example (from repo root, with cuppa importable — e.g. `pip install -e .` or `PYTHONPATH=.`):

```sh
cd examples/minimal
cuppa -D --dbg --test
```

Release checklist: see `release.txt` (`sdist` / `bdist_wheel` / `twine`).

## Documentation

- Human landing: `README.md`
- Canonical reference: Antora under `docs/` → https://ja11sop.github.io/cuppa/
- Further reading (talks / Clearpool posts): `docs/modules/ROOT/pages/index.adoc` (Further reading) and https://clearpool.io/tag/cuppa
- Lint settings / ignore rationale: `docs/modules/ROOT/pages/linting.adoc`
- Preview docs: `cd docs && npm ci && npm run build` → `_docs_build/site/` (Lunr search via `@antora/lunr-extension`; Mermaid via `@sntke/antora-mermaid-extension`)
- Integration test scenarios: Antora **Integration tests** section (`docs/modules/ROOT/pages/integration/`)

**Diagrams:** Antora 3 uses Asciidoctor.js, so the Ruby gem `asciidoctor-diagram` cannot be registered as an Antora AsciiDoc extension. Use `@sntke/antora-mermaid-extension` (`docs/playbook.yml`) so `[mermaid]` listing blocks render client-side with Mermaid.js (no Kroki network fetch at build time).

When docs and code disagree, **code is authoritative** (especially storage defaults, toolchain version lists, default compiler flags, and whether `--cov` implies `--test`).

### Where topics live (do not invent parallel pages)

| Topic | Primary page |
|-------|----------------|
| Overview, benefits, CMake contrast | `docs/modules/ROOT/pages/index.adoc` |
| Install / first project | `install.adoc`, `quickstart.adoc` |
| Vocabulary (methods, deps, variants) | `concepts.adoc` |
| Build / test / library APIs + examples | `methods.adoc` |
| Compiler defaults and flags | `toolchains.adoc` |
| C++20 modules intro, tutorial, papers, reference | `cxx-modules.adoc` |
| CLI flags | `cli-reference.adoc` |
| Pytest scenarios | `integration-tests.adoc` + `integration/*.adoc` |

Update `docs/modules/ROOT/nav.adoc` when adding a new top-level page.

## Consumer-project tips

In a project that *uses* cuppa (not this repo):

```sh
cuppa -D --dbg --develop --offline --test
cuppa -D --list-develop
cuppa -D --update-develop
cuppa -D --cov --test --toolchains=gcc
```

`--list-develop` reports the branch and cleanliness of each configured develop working copy; `--update-develop` fast-forwards the clean ones that are behind. See `dependencies.adoc` § Checking your develop copies.

Package registry dependencies need matching toolchain archives in the registry (or cache); `--develop` does not invent them.
GitLab auth: `GITLAB_REGISTRY_TOKEN` or `CI_JOB_TOKEN`.

---
description: Documentation style guide for Cuppa docs
globs:
  - "doc/**"
  - "**/*.adoc"
---

# Style

Technical documentation should be:

- **Comprehensive and written for all experience levels**
- **Technically detailed and correct**
- **Practical, useful, and self-contained**
- **Friendly but formal**

## Comprehensive and Written for All Experience Levels

Write clearly without assuming background knowledge. Provide explanations and context readers need to understand concepts, not just copy code.

Avoid words like "simple," "straightforward," "easy," "simply," "obviously," and "just." These make assumptions about the reader's knowledge. A reader who hears something is "easy" may be frustrated when they encounter an issue.
Prefer precise terms over colloquial ones (for example "convenience method" instead of "sugar", "compatibility wrapper" instead of slangy shorthand).

## Technically Detailed and Correct

Don't provide blocks of code and ask readers to trust it works. Every command should have a detailed explanation. Every block of code should be followed by prose explaining what it does and why.

When asking the reader to execute a command or modify code, first explain what it does and why. These details help readers grow their skills.

Quote **real** toolchain defaults and CLI behaviour from `cuppa/toolchains/*.py` and `cuppa/methods/*.py`. If a flag list changes in code, update `toolchains.adoc` in the same change.

## Practical and Self-Contained

Readers should have something usable when finished. Link to prerequisites they should complete first. Link to other docs for additional information. Only send readers offsite if no existing doc covers it and the information can't be summarized.

## Friendly but Formal

No jargon, memes, excessive slang, emoji, or jokes. Aim for a tone that works across language and cultural boundaries.

Use second person ("You will configure...") to keep focus on the reader. In some cases, use first person plural ("We will examine..."). Avoid first person singular ("I think...").

Use motivational language focused on outcomes. Instead of "You will learn how to install Apache," try "In this tutorial, you will install Apache."

## Cuppa subject matter

Cuppa docs teach a **SCons-based C++ build system**. Prefer this framing:

- **Intent over ceremony** -- show `env.Build` / `env.BuildTest` / `env.BuildWith` before raw SCons builders
- **Visible artefacts** -- talk about `_build/`, variants (`--dbg` / `--rel` / `--cov`), and toolchains by name
- **Honest comparisons** -- when contrasting CMake (or Make/Ninja wrappers), be specific about DSL complexity, property/generator-expression load, and where cuppa's Python API helps; do not dismiss other tools without nuance
- **Toolchain truth** -- every toolchain page/section should state default dialect, warning, optimisation, CRT/stdlib, and modules flags so readers know what they are getting
- **Modules as a product feature** -- for C++20 modules, start with *why* (include model costs), cite relevant WG21 papers (`wg21.link/p…`), then a cuppa tutorial, then reference detail; call out vendor gaps (Apple Clang, GCC private fragments, MSVC DLL export vs module export)
- **Fail clearly** -- document cuppa's preference for StopError / skip-with-reason over silent fallback

## Technical Depth for Core Topics

Certain foundational topics require deeper, more methodical treatment, for example:

- how `sconstruct` and `sconscript` files work together
- how Python code in sconscript files is interpreted with SCons's deferred graph construction
- foundational workflows (multi-toolchain grids, coverage+test, offline/develop)
- significant features such as C++20 modules, package BMIs, and location dependencies

For these sections:

- Use more technical and methodical exposition
- Provide convincing explanations with thorough reasoning
- Include extended background and context
- Explain the "why" behind design decisions
- Prefer AsciiDoc tutorials with numbered steps (gerund titles) over bare API tables alone

These topics build reader understanding from first principles, not just usage. Readers need to understand the reasoning to apply concepts correctly in their own code.

# Build Workflow

When documentation is built:

- Obsolete pages are automatically removed
- New pages are linked into the table of contents

No manual cleanup of old files is needed. Do update `nav.adoc` for new top-level pages.

# Structure

## Introduction

Usually one to three paragraphs. Answer:

- What is this about? What does each component do (briefly)?
- Why should the reader learn this? What are the benefits?
- What will the reader do or create? Be specific.
- What will they have accomplished when done? What new skills?

Keep focus on the reader and what they will accomplish. Instead of "we will learn how to," use "you will configure" or "you will build."

## Prerequisites

Spell out exactly what the reader should have or do before starting. Format as a checklist. Link to existing docs covering prerequisite content.

Be specific. "Familiarity with Boost" without a link gives little context. Instead: "Familiarity with Boost. To build your skills, check out [resource]."

## Steps

Each step describes what the reader needs to do and why. Include commands, code listings, and explanations of both what to do and why.

Step titles describe what readers will accomplish using gerunds (-ing words):

> Step 1 — Creating User Accounts

After the title, add an introductory sentence describing what the reader will do and how it contributes to the overall goal.

### Commands

All commands go on their own line in a code block. Precede with a description of what the command does. After the command, explain arguments and why they're used:

> Execute the following command to display the contents of the directory, including hidden files:
>
> `ls -al /home/sammy`
>
> The `-a` switch shows all files including hidden ones, and `-l` shows a long listing with timestamps and sizes.

Display command output in a separate block with text explaining what it shows.

### Code Blocks

Introduce code with a high-level explanation of what it does. Show the code. Then call out important details:

> Add the following code, which prints a message to the screen:
>
> ```cpp
> std::cout << "Hello world!\n";
> ```
>
> The `std::cout` stream sends text to standard output.

When changing something specific in existing code, show the relevant parts and highlight what should change. Explain what the change does and why it's necessary.

### Transitions

Frame each step with a brief intro sentence and a closing transition describing what the reader accomplished and where they're going next. Vary the language to avoid repetition:

> You have now configured the server. Before proceeding, you need to verify the settings in the next step.

## Conclusion

Summarize what the reader accomplished. Instead of "we learned how to," use "you configured" or "you built."

Describe what the reader can do next: use cases, features to explore, links to related docs.

# Formatting

## Line-level

**Bold** for:
- Visible GUI text
- Hostnames and usernames
- Term lists
- Emphasis when changing context

*Italics* only for introducing technical terms.

`Inline code` for:
- Command names
- Package names
- File names and paths
- Example URLs
- Ports
- Key presses (ALL CAPS, use + for simultaneous: `CTRL+C`)
- Cuppa methods and CLI flags (`env.Build`, `--modules`)

## Code Blocks

Use for:
- Commands to execute
- Files and scripts (`sconstruct` / `sconscript`, C++ sources)
- Terminal output

Use ellipses (`...`) to indicate excerpts and omissions.

If most of a file can be left with defaults, show just the section that needs changing.

## Variables

Highlight items the reader must change: example URLs, version numbers, modified lines. Make clear what needs customization.

## Notes and Warnings

Use note and warning callouts for very important information (unsupported toolchains, `--cov` not implying `--test`, Apple Clang vs LLVM Clang, MSVC DLL export vs module export).
