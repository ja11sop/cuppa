# Plan: agent-readable Markdown docs (`llms.txt` + page MD + `llms-full.txt`)

- **Status:** proposal
- **Related:** [`ROADMAP.md`](../../ROADMAP.md) — Documentation tooling (`doc-llms-txt`); [`docs-site-release-default.md`](docs-site-release-default.md); Antora build [`docs/playbook.yml`](../../docs/playbook.yml) / [`.github/workflows/docs.yml`](../../.github/workflows/docs.yml); product docs under [`docs/`](../../docs/); coding-agent notes [`AGENTS.md`](../../AGENTS.md) (different audience)
- **Updated:** 2026-08-30
- **Impact:** none — publish artefacts beside the Antora site (no Cuppa CLI behaviour)

## Take (recommendation)

The Gemini sketch is **directionally right** for Cuppa:

1. **Pandoc over Turndown** for HTML→Markdown — Cuppa docs lean on tables, admonitions, nested
   lists, and code blocks; Pandoc’s HTML reader → GFM is the more reliable converter. Turndown is
   fine for marketing HTML; it is a weaker fit here.
2. **Strip Chrome first** — convert only the Antora article body (typically
   `article.doc` / main content), never the full page with nav/footer. Boilerplate burns agent
   context and confuses retrieval.
3. **Three layers** match how agents actually work:
   - `llms.txt` — curated index (links + one-line blurbs)
   - per-topic `.md` (or paths that serve Markdown) — precision fetch
   - `llms-full.txt` — one-shot ingestion (hyphenated name; Markdown inside, `.txt` for MIME /
     crawler convention)

**Prefer generating from the Antora *HTML output*** (post-`antora generate`), not from raw
AsciiDoc sources. Sources are modular (includes, attributes, xrefs, Antora page IDs); the HTML
is already the resolved “what we published.” Extract → Pandoc keeps that contract.

**Couple to release-default docs.** Once
[`docs-site-release-default.md`](docs-site-release-default.md) lands, the agent corpus should
default to the **same version visitors see** (latest release). A `next` / master corpus can exist
but must not be the only or silent default — otherwise agents learn unreleased Methods APIs.

**Do not confuse with `AGENTS.md`.** Repo `AGENTS.md` teaches agents *working on Cuppa’s
codebase* (CI, private-name rules, commit ritual). `llms.txt` teaches agents *using Cuppa as a
product* (CLI, methods, toolchains). Keep both; cross-link lightly from Contributing.

## Problem

Public docs are HTML-oriented. Coding agents and IDE assistants either scrape noisy HTML or miss
the site entirely. There is no first-class, MIME-safe Markdown map of the Cuppa documentation
surface for machine readers.

## Goals

