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
- The `release` workflow — no `.dev`, the section is dated and non-empty, and the tag matches
  `cuppa/VERSION`. Prefer Actions **prepare** (opens the finish_release PR) then **publish**
  (builds from master, creates the GitHub Release/tag, then PyPI after `pypi` environment
  approval). A `v*` tag push is an escape hatch. See `release.txt`.

A patch-sized pull request landing inside an open minor cycle is fine: the gate asks for *at
least* the implied version, so `1.4.0.dev` satisfies a `patch` label. Raising the target
mid-cycle (a `major` arrives) is a `start_release` call on that branch.

## Working documents

Long-form plans, measurements, and unfiled issue text live under `design/`, never in the
repository root and never in `docs/` (that tree is the published Antora site):

- `design/plans/` — proposals that have not shipped. Delete a plan when its work ships, unless
  the reasoning is still cited from code or docs, in which case move it to `design/archive/`.
  Console judgement-tree / severity-timing rules:
  [`design/archive/console-report-patterns.md`](design/archive/console-report-patterns.md).
- `design/issues/` — text drafted for a GitHub issue. Delete it once the issue is filed.
- `design/archive/` — shipped work whose rationale something still references.
- `design/process/` — living maintainer process narrative (how this repo is operated with CI and
  agents). Not a product plan. Today: [`design/process/agent-workflow-journey.md`](design/process/agent-workflow-journey.md).

Filenames are kebab-case. Every document opens with a `Status` / `Related` / `Updated` header,
and must be added to the Index table in `design/README.md`; `tests/unit/test_design_index.py`
fails otherwise. Statuses are `proposal`, `in progress`, `issue draft`, `shipped`, or `living`
(`living` only under `process/`). An issue draft also carries an `Impact` line — the release
impact of the work, which becomes the pull request's `impact:` label and decides the version it
targets.

`ROADMAP.md` remains the canonical statement of what is planned — a design document explains the
reasoning behind a roadmap entry and links back to it, rather than duplicating it.

For a multi-PR workstream, **settle vocabulary and refusal rules in the plan before the first
implementation commit** (a short settled-decisions table beats rewiring CLI help mid-flight).
When behaviour lands, **update that plan's progress snapshot in the same change** (or the same
PR), not only in a late housekeeping sweep — stale “still a proposal” rows are how agents and
people lose the plot.

### Process journey (`design/process/`)

[`agent-workflow-journey.md`](design/process/agent-workflow-journey.md) is maintainer context: why
the release ritual, `AGENTS.md` rules, and helpers exist. Day-to-day “what do I run?” stays in
`AGENTS.md` and Antora Contributing — do not duplicate those checklists into the journey.

**Who edits it:** the primary maintainer owns it. Agents and other contributors **append by
default** (new §5/§6 bullets, a timeline row, or a short case study). Do not rewrite the whole
arc unless the maintainer asks. `.github/CODEOWNERS` requests review on `design/process/`.

**When to update** (event-driven, not a fixed calendar):

- A durable rule lands in `AGENTS.md`, Contributing, or `release.yml`.
- A process incident (wrong tag, CI footgun, new helper invented under pressure).
- A blueprint Stage proves necessary, or a multi-session product arc ends.
- The merge-readiness or release ritual itself changes.

**When not to:** routine feature PRs, typo-only docs, chat that did not change repo rules.

**Periodic skim:** when opening a new cycle with `start_release`, re-read the journey once for
drift against `AGENTS.md` / Contributing and bump `Updated:` if you fix anything.

**Privacy:** the same private-projects rule as every tracked file. Never copy names from
`INTERNAL_PROJECTS.local.md` into the journey. Gitignored `*.local.md` files remain local-only.

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

**`master` is protected.** Never push commits directly to `master` (or force-push it). Land every
change — including release tagging prep, ROADMAP/CHANGELOG housekeeping, and `AGENTS.md` edits —
through a pull request branch: create a branch, `git push -u origin HEAD`, open or update the PR,
wait for CI, then merge on GitHub. `git push origin master` will be rejected.

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

