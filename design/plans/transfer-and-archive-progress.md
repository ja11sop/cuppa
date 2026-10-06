# Plan: Uniform transfer and archive progress (terse-aware)

- **Status:** proposal
- **Related:** [`archive/download-progress.md`](../archive/download-progress.md) (shipped HTTP / extract / git / Conan progress); [`cmake-drive-and-package-staging.md`](cmake-drive-and-package-staging.md) (surfaced need: silent multi-minute package `tar`); [`quiet-tty-heartbeat.md`](quiet-tty-heartbeat.md); [`terse-build-output.md`](terse-build-output.md) / [`terse-delegated-output.md`](terse-delegated-output.md); [`console-channels.md`](console-channels.md); `cuppa.utility.heartbeat`; `cuppa.utility.download.ProgressReporter`; `create_package_archive` in [`gitlab.py`](../../cuppa/package_managers/gitlab.py)
- **Updated:** 2026-10-06
- **Impact:** minor — UX / shared progress channel; no package format change

## Problem

Long byte-moving work still looks hung in places the shipped download-progress
work did not cover — especially **creating** a large GitLab package archive
(`tar -czf` / zip walk in `create_package_archive` with no feedback). The same
gap can appear on **uploads** and any other compress/extract path that bypasses
`ProgressReporter`.

Console work for **1.12.0** also left two progress dialects:

| Today | Where it shows |
|-------|----------------|
| Quiet+TTY heartbeat (`pulse` / `spinner`) | `-Q` / `-s` INFO diversion only |
| `ProgressReporter` ASCII `[====]` bar | Download / extract when INFO-gated progress is on |

Operators should recognise **one** liveliness animation whether they are in
normal, `--terse-output`, or `-Q` — muted under quiet, full colour otherwise —
and that animation must behave sensibly on a TTY and in a CI log (non-TTY).

A package `tar` that takes minutes must not:

1. Stay completely silent on an interactive TTY, or
2. Fight the heartbeat / shear terse `[ok]` lines with a second rewrite dialect, or
3. Dump `\r`-rewritten frames into a CI log, or stay mute for the whole transfer.

The CMake / large-install publisher soak is where the pain showed up; the fix
belongs to a **shared** transfer/archive progress story, not to Option C or E.

## Intent

One Cuppa approach for **download, upload, compress, and extract** progress that:

1. Uses the **same animation** (heartbeat `pulse` / `spinner` widget) in
   **normal**, **`--terse-output`**, and **`-Q` / `-s`** — differing only in
   mute / colour / transcript coexistence, not in a second bar dialect.
2. Covers **archive create** (`create_package_archive`) and **registry upload**
   with the same reporter vocabulary as download / extract.
3. Defines **TTY vs non-TTY** behaviour explicitly (interactive rewrite vs CI-
   friendly periodic lines).
4. Reuses / extends `heartbeat` + `ProgressReporter` plumbing rather than a
   third progress library.

## Non-goals

- Changing `.packaged` / staging skip logic (correctness of *whether* to tar).
- Option E in-place staging (`cmake-pkg-stage-inplace`).
- A second progress library or alive-progress dependency.
- Turning `-Q` into a full transfer log (still muted; animation only).
- Replacing terse counted `[ok]` / `[progress]` transcript lines — transfer
  status is a **status rewrite** (or CI line), not a substitute transcript.

## Direction (settled sketch)

### One animation, three modes

| Mode | Animation | Presentation |
|------|-----------|--------------|
| Interactive, **normal** | Same `pulse` / `spinner` as quiet heartbeat | Full colour / emphasis; caption = phase + percent / bytes / rate (e.g. `compress · pkg.tar.gz  42% …`) |
| Interactive, **`--terse-output`** | **Same** widget | Compact / arrow-aligned form already used by heartbeat under terse; clear before the next counted terse line (transcript lock + idle-gate rules) |
| Interactive, **`-Q` / `-s`** | **Same** widget | **Muted** (subdued colours); off entirely if `--quiet-heartbeat=off` |
| **Non-TTY / CI** | No `\r` rewrite | Periodic whole-line updates (phase + percent or bytes), throttled — useful in build logs, not a silent multi-minute gap and not a storm of frames |

`--quiet-heartbeat=pulse|spinner|off` remains the style switch for the shared
widget in all interactive modes (not only under `-Q`).

### Retire the dual dialect

Today’s download `ProgressReporter` ASCII bar stays as an implementation detail
only until call sites move onto the shared animation path. Target end state:

- **No** separate “download bar vs heartbeat pulse” look for the same class of
  work.
- Byte / percent math and throttle intervals can remain in `ProgressReporter`
  (or a thin successor); **rendering** goes through the shared status line
  (heartbeat-shaped) on TTY, line mode off TTY.

### Surfaces to enrol

| Surface | Today | Target |
|---------|--------|--------|
| HTTP download | `ProgressReporter` bar | Shared animation + CI lines |
| Tar/zip **extract** | Shared helpers in `download.py` | Same |
| Package **compress** (`create_package_archive`) | Silent `tar` / zip walk | Same (bytes or entry count) |
| Package **upload** (curl / API put) | Often quiet / tool-native | Same |
| Git / Conan | Streamed tool progress | Keep; do not regress; prefer shared animation where Cuppa owns the stream |

### Implementation lean

1. Inventory call sites; mark which already use `ProgressReporter` / heartbeat.
2. Lift or adapt heartbeat status rendering so transfer phases can drive the
   **same** widget outside quiet diversion (normal + terse + quiet).
3. Teach `ProgressReporter` (or successor) to render via that path on TTY and
   periodic lines off TTY; remove reliance on the ASCII `[====]` bar as the
   product look.
4. Enrol `create_package_archive` and upload.
5. Unit tests with fake clocks/streams (TTY rewrite + non-TTY lines); soak a
   large package create under normal, `--terse-output`, `-Q`, and a redirected
   (non-TTY) log.

## Open questions

1. Caption spelling for phases (`download` / `extract` / `compress` / `upload`)
   and whether percent always prefers bytes when total known.
2. Whether upload uses Cuppa’s HTTP stack (progress for free) or keeps curl with
   `--progress-meter` parsed into the reporter.
3. Zip / tar create: progress by uncompressed bytes vs file count when total
   size is expensive to precompute.
4. Migration: flip download/extract to the shared animation in the same PR as
   compress, or compress-first then migrate download look?

## Progress

| Item | Status |
|------|--------|
| Need split from cmake package-archive-progress | Done — this proposal |
| Download / extract foundation | Shipped — [`download-progress.md`](../archive/download-progress.md) (bar dialect; to be unified) |
| Settled: one animation across normal / terse / quiet; TTY vs CI | Done — this revision |
| Compress / upload + shared render path | Proposal |
| Implementation | Not started |