1. Publish **`llms.txt`** at a stable site URL (site root under Pages, e.g.
   `https://ja11sop.github.io/cuppa/llms.txt`) following [llmstxt.org](https://llmstxt.org)-style
   structure (H1, summary blockquote, H2 sections with curated link lists).
2. Publish **per-page Markdown** derived from Antora article HTML (clean GFM).
3. Publish **`llms-full.txt`** concatenating the curated (or full) page set for single-request
   ingestion.
4. Generate all of the above in the **docs CI / release** pipeline so the files cannot drift from
   the HTML site by hand maintenance.
5. Keep **token budget** honest: exclude or demote low-value pages (e.g. exhaustive integration-test
   scenario dumps) from `llms-full.txt` and possibly from the curated index.

## Non-goals

- Replacing Antora HTML for humans.
- Feeding private consumer project names into agent docs (same public-docs rules as always).
- Guaranteeing every crawler will fetch `llms.txt` (publication ≠ discovery; still worth doing).
- Perfect round-trip of Mermaid / interactive UI chrome into Markdown (diagrams → fenced code or
  short “see HTML docs” notes is enough).

## Pipeline (proposed)

```text
antora generate
    → _docs_build/site/**/*.html
    → extract article body (cheerio / htmlq / similar)
    → pandoc -f html -t gfm
    → _docs_build/site/…/*.md  (mirror or parallel tree)
    → assemble llms.txt (curated index)
    → assemble llms-full.txt (concat)
deploy Pages artefact (HTML + MD + txt)
```

| Step | Tooling sketch | Notes |
|------|----------------|-------|
| Isolate | Node `cheerio` (fits existing `docs/` npm world) or `htmlq` | Selector: Antora `article.doc` (verify against current UI) |
| Convert | Pandoc (`extra/setup-pandoc` in Actions; document local install) | `-t gfm`; fail the job on converter errors for listed pages |
| Index | Small script over `nav.adoc` order or site manifest | Curate sections: Overview, Methods, Toolchains, Dependencies, CLI, … |
| Full file | Concat in nav / index order with clear `---` / H2 separators and source URLs | Cap size or split later if needed |

Individual page URLs: prefer stable paths such as
`…/cuppa/cuppa/methods/build.html` ↔ `…/cuppa/agent/methods/build.md` **or** sibling `.md` next to
HTML. Settle path scheme in the first spike so `llms.txt` links stay stable across UI changes.

## Content policy

| Include in curated `llms.txt` / full | Demote or omit from full |
|-------------------------------------|---------------------------|
| Overview, Concepts, Quickstart, CLI hubs | Per-scenario `integration/test-*.adoc` pages (link the hub only) |
| Methods hub + topic children | Raw design/`ROADMAP` (not on Antora site today — keep it that way) |
| Toolchains, Dependencies, Modules, Profiles hubs | Generated coverage HTML samples if any appear under site |
| Contributing / versioning (short) | Duplicate changelog dumps |

Always include absolute `https://ja11sop.github.io/cuppa/…` links in the index so agents can cite
the human HTML page too.

## Work slices

| ID | Deliverable | Depends on | Notes |
|----|-------------|------------|-------|
| `llms-spike` | Local script: one Methods page HTML → GFM; judge tables/admonitions | Antora build | Choose cheerio vs htmlq; lock selector |
| `llms-pipeline` | npm script or Python helper wired after `antora generate` | spike | Pandoc in CI |
| `llms-index` | Generate `llms.txt` from nav / allowlist | pipeline | Spec-shaped H1 / quote / H2 lists |
| `llms-full` | Generate `llms-full.txt` with size check / omit list | index | Fail or warn over budget |
| `llms-ci` | Docs workflow publishes MD + txt beside HTML | pipeline | |
| `llms-release` | Align default corpus with release-default site version | [`docs-site-release-default.md`](docs-site-release-default.md) | After or with that plan |
| `llms-docs` | Short Contributing note: where agents should read; contrast `AGENTS.md` | ci | |

## Acceptance criteria

1. After docs build, `llms.txt`, `llms-full.txt`, and a representative set of topic `.md` files exist
   in the deployed artefact.
2. `llms.txt` is valid curated Markdown (H1 + summary + link sections) and points at **Markdown**
   detail URLs (and optionally HTML).
3. Converted Methods / Toolchains sample pages retain tables and fenced code without nav chrome.
4. CI does not require hand-editing the generated files.
5. Docs note the distinction between product `llms.txt` and repo `AGENTS.md`.

## Risks

| Risk | Mitigation |
|------|------------|
| `llms-full.txt` too large for context windows | Allowlist; omit integration leaves; optional size gate |
| Antora UI class rename breaks extractor | One selector helper + integration assert in docs build |
| Stale full file if HTML deploy skipped | Generate in the same job as `antora generate` |
| Agents prefer HTML anyway | Still ship MD; HTML remains canonical for humans |

## Refusal rules

| Request | Response |
|---------|----------|
| Commit generated MD into `docs/modules/` by hand | Refuse — generate from build output |
| Turndown-only because “already on npm” | Refuse as primary converter once tables/admonitions regress |
| Put private project maps into `llms-full.txt` | Refuse |
| Replace `AGENTS.md` with site `llms.txt` | Refuse — different audiences |

## Timing

| Phase | When |
|-------|------|
| Spike + pipeline | After Methods topic **baseline** is mergeable (same docs cycle is fine) |
| Release-aligned default | With or right after [`docs-site-release-default.md`](docs-site-release-default.md) |

## Candidacy

| Factor | Assessment |
|--------|------------|
| User value | High for agent / IDE users of Cuppa |
| Risk | Low–medium (CI tooling) |
| Size | Small–medium |
| Release impact | `none` |
