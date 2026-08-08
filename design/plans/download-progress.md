# Shared HTTP download progress

- **Status:** in progress
- **Related:** [`ROADMAP.md`](../../ROADMAP.md) (follow-on polish after toolchains-as-deps); location archive downloads (Boost etc.); toolchain archives ([#160](https://github.com/ja11sop/cuppa/issues/160) / [#164](https://github.com/ja11sop/cuppa/pull/164)); GitLab package `wget` path
- **Updated:** 2026-08-08
- **Impact:** patch (UX / internal helper; no new public CLI flags)

Large toolchain archives (for example a ~1.6 GiB Debian `gcc-snapshot` `.deb`) used to download
with a single INFO line and then silence until completion. Location / Boost had a custom
`|=` bar that was not shared. Phase 1 lands a shared reporter for location and toolchain HTTP
fetches (`cuppa.utility.download`).

## Progress snapshot

| Item | Status |
|------|--------|
| `cuppa.utility.download` (`download_file` + `ProgressReporter`) | Done (this branch) |
| Toolchain `_download_archive` uses shared helper | Done |
| Location archive download uses shared helper; remove `ReportDownloadProgress` | Done |
| Progress on controlling tty (`/dev/tty`) so `cuppa` pipe + line masking does not force newlines | Done (this branch) |
| Toolchain extract: INFO start/elapsed + byte progress while feeding `data.tar*` to tar | Done (this branch) |
| Docs / CHANGELOG | Done |
| GitLab / Conan / curl backends | Later (`dl-prog-gitlab`, …) |

## Why

- Toolchain downloads had **no** live progress.
- Location / Boost used a location-branded `|=` bar that was weak for multi-gigabyte transfers.
- GitLab packages use `wget -nv` (tool-native; not on every platform).
- Conan install captures subprocess output — out of scope for phase 1.

## Goals

1. **One progress shape:** bytes done, total if known, percent, rate, ETA.
2. **Same shape on every platform;** TTY rewrite vs CI newlines only.
3. **Shared helper** for location archives and toolchain archives.
4. **Honour log level** — progress at INFO; keep start/complete logger lines.
5. Keep **`.partial` + rename** for interrupted downloads.

## Settled progress shape

**Interactive (controlling tty):** rewriting line (throttled), written to `/dev/tty`
(or `CONOUT$` on Windows) when available — not to piped scons stderr. The `cuppa`
launcher always pipes stdio for secret masking and consumes it with `readline`, so
stderr inside scons is never a TTY and `\r` updates would never appear if we wrote
there. The old location `|=` bar avoided mid-transfer newlines by appending without
`\n`; under the same pipe it still could stall until a newline or buffer flush.

Example:
`Downloading gcc-snapshot_….deb  412M / 1.6G  (26%)  3.1M/s  ETA 6m20s`

**Non-TTY / CI:** same fields on stderr, new line every ~5% or every few seconds.

**Unknown size:** bytes + rate only (`412M transferred  3.1M/s`).

**Extract (toolchain `.deb`):** INFO line with archive size, then the same reporter
shape with action `Extracting` while streaming `data.tar*` into `tar -xf -`, then
INFO with elapsed time.

## API

Module: `cuppa/utility/download.py` — `download_file`, `transfer_file`, and `ProgressReporter`
(controlling tty when available; stderr otherwise).

## Call sites (phase 1)

| Caller | After |
|--------|-------|
| `cuppa/location.py` archive download | `download_file` |
| `cuppa/toolchains/toolchain_archive.py` | `download_file` |

## Later

| Id | Work |
|----|------|
| `dl-prog-gitlab` | GitLab HTTPS via `download_file` |
| `dl-prog-curl` | Optional curl/wget resume backend |
| `dl-prog-conan` | Stream Conan output instead of capturing |

## Tests / docs

Unit tests for formatter, reporter throttle modes, and `download_file` against a local HTTP server.
Toolchains Antora page notes INFO transfer progress; CHANGELOG under Changed.
