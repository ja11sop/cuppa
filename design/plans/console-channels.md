# Plan: console channels (log, report, transcript, heartbeat)

- **Status:** in progress
- **Related:** [`ROADMAP.md`](../../ROADMAP.md) — Build console output; [`console-mode-banners.md`](console-mode-banners.md); [`terse-build-output.md`](terse-build-output.md); [`terse-delegated-output.md`](terse-delegated-output.md); [`terse-dependency-locations.md`](terse-dependency-locations.md); [`native-toolchain-output.md`](native-toolchain-output.md); [`quiet-tty-heartbeat.md`](quiet-tty-heartbeat.md); [`build-log-hygiene.md`](build-log-hygiene.md); [`console-stop-error-reporting.md`](console-stop-error-reporting.md); [`archive/console-report-patterns.md`](../archive/console-report-patterns.md)
- **Updated:** 2026-10-04
- **Impact:** none for this index; individual console slices keep their own impact labels

This is the map for Cuppa's console work. Individual plans stay the spec for their slice. Do not re-decide which channel a line belongs to inside a later pull request.

## Channels

| Channel | What it is | Controlled by | Quiet |
|---------|------------|---------------|-------|
| **Log** | `logger` lines: configure commentary, "Updating…", the version line, warnings | `--verbosity`. `-Q` forces `warn` unless `--verbosity=` is set. `-s` / `--quiet` / `--silent` forces `error` | Info drops under `-Q`. Warnings drop under `-s` |
| **Console report** | What you asked Cuppa to show: `--list-*`, cascade trees, mode banners, Options Error trees | The command, not verbosity | Stays. Colour drops under `--raw-output` / `NO_COLOR`; the text stays |
| **Build transcript** | SCons progress, command lines, compiler and linker output | Spawn-mode flags below. SCons `-Q` drops Reading/Building. `-s` also drops command lines | Not a report |
| **Heartbeat** | One TTY status line while logs are quiet | TTY + quiet only. Silent on a pipe or in CI | A stand-in for suppressed info logs. Clear it before a report or a warn/error |

**Console report** is the name. "Tooling output" means spawned compilers and other tools, which is the build transcript. File artefacts (Profiles HTML, coverage HTML) are not this channel.

## Quiet flags (today)

`Construct._set_verbosity_level` in `cuppa/construct.py`:

| Flag | SCons option | Cuppa logger | SCons itself |
|------|----------------|--------------|--------------|
| `-Q` | `no_progress` | `warn` | No Reading/Building lines. Commands stay |
| `-s`, `--quiet`, `--silent` | `silent` | `error` | Commands hidden as well |
| `--verbosity=LEVEL` | — | that level, and it wins over both of the above | unchanged |

That is why a mode chip emitted with `logger.info` vanishes under `-Q` while the list or cascade tree (stdout) remains. Docs that say `-Q` keeps all Cuppa output are wrong for info logs.

## Output controls (build transcript only)

Normal or terse owns the transcript. The other controls modify diagnostics,
colour, or who launches the child. They do not restyle console reports.

