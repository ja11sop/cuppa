# Console report patterns (judgement trees and severity timing)

- **Status:** in progress
- **Related:** [`ROADMAP.md`](../../ROADMAP.md) — `console-report-patterns`; umbrella [#161](https://github.com/ja11sop/cuppa/issues/161); [`removal-options.md`](removal-options.md); toolchains [#160](https://github.com/ja11sop/cuppa/issues/160); `--list-develop` report shape
- **Updated:** 2026-08-07

Cuppa’s storage and develop reports now share a recognisable **judgement tree**: a one-line intro
with severity brackets, then a tree grouped error → warning → note. Several wording and severity
choices were settled while shipping wipe / remove polish. This document records those choices so
later work (and agents) do not re-litigate them casually — and sketches what a longer
contributor-facing “report patterns” guide might grow into.

This is **not** yet Antora product documentation. Until a curated page exists under Contributing,
treat this plan as the working reference and keep shipped behaviour honest in the topic pages
(`build-layout.adoc`, `dependencies-managing.adoc`).

---

## 1. Settled decisions (do not reverse without intent)

| Decision | Rule | Why |
|----------|------|-----|
| Judgement intro shape | `{Verb} {emphasised N} {subject}: [N errors][N warnings][N notes]` | Same look for wipe, remove, builds, and `--list-develop` (develop also appends ok / not-using-develop) |
| Zero brackets | Always show all three; **mute** zeros; colour non-zeros (error / warning / info) | Scan the line without hunting for missing severities |
| Tree hang | Stem hangs from the intro (`│` / `└──`), severity headings first, then labels, then prose/blocks | Reading down is a work list, worst first |
| Subject count | Emphasise the numeric count in intro **and** in freed-space footers | Matches announce lines (`Wiping **9** trees`) |
| Bracketed values only | Colour `[placeholders]` in prose; leave surrounding words plain | Same as `--list-develop` |
| **Warn before, note after** | If an outcome is “proceed anyway / already done / cannot abort”, dry-run (or pre-act) may **warn**; after a real action demote to **note** and use **past tense** | Warnings after the fact train users to ignore them |
| True failures stay errors | Permission denied, refusals, ambiguous tokens, missing required targets | Exit non-zero; path still wrong or still on disk |
| Routing / bookkeeping `logger.warn` | CLI precedence, inventory refresh failures | Not judgement-tree items; still actionable |

### 1.1 Instances of warn → note

| Scenario | Dry-run / before | After real action |
|----------|------------------|-------------------|
| Force-wipe `used_by` (incl. safe unqualified duplicate) | `warning`: `wiping…`, `removing this copy is safe`, `would be re-fetched` | `note`: `wiped…`, `removing the copy was safe`, `will be re-fetched` |
| Path already gone on remove/wipe/builds | (does not fire on dry-run) | `note`: `was already gone: [path]` — never leave as warning |

### 1.2 Shared helpers (prefer these)

| Helper | Module | Use for |
|--------|--------|---------|
| `format_severity_count_brackets` | `cuppa.utility.storage` | Intro suffix |
| `emphasised_count_phrase` | `cuppa.utility.storage` | `N trees` / `N develop locations` |
| `_removal_error_lines` | `cuppa.core.storage_actions` | Judgement tree body (builds, deps, wipe) |
| `_is_already_gone_error` / `_already_gone_note_reason` | `cuppa.core.storage_actions` | Benign miss classification |

Do **not** invent a second flat `as_warning("Not all…")` + indented list for dependency failures.

---

## 2. When adding a new report notice

Ask, in order:

1. **Can the user still abort?** If yes and proceeding is surprising → **warning** (present / future tense).
2. **Has the action already completed?** If the message only records what happened and needs no further action → **note** (past tense).
3. **Is something still wrong on disk or in the request?** → **error** (exit non-zero).
4. **Is it routing or log commentary?** → `logger.warn` / subdued line, not a judgement item.

If the same fact appears on dry-run and on live run, write **two wordings** (or tense switch on `planning`) rather than one eternal warning.

---

## 3. Longer-term work (this plan grows here)

| Phase | Work | Outcome |
|-------|------|---------|
| A | Keep this file updated as new report notices ship | Agents have one place for severity timing |
| B | Extract a short “Report patterns” subsection into Antora Contributing (link here for depth) | Human contributors see the rules without reading the whole removal plan |
| C | Optional: fold develop `summary()` further toward shared helpers only (already uses brackets) | Less drift |
| D | Optional: promote force-wipe subdued `no inventory record` lines into judgement notes with past tense after wipe | Consistency, low urgency |
| E | Optional: regular `--wipe-dependencies` emitting `used_by` notices like force-wipe | Product gap, not tense |

Phase B is the main “contributor docs” deliverable; do not expand Antora until a few more notices have proven the rules stable.

---

## 4. Progress snapshot

| Item | Status |
|------|--------|
| Shared severity brackets + emphasised counts | Done (1.5.0.dev) |
| Force-wipe `used_by` warn→note | Done |
| Already-gone → note (builds + deps + force-wipe) | Done |
| `remove_dependencies` failures → `_removal_error_lines` | Done |
| `--list-scope=compact` / `referenced` sibling fix / unqualified stem wipe UX | Done (this workstream) |
| Design plan + issue [#161](https://github.com/ja11sop/cuppa/issues/161) | Done |
| Antora Contributing “Report patterns” page | Not started (Phase B) |
| `--wipe-dependencies` `used_by` parity with force-wipe | Not started (Phase E) |

---

## 5. Privacy

Do not paste private project paths or registry hosts into examples here; use the usual fixtures
(`widget`, `~/coding/…`, `example.com`).
