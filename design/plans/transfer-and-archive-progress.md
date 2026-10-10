# Plan: Uniform transfer and archive progress (terse-aware)

- **Status:** done
- **Related:** [`archive/download-progress.md`](../archive/download-progress.md) (shipped HTTP / extract / git / Conan progress); [`cmake-drive-and-package-staging.md`](cmake-drive-and-package-staging.md) (surfaced need: silent multi-minute package `tar`); [`quiet-tty-heartbeat.md`](quiet-tty-heartbeat.md); [`terse-build-output.md`](terse-build-output.md) / [`terse-delegated-output.md`](terse-delegated-output.md); [`console-channels.md`](console-channels.md); [`console-write-ownership.md`](console-write-ownership.md); `cuppa.utility.heartbeat`; `cuppa.utility.download.ProgressReporter`; `create_package_archive` in [`gitlab.py`](../../cuppa/package_managers/gitlab.py)
- **Updated:** 2026-10-10
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

| Capability | Role |
|------------|------|
| **Alive** | Pulse or spinner — terse TTY only (unless `--quiet-heartbeat=off`) |
| **Progress bar** | Percent / bytes / rate / ETA bar — normal and terse |
| **Idle reveal** | Do not paint progress until the idle gate (~0.2s) has elapsed — **except** normal TTY without `-Q`/`-s` (show immediately). Fast small transfers never flash |
| **Dwell** | If progress (and alive) was shown, wait one full animation cycle before clearing / printing the next transcript line |
| **Overwrite** | Ephemeral `\r` status: clear on completion (no durable 100% newline) when muted/overwrite applies |

| Mode | TTY presentation |
|------|------------------|
| **Normal** (no quiet) | **No** alive widget; progress bar in full colour; show immediately; final 100% line may remain (durable) |
| **Normal + `-Q`/`-s`** | Same as normal (no alive) but **muted**; idle-gate reveal; **overwrite** on completion |
| **`--terse-output`** (± `-Q`/`-s`) | Alive (unless `off`) + `→` + progress **bar**, always **muted**; idle-gate reveal; overwrite on completion; then a durable terse identity line |
| **Non-TTY / CI** | Periodic whole lines **only in normal** mode (not under `--terse-output`) |

### Terse completion identity (durable)

After a transfer finishes under `--terse-output`, print an identity line (progress
status already cleared). Global / resolve form:

```text
              → [download] https://example.com/…/pkg.tgz → <downloads>/pkg.tgz
              → [extract]  <downloads>/pkg.tgz → <dependencies>/<variant>/pkg
```

Variant / action form (ordinary terse ledger):

```text
   6/  8 ·  19% [ok]   test/matching_engine · gcc16_dbg_… · download · url → <final>/…
              → [ok]   test/matching_engine · gcc16_dbg_… · extract · <final>/… → <artefacts>/…
```

Actions: `download`, `extract`, `compress`, `upload`, `publish`.

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
| Package **upload** (GitLab publish PUT) | Was silent ``curl --upload-file`` | ``upload_file`` + ``ProgressReporter`` (same as download) |
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

1. ~~Upload transport~~ — **Settled:** Cuppa HTTP PUT via ``upload_file`` (same
   stack as collect’s ``download_file`` + ``ProgressReporter``). Curl
   ``--progress-meter`` parsing declined (fragile; second dialect). Keep curl
   only as an emergency escape hatch if a soak shows a real TLS/proxy gap.
2. Zip / tar create: currently uncompressed file bytes as they are added (good
   enough; precompute walk cost accepted for package trees).

## Progress

| Item | Status |
|------|--------|
| Need split from cmake package-archive-progress | Done — this proposal |
| Download / extract foundation | Shipped — [`download-progress.md`](../archive/download-progress.md) |
| Settled presentation (normal / terse / quiet / idle / CI) | Done — this revision |
| Shared engine + mode-tuned `ProgressReporter` | Done on this PR |
| Compress (`create_package_archive`) | Done on this PR |
| Terse completion identity (download / extract / compress / publish) | Done on this PR |
| Upload live progress bar | Done — ``upload_file`` PUT + ``ProgressReporter``; ``GitlabPackagePublisher.publish_package`` no longer shells to curl |
| Location git update/clone start trigger under terse | Done — ``heartbeat.operation_status`` (pip fetch is quiet; terse skipped INFO); captions ``Updating   <token> · url@branch`` (pad to ``[location]``), full ``~/`` path line in normal (incl. ``-Q``); one shared status row + resolve children ``dwell=False`` (no ~1.5s×N seize) |
| Terse transfer mute body (keep green ECG) | Done — verb/label/metrics subdued; alive prefix stays hospital-green |
| Package ``[collect]`` / ``[extract]`` with ``src → dest`` | Done — ``<registry>`` / ``<downloads>`` / stem tokens; package location RHS is ``name/ver`` (token carries version; no extra ``/3.9.0/`` segment) |
| ``[ready]`` after all toolchains × sconscripts read | Done — no longer closes on the first tip ``BuildWith`` (gcc16 collect was after ready) |
| Property-based resolve ensure phases | **Deferred** — see below; not required for 1.12.0 transfer UX |
| Docs / CHANGELOG / soak | Done — [#360](https://github.com/ja11sop/cuppa/pull/360) soaks (cascade plan / transfer / nest handoff) |
| URL ``https://`` on publish/transfer (no ``normpath``) | Done on this PR (content OK in soak) |
| Publish dest ``<registry>/name/ver/file`` + map | Done on this PR (content OK in soak) |
| Clear progress bar before delegate/cmake ``→`` | Superseded by owned-stream ``write_line`` |
| CMake ``-- Up-to-date:`` flood suppressed | Done on this PR |
| CMake ``-- All targets Up-to-date`` summary | Done — preamble ignored for “other” |
| Deduplicate mode banners (OFFLINE ×2) | Fixed via nested ``CUPPA_STDOUT_IS_TTY`` preserve (+ once-per-process guard) |
| Cascade tip→nest transition marker | Done — tip ``begin``/``end`` + nest entering/exiting; prepare→``[ready]``→plan |
| **One console write path** (TTY ownership) | Done on this PR — [`console-write-ownership.md`](console-write-ownership.md) |

## Deferred: property-based resolve ensure phases

Today resolve is still the mixed ``BuildWith(default_dependencies)`` walk (live
children). ``[ready]`` now waits until every toolchain × variant × sconscript
has been read, so multi-stem package collects stay under prepare→ready.

A later optional redesign (not required for 1.12.0 transfer UX):

| Phase | Scope | Examples |
|-------|--------|----------|
| ``once`` | Identity not toolchain-keyed | Location repos / URL archives |
| ``per-identity`` | Active package/Conan stems | GitLab package tip → transitives; Conan settings |

Factories would advertise ``ensure_scope`` + idempotent ``ensure(identity)``.
Orchestrator runs ``once`` then each active identity; ``[ready]`` closes after.
Do **not** grow hard-coded product passes (``repos → gitlab → conan → …``).

Left deferred after [#360](https://github.com/ja11sop/cuppa/pull/360) soaks: not required for the
shipped transfer / ownership UX. Open a follow-on plan only if multi-stem prepare
cost or identity-keyed ensure becomes a real pain.
