# Note: topic / group / single-option help instead of a flat `--help` dump

- **Status:** proposal
- **Related:** ROADMAP `cli-help-topics`; `cuppa/core/options.py`, `cuppa/core/base_options.py`,
  `cuppa/core/storage_options.py`, `cuppa/configure.py`, dependency/method
  `add_options`; Antora CLI hub
  [`cli-reference.adoc`](../../docs/modules/ROOT/pages/cli-reference.adoc) and children;
  console report patterns
  [`archive/console-report-patterns.md`](../archive/console-report-patterns.md)
- **Updated:** 2026-11-14
- **Impact:** likely `minor` if the default `--help` shape changes or new public
  flags appear; `patch` if additive only (`--help-topic=…` beside today’s dump)

## Problem

`cuppa --help` (SCons `AddOption` → optparse/argparse help) prints **every** registered
flag in one long, barely structured list. Operators already think in groups — configure /
storage / develop / cascade / output / Boost / GitLab package / toolchains / methods —
and Antora already documents those groups on separate CLI pages. The terminal does not:

- Group or section the dump.
- Offer a short “table of contents” of help topics.
- Let you ask for one family (`configure`, `develop`, `boost`, …).
- Let you ask for one flag (`--offline`, `--storage-root`, …) without scrolling.
- Use Cuppa console chrome (judgement-tree / report surface) — it is stock SCons help.

The list grows with every dependency plugin and tip `cuppa.add_option`, so the problem
only gets worse.

## Goals

1. **Discoverable structure** — a default help path that shows topics / groups first (or
   a short summary + how to dig in), not hundreds of flags at once.
2. **Group help** — show all options for a named family (configure, develop, storage,
   boost, …) with readable chrome.
3. **Single-option help** — show one flag’s spelling(s), dest, help text, and related
   flags (aliases, global twins like `--save-conf` / `--save-global-conf`).
4. **Better chrome** — section headers, consistent columns or wrapped prose, colour that
   survives `--raw-output` / `NO_COLOR` the same way other console reports do; optional
   pager when stdout is a TTY and the body is long.
5. **Stay honest with Antora** — terminal topic names should map to CLI hub children
   where they exist; do not invent a second taxonomy without updating docs.

## Non-goals (v1 exploration)

- Replacing Antora CLI pages with terminal-only docs.
- Interactive TUI menus (unless a later spike proves they fit).
- Changing flag spellings or dest keys.
- Teaching tip `cuppa.add_option` authors a full man-page DSL on day one (start with
  Cuppa-owned registrations; tip flags can join once the registry exists).

## Inventory (today)

| Layer | How options appear | Notes |
|-------|--------------------|-------|
| `cuppa.core.options.add_option` | Cuppa-owned flags | Configure, base, output, … |
| `add_storage_options` / location / develop / cascade | Family modules | Natural group boundaries |
| Toolchain / dependency / method / profile `add_options` | Plugin factories | Often prefixed (`--boost-*`, package-scoped) |
| Tip `cuppa.add_option` / `add_tip_option` | Project-only | Nest argv drops tip-local; help still shows them on the tip |
| SCons built-ins | `-c`, `-j`, `-Q`, … | Curated subset already on Antora; decide whether topic help includes them |

There is **no** Cuppa-owned help formatter today — construct registers options, then SCons
owns `--help`.

## Design space (explore before settling)

### A. Invocation shapes

| Id | Shape | Pros | Cons |
|----|-------|------|------|
| `A-help-default-toc` | Bare `--help` prints a **topic index** (+ maybe “common flags”); full dump behind `--help=all` or `--help-all` | Fixes the first-screen problem | Behaviour change; scripts that scrape full `--help` break unless `all` is the compatibility path |
| `A-help-topic` | Keep full dump; add `--help-topic=configure` / `--help-topic=boost` | Additive; low risk | Full dump still the default |
| `A-help-equals` | `--help=configure` or `--help=--offline` (SCons/optparse value on help) | Familiar “help=thing” | Parsing / conflict with store_true help; SCons may not allow it cleanly |
| `A-subcommand` | `cuppa help`, `cuppa help configure`, `cuppa help --offline` via `__main__` before SCons | Clean UX; pager-friendly | Two entry paths (`cuppa --help` vs `cuppa help`); document both |
| `A-filter-prefix` | `--help --boost` or `--help boost*` | Cheap | Ambiguous vs real flags; poor for cross-cutting groups |

**Lean (not settled):** prefer **additive** first (`--help-topic=` and/or `cuppa help …`) while
deciding whether bare `--help` becomes a TOC (`A-help-default-toc`) in the same release or a
follow-on. Keep a documented escape hatch for the full dump.

### B. Group / topic model

