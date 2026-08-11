# Journey: hardening a Git project for humans and agents

- **Status:** living
- **Related:** [`AGENTS.md`](../../AGENTS.md) (agent ops); Antora Contributing (human versioning/release)
- **Updated:** 2026-08-11
- **Maintainer:** primary author of this journey; others append only (see `AGENTS.md`)
- **Privacy:** obey the private-projects rule; never copy names from `INTERNAL_PROJECTS.local.md`
- **Source:** Cursor sessions spanning roughly mid-July → 2026-08-07 on cuppa
- **Audience:** maintainers who want a blueprint for taking a working OSS/tooling repo and making it safer to change with CI and AI agents

This is not a product roadmap and not Antora documentation. It is a *process* narrative:
what we did, in what order, what became habit, and what we would reorder if we started again.
Day-to-day commands live in `AGENTS.md` and Contributing; this file explains how those habits were earned.

---

## 1. Why this journey matters

Cuppa started the session as a capable SCons extension with real users, but thin automated
guardrails relative to its surface area. Over about two weeks of dense work we repeatedly
discovered the same pattern:

1. Add or clarify a capability.
2. Hit a gap (missing tests, opaque CI, agent confusion, private names leaking into public docs).
3. Encode the fix in the **repository** (tests, docs, `AGENTS.md`, helper scripts, design plans),
   not only in chat memory.
4. Use the next PR to *obey* those encoded rules until they feel automatic.

The destination is not “more AI.” It is a project that:

- fails loudly and locally before burning CI,
- has one place agents (and people) read for workflow,
- keeps long design reasoning out of chat and out of the published docs site,
- treats CI as confirmation, not discovery,
- never trusts an agent’s improvisation for repeated GitHub/API sequences,
- and makes **releases** a short, button-driven path that cannot tag the wrong commit by accident.

---

## 2. Arc of the session (compressed timeline)

Rough phases, not strict calendar days:

| Phase | What we worked on | Process lesson that stuck |
|-------|-------------------|---------------------------|
| **A. Docs foundation** | Antora overhaul, search (Lunr), style, further reading | Docs are a product surface; Markdown-in-AsciiDoc tables fail in CI/site builds |
| **B. Test foundation** | Unit suite + method integration tests; document each scenario in Antora | Tests without docs drift; docs without tests lie |
| **C. CI / lint / matrix** | Fix pip/install, pyflakes/pylint noise, Windows `cl`, gcc/clang cells, UTF-8 reports | First green matrix is expensive; encode platform quirks in tests and docs notes |
| **D. Core coverage + features** | Deeper unit tests (`location`, etc.); modules; Conan consume/publish; toolchain flags | Plan → implement → harden; pause big plans when a live bug is blocking |
| **E. Release hygiene** | `CHANGELOG`, `ROADMAP`, squash messages, version/impact discipline | Releases need mechanical rules or agents invent them |
| **F. Agent operating system** | `AGENTS.md`, sealed GitHub token, `scripts.github_*`, no `gh` CLI, private-name rules | Agents need *scripts* and *prohibitions*, not vibes |
| **G. Design folder discipline** | `design/plans`, archive, index test, `*.local.md` for private maps | Long plans live in-repo; private labels stay local |
| **H. Storage / develop product arc** | list/remove/purge/wipe, develop report/update/clone/branch helpers | Large features need a living plan + PR-sized slices + live-output feedback loops |
| **I. Merge readiness ritual** | Local full gate before push; watch-pr schedule; fetch-ci-logs; docs/ROADMAP/CHANGELOG housekeeping; update-pr; squash draft | “CI green” alone is not merge-ready |
| **J. Release automation + first cut** | Trusted Publishing, `pypi` env, prepare/publish `workflow_dispatch`, 1.4.0, Contributing Antora | Manual tag push is a footgun; buttons + gate + diagrams beat checklist prose alone |

Late in the arc, develop-branch design (base vs default, no parent guessing) and Mermaid
diagram choices showed the same maturity: **decide vocabulary in the plan**, illustrate with
the right diagram type, encode in CLI/docs/tests together.

The release cut (phase **J**) proved the same for *process* diagrams: a flowchart and a
`gitGraph` of prepare → merge → publish are worth more than another paragraph in `release.txt`.

---

## 3. What “agent-friendly” meant in practice

### 3.1 A single agent contract: `AGENTS.md`

Grew from build tips into an operating manual:

