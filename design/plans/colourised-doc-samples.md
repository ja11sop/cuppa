# Plan: colourised sample output for documentation and preview

- **Status:** in progress
- **Related:** [`ROADMAP.md`](../../ROADMAP.md) — Documentation tooling (`doc-output-samples`); [#252](https://github.com/ja11sop/cuppa/issues/252); follows build-report work in [`removal-options.md`](removal-options.md) Phase 2; syntax highlighting [`shiki-syntax-highlighting.md`](shiki-syntax-highlighting.md)
- **Updated:** 2026-09-02

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

Implementation options considered:

1. **Injectable colouriser** — `colourise` gains `set_colouriser(...)` / context manager used only
   by the capture runner; production builds keep today's ANSI colouriser.
2. **Dual emit** — helpers append to a side channel (fragile; avoid).
3. **Post-process a tagged stream** — reports emit `\0meaning\0text\0` (invasive; avoid).

**Selected for [#252](https://github.com/ja11sop/cuppa/issues/252): option 1.** A context manager
temporarily replaces the process colouriser for single-threaded sample generation. The HTML
backend records opaque operations while formatters assemble strings, then escapes literal text
and resolves operations into spans. This preserves nested meanings without trusting report data
as HTML. Production builds retain the ANSI backend.

Escape HTML in text nodes; preserve spaces/newlines inside a `<pre class="cuppa-output">`.

### 3.2 Capture runner

Extend the existing `scripts/generate_doc_samples.py` module rather than adding a parallel sample
runner. It:

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

Report output is a terminal character grid, not prose. Use `line-height: 1` on the `<pre>` and
inherit it on the nested `<code>`: added leading creates visible gaps between consecutive `│`
glyphs and makes a judgement tree look broken. Padding around the whole report frame is fine;
padding or margins between report lines are not.

v1 used Antora chrome tokens for sample colours; samples now consume `--cuppa-console-*`
(Colorama hues plus a console surface). Admonition `--cuppa-warning` stays orange. See
[Follow-on: console vs docs-chrome palette](#follow-on-console-vs-docs-chrome-palette).

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
python -m scripts.generate_doc_samples list-builds --preview
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
| A | `HtmlColouriser` + unit tests + preview CSS | **Landed on #252** |
| B | `scripts.generate_doc_samples` semantic recipes | **Landed on #252:** `list-builds`, both dry-run removals, and removal failure |
| C | Wire samples into `build-layout.adoc`; supplemental-ui CSS in the site | **Landed on #252:** all four human-readable build-layout fragments |
| D | Add `list-develop` and other high-value recipes; optional `ansi-html` format | **Complete on #252:** semantic HTML covers every human-readable report sample in the affected pages, including dependency remove / product-clean / purge. ANSI preview is deferred to `doc-shiki`, not a blocker |

### Which recipes can be colourised

A recipe only yields an honest HTML sample when **every** line comes from a real formatter running
under the colouriser. The first versions of several recipes assembled their intro and summary
lines literally and called a tree renderer for the middle. Those versions stayed text-only until
the generator could use the production report path.

**On #252:** `list-downloads` and `list-dependencies` (+verbose) now call
`write_list_downloads_report` / `write_list_dependencies_report` — the same
functions the CLI uses after collation — so intro, footer, extract/`[D]` marks,
and wipe hints take the HTML colouriser. Text siblings stay generated.

The removal recipes now plant deterministic targets and inject them at
`collect_removal_plan` / `collect_purge_downloads`, then run `remove_dependencies()` itself.
That keeps collection deterministic without copying the production announcement, dry-run,
tree, leftover, freed-space, or verify narration. The formatter wins where this differs from
the old hand-assembled sample: for example, actual purge bytes include both the extract and
download, and a dry run says `Would remove` / `would rm`.

There are no checked-in wipe-report samples or wipe sample includes. This work does not add one:
the close-out rule is to colourise the existing human-readable sample set, not expand it with
new report scenarios.

**Superseded text partials.** When a page moves to the HTML fragment, its `.txt` sibling stops
being included but is still generated (`list-develop.txt`, `list-toolchains.txt`,
`list-toolchains-verbose.txt`, `list-downloads.txt`, `list-dependencies.txt`,
`list-dependencies-verbose.txt`, `remove-gitlab-dry-run.txt`,
`remove-boost-product-clean.txt`, `purge-gitlab.txt`). They are kept deliberately:
the unit tests assert report **shape**
against the text form (columns, rules, tree glyphs), which is far more legible than asserting the
same layout through spans, and they remain the reference for `--raw-output`. Do not wire them back
into a page beside the HTML, and do not delete them expecting the HTML assertions to cover layout.

Phase A+B can land without waiting on removal Phase 2 merge; Phase C should use the final report
shapes from `#134` so samples do not churn.

### Follow-on (console vs docs-chrome palette)

Admonition / UI tokens (`--cuppa-warning`, `--cuppa-note`, `--cuppa-important`, `--cuppa-tip`)
describe **page chrome**: WARNING callouts, notes, tips. Report samples describe **the same
meanings the terminal paints**. Those two jobs should not share one hue table.

Confirm hues from `Colouriser._start_colour` (and highlight counterparts), not from the Antora
palette names:

| Meaning | Console (Colorama) | Typical SGR | Sample token |
|---------|--------------------|-------------|--------------|
| `warning`, `remove_notice` | `Fore.MAGENTA` | 35 | `--cuppa-console-warning` |
| `notice`, `expected_failure` | `Fore.YELLOW` | 33 | `--cuppa-console-notice` |
| `info`, `time` | `Fore.BLUE` | 34 | `--cuppa-console-info` |
| `error`, `remove_error`, `failure`, … | `Fore.RED` | 31 | `--cuppa-console-error` |
| `success`, `passed`, … | `Fore.GREEN` | 32 | `--cuppa-console-success` |

Keep `--cuppa-warning` (orange) for admonitions. Sample CSS uses `--cuppa-console-*` only, tuned
for the light/dark page rather than copying a 16-colour VGA chart.

**On #252:** `--cuppa-console-*` tokens (surface, ink, recess, and
warning/notice/info/error/success/muted) live in each palette. `.cuppa-output` and
`.doc .cuppa-scroll-panel:has(pre.cuppa-output) .cuppa-scroll-panel__*` consume them.
JSON / listing scroll panels keep `--cuppa-code-surface`.

Dark schemes take their hues from the **KDE Plasma Breeze** Konsole scheme
(`data/color-schemes/Breeze.colorscheme`), so a sample matches a real terminal: background
`#232627`, foreground `#fcfcfc`, `Color1`–`Color5` for red / green / yellow / blue / magenta, and
`Color0Intense` `#7f8c8d` for subdued. cup-of-tea uses that background verbatim; the other
palettes keep a slightly hue-tinted field with the same hues. Light schemes cannot reuse Breeze —
those hues are chosen against a dark field and `#11d116` green is unreadable on near-white — so a
light console is a near-white paper field with darkened equivalents: cup-of-tea
`#fefdfc`, harbour `#fcfdfe`, forest `#fcfefc`, aubergine `#fefcfd`. Light and dark
schemes both take a stronger `--cuppa-console-border` than page chrome (darker on
light, lighter on dark) so the sample does not dissolve into the canvas.

A small `inset` shadow (`--cuppa-console-inset`) gives the recess. It is applied to the
**viewport**, not the frame: the frame's `box-shadow` is the edge-overflow hint, whose state rules
would otherwise drop the recess exactly when a sample became scrollable.

Shell command listings (`[source,sh]`, `[source,shell]`, `[source,bash]`, and future
`[source,console]`) use the same console surface, border, and recess. They remain ordinary
Highlight.js / AsciiDoc listings rather than semantic report HTML, and retain the bundle's
normal line height: command lists benefit from readable leading, while only report trees need
`line-height: 1` to join box-drawing glyphs.

### Follow-on (wide-panel UX, not sample-specific)

Wide listings already wrap in `cuppa-scroll-panels.js` (fade + chevron while more content exists
past an edge; resist pulse only after overshooting into the bounce). A later slice could **snap
to the side** when the viewport is already close to the left or right edge, so the scroll
position lands flush and the fade/chevron can clear without requiring that bounce. This is a
general affordance for every wrapped listing, JSON sample, and `pre.cuppa-output` — not only
colourised reports. Track it on [`antora-ui-bundle.md`](antora-ui-bundle.md) (`ui-scroll-snap`).

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

1. **Checked-in vs generate-at-doc-build** — **Settled: checked in.** Fragments are reviewable and
   Antora does not need Python. The generator and tests detect drift/privacy failures.
2. **Emphasise + colour nesting** — **Settled: nested spans.** The semantic operation renderer
   preserves both meanings; CSS composes them.
3. **Dark-mode docs** — **Settled and landed:** each palette has light and dark console tokens;
   cup-of-tea dark follows KDE Plasma Breeze Konsole and companion palettes retain a tinted field.
4. **Console vs chrome palette** — **Settled and landed:** dual tokens. HTML class names stay
   meaning-based (`cuppa-warning`); `.cuppa-output` uses `--cuppa-console-*` (including
   surface and ink). Admonition `--cuppa-warning` / `--cuppa-note` unchanged. Hues remain
   tunable against Colorama.
5. **Tracking** — [#252](https://github.com/ja11sop/cuppa/issues/252).

---

## 10. Success criteria

- A maintainer can regenerate a colourised `--list-builds` sample with one command and open a
  preview HTML file locally.
- The published build-layout page shows that sample in colour without describing “red” and “blue”
  as the only way to understand marks.
- No committed sample contains a personal absolute path or private project name.
- Unit tests cover the HTML colouriser without a compiler.
