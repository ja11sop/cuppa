# Plan: Uniform transfer and archive progress (terse-aware)

- **Status:** in progress
- **Related:** [`archive/download-progress.md`](../archive/download-progress.md) (shipped HTTP / extract / git / Conan progress); [`cmake-drive-and-package-staging.md`](cmake-drive-and-package-staging.md) (surfaced need: silent multi-minute package `tar`); [`quiet-tty-heartbeat.md`](quiet-tty-heartbeat.md); [`terse-build-output.md`](terse-build-output.md) / [`terse-delegated-output.md`](terse-delegated-output.md); [`console-channels.md`](console-channels.md); `cuppa.utility.heartbeat`; `cuppa.utility.download.ProgressReporter`; `create_package_archive` in [`gitlab.py`](../../cuppa/package_managers/gitlab.py)
- **Updated:** 2026-10-06
- **Impact:** minor — UX / shared progress channel; no package format change
- **PR:** [#360](https://github.com/ja11sop/cuppa/pull/360)
## Problem

Long byte-moving work still looks hung in places the shipped download-progress
work did not cover — especially **creating** a large GitLab package archive
(`tar -czf` / zip walk in `create_package_archive` with no feedback). The same
gap can appear on **uploads** and any other compress/extract path that bypasses
`ProgressReporter`.

Console work for **1.12.0** also left two **uncoordinated** progress stacks:

| Today | Owns | Gap |
|-------|------|-----|
| Quiet+TTY heartbeat (`pulse` / `spinner`) | Alive / “not hung” under `-Q` | Does not know about byte transfers |
| `ProgressReporter` ASCII `[====]` bar | Download / extract percent | Separate dialect; gated off under `-Q`; silent package `tar` never enrolled |

The quiet-heartbeat work already shows the right **strategy**: share core
elements, tune presentation per mode. Under `-Q`, the same pulse/spinner head
appears in normal quiet and in `--terse-output` (compact / arrow-aligned),
muted, with transcript lock and idle-gate — not a second spinner product.

Transfer / archive progress should adopt that strategy: combine the existing
**alive** capability with an **improved progress-bar** capability behind one
shared engine, then present them in ways that fit normal, terse, quiet, TTY,
and CI — not force one identical frame everywhere, and not keep two unrelated
rewriters fighting the console.

A package `tar` that takes minutes must not:

1. Stay completely silent on an interactive TTY, or
2. Fight the heartbeat / shear terse `[ok]` lines with a private rewrite path, or
3. Dump `\r`-rewritten frames into a CI log, or stay mute for the whole transfer.

The CMake / large-install publisher soak is where the pain showed up; the fix
belongs to a **shared** transfer/archive progress story, not to Option C or E.

## Intent

One Cuppa approach for **download, upload, compress, and extract** progress that:

1. **Shares core capabilities** — alive animation (`pulse` / `spinner`) plus
   percent / bytes / rate / ETA bar (evolved from today’s `ProgressReporter`) —
   so call sites drive one reporter API, not bespoke UIs.
2. **Tunes presentation per mode** — same strategy as quiet heartbeat under
   normal vs terse: same building blocks, layout / mute / density fitted to
   normal, `--terse-output`, and `-Q` / `-s` (e.g. fuller bar+alive in normal;
   more compact under terse; muted under quiet; respect `--quiet-heartbeat=off`).
3. Covers **archive create** (`create_package_archive`) and **registry upload**
   with the same reporter vocabulary as download / extract.
4. Defines **TTY vs non-TTY** behaviour explicitly (interactive rewrite vs CI-
   friendly periodic lines).
5. Reuses / extends `heartbeat` + `ProgressReporter` plumbing rather than a
   third progress library.

## Non-goals

- Changing `.packaged` / staging skip logic (correctness of *whether* to tar).
- Option E in-place staging (`cmake-pkg-stage-inplace`).
- A second progress library or alive-progress dependency.
- Turning `-Q` into a full transfer log (still muted; transfer status only).
- Replacing terse counted `[ok]` / `[progress]` transcript lines — transfer
  status is a **status rewrite** (or CI line), not a substitute transcript.
- Collapsing everything to pulse-only or bar-only — the point is **shared
  capabilities**, mode-tuned composition.

## Direction (settled sketch)

### Shared capabilities, mode-tuned presentation

Analogous to quiet heartbeat (same widget head; normal quiet vs terse compact
arrow form; muted colours; clear before transcript):

| Capability | Role |
|------------|------|
| **Alive** | Pulse or spinner — process is working (existing `--quiet-heartbeat` styles) |
| **Progress** | Improved bar / percent / bytes / rate / ETA — how far through this transfer |
| **Phase caption** | `download` / `extract` / `compress` / `upload` + label |
| **Throttle + clear** | Shared rewrite stream, transcript lock, idle-gate coexistence |

| Mode | Presentation (sketch — exact spelling TBD) |
|------|-----------------------------------------------|
| Interactive, **normal** | Alive + fuller progress (bar and/or percent/bytes/rate); full colour |
| Interactive, **`--terse-output`** | Same capabilities, **compact** layout (arrow-aligned / denser — parallel to heartbeat’s terse form); clear before counted terse lines |
| Interactive, **`-Q` / `-s`** | Same capabilities, **muted**; off if `--quiet-heartbeat=off`; do not resurrect a loud multi-line private dialect |
| **Non-TTY / CI** | No `\r` rewrite; periodic whole-line updates (phase + percent or bytes), throttled — useful in build logs |

Exact composition (when bar appears vs percent-only, how alive sits next to the
bar) is an implementation soak detail — the requirement is **one engine**,
mode-tuned views, not three independent progress products.

### Unify the stacks (not erase the bar)

- Keep and **improve** the progress-bar math / formatting from
  `ProgressReporter`; do not throw it away in favour of pulse-only captions.
- Teach alive + progress to share stream ownership, throttle, clear-before-
  transcript, and quiet mute — the same coexistence rules heartbeat already
  proved.
- Enrol compress / upload (and migrate download / extract) onto that shared
  path so package `tar` stops looking hung and download no longer speaks a
  private console dialect under parallel modes.

### Surfaces to enrol

| Surface | Today | Target |
|---------|--------|--------|
| HTTP download | `ProgressReporter` bar (alone) | Shared alive + progress; mode-tuned; CI lines |
| Tar/zip **extract** | Shared helpers in `download.py` | Same |
| Package **compress** (`create_package_archive`) | Silent `tar` / zip walk | Same (bytes or entry count) |
| Package **upload** (curl / API put) | Often quiet / tool-native | Same |
| Git / Conan | Streamed tool progress | Keep; do not regress; prefer shared engine where Cuppa owns the stream |

### Implementation lean

1. Inventory call sites; mark which already use `ProgressReporter` / heartbeat.
2. Factor a shared transfer-status engine: alive frames + progress metrics +
   mode/TTY policy (likely growing `heartbeat` / `ProgressReporter` toward each
   other, not a third module).
3. Define mode views (normal / terse / quiet / non-TTY) on top of those
   capabilities.
4. Enrol `create_package_archive` and upload; migrate download / extract.
5. Unit tests with fake clocks/streams (TTY rewrite + non-TTY lines); soak a
   large package create under normal, `--terse-output`, `-Q`, and a redirected
   (non-TTY) log.

## Open questions

1. Caption spelling for phases and how densely alive + bar compose in each mode
   (current: normal = alive + bar; terse = alive + metrics without bar; quiet =
   muted; soak may tweak).
2. Whether upload uses Cuppa’s HTTP stack (progress for free) or keeps curl with
   `--progress-meter` parsed into the reporter.
3. Zip / tar create: currently uncompressed file bytes as they are added (good
   enough; precompute walk cost accepted for package trees).

## Progress

| Item | Status |
|------|--------|
| Need split from cmake package-archive-progress | Done — this proposal |
| Download / extract foundation | Shipped — [`download-progress.md`](../archive/download-progress.md) (bar; engine now shared with alive) |
| Settled: shared alive + progress capabilities; mode-tuned presentation; TTY vs CI | Done |
| Shared engine (`format_alive_prefix`, `transfer_progress_allowed`, `ProgressReporter` composition) | Done on this PR |
| Compress (`create_package_archive`) | Done on this PR — Python tar/zip with reporter |
| Download / extract migrate onto composed reporter | Done on this PR (same `ProgressReporter`) |
| Upload (curl) | Open — follow-on |
| Docs / CHANGELOG / soak | In progress |