| Control | Spawn processor | Cuppa colour on logs and reports | Notes |
|------|-----------------|----------------------------------|-------|
| default / `--normal-output` | on, interpreted | on | today. `--normal-output` is how a command line beats a saved `--terse-output` |
| `--standard-output` | on | off | today |
| `--minimal-output` | on, errors and warnings only | on | today; needs the interpreter |
| `--terse-output` | on; success folded to one line | on | Done on master ([#353](https://github.com/ja11sop/cuppa/pull/353)). Build/test/coverage transcript only. `[progress]` checkpoints replace `Progress(...)` and stay under `-Q` |
| `--native-output` | on; diagnostic body passes through | toolchain's own colour on that body | Done on master ([#354](https://github.com/ja11sop/cuppa/pull/354)). Modifier, not a transcript. On a warning or failure, in normal or terse, show the toolchain's own lines and still count them |
| `--scons-output` | **off** | unchanged | Done on master ([#352](https://github.com/ja11sop/cuppa/pull/352)) |
| `--raw-output` | off | off | today. Implies the spawn half of `--scons-output` |

`--raw-output` bundles two switches: the colouriser stays off, and `Processor.install` is skipped so SCons' own `SPAWN` runs. People also use it to pipe a list without ANSI. `--scons-output` is only the second switch.

`--terse-output` and `--minimal-output` are refused with `--scons-output` or `--raw-output` (they need the processor). `--native-output` will be refused the same way. `--scons-output` plus `--standard-output` is the same outcome as `--raw-output`.

Even `--scons-output` is not byte-identical to bare `scons`. `NotifyProgress` still inserts `Progress(…)` nodes, and the `cuppa` wrapper still masks `*TOKEN*` on its pipe. The flag does not remove either.

## Which plan owns which channel

| Plan | Channel | Status |
|------|---------|--------|
| [`build-log-hygiene.md`](build-log-hygiene.md) | Log (which info lines exist) | Done on master |
| [`cuppa-info.md`](cuppa-info.md) | A one-line console report that exits before SCons | Done on master ([#350](https://github.com/ja11sop/cuppa/pull/350)) |
| [`console-mode-banners.md`](console-mode-banners.md) | Mode chips move from log to console report | Done on master ([#351](https://github.com/ja11sop/cuppa/pull/351)) |
| [`console-stop-error-reporting.md`](console-stop-error-reporting.md) | Options Error tree (report) plus a one-line critical log | In progress; keep that split |
| [`archive/console-report-patterns.md`](../archive/console-report-patterns.md) | Shape of console reports (judgement trees) | Shipped |
| [`quiet-tty-heartbeat.md`](quiet-tty-heartbeat.md) | Heartbeat. Done on [#356](https://github.com/ja11sop/cuppa/pull/356): logger INFO diversion + throttle under quiet+TTY | Not a report. Honour non-TTY and `NO_COLOR`. Clear before a console report. Do not treat `--raw-output` as "this is a report" |
| [`terse-build-output.md`](terse-build-output.md) | Build transcript | Phase 1 done for 1.12.0. Must not restyle lists, trees, or mode banners |
| [`terse-delegated-output.md`](terse-delegated-output.md) | Build transcript (file fields + CMake/`b2`) | Done for 1.12.0. Transform `source → product`; `delegate … [launch]` + status fields; `[done]` close; muted `→` children; `[location]` maps |
| [`native-toolchain-output.md`](native-toolchain-output.md) | Build transcript (child output only) | Done on master ([#354](https://github.com/ja11sop/cuppa/pull/354)). Must not recolour console reports |
| [`terse-dependency-locations.md`](terse-dependency-locations.md) | Build transcript (terse file cells / `[location]` maps) | Done on [#355](https://github.com/ja11sop/cuppa/pull/355). Nested `<dependencies>/<name>/…` + `[prepare]`/`[ready]` · `resolve` |
| `--scons-output` | Build transcript | Done on master ([#352](https://github.com/ja11sop/cuppa/pull/352)). No separate plan; the matrix above is the spec |
| `console-stream-split` (ROADMAP) | Which file descriptor | Orthogonal. Do not decide it inside terse or native |

## Order

1. **Mode banners** — done on master ([#351](https://github.com/ja11sop/cuppa/pull/351)). Smallest change that makes the report channel real, and the `-Q` soak bug.
2. **`--scons-output`** — done on master ([#352](https://github.com/ja11sop/cuppa/pull/352)). Split it out of `--raw-output` so the matrix exists in code before terse and native land.
3. **Terse** — done on master ([#353](https://github.com/ja11sop/cuppa/pull/353)). Transcript only, citing this matrix.
4. **Native output** — done on master ([#354](https://github.com/ja11sop/cuppa/pull/354)).
5. **Terse dependency locations** — done on [#355](https://github.com/ja11sop/cuppa/pull/355); nested maps for dependency/package trees under terse. Resolve uses a `[prepare]` / `[ready]` bookend during SCons reading; maps print live under `[prepare]`; retrieve children print after the work. Not under `[progress] · begin`.
6. **Heartbeat** — done on [#356](https://github.com/ja11sop/cuppa/pull/356): logger INFO diversion + ~0.35s throttle under quiet+TTY (off with `--terse-output` / non-TTY / `--verbosity=`). Banners and warns clear the status line.

Stream split waits until someone measures where lines go today. It is not a starter.

## Non-goals

- Implementing terse, native, heartbeat, or `--scons-output` in the mode-banner pull request.
- Turning every `logger.info` into a console report.
- Hiding console reports under `-Q` or `--verbosity`.