**Do not use the `gh` CLI.** It is not authenticated in this environment and is not the path these
notes set up. For authenticated writes use `scripts.github_api` (and the helpers below). For
anonymous reads use the public GitHub HTTP API, `curl`, or `urllib` — still not `gh`.

Cuppa is a public repository, so anything that only reads *metadata* — issue lists, issue bodies,
pull request state, check-run conclusions — needs no credential at all. Use the public API
anonymously (`GitHub.public()` / `show-pr` / `pr-status` / `watch-pr`) and do not ask for a token.

**Exception — Actions log archives:** even on a public repository, GitHub's
`/actions/runs/{id}/logs` and `/actions/jobs/{id}/logs` endpoints return **403** to anonymous
clients ("Must have admin rights to Repository"). Check-run *annotations* are public but usually
only say the step exited non-zero. To read the pytest failure text, use ``fetch-ci-logs`` with
the sealed credential (see below).

A token is for **writing** (filing or editing issues, applying labels, commenting on pull
requests) and for **downloading CI logs**. Pushing a branch is ordinary `git push -u origin HEAD`;
that does not need this credential either.

Having a token is optional. If you want an agent to write on your behalf, set it up as follows;
tokens are personal, so mint your own rather than reusing anyone else's, and what an agent did
stays attributable to you while revoking it affects nobody else. Agents: when no credential is
present, that is not a blocker — say what needs filing, labelling, or commenting, and leave it to
the person.

### Creating the token

On GitHub, under **Settings → Developer settings → Personal access tokens → Fine-grained tokens**,
create a token with:

- **Repository access:** only the cuppa repository — your fork if you work from one.
- **Permissions:** *Issues* read and write, *Pull requests* read and write, *Actions* read-only,
  *Metadata* read-only. Grant nothing else. *Actions* read is only so ``fetch-ci-logs`` can
  download workflow log zips; without it, status polling still works via the public API. Without
  *Contents* or *Workflows* write, the worst an agent can do is reversible, visible noise on
  issues and pull requests; it cannot touch code, branches, or CI configuration.
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

**Reads** go through the public API — no sealed token. Prefer `scripts.github_helpers`
(`show-pr` / `pr-status` / `watch-pr`) for pull-request metadata and CI, or an anonymous client
for other ad-hoc GETs:

```sh
python -m scripts.github_helpers show-pr --pr 165          # title, labels, body (alias: fetch-pr)
python -m scripts.github_helpers show-pr --pr 165 --json
python -m scripts.github_helpers pr-status --pr 140
python -m scripts.github_api GET /repos/ja11sop/cuppa/issues/132
```

```python
from scripts.github_helpers import show_pull_request
show_pull_request( number=165 )

from scripts.github_api import GitHub
GitHub.public().request( 'GET', '/repos/ja11sop/cuppa/pulls/140' )
```

The CLI uses the anonymous client for `GET` / `HEAD` by default. Pass `--auth` only when a read
truly needs the sealed credential (private resources). Do not unseal just to poll CI or to read
a public pull request's title and body.

**Writes** use the sealed credential. `scripts.github_api` reads the token into the calling
process only — never into the environment:

```sh
python -m scripts.github_api PATCH /repos/ja11sop/cuppa/pulls/140 --data '{"title":"…"}'
```

```python
from scripts.github_api import GitHub
GitHub().request( 'POST', '/repos/ja11sop/cuppa/issues/132/labels', { 'labels': [ 'bug' ] } )
```

Repeated write workflows live in `scripts.github_helpers` so agents do not rewrite the same API
sequence each time. Add to that module when the same sequence appears twice; do not invent helpers
for a one-off. Opening a pull request for the current branch (and applying labels such as
`impact:minor`) is already there:

```sh
python -m scripts.github_helpers create-pr \
  --title "…" --body-file /tmp/pr.md --label impact:minor

python -m scripts.github_helpers update-pr \
  --pr 154 --title "…" --body-file /tmp/pr.md
```

