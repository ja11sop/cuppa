# Plan: default published docs to the latest release (not master)

- **Status:** proposal
- **Related:** [`ROADMAP.md`](../../ROADMAP.md) — Documentation tooling (`doc-site-release-default`); [`docs/playbook.yml`](../../docs/playbook.yml); [`.github/workflows/docs.yml`](../../.github/workflows/docs.yml); [`docs/antora.yml`](../../docs/antora.yml); Methods baseline [`methods-pages-split.md`](methods-pages-split.md); agent Markdown [`docs-llms-txt.md`](docs-llms-txt.md); UI companion [`antora-ui-bundle.md`](antora-ui-bundle.md)
- **Updated:** 2026-08-30
- **Impact:** none — site publish / Antora versioning only (no Cuppa CLI behaviour)

## Problem

The public site ([ja11sop.github.io/cuppa](https://ja11sop.github.io/cuppa)) is built from **`master` tip** whenever `docs/**` changes:

- [`docs/playbook.yml`](../../docs/playbook.yml) uses `branches: HEAD`
- [`docs/antora.yml`](../../docs/antora.yml) sets `version: ~` (floating / unversioned component)
- [`.github/workflows/docs.yml`](../../.github/workflows/docs.yml) deploys on push to `master`/`main`

So readers browsing the “official” docs often see **unreleased** behaviour from an open
`CHANGELOG` / `VERSION` `.dev` cycle (for example Methods pages mid-split, or flags that only
exist on master). That fights the release ritual: PyPI/GitHub Releases are versioned, but the
docs homepage is not.

After the Methods pages baseline lands, the site should **default to documentation for the
latest released Cuppa**, with master / prerelease docs available explicitly if we keep them.

## Goals

1. **Default landing** = docs that match the **latest GitHub/PyPI release** (not `master`).
2. Optional **prerelease / next** docs (from `master` or a `docs-next` branch) reachable via an
   Antora version selector or a clearly labelled URL — never the silent default.
3. Local `cd docs && npm run build` remains useful for contributors on the current checkout.
4. Playbook stays honest: no pretending `version: ~` is “the release.”

## Non-goals

- Hosting every historical minor forever on day one (start with **latest release + optional next**).
- Changing Cuppa’s SemVer / `start_release` / `finish_release` ritual beyond what docs publish needs.
- Blocking docs PRs from merging to `master` — only changing **what the public default shows**.

## Options (settle before implementation)

| Approach | Idea | Pros | Cons |
|----------|------|------|------|
| **A. Tag-sourced Antora versions** | Playbook lists `v*` tags (and maybe `HEAD` as `next`); `antora.yml` uses real `version:` / `display_version` | Standard Antora; version picker | Tag must include `docs/` content; release workflow must build or refresh site |
| **B. Release-only deploy** | Keep one unversioned site but trigger Pages **only** from `release` / tag publish, not every master docs push | Smallest playbook change | Master docs invisible until release; harder to preview “what will ship” |
| **C. Two deploys** | `…/cuppa/` = last release artefact; `…/cuppa/next/` = master | Clear URLs | More CI; need redirect/default |

**Preference to validate:** **A** (or A+C hybrid) so Antora’s version selector is the product UI,
with **latest stable as `site.start_page` / preferred version**. Keep a `next` / `master` version
for maintainers and early adopters.

## Settled intent (2026-08-30)

| Decision | Choice |
|----------|--------|
| When to do this | **After** Methods split has a baseline across topic pages and #234 (or successor) merges — avoid teaching a half-migrated Methods tree as “the release” |
| Default for visitors | Latest **released** Cuppa docs |
| Master | Available as non-default (`next` / prerelease), or not published until we need it |
| Coupling | Coordinate with `finish_release` / publish workflow so a release refreshes the stable docs |

## Work slices (later)

| ID | Deliverable | Notes |
|----|-------------|-------|
| `doc-site-model` | Choose A/B/C; document version naming (`1.9.0` vs `1.9` vs `latest`) | Short settled table |
| `doc-site-playbook` | Multi-version or release-pinned playbook; drop silent `version: ~` as public default | |
| `doc-site-ci` | Adjust `docs.yml` and/or `release.yml` so stable site updates on publish | |
| `doc-site-local` | Contributor notes: preview current branch vs build release set | Contributing / AGENTS |
| `doc-site-verify` | After first release with the model: homepage shows released Methods/toolchains text | Manual check |

## Acceptance criteria

1. Visiting the site root without picking a version shows docs for the **latest release**.
2. Unreleased master-only pages are **not** the default view (either absent or under an explicit
   prerelease version).
3. Cutting a release updates (or can update) the stable docs without a special manual Pages hack.
4. Local Antora build on a feature branch still works for PR review.

## Refusal rules

| Request | Response |
|---------|----------|
| Keep deploying every master docs push as the only public site | Refuse once this workstream starts — that is the bug |
| Delete all ability to read master docs | Not required; demote, do not necessarily erase |
| Versioned links that rot every patch | Prefer Antora component versions + `latest` alias, not hand-maintained `/1.9.0/` prose URLs in CHANGELOG |

## Candidacy

| Factor | Assessment |
|--------|------------|
| User value | High — docs match what `pip install cuppa` gets |
| Risk | Medium (CI/publish wiring); low product-code risk |
| Size | Medium |
| Release impact | `none` |

Pairs well with finishing [`methods-pages-split.md`](methods-pages-split.md) and a docs-visible
1.9.0 (or following) release so the first “stable default” snapshot includes the Methods hub.