- Preferred `cuppa` / pytest / lint commands.
- Versioning and changelog rules (`start_release` / `finish_release`, impact labels).
- Where design docs live vs Antora docs (including **Contributing** for humans).
- Private projects: never name them in tracked files; use labels + `INTERNAL_PROJECTS.local.md`.
- GitHub: no `gh`; public reads vs sealed writes; `watch-pr` / `fetch-ci-logs` / `create-pr` /
  `update-pr`.
- Protected `master`: every tree change — including release prep — is a PR branch.
- Before push: full local unit + integration gate.
- Before merge: documentation + ROADMAP + CHANGELOG + plan housekeeping + PR test-plan ticks +
  squash message draft.

**Teaching point:** put agent instructions in the repo early, then *extend them when you catch
yourself repeating a correction in chat*.

### 3.2 Helpers instead of one-off API calls

Whenever an agent mistook `GitHub.request`’s `(status, body)` tuple, or reinvented PR polling,
we added a helper:

- `show-pr` / `fetch-pr` (title, labels, body via the public API — not `gh`, not sealed token)
- `pr-status` / `watch-pr` (sparse poll schedule to spare the API)
- `fetch-ci-logs` (Actions logs need auth even on public repos; pass `--pr` or `--run-id`)
- `create-pr` / `update-pr` (title/body/labels without hand-rolled PATCH)

**Teaching point:** the second time you debug the same API footgun, stop and write the script.

### 3.3 Tests as the cheap oracle

Order that emerged:

1. Prefer **unit** tests for pure decisions (classify, wipe tokens, URL parsing).
2. Prefer **integration** tests for real `cuppa` CLI + temp projects + local git origins.
3. Document integration scenarios on the Antora site so humans see the same fixtures.
4. Run **full** `pytest -m unit` and `pytest -m integration` before push — CI is too slow to be
   the first notifier.

Windows and multi-toolchain cells repeatedly taught: fix the fixture (`Path.as_uri()`, OS
archive names, PYTHONPATH) rather than skip the platform.

### 3.4 Design plans as the long memory

`design/plans/removal-options.md` became the spine for months of work: progress snapshot,
settled decisions table, deferred items, next focus. Index enforced by unit test.
Pre-plan seeds live in [`design/ideas/scratchpad.md`](../ideas/scratchpad.md) (living;
graduate to `plans/` + ROADMAP, then delete the note) — not in `*.local.md`, which stays for
private project maps only.

**Teaching point:** chat summaries evaporate; a dated progress table in a plan does not.

### 3.5 Live consumer feedback as design input

Many listing/wipe/remove behaviours were shaped by pasting real command output from consumer
projects (anonymised in public docs). Agents proposed; humans corrected colour, tree shape,
selectors, and vocabulary (`repository` vs `location`, develop base vs default).

**Teaching point:** for CLI UX, plan for a “paste output → adjust → retest” loop; do not pretend
the first tree layout is final.

### 3.6 Diagrams with honest jobs

- Flowcharts / sequence diagrams for **cuppa options and sessions**.
- `gitGraph` for **branch topology** (develop base ≠ default; release prepare branch → tag).
- State diagrams for **VERSION / CHANGELOG** (`.dev` → dated → next `start_release`).
- Prefer Mermaid that builds offline in Antora over network Kroki.

### 3.7 Split “agent ops” from “human contributing”

`AGENTS.md` stays dense (tokens, `watch-pr` schedules, sealed credentials).
Antora **Contributing** teaches humans the same release story with diagrams and without the
agent-only machinery. `release.txt` remains the one-page checklist; the site is the illustrated
guide. Cross-link all three; do not let them drift.

---

## 4. A blueprint you can apply to another Git project

Use this as an ordered checklist. Cuppa did not follow it perfectly (see §5); this is the
*recommended* order distilled from the journey.

### Stage 0 — Decide the public/private boundary

- [ ] What may appear in the public repo (no customer names, no private hosts, no home paths)?
- [ ] Add a gitignored `*.local.md` map if you need private ↔ public labels.
- [ ] Write one paragraph in `AGENTS.md` (or Contributing docs) stating the rule.

### Stage 1 — Make the project buildable and documentable

- [ ] One obvious “how do I build/test?” path.
- [ ] Docs site or README that matches reality (code wins when they disagree).
- [ ] Fix doc tooling early (search, diagram renderer, output dir) so docs CI is trustworthy.

### Stage 2 — Tests before feature churn