| Id | Model | Pros | Cons |
|----|-------|------|------|
| `B-module-map` | Explicit registry: topic id → list of dests / callables that registered them | Precise; matches code modules | Must maintain the map as options move |
| `B-prefix` | Infer from `--boost-*`, `--cascade-*`, … | Automatic | Cross-cutting flags (`--offline`, `--terse-output`) need a home; ugly prefixes |
| `B-tag-at-register` | `add_option(..., topics=('configure','storage'))` | Accurate; tip-friendly later | Touches every registration; migration churn |
| `B-antora-align` | Topic ids = CLI child page stems (`building`, `storage-and-configuration`, …) | Docs ↔ terminal | Some pages mix concerns; not 1:1 with modules |

**Lean:** `B-tag-at-register` for Cuppa-owned options (small decorator / wrapper kwargs), with a
bootstrap `B-module-map` for the first cut so not every call site must move on day one.
Topic ids should be **stable kebab strings** listed in one table (plan + Antora).

Candidate topics (draft — refine when implementing):

| Topic id | Rough contents |
|----------|----------------|
| `common` | High-frequency: `--offline`, `--develop`, `--parallel`, output modes, `--info` |
| `configure` | `--show-conf`, `--save-conf`, global twins, `--use-conf`, … |
| `storage` | roots, list/remove/purge/wipe, `--deep-clean` |
| `develop` | clone / update / list develop, location branch flags |
| `cascade` | `--cascade*`, publishers, amend |
| `output` | `--terse-output`, `-Q`, native, scons-output, heartbeat |
| `toolchains` | `--toolchains`, archive / identity / stdlib |
| `boost` | `--boost-*` |
| `packages` / `gitlab` | package consume / publish / latest |
| `profiles` | `--cxx-profiles*` |
| `scons` | Curated SCons subset Cuppa documents |
| `all` | Everything (compatibility dump) |

### C. Single-option lookup

| Id | Shape | Notes |
|----|-------|-------|
| `C-flag` | `cuppa help --offline` or `--help-topic=--offline` | Exact long opt; also accept dest `offline`? |
| `C-fuzzy` | Substring match with Options Error tree if ambiguous | Nice; needs careful ranking |
| `C-related` | Show global/project twins, deprecated aliases, Antora xref path | High value for configure/storage |

**Lean:** exact long-opt and dest first; fuzzy as follow-on. Always mention related twins.

### D. Chrome / formatting

| Idea | Notes |
|------|-------|
| Topic index as judgement-style count + muted stem list | Matches conf-show / Options Error familiarity |
| Per-topic: section header, then flag lines with wrapped help | Columns if width allows; wrap with `storage.wrapped` |
| Colour: flag names emphasised/info; help prose plain; aliases subdued | Honour `NO_COLOR` / `--raw-output` |
| Pager: `less -R` when TTY and line count > threshold | Opt-out `CUPPA_HELP_PAGER=0` or `--no-pager` |
| Do not route help through `logger.info` | Console report channel so `-Q` is irrelevant for help-only runs |

### E. Implementation constraints

- SCons owns early argv for `--help`; a Cuppa pre-parse in `cuppa/__main__.py` (like
  `--info`) may be required for `cuppa help` or to intercept before the flat dump.
- Registration order ≠ display order — the topic registry must sort stably.
- Nested cascade / tip-local flags: document whether nest `--help` shows tip flags (today
  tip registers on tip only).
- Tests: unit for registry membership and single-option render; integration for
  `cuppa help configure` exit 0 and presence of expected flags; no full golden dump.

## Recommended exploration order

1. Spike `__main__` / construct: can we intercept help without breaking SCons?
2. Build a **read-only topic registry** for configure + storage + output (three topics) with
   hand-listed dests — prove chrome + `cuppa help <topic>` / `--help-topic=`.
3. Decide bare `--help` TOC vs full dump default (product call; CHANGELOG carefully).
4. Extend tags to boost / develop / cascade; add single-option lookup.
5. Align Antora CLI hub with the same topic ids (cross-links both ways).
6. Optional pager + fuzzy match.

## Open questions

1. Should bare `--help` change in the first shipping PR, or only after topics feel complete?
2. Topic id for GitLab package flags: `packages` vs `gitlab` vs split consume/publish?
3. Do tip `cuppa.add_option` flags get an automatic `project` topic or stay in `all` only?
4. Is `cuppa help` worth a real subcommand parser, or is `--help-topic=` enough for v1?

## Progress

| Slice | Status |
|-------|--------|
| Problem / design space | **This plan** |
| Spike intercept + 3-topic registry | Todo |
| Product call on bare `--help` default | Todo |
| Ship additive topic / single-option help | Todo |
| Antora topic id alignment | Todo |
