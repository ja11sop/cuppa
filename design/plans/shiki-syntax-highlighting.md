# Plan: Shiki syntax highlighting for Antora

- **Status:** proposal
- **Related:** [`ROADMAP.md`](../../ROADMAP.md) — Documentation tooling (`doc-shiki`); companion [`colourised-doc-samples.md`](colourised-doc-samples.md); site chrome [`antora-ui-bundle.md`](antora-ui-bundle.md)
- **Updated:** 2026-08-25
- **Impact:** none — docs build tooling only (unless a highlighter swap breaks the docs CI build)

**Release timing:** deferred past the open **1.9.0** cycle. See [§7 Adoption decision](#7-adoption-decision-and-release-timing).

Source listings on the Antora site are still highlighted **in the browser** by the default UI's
highlight.js. Shiki can highlight at **site build time**, so pages ship already-coloured HTML,
line numbers become a first-class option, and a special `ansi` language can colour real terminal
captures. That last point overlaps [`colourised-doc-samples.md`](colourised-doc-samples.md); this
plan keeps the two jobs distinct.

---

## 1. Feasibility of the scratchpad note

The note is directionally right: prefer current Shiki, treat
[lask79/antora-shiki-extension](https://github.com/lask79/antora-shiki-extension) as a **recipe
and grammar source**, not as the runtime we pin forever.

| Claim | Assessment |
|-------|------------|
| Use latest Shiki | **Do this.** The npm package `antora-shiki-extension` documents support for **Shiki 0.14.1** only. Current Shiki is a different API (`codeToHtml`, dual themes, transformers). Depending on that package would freeze highlighting quality. |
| Pull grammar / CSS from the extension | **Partially.** Reuse its **AsciiDoc TextMate grammar** (Shiki still does not bundle AsciiDoc) and study how it hooks Asciidoctor's `source-highlighter`. Do **not** copy its Shiki 0.x CSS as the long-term theme; map tokens onto Cuppa palettes instead. |
| Combine into our own workflow | **Yes.** Antora 3 already loads Node extensions from `docs/playbook.yml` (Lunr, Mermaid). A small **local** extension under `docs/` that `require`s current `shiki` is the same pattern. |
| Line numbers | **Yes**, via Shiki transformers or the extension's `use_line_numbers` idea, then style with supplemental CSS so numbers do not fight listing chrome. |
| Fewer reader dependencies | **Yes, if highlight.js is actually turned off.** Build-time spans mean no highlighter JS for listings. The default UI still *ships* highlight.js unless the overlay stops loading it (`head-scripts` / `footer-scripts` or a supplemental partial). That disable step is part of the work, not automatic. |
| Coloured ANSI blocks for doc examples | **Feasible as a renderer, not as the canonical Cuppa-report path.** Shiki's special language `ansi` turns SGR sequences into spans. That is a good **preview / compiler-log** tool. It does **not** replace semantic `cuppa-*` HTML for `--list-builds` and judgement trees — see [§3](#3-relationship-to-colourised-doc-samples). |

Risks to plan around:

- **Build-time cost.** Shiki loads grammars; restrict the language allowlist (`cpp`, `python`,
  `bash`/`console`/`shell`, `diff`, `json`, `yaml`, `asciidoc`, `ansi`, `text`).
- **Theme vs palettes.** Stock Shiki themes (nord, github-light) will clash with cup-of-tea unless
  we either (a) dual-theme + `prefers-color-scheme` like the palettes, or (b) emit token classes
  and colour them in `cuppa.css`. Prefer (b) or a thin dual-theme pair that we restyle, not a
  dark-nord island on a light page.
- **Listing HTML shape.** Today's overlay targets `.doc pre.highlight > code` (highlight.js).
  Shiki's markup differs (`pre.shiki`, `span` tokens). Phase 1 must restyle those selectors or
  listings regress.
- **Passthrough HTML.** Colourised report fragments stay `++++` includes; Shiki must not try to
  re-highlight them.

---

## 2. Goals and non-goals

**Goals**

- Highlight `[source,…]` listings at Antora generate time with current Shiki.
- Keep highlight quality independent of the published `antora-shiki-extension` Shiki pin.
- Style tokens and optional line numbers through supplemental CSS so they follow the selected
  Cuppa palette (light and `prefers-color-scheme: dark`).
- Offer `[source,ansi]` for captures that already contain SGR, as an authoring/preview aid.
- Stop shipping a client highlighter for those listings once Shiki is on.

**Non-goals**

- Replacing [`colourised-doc-samples.md`](colourised-doc-samples.md) `HtmlColouriser` for Cuppa
  *owned* report samples.
- Colourising arbitrary tool output Cuppa does not emit (except when an author pastes ANSI into
  an `ansi` listing).
- Kroki / network highlighters at doc build.
- Pixel-perfect VS Code / terminal screenshots.

---

## 3. Relationship to colourised-doc-samples

Two different meanings of “colour in the docs”:

| | Shiki (this plan) | Colourised samples (companion) |
|--|-------------------|--------------------------------|
| Input | Source text + a **language** (`cpp`, `python`, `ansi`, …) | Cuppa report code calling `as_error` / `as_info` / … |
| Colour means | Syntax tokens (keyword, string, comment) or **raw SGR** | **Semantic** severity / emphasis Cuppa already defined |
| Stability | Grammar + theme; same listing always looks the same | Meaning vocabulary; independent of `COLORFGBG` / DIM |
| First recipes | Quickstart Python, CLI `sh`, C++ examples | `list-builds`, dry-run remove, `list-develop` |
| Failure if mixed | Using `ansi` for `--list-builds` reintroduces machine palette drift (`doc-ansi-only` is already out of scope on the ROADMAP) | Using `HtmlColouriser` on a `sconscript` does not highlight Python |

**How they compose**

1. **Ship Shiki for languages first.** Reader-visible win on every `[source,cpp]` / `[source,python]`
   page; does not wait on an injectable colouriser in `cuppa.colourise`.
2. **Keep `scripts.generate_doc_samples` stripping ANSI** for committed `[source,text]` samples
   until Phase C of the colourised-samples plan writes `cuppa-output` HTML.
3. **Reuse Shiki `ansi` as the optional ANSI preview** described in colourised-samples §3.5
   (`--format=ansi-html`), instead of adding a second `ansi2html` dependency — **preview only**,
   pinned `TERM` / `CUPPA_CONSOLE_BACKGROUND`, not the committed canonical fragment.
4. **Shared CSS contract.** Palettes already reserve room for `.cuppa-error` sample classes
   (`antora-ui-bundle` catalogue). Shiki token colours should live beside those, not as a third
   unrelated palette.

```text
  [source,python] / [source,cpp]     → Shiki (this plan)
  [source,ansi]  (preview / rare)    → Shiki ansi language
  Cuppa list/remove/develop reports  → HtmlColouriser + cuppa-* (companion plan)
```

---

## 4. Approach (settled for the first spike)

| Id | Option | Use this? |
|----|--------|-----------|
| `use-npm-extension-as-is` | `require: antora-shiki-extension` + Shiki 0.14 | **No** — version pin |
| `local-extension` | `docs/` Antora extension wrapping current `shiki` | **Yes** |
| `borrow-asciidoc-grammar` | Grammar (and hook sketch) from the extension / asciidoctor-vscode | **Yes** |
| `keep-highlightjs` | Dual highlighters | **No** once Shiki is green — extra JS and conflicting CSS |
| `ansi-for-cuppa-reports` | Commit Shiki-ansi HTML as the docs sample | **No** — same reason as ROADMAP `doc-ansi-only` |

Playbook sketch (illustrative):

```yaml
antora:
  extensions:
  - require: '@antora/lunr-extension'
  - require: '@sntke/antora-mermaid-extension'
  - require: './extensions/shiki-highlight.js'
    languages: [cpp, python, bash, console, diff, json, yaml, asciidoc, ansi, text]
asciidoc:
  attributes:
    source-highlighter: shiki
```

Exact file name and option keys land in the first implementation PR.

---

## 5. Phased delivery

| Phase | Delivers | Notes |
|-------|----------|-------|
| A | Spike: local extension + current Shiki on a branch; 2–3 languages; compare listing HTML to today's `.highlight` CSS | Fail the spike if listings lose chrome or dark-mode contrast |
| B | Language allowlist covering real docs (`cpp`, `python`, `sh`/`bash`/`console`, `diff`, `json`, `yaml`, AsciiDoc grammar, `text`); disable highlight.js in supplemental UI | Reader-visible |
| C | Line numbers opt-in (page attribute or listing role); restyle numbers in `cuppa.css` | Do not force numbers on one-liners |
| D | Dual theme or token CSS aligned with palettes | After A proves markup |
| E | `[source,ansi]` documented for authors; optional hook from `scripts.sample_output --format=ansi-html` | Preview path for colourised-samples §3.5; still not canonical report HTML |

**Not in 1.9.0.** Land [`antora-ui-bundle.md`](antora-ui-bundle.md) (`doc-antora-ui`) first. Start Phase A only after listing chrome in `cuppa.css` is stable and a maintainer can compare Shiki output on real tutorial pages — not as part of the current UI release PR.

---

## 6. Testing and docs impact

- Unit or a small Node script: given a fixture listing, Shiki emit contains expected token
  classes / no raw `<` in text.
- `cd docs && npm run build` stays the contributor command; add `shiki` to `docs/package.json`.
- One integration-style assertion: a built page with `[source,python]` contains Shiki markup and
  does not load highlight.js for that block.
- Contributor note only after Phase B: which `source` languages are registered; use `text` when
  unsure; never put private paths in `ansi` captures.

Release impact: **none** for the facility; **patch** only if an open cycle treats the visual
change as a doc fix.

---

## 7. Adoption decision and release timing

This section records the maintainer decision on **whether migrating from highlight.js is worth
the cost**, so the spike is not treated as mandatory follow-on to the Antora UI pass.

### Verdict

**Worth doing eventually, but not urgent — and not instead of colourised report samples.**

highlight.js is **good enough today**. Listings render, the supplemental overlay already quiets
block chrome (`--cuppa-code-size*`, borders, surfaces), and readers are not blocked. The default
UI loads a client highlighter, but that is a modest cost on a mostly textual docs site. The open
**1.9.0** cycle should **not** include Shiki work; finish `doc-antora-ui` and treat Shiki as a
later, deliberate docs-quality slice (`doc-shiki`).

### What Shiki would pay for (when we do pick it up)

| Benefit | Why it matters |
|---------|----------------|
| Build-time, stable HTML | Same listing in CI, local preview, and GitHub Pages; no wait for client JS |
| Line numbers | First-class on longer tutorial / CLI snippets without hand-maintaining them |
| Token colours aligned with palettes | The UI pass intentionally leaves highlight.js token colours alone; Shiki (or class-based tokens + `cuppa.css`) is how listing syntax colours match cup-of-tea / dark mode |
| Pinned ANSI preview | Convenient for compiler or log captures via `[source,ansi]` — preview only; see [§3](#3-relationship-to-colourised-doc-samples) |

### What Shiki does not solve

Cuppa **report semantics** (`as_error`, `as_info`, judgement trees). That remains
[`colourised-doc-samples.md`](colourised-doc-samples.md) (`HtmlColouriser` + `cuppa-*` classes).
Shiki's `ansi` language is not a substitute for committed `--list-builds` samples (ROADMAP
`doc-ansi-only`).

### Costs and risks (why defer is reasonable)

- The published `antora-shiki-extension` pins old Shiki — we commit to a **small local extension**,
  not a one-line playbook change.
- Listing markup changes (`.highlight` → `.shiki`); overlay CSS and both light/dark palettes need
  a retarget pass.
- highlight.js must be **explicitly disabled** in supplemental UI or we run two highlighters.
- Antora build time grows slightly (grammar load); mitigated by a tight language allowlist.

### Recommended sequencing

| When | Action |
|------|--------|
| **1.9.0 (now)** | Ship Antora UI (`doc-antora-ui`); keep highlight.js; optional colourised **report** samples (`doc-output-samples`) if that slice is prioritised |
| **After 1.9.0** | Phase A spike only: local Shiki on 2–3 real pages (e.g. quickstart, a CLI page, one C++ snippet); compare readability and CSS effort |
| **If spike wins clearly** | Phase B–D: migrate listings, disable highlight.js, align tokens with palettes |
| **If spike is marginal** | Stay on highlight.js until line numbers or palette-aligned code blocks become a reader-facing goal |

**Spike success bar:** listings look clearly better on the pages people learn from (especially
`cpp` / long `python` blocks), listing chrome and dark-mode contrast hold, and the extension +
CSS maintenance is acceptable. “Slightly nicer but a week of plumbing” → **defer**.

---

## 8. Open questions

1. **Class-based tokens vs dual Shiki themes** — classes + palette CSS match Cuppa's overlay
   model; dual themes are faster to spike.
2. **Callouts / conums** — Asciidoctor callout numbers in listings must survive Shiki; verify in
   Phase A.
3. **Windows docs CI** — Shiki is Node; docs job is already Node. Confirm file encodings on
   `ansi` fixtures.
4. **GitHub issue** — File when Phase A starts; quote this plan's goals table, not “prettier code
   blocks”.