- [ ] Unit tests for pure logic (no network, no compiler if possible).
- [ ] Integration tests for the real CLI/entrypoints you care about.
- [ ] Markers (`unit` / `integration`) so local and CI can choose cost.
- [ ] Document the important integration scenarios next to the site nav.

### Stage 3 — CI as a matrix, not a single happy path

- [ ] Lint with an explicit, documented policy (what is ignored and why).
- [ ] Unit job on several Python versions if relevant.
- [ ] Integration on the platforms/toolchains users actually use (Linux gcc/clang, Windows MSVC, …).
- [ ] Encode platform quirks in tests the first time they bite.

### Stage 4 — Agent / contributor operating manual

- [ ] `AGENTS.md` (or equivalent) with copy-pastable commands.
- [ ] “Always run X locally before push.”
- [ ] “How we open/update PRs and watch CI” — prefer small scripts over ad-hoc API.
- [ ] Credentials: sealed or keyring; never in env dumps or chat.
- [ ] State that the default branch is protected and release prep is a PR too.

### Stage 5 — Release and roadmap discipline

- [ ] Changelog with one open section; SemVer impact labels on PRs.
- [ ] Mechanical `start_release` / `finish_release` (or equivalent); CI gates that refuse `.dev` tags.
- [ ] Roadmap “Today / Planned” that cites PR numbers, not stale branch names.
- [ ] Design plans for multi-PR workstreams; archive or delete when shipped.

### Stage 5b — Make the release path push-button (learned the hard way)

- [ ] Prefer `workflow_dispatch` **prepare** (open finish PR) and **publish** (build master tip,
      create tag/release via API, approve environment) over hand-pushed tags.
- [ ] Wire Trusted Publishing *after* the workflow file is on the default branch; name a GitHub
      Environment with required reviewers before the first real upload.
- [ ] Document order clearly: merge finish PR → publish from **master tip** → approve PyPI.
- [ ] Gate must fail if VERSION is still `.dev` or CHANGELOG is still `unreleased`.
- [ ] Publish must refuse a tag that already points at the wrong commit.
- [ ] Put the happy path on the docs site with Mermaid (`gitGraph` + sequence + flowchart);
      keep a short `release.txt` checklist in sync.
- [ ] After a cut, open the next cycle with `start_release` on a PR when the *next* workstream
      starts — do not auto-bump at tag time.

### Stage 6 — Slice large product work

- [ ] One living plan with a progress table and **next focus**.
- [ ] Ship vertical slices (list → remove → purge → wipe; or clone → checkout → reset).
- [ ] Settle vocabulary in the plan before coding (`base` vs `default`, selectors, …).
- [ ] Housekeeping pass on every merge-ready PR: docs, changelog, roadmap, plan, test plan, squash message.
- [ ] Squash commit drafts belong at **merge readiness** (from the landed diff + issue/plan context), not in the PR body at open time.

### Stage 7 — Encode repeated pain

Whenever chat says “remember to …”:

- [ ] Add to `AGENTS.md`, or
- [ ] Add a helper script, or
- [ ] Add a unit test that fails if the index/plan/version drifts, or
- [ ] Add a workflow / docs page if the pain was a *human* process mistake (wrong tag, wrong order).

---

## 5. What we might have done better (hindsight)

These are recommendations for the next project, not self-flagellation.

1. **Write `AGENTS.md` and the local-gate rule earlier.**  
   We learned “always run full unit+integration before push” after burning CI cycles. Put Stage 4
   nearer Stage 2.

2. **Introduce `watch-pr` / log helpers before the first multi-PR feature arc.**  
   Polling and log-fetch were invented mid-stream under pressure. Scaffold them when you first
   open a PR from an agent.

3. **Prefer plan-settled vocabulary before the first implementation PR.**  
   Develop reset→master vs long-running parent, wipe selectors, and `[D]` placement all needed
   mid-flight redesign. A short “decisions” table up front is cheaper than rewiring CLI help.

4. **Keep design plans updated in the same commit as behaviour, not as a late housekeeping
   sweep.**  
   Stale “§3.7 remains a proposal” text survived past implementation until a dedicated pass.

5. **Do not over-invest in diagram tooling before the first real diagram need.**  
   Kroki → Mermaid extension churn was real. Start with one offline Mermaid path.

6. **Separate “product feature” PRs from “agent workflow” PRs when possible.**  
   `update-pr` landing on the develop-helpers branch was correct and useful, but it mixes
   concerns for reviewers. A tiny follow-up PR for tooling is often clearer.

