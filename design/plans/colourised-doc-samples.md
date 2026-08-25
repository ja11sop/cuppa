# Plan: colourised sample output for documentation and preview

- **Status:** proposal
- **Related:** [`ROADMAP.md`](../../ROADMAP.md) — Documentation tooling (`doc-output-samples`); follows build-report work in [`removal-options.md`](removal-options.md) Phase 2; syntax highlighting [`shiki-syntax-highlighting.md`](shiki-syntax-highlighting.md)
- **Updated:** 2026-08-25

Cuppa already produces rich, colour-coded reports (`--list-builds`, `--list-develop`,
`--remove-builds`, coverage summaries, and more). The Antora docs currently show those reports as
plain `[source,text]` blocks and describe colour in prose. That works, but readers never see the
hierarchy that colour and emphasis are meant to convey.

This plan proposes a **general facility** to capture cuppa report output and render it as stable,
colourised HTML suitable for:

1. Inclusion in Antora pages (annotated examples next to commands).
2. Local **preview** of what a report looks like without reading a terminal transcript.
3. Optional CI checks that sample pages still build.

It is deliberately separate from the storage/removal phases: those land reports first; this makes
the reports teachable in the docs.

---

## 1. Goals and non-goals

**Goals**

- Turn real cuppa report output into something the documentation site can show in colour.
- Prefer **semantic** markup driven by cuppa's existing meaning vocabulary (`error`, `warning`,
  `info`, `notice`, `emphasised`, `subdued`, labels, …) over scraping terminal-dependent ANSI.
- Provide a small capture/preview CLI so authors can regenerate samples without hand-editing HTML.
- Keep samples free of private project names and absolute home paths (same rule as the rest of
  this repository).
- Style samples so they remain readable on the Antora UI's light page background.

**Non-goals**

- Replacing the live terminal colouriser or changing default build log colours.
- Pixel-perfect terminal screenshots or animated demos.
- Colourising arbitrary compiler/tool stdout that cuppa does not own.
- Requiring a network fetch (Kroki, etc.) at Antora build time — same constraint as Mermaid today
  (client-side or checked-in artefacts only).

---

## 2. Why not only “capture ANSI and convert”?

Cuppa already depends on **colorama** and enables colour when not under `--raw-output`. Capturing
ANSI and feeding it to `ansi2html` (or similar) is attractive for “what the terminal showed”, but:

| Issue | Effect on docs |
|-------|----------------|
| `CUPPA_CONSOLE_BACKGROUND` / `COLORFGBG` | Subdued text uses DIM vs grey-256; samples drift by machine |
| Nested emphasise + colour | Reset sequences are easy to mis-parse |
| Docs site is light-themed | Raw dark-terminal palettes can be illegible |
| `--raw-output` / pipes | Easy to accidentally capture uncoloured text in CI |

ANSI conversion remains useful as an **optional preview mode** (“show me exactly this run”). The
**canonical docs path** should be semantic HTML from the same `as_*` meanings the terminal uses.

Do not fold that canonical path into Shiki's `ansi` language (see
[`shiki-syntax-highlighting.md`](shiki-syntax-highlighting.md)). Shiki is the right highlighter for
`[source,cpp]` / `[source,python]` and a convenient **renderer** for pinned ANSI previews; it does
not know Cuppa's `as_error` / `as_info` vocabulary, and unpinned SGR still drifts with
`CUPPA_CONSOLE_BACKGROUND` (ROADMAP `doc-ansi-only`).

---

## 3. Design sketch

```text
  report code
      │
      ├─ Colouriser (ANSI)     → terminal / CI logs
      │
      └─ HtmlColouriser (new)  → spans with cuppa-* classes
                │
                v
        capture runner (script)
                │
                ├─ stdout HTML fragment
                ├─ optional full preview page
                └─ checked-in sample under docs/…/samples/  (or generated at doc build)
                │
                v
        Antora page include + supplemental-ui CSS
```

### 3.1 HtmlColouriser

Add a parallel implementation (name illustrative) that implements the same operations the report
code already calls through `cuppa.colourise` helpers:

