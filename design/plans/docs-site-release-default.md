# Plan: default published docs to the latest release (not master)

- **Status:** in progress
- **Related:** [`ROADMAP.md`](../../ROADMAP.md) — Documentation tooling (`doc-site-release-default`); [`docs/playbook.yml`](../../docs/playbook.yml); [`.github/workflows/docs.yml`](../../.github/workflows/docs.yml); [`docs/antora.yml`](../../docs/antora.yml); Methods baseline [`methods-pages-split.md`](methods-pages-split.md) / [#234](https://github.com/ja11sop/cuppa/pull/234); agent Markdown [`docs-llms-txt.md`](docs-llms-txt.md) (**same PR**); UI companion [`antora-ui-bundle.md`](antora-ui-bundle.md)
- **Updated:** 2026-09-03
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

1. **Default landing** = docs that match the **latest GitHub/PyPI release** (not `master`), via a
   stable **`/latest/`** URL segment so bookmarks and agent links always hit current stable.
2. Optional **prerelease / next** docs (from `master`) reachable via the Antora version selector —
   never the silent default.
3. Local `cd docs && npm run build` remains useful for contributors on the current checkout.
4. Playbook stays honest: no pretending `version: ~` is “the release.”

## Non-goals

- Hosting every historical minor forever on day one (start with **latest release + optional next**).
- Changing Cuppa’s SemVer / `start_release` / `finish_release` ritual beyond what docs publish needs.
- Blocking docs PRs from merging to `master` — only changing **what the public default shows**.
- Patch-exact URL trees (`/1.9.0/`, `/1.9.1/`, …) as the primary scheme (too much picker churn).

## Options (background)

| Approach | Idea | Pros | Cons |
|----------|------|------|------|
| **A. Tag-sourced Antora versions** | Playbook lists `v*` tags (and `HEAD` as `next`); real `version:` / `display_version` | Standard Antora; version picker; `latest` segment | Tag must include `docs/`; release workflow refreshes site |
| **B. Release-only deploy** | One unversioned site; Pages only from tag publish | Small playbook change | No `next`; master invisible until release |
| **C. Two deploys** | Separate roots for stable vs master | Clear URLs | More CI; hand-rolled default |

**Chosen:** **A**, with Antora `latest_version_segment` so the preferred stable version is served under
`/cuppa/latest/…`.

## Settled decisions (2026-08-31)

| Decision | Choice |
|----------|--------|
| When to do this | After Methods baseline (#234); implement with [`docs-llms-txt.md`](docs-llms-txt.md) in **one PR** |
| Site model | **A** — multi-version Antora from release tags + optional `next` |
| Stable `version` key | **Minor line** from the latest release tag — e.g. tag `v1.9.0` → `version: '1.9'` (YAML-quoted) |
| Stable `display_version` | Full SemVer of that release — e.g. `1.9.0` (picker shows the exact release; URLs stay on the minor / `latest`) |
| Default URL segment | Playbook **`latest_version_segment: latest`** so visitors and `llms.txt` use `/cuppa/latest/…` and always resolve to the newest **non-prerelease** component version |
| Master / tip | Component version named **`next`**, with **`prerelease: true`**, sourced from `master` (or `HEAD` in the playbook). Must not win “latest stable.” |
| History depth (v1) | Latest stable minor + `next` only; older minors optional later |
| Coupling | `finish_release` / publish refreshes the stable docs; same pipeline emits agent Markdown ([`docs-llms-txt.md`](docs-llms-txt.md)) |
| Refuse | Silent `version: ~` as the only public site; patch-only URL scheme without a `latest` alias |

### Naming sketch

```text
Release tag v1.9.0
  → antora version:     '1.9'
  → display_version:    '1.9.0'
  → public default URL: …/cuppa/latest/…   (symbolic; tracks newest stable)
  → also available as:  …/cuppa/1.9/…      (actual version segment)

master tip
  → version:            next
  → prerelease:         true
  → URL:                …/cuppa/next/…
```

When `1.9.1` ships, bump `display_version` (and rebuild from that tag); keep `version: '1.9'` so
patch docs replace the same minor tree. When `2.0.0` ships, add `version: '2.0'` and Antora’s
latest routing moves `latest` to that line.

## Work slices

| ID | Deliverable | Notes | Status |
|----|-------------|-------|--------|
| `doc-site-model` | Version naming + `latest` segment (table above) | Settled 2026-08-31 | **Done** |
| `doc-site-playbook` | Multi-version playbook; drop silent `version: ~` as public default | Tags + `next`; `latest_version_segment`; prepare script | **Done** |
| `doc-site-ci` | Adjust `docs.yml` and/or `release.yml` so stable site updates on publish | `workflow_call` from **publish** after the tag exists (`GITHUB_TOKEN` `release: published` does not start other workflows); also `workflow_dispatch` | **Done** |
| `doc-site-local` | Contributor notes: preview current branch vs build release set | Contributing / AGENTS | **Done** |
| `doc-site-verify` | After first release with the model: homepage / `/latest/` shows released text | Manual check after merge/deploy | Open |

## Acceptance criteria

1. Visiting the site root (or `/cuppa/latest/…`) without picking a version shows docs for the
   **latest release**.
2. Unreleased master-only pages are under **`next`** (prerelease), not the default view.
3. Cutting a release updates (or can update) the stable docs without a special manual Pages hack.
4. Local Antora build on a feature branch still works for PR review.
5. Bookmarks and agent indexes can rely on a stable **`…/latest/…`** prefix.

## Refusal rules

| Request | Response |
|---------|----------|
| Keep deploying every master docs push as the only public site | Refuse once this workstream starts — that is the bug |
| Delete all ability to read master docs | Not required; demote to `next`, do not necessarily erase |
| Versioned links that rot every patch | Prefer minor `version` + `latest` segment, not hand-maintained `/1.9.0/` prose URLs in CHANGELOG |
| Patch-exact trees as the only public URLs (no `latest`) | Refuse — users and agents need a durable default |

## Candidacy

| Factor | Assessment |
|--------|------------|
| User value | High — docs match what `pip install cuppa` gets |
| Risk | Medium (CI/publish wiring); low product-code risk |
| Size | Medium |
| Release impact | `none` |

Ship in one PR with [`docs-llms-txt.md`](docs-llms-txt.md) so the agent corpus defaults to the same
`/latest/` surface as human visitors.
