# Plan: Uniform transfer and archive progress (terse-aware)

- **Status:** proposal
- **Related:** [`archive/download-progress.md`](../archive/download-progress.md) (shipped HTTP / extract / git / Conan progress); [`cmake-drive-and-package-staging.md`](cmake-drive-and-package-staging.md) (surfaced need: silent multi-minute package `tar`); [`quiet-tty-heartbeat.md`](quiet-tty-heartbeat.md); [`terse-build-output.md`](terse-build-output.md) / [`terse-delegated-output.md`](terse-delegated-output.md); [`console-channels.md`](console-channels.md); `cuppa.utility.download.ProgressReporter`; `create_package_archive` in [`gitlab.py`](../../cuppa/package_managers/gitlab.py)
- **Updated:** 2026-10-05
- **Impact:** minor — UX / shared progress channel; no package format change

## Problem

Long byte-moving work still looks hung in places the shipped download-progress
work did not cover — especially **creating** a large GitLab package archive
(`tar -czf` / zip walk in `create_package_archive` with no feedback). The same
gap can appear on **uploads** and any other compress/extract path that bypasses
`ProgressReporter`.

Separately, console work for **1.12.0** changed the rules:

| Channel | Role under quiet / terse |
|---------|---------------------------|
| Quiet+TTY heartbeat | Subdued status for INFO gaps; idle-gate after transcript |
| Terse transcript | Counted `[ok]` / `[progress]` / nested `→` lines |
| `ProgressReporter` (today) | TTY rewrite bar / stderr lines; gated off under `-Q` |

A package `tar` that takes minutes must not:

1. Stay completely silent on an interactive TTY, or
2. Dump a private progress dialect that shears terse lines or fights the
   heartbeat, or
3. Re-enable multi-line download bars under `-Q` (heartbeat already owns that
   quiet surface).

The CMake / large-install publisher soak is where the pain showed up; the fix
belongs to a **shared** transfer/archive progress story, not to Option C or E.

## Intent

One Cuppa approach for **download, upload, compress, and extract** progress that:

1. Reuses / extends `cuppa.utility.download.ProgressReporter` (and extract
   helpers) where they already work.
2. Covers **archive create** (`create_package_archive`) and **registry upload**
   (curl / HTTPS put) with the same reporter vocabulary.
3. Defines behaviour under **normal**, **`--terse-output`**, and **`-Q` / `-s`**
   (including coexistence with the quiet heartbeat).
4. Stays silent in CI / non-TTY (same as today’s download progress).

## Non-goals

- Changing `.packaged` / staging skip logic (correctness of *whether* to tar).
- Option E in-place staging (`cmake-pkg-stage-inplace`).
- A second progress library or alive-progress dependency.
- Turning `-Q` into a full transfer log.

## Direction (sketch)

| Mode | Progress behaviour |
|------|-------------------|
| Interactive, normal transcript | Existing TTY rewrite bar (or line mode on non-TTY stderr) for download/extract; **same** for compress/upload |
| Interactive, `--terse-output` | Prefer **one subdued status** (heartbeat-shaped or nested `→ [progress] …`) keyed by phase — `download` / `extract` / `compress` / `upload` — not a free-running bar that shears `[ok]` lines. Exact spelling TBD; must clear before the next counted terse line (same transcript lock / idle-gate rules as heartbeat) |
| `-Q` / `-s` + TTY | Fold into quiet heartbeat captions (phase + percent / bytes) or stay off if `--quiet-heartbeat=off`; do **not** resurrect multi-line bars |
| Non-TTY / CI | No bar; optional rare percent lines only if already useful for logs (match download helper) |

### Surfaces to enrol

| Surface | Today | Target |
|---------|--------|--------|
| HTTP download | `ProgressReporter` | Keep; ensure terse/quiet policy documented |
| Tar/zip **extract** | Shared helpers in `download.py` | Keep; same policy |
| Package **compress** (`create_package_archive`) | Silent `tar` / zip walk | Progress (bytes or entry count) |
| Package **upload** (curl / API put) | Often quiet / tool-native | Cuppa reporter or streamed tool progress under the same policy |
| Git / Conan | Streamed tool progress | Keep; do not regress under terse |

### Implementation lean

1. Inventory call sites; mark which already use `ProgressReporter`.
2. Settle **one** terse/quiet rendering path (likely: drive heartbeat / nested
   progress from the reporter, not a third UI).
3. Teach `create_package_archive` (and upload) to report through that path.
4. Unit tests with fake clocks/streams; soak on a large package create under
   normal, `--terse-output`, and `-Q`.

## Open questions

1. Terse spelling: heartbeat-only vs counted nested `→ [progress] compress · …`.
2. Whether upload uses Cuppa’s HTTP stack (progress for free) or keeps curl with
   `--progress-meter` parsed into the reporter.
3. Zip create: progress by uncompressed bytes vs file count.

## Progress

| Item | Status |
|------|--------|
| Need split from cmake package-archive-progress | Done — this proposal |
| Download / extract foundation | Shipped — [`download-progress.md`](../archive/download-progress.md) |
| Compress / upload + terse/quiet policy | Proposal |
| Implementation | Not started |