| Helper today | Docs class (illustrative) |
|--------------|---------------------------|
| `as_error` / `as_error_label` | `cuppa-error` / `cuppa-error-label` |
| `as_warning` / `as_warning_label` | `cuppa-warning` / `cuppa-warning-label` |
| `as_info` / `as_info_label` | `cuppa-info` / `cuppa-info-label` |
| `as_notice` | `cuppa-notice` |
| `as_emphasised` | `cuppa-emphasised` (bold / stronger weight) |
| `as_subdued` | `cuppa-subdued` (grey, not DIM-on-white) |

Implementation options (pick one in the first PR):

1. **Injectable colouriser** — `colourise` gains `set_colouriser(...)` / context manager used only
   by the capture runner; production builds keep today's ANSI colouriser.
2. **Dual emit** — helpers append to a side channel (fragile; avoid).
3. **Post-process a tagged stream** — reports emit `\0meaning\0text\0` (invasive; avoid).

Option 1 matches how tests already stub behaviour and keeps report code unchanged aside from
going through the shared helpers (which they already do).

Escape HTML in text nodes; preserve spaces/newlines inside a `<pre class="cuppa-output">`.

### 3.2 Capture runner

A module under `scripts/` (illustrative: `python -m scripts.sample_output`) that:

1. Builds a **fixture project** under a temp dir (reuse integration helpers / dummy project), or
   accepts `--project=` for local preview against a real tree (never commit that capture).
2. Forces colour / HTML mode and a fixed console background for any ANSI fallback.
3. Invokes specific reports in-process where possible (`storage_actions.list_builds`,
   `develop.list_develop`, …) so samples do not need a full compiler — or shells out to
   `python -m cuppa` when the report only exists as a CLI mode.
4. Rewrites paths through the existing `short_path` / display helpers so samples show `_build`,
   `~/.cuppa/…`, not `/home/<user>/…`.
5. Writes:

   - `*.html` fragment (body inner HTML only), and/or
   - `*.adoc` wrapper with a passthrough block, and/or
   - a standalone preview page with the CSS inlined for `file://` viewing.

Suggested first recipes (names illustrative):

| Recipe | Source |
|--------|--------|
| `list-builds` | Planted variant trees + `list_builds` |
| `remove-builds-dry` | Same + `remove_builds` with dry-run |
| `remove-all-builds-dry` | Same + `remove_all_builds` with dry-run |
| `list-develop` | Fake develop copies / existing unit fakes |

### 3.3 Antora integration

**CSS:** add `docs/supplemental-ui/css/cuppa-output.css` (or partial + `ui.yml` edit) defining the
`cuppa-*` classes against the default Antora light background. Keep contrast accessible; do not
rely on terminal bright-on-black.

**Pages:** replace or supplement plain listings with an include, for example:

```asciidoc
.Example `--list-builds` output (colours approximate the terminal meanings)
++++
include::partial$samples/list-builds.html[]
++++
```

Exact include path depends on whether fragments live as Antora partials or as generated files
copied in a docs npm script before `antora generate`.

**Optional AsciiDoc role:** `[cuppa-output]` on a listing that contains only escaped plain text is
*not* enough for spans; passthrough HTML (or a tiny Antora extension that expands a custom block)
is required for colour. Prefer checked-in or pre-build fragments over a Ruby/Asciidoctor extension
(Antora 3 uses Asciidoctor.js — same constraint that blocked `asciidoctor-diagram`).

### 3.4 Preview facility

```sh
python -m scripts.sample_output list-builds --preview
# → opens or prints path to _docs_build/samples/list-builds.preview.html
```

Authors use this while iterating on report layout, without running a full Antora build. The same
artefact can be copied into `docs/` when the sample should ship.

### 3.5 Optional ANSI path

```sh
python -m scripts.sample_output list-builds --format=ansi-html
```