```python
from scripts.github_helpers import create_pull_request, update_pull_request
create_pull_request( title='…', body='…', labels=['impact:minor'] )
update_pull_request( number=154, title='…', body='…' )
```

### Before pushing a pull request branch

**Always run the full local Python test gate before `git push`.** Waiting for CI to report a unit
or integration failure wastes a long Actions cycle and rate-limited status polls. From the repo
root (with cuppa importable — e.g. `pip install -e .` or `PYTHONPATH=.`):

```sh
flake8 cuppa
pylint -E cuppa
pytest -m unit
pytest -m integration
```

Do not skip `pytest -m unit` or `pytest -m integration` because only a helper script or docs
changed — those suites are fast relative to CI and catch import / CLI regressions. Use
`CUPPA_TEST_TOOLCHAIN=…` when you need a non-default compiler for integration (see
[Validating changes to cuppa](#validating-changes-to-cuppa)). Fix failures locally, then push.

**Batch local commits; do not push every small edit.** Each push restarts CI, and a full matrix
run often takes **more than ten minutes**. While a PR is open — especially once feature work is
largely done and you are polishing docs, plans, CHANGELOG wording, or tiny test fixes — prefer:

1. Make several related commits locally (or one coherent commit).
2. Re-read the diff and run the local gate above until you are satisfied.
3. **Then** push once (or rarely), and only then run `watch-pr`.

Pushing after every minor tweak is eager in the wrong way: it burns CI time and delays the merge
more than holding a few commits until the batch is ready. Reserve frequent pushes for real CI
failures that need a green signal on the next head, not for iterative housekeeping.

### When a pull request is ready to merge

Once the branch looks merge-ready (feature work done, local tests green, or CI already green and
only polish remains), **do a documentation and housekeeping pass before the final push** — do not
treat merge readiness as “CI green alone”. In the same local batch (see batching above):

1. **Documentation review** — Antora pages under `docs/`, CLI reference, integration-test pages,
   and any consumer-facing samples touched by the work. Confirm they match shipped behaviour
   (flags, report shape, verify hints, examples). Prefer updating the eventual topic page from
   [Documentation](#documentation) / the removal-plan docs split rather than leaving stale prose.
2. **`CHANGELOG.md`** — open section has accurate Added / Changed / Fixed entries for everything
   that lands in the PR (including late fixes). No sweep of unrelated history.
3. **`ROADMAP.md`** — Today / Planned rows reflect what this PR ships and what is next; do not
   leave “on branch `…`” once the PR is the landing vehicle (cite the PR number).
4. **Related design plans** — progress snapshot, phase tables, “next focus”, and `design/README.md`
   index row. Mark shipped slices done; park deferred work explicitly; update `Updated:` dates.
   Prefer that these already moved with the behaviour commits; this pass is the safety net.
   Do not close umbrella issues in PR text unless the plan says that slice closes them.
   If this PR changed agent/release *process* (`AGENTS.md`, `release.yml`, Contributing release
   pages), append to [`design/process/agent-workflow-journey.md`](design/process/agent-workflow-journey.md)
   per the Working documents rules — skip that file on ordinary feature PRs.

After that batch is committed and pushed, watch CI as usual. If only docs/plan/CHANGELOG change
after a green run, still prefer **one** push of the housekeeping batch rather than dripping
commits.

5. **PR test plan** — open the pull request body and walk the Test plan checklist. Tick items that
   are done (local gate, focused integration suites, **CI green on the matrix**). Leave optional
   manual spot-checks unchecked unless they were actually run, and say so when reporting
   merge readiness. Update the PR body via ``update-pr`` (or ``create-pr`` when opening) if the
   checklist is
   stale — do not treat an unchecked “CI green” box as unknown when `watch-pr` already
   succeeded.
6. **Squash commit message** — when the person will squash-merge, draft a single commit message
   that matches this repo’s style (imperative subject, blank line, why/what prose, no trailers;
   reference umbrella issues in prose, not `Fixes`/`Closes` unless that slice should close them).
   Offer it in the chat (and optionally paste into the GitHub squash UI) before merge.

### After pushing a pull request branch

After `git push -u origin HEAD` (or any later push to an open PR), **do not stop without knowing
how CI finished**. The person should not be the first to discover a red check. Poll until the
checks complete, then report the outcome and be ready to decide next steps — merge discussion if
green, diagnosis and a fix if red.

```sh
python -m scripts.github_helpers watch-pr          # current branch's open PR
python -m scripts.github_helpers watch-pr --pr 139
python -m scripts.github_helpers pr-status --pr 139   # one snapshot; no wait
```

These status helpers read the public API anonymously by default — they do **not** unseal the token
unless you pass `--auth` or the public API rate-limits (then they fall back to the sealed
credential and keep using it for later polls). Owner and repository come from the local `origin`
remote.

**Default `watch-pr` schedule** (sleep *before* each poll):

1. Wait **2 minutes**, then poll once — catches quick failures (lint, misconfigured CI) without
   hammering the API while jobs are still queuing.
2. Wait **another 8 minutes** (about **10 minutes** from start) — full CI usually finishes around
   here, so mid-run polls are skipped on purpose.
3. Then poll **every 2 minutes** until success, failure, or `--timeout` (default one hour).

Pass `--interval N` for a fixed delay before every poll instead of that schedule. Prefer the
default after a push; use `pr-status` when you only need a snapshot.

Exit codes: `0` all checks succeeded (or were skipped / neutral), `1` at least one failed, `2`
still pending (`pr-status` only), `3` timed out while still pending (`watch-pr`).

If `watch-pr` times out with **no check runs**, or Actions never starts for new pushes, check
[GitHub Status](https://www.githubstatus.com/) before assuming the branch is wrong. During an
Actions outage, webhooks are often throttled: empty “retrigger” commits do nothing useful. Keep
the PR honest (local gate ticked; CI box unchecked with a note), wait for recovery, then
`watch-pr` or re-run from the UI — do not burn the API on empty pushes.

When `watch-pr` / `pr-status` reports a failure, feed the failed job name into the log helper
(sealed token; Actions read permission required — see token permissions above):

```sh
python -m scripts.github_helpers fetch-ci-logs
python -m scripts.github_helpers fetch-ci-logs --job integration-windows
python -m scripts.github_helpers fetch-ci-logs --job integration-windows --full
python -m scripts.github_helpers fetch-ci-logs --output-dir /tmp/cuppa-ci-logs
```

`fetch-ci-logs` defaults to every check that failed on the open PR, downloads that head's workflow
run log zip, and prints failure excerpts (`FAILED`, `AssertionError`, …). Pass `--job` to narrow
to one check name substring from the `pr-status` listing. Do not use `gh` for this, and do not
hand-roll log downloads when the helper already encodes the redirect/auth stripping.

Grow this helper if the same follow-up starts repeating.

**When chat has to correct the same mistake twice**, encode it: extend this file, add a helper
under `scripts.github_helpers` (or similar), or add a unit test that fails when an index / version
/ plan header drifts. Do not leave the rule only in conversation memory.

Prefer **separate pull requests** for agent/CI tooling (`update-pr`, poll schedules, sealed-token
fixes) versus product behaviour when practical — mixed PRs ship fine in a pinch, but they make
review and squash messages harder.

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
cuppa -D --list-builds
cuppa -D --dbg --remove-builds -n
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

Run this **before every push** to a pull-request branch (see
[Before pushing a pull request branch](#before-pushing-a-pull-request-branch)). It is much cheaper
than learning about a failed unit or integration test from CI.

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

Release checklist: see `release.txt` (Actions **prepare** → merge → **publish** → approve `pypi`).

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
| Fetched toolchain archives (`--toolchain-archive`, `--*-root`) | `toolchains.adoc` § Fetched toolchain archives |
| C++20 modules intro, tutorial, papers, reference | `cxx-modules.adoc` |
| CLI flags | `cli-reference.adoc` |
| Dependencies overview (kinds, declare, `BuildWith`) | `dependencies.adoc` (hub) |
| Location / header libraries | `dependencies-location.adoc` |
| Package consume overview | `dependencies-packages.adoc` |
| GitLab packages (consume) | `dependencies-gitlab.adoc` |
| Conan packages (consume) | `dependencies-conan.adoc` |
| Built-in deps index | `dependencies-builtins.adoc` |
| Boost (source / b2; contrast `boost_package`) | `dependencies-boost.adoc` |
| Qt / Quince | `dependencies-qt.adoc` / `dependencies-quince.adoc` (thin stubs) |
| Managing deps (list / update / remove) | `dependencies-managing.adoc` |
| Writing your own dependencies | `dependencies-extending.adoc` (also `extending.adoc` for plugins) |
| Publishing packages (GitLab / Conan) | `packages.adoc` (publish focus; not consume tutorials) |
| Contributing to cuppa itself (hub) | `contributing.adoc` |
| Versioning / changelog / start_release | `contributing-versioning.adoc` |
| Cutting a release (prepare / publish) | `contributing-release.adoc` |
| Pytest scenarios | `integration-tests.adoc` + `integration/*.adoc` |

The Phase 3 documentation split in [`design/plans/removal-options.md`](design/plans/removal-options.md) §7.1 has landed. Prefer the child page above rather than growing the hub.

Update `docs/modules/ROOT/nav.adoc` when adding a new top-level page or nesting children under Dependencies.

### Documentation partitioning (rules of thumb)

Use these when splitting or placing dependency (and similar) docs — same principles as §7.1 of the removal-options plan:

- **Mirror the code shape.** Location, GitLab package, Conan, built-ins, manage-on-disk, and authoring already live in different modules; docs should follow that map rather than one growing page.
- **Hub pages stay short.** Overview + kinds table + `cuppa.run` / `BuildWith` + pointers. No deep tutorials on the hub.
- **Consume vs publish.** Consuming a registry or Conan package belongs under Dependencies; publishing Cuppa-built libraries belongs under Packages (or a Publishing child). Cross-link the round-trip; do not duplicate the full story on both sides.
- **Managing is its own page.** List / update / remove / inventory are storage and develop workflows, not a footnote on declaring dependencies.
- **Nest by surface area, not by every registered name.** Give a child page when the topic has its own CLI options, `env.*` helpers, or a choose-your-flavour decision (e.g. Boost source vs `boost_package`). Keep an index as name → one-line purpose → xref.
- **Honest stubs beat invented depth.** Thin or nearly undocumented built-ins (Qt, Quince today) get short pages or index sections that name the dependency, prerequisites, and module — expand when real usage is documented.
- **Do not rewrite unstable samples twice.** When CLI table presentation or removal flags are still churning, finish that polish before (or land Managing together with) the docs that quote those examples.
- **Integration test pages stay under Integration tests**; topic pages link them rather than inlining scenario prose.
- **Fix known doc/code drift while moving** (wrong method names, obsolete paths); do not copy mistakes into the new tree.

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

## Page partitioning

Prefer a **hub + topic children** over a single long page when a subject already has distinct code modules or reader jobs (declare vs consume vs publish vs manage vs extend).

Rules of thumb (see also agent notes § Documentation partitioning and `design/plans/removal-options.md` §7.1):

- Keep the hub short: what it is, kinds or map, how to declare, where to go next.
- Split **consume** tutorials from **publish** tutorials; cross-link instead of duplicating.
- Put **manage on disk** workflows (list / update / remove) on their own page.
- Nest further only when surface area warrants it (own CLI flags, `env.*` helpers, or a non-trivial flavour choice). An index of registered names with one-line purpose and xrefs is enough for thin built-ins.
- Prefer honest stubs over pages that invent depth the product does not yet document.
- Update `nav.adoc` so nested children appear under the hub; do not leave orphan pages.

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