7. **Expect forge outages.**  
   Actions major outages taught: local green + honest PR checklist beats waiting forever;
   empty retrigger commits do nothing when webhooks are throttled.

8. **Private-name hygiene should precede publicity.**  
   Anonymised labels + local map should exist before the first blog post, coverage note, or
   design doc that mentions consumer shapes.

9. **Integration tests for docs examples sooner.**  
   “Examples in docs” that are not executed will rot; we added verification after noticing.

10. **Batch pushes while polishing.**  
    AGENTS later formalised “don’t push every tiny docs tweak” — learn that before the tenth
    CI restart.

11. **Do not ship “tag push publishes” without a prepare step that is hard to skip.**  
    First 1.4.0 attempt: `v1.4.0` was pushed on the housekeeping merge (#155) while VERSION was
    still `1.4.0.dev` and CHANGELOG still `unreleased`. `scripts.check_release` correctly failed —
    the gate worked; the *process* did not. Delete the bad tag, merge finish_release, retag (or
    better: **publish from master** so the tag is created only after the gate on the right tip).
    Automate prepare → merge → publish before the first production cut if you can.

12. **Verify “what is tagged” when anyone is confused.**  
    Compare: remote tag peeled SHA, `master` tip, `cuppa/VERSION` at each, open finish PR state,
    and recent `release` workflow runs. A one-shot status dump beats arguing from memory.

13. **Trusted Publishing setup order: workflow on default branch → GitHub Environment → PyPI
    publisher.**  
    PyPI needs the workflow filename and environment name; creating the publisher first is wasted
    motion if the workflow is not merged yet.

14. **Document the release path for humans when you automate it.**  
    Buttons without diagrams still confuse. Contributing Antora (versioning + cutting a release)
    landed in the same workstream as prepare/publish for a reason.

15. **Pin the local Python gate to a virtualenv.**  
    Host / `~/.local/bin` `flake8` and `pylint` shims can look present and still fail
    (`ModuleNotFoundError`), and system Python often lacks test extras from
    `requirements.txt` (for example `grip`). Prefer an existing checkout `venv/` or create one;
    encoded in `AGENTS.md` / Contributing / Linting so agents do not skip lint as “unavailable.”

16. **Generate listing doc samples from the real formatters.**  
    Hand-indented trees and JSON in AsciiDoc drift the moment the CLI changes (stem spacers,
    Allman braces, wipe footers). Prefer `python -m scripts.generate_doc_samples` writing
    `docs/modules/ROOT/partials/samples/`, unit tests on nesting/shape, shortened fixtures for
    readable pages, and collapsible Antora blocks for JSON. Keep one pretty-printer
    (`storage.render_json_payload`) for CLI and samples. Hub + family pages for toolchains
    (like Dependencies) belong in `AGENTS.md`’s topic map so agents stop stuffing flag tables
    into the hub.

---

## 6. Patterns worth stealing (short list)

| Pattern | Why |
|---------|-----|
| Progress snapshot table at top of the long plan | Instant orientation for humans and agents |
| Settled-decisions table | Stops re-litigating “should reset guess the parent?” |
| Pure decision functions + orchestration | Unit-test the rules without git/network |
| Act-where-safe / report-where-not | Same philosophy across update/clone/checkout/reset/wipe |
| `--list-format=json` for agent consumption | Text is for eyes; JSON is for scripts |
| Housekeeping ritual before merge | Prevents “green CI, stale ROADMAP” |
| Sealed token + public reads by default | Safer defaults for agents |
| `show-pr` / `fetch-pr` for PR metadata | Prefer helpers over ad-hoc `GET /pulls/{n}` (and never `gh`) |
| `*.local.md` for secrets of context | Public repo stays clean |
| `check_release` before build/publish | Catches `.dev` / unreleased before PyPI |
| prepare / publish `workflow_dispatch` | Removes hand-tag ordering mistakes |
| Tag via GitHub API from publish job | Avoids double-firing `push: tags` when softprops creates the tag |
| Environment approval on `pypi` | Human gate without long-lived Twine tokens |
| Contributing Antora + `release.txt` + `AGENTS.md` | Humans get diagrams; agents get ops; checklist stays short |
| Local gate via checkout `venv/` + `requirements.txt` | Avoids broken host flake8/pylint shims and missing test extras |
| `generate_doc_samples` + partial includes | Listing docs cannot drift from CLI trees / JSON |
| Hub + family topic pages (Dependencies, Toolchains) | Agents know which AsciiDoc file owns defaults vs inventory |

---

## 7. Suggested outline for teaching others

If you turn this into a talk or internal guide, a clean narrative is:

1. **Start with truth:** docs and tests that match the code.
2. **Widen CI until it hurts, then encode the pain.**
3. **Write the agent contract when you first get tired of repeating yourself.**
4. **Script the forge; don’t improvise it.**
5. **Put multi-week work in a plan with a progress table.**
6. **Ship slices; polish vocabulary with real output pastes.**
7. **Merge only when the ritual is done** (local gate, CI, docs, roadmap, changelog, plan, PR
   checklist, squash message).
8. **Automate the release cut** (prepare PR → publish from default-branch tip → approve env);
   illustrate it; never rely on “remember to tag the finish commit.”

Cuppa’s session is evidence that you can retrofit this onto an existing project — but the
blueprint’s order is still cheaper than rediscovering it under production pressure.
The premature `v1.4.0` tag is the exhibit for step 8.

---

## 8. Case study: the 1.4.0 cut (what actually happened)

Compressed facts worth remembering when teaching:

1. Feature work and dogfood landed; housekeeping PR (#155) shipped release workflow + docs notes
   while VERSION was still `1.4.0.dev`.
2. Someone tagged `v1.4.0` on the #155 merge. Gate failed: development VERSION + unreleased
   CHANGELOG. **Good failure.**
3. Finish-release PR (#156) closed the cycle on `master`. Remote bad tag was deleted; local tag
   could still point at the old SHA — refresh with `git fetch --tags` / delete local tag.
4. Retagged (or: next time, **publish** with blank tag) on the finish merge commit → Release +
   PyPI after `pypi` approval.
5. Immediate follow-up: prepare/publish buttons + Contributing docs with Mermaid so the next cut
   does not depend on chat memory of this incident.

**Recovery checklist when a tag is wrong:**

```text
remote tag gone?     git ls-remote origin refs/tags/vX.Y.Z
master VERSION?      git show origin/master:cuppa/VERSION
tag peeled commit?   git rev-parse vX.Y.Z^{}   # local may lie until fetch
finish PR merged?    must be on master before publish
then:                delete bad tag → publish from master (preferred)
                     or retag the finish merge SHA and push
```

---

## 9. Pointers inside this repository (public)

| Artefact | Role |
|----------|------|
| [`AGENTS.md`](../../AGENTS.md) | Agent/human operating manual |
| [`ROADMAP.md`](../../ROADMAP.md) | Canonical planned vs today |
| [`CHANGELOG.md`](../../CHANGELOG.md) | Release-facing history |
| [`release.txt`](../../release.txt) | One-page release checklist |
| [`.github/workflows/release.yml`](../../.github/workflows/release.yml) | prepare / publish / tag-push |
| [`scripts/check_release.py`](../../scripts/check_release.py) | Gate: no `.dev`, dated notes, tag match |
| [`scripts/finish_release.py`](../../scripts/finish_release.py) / [`start_release.py`](../../scripts/start_release.py) | Close / open cycles |
| [`docs/.../contributing.adoc`](../../docs/modules/ROOT/pages/contributing.adoc) | Human Contributing hub (diagrams on children) |
| [`design/README.md`](../README.md) | Index of plans / process / archive |
| [`design/plans/removal-options.md`](../plans/removal-options.md) | Example of a living multi-PR plan |
| [`scripts/github_helpers.py`](../../scripts/github_helpers.py) | PR/CI agent helpers |
| [`scripts/github_api.py`](../../scripts/github_api.py) | Sealed credential transport |
| Antora `docs/` | Published truth for users |
| Integration pages under `docs/.../integration/` | Executable scenarios as docs |
| [`scripts/generate_doc_samples.py`](../../scripts/generate_doc_samples.py) | Regenerates listing/remove sample trees and JSON for Antora partials |

Private name map (gitignored, this machine only): `design/INTERNAL_PROJECTS.local.md`.

---

## 10. How to extend this file

Follow the rules in `AGENTS.md` § Working documents (process journey). In short:

1. **Append by default** — prefer new bullets under §5 / §6, a timeline row, or a short §8 case
   study. Do not rewrite the whole arc unless the maintainer asks.
2. If the lesson became an `AGENTS.md` or Contributing rule, link it; do not duplicate checklists.
3. Keep recovery checklists accurate when process incidents happen.
4. Never copy private project names out of `INTERNAL_PROJECTS.local.md`.
5. Bump **Updated:** when you change substance.