Force `TERM=xterm-256color`, `CUPPA_CONSOLE_BACKGROUND=dark` (or `light`), enable colour, capture
stdout, convert with a pinned dependency, a minimal SGR→span mapper, or — once
[`shiki-syntax-highlighting.md`](shiki-syntax-highlighting.md) Phase E exists — Shiki's `ansi`
language. Document that this mode is for preview parity checks, not for committed docs samples,
unless the env is fully pinned in the recipe.

---

## 4. Path and privacy rules

Samples committed under `docs/` are public. The capture runner must:

- Run under a temp project root with generic names (`widget`, `_build`, …).
- Apply `short_path` / `display_path` so home directories become `~`.
- Fail the recipe if output matches `/home/` or other absolute user paths (guard test).

Private consumer project names must not appear — same policy as `AGENTS.md`.

---

## 5. Testing

| Layer | What |
|-------|------|
| Unit | `HtmlColouriser` escapes HTML; nested emphasise+info produces expected class nesting or ordered spans; subdued never emits raw DIM alone without a docs-safe class |
| Unit | Path guard rejects absolute home paths in fragments |
| Unit | Design-index / recipe registry stays consistent if recipes are listed in a table |
| Optional integration | One Antora build job or local `npm run build` asserts a sample page contains `cuppa-output` and `cuppa-info` |

Do not require a C++ toolchain for the HTML colouriser unit tests; plant directories like the
storage-action unit tests already do.

---

## 6. Documentation impact

Once the facility exists:

- Update `build-layout.adoc` (and later `dependencies.adoc` develop section) to include colourised
  samples beside the existing plain listings, or replace plain listings where colour is the point.
- Document the capture command for contributors in `docs/modules/ROOT/pages/extending.adoc` or a
  short “Writing docs” note — only if we want contributors to regenerate samples; otherwise keep
  the runner as a maintainer tool referenced from this plan and `AGENTS.md`.

Release impact: **none** for the facility alone (docs/tooling); **patch** if shipped samples are
considered doc fixes in an open release cycle.

---

## 7. Phased delivery

| Phase | Delivers | Notes |
|-------|----------|-------|
| A | `HtmlColouriser` + unit tests + preview CSS | No Antora page changes required yet |
| B | `scripts.sample_output` with `list-builds` / `remove-builds-dry` recipes | Unblocks authoring |
| C | Wire samples into `build-layout.adoc`; supplemental-ui CSS in the site | Reader-visible |
| D | Add `list-develop` and other high-value recipes; optional `ansi-html` format | Expand coverage |

Phase A+B can land without waiting on removal Phase 2 merge; Phase C should use the final report
shapes from `#134` so samples do not churn.

---

## 8. Alternatives considered

| Approach | Why not first |
|----------|----------------|
| Manual HTML in AsciiDoc | Rotates out of date the first time marks or columns change |
| Screenshots / SVG exports | Heavy to regenerate; inaccessible to search; poor for copy-paste |
| Kroki / server-side render | Network at doc build; avoided for Mermaid already |
| Only ANSI→HTML | Environment-dependent; weak on light doc backgrounds |
| Asciidoctor / Shiki language themes | Highlights “language” (or raw ANSI), not cuppa meanings — use the Shiki plan for source listings instead |

---

## 9. Open questions

1. **Checked-in vs generate-at-doc-build** — Checked-in fragments are reviewable in PRs; generate
   during `npm run build` always matches code but needs Python on the docs CI path.
2. **Emphasise + colour nesting** — Emit outer `<span class="cuppa-emphasised"><span class="cuppa-info">` or a single combined class? Combined classes are simpler for CSS.
3. **Dark-mode docs** — Antora UI default is light; if the site later gains a dark theme, samples
   need paired CSS variables.
4. **GitHub issue** — File when Phase A starts; no issue number yet.

---

## 10. Success criteria

- A maintainer can regenerate a colourised `--list-builds` sample with one command and open a
  preview HTML file locally.
- The published build-layout page shows that sample in colour without describing “red” and “blue”
  as the only way to understand marks.
- No committed sample contains a personal absolute path or private project name.
- Unit tests cover the HTML colouriser without a compiler.
