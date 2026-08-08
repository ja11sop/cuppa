# Shared HTTP download progress

- **Status:** in progress
- **Related:** [`ROADMAP.md`](../../ROADMAP.md) (follow-on polish after toolchains-as-deps); location archive downloads (Boost etc.); toolchain archives ([#160](https://github.com/ja11sop/cuppa/issues/160) / [#164](https://github.com/ja11sop/cuppa/pull/164)); GitLab package `wget` path; [#165](https://github.com/ja11sop/cuppa/pull/165)
- **Updated:** 2026-08-08
- **Impact:** patch (UX / internal helper; no new public CLI flags)

Large toolchain archives (for example a ~1.6 GiB Debian `gcc-snapshot` `.deb`) used to download
with a single INFO line and then silence until completion. Location / Boost had a custom
`|=` bar that was not shared. Phase 1 lands a shared reporter for location and toolchain HTTP
fetches (`cuppa.utility.download`), including tty rewrite, column-stable ASCII bar, and
toolchain `.deb` extract progress.

## Progress snapshot

| Item | Status |
|------|--------|
| `cuppa.utility.download` (`download_file`, `transfer_file`, `ProgressReporter`) | Done (#165) |
| Toolchain `_download_archive` uses shared helper | Done (#165) |
| Location archive download uses shared helper; remove `ReportDownloadProgress` | Done (#165) |
| Progress on controlling tty (`/dev/tty`) so `cuppa` pipe + line masking does not force newlines | Done (#165) |
| Settled line shape: percent, ASCII bar, `done/total`, rate, ETA + colour rules | Done (#165) |
| Toolchain `.deb` extract: INFO start/elapsed + `transfer_file` into `tar` | Done (#165) |
| Docs / CHANGELOG (phase 1) | Done (#165) |
| `dl-prog-extract` — shared tar extract helper for `Location.extract` + GitLab package tars | Done (this branch / #165) |
| `dl-prog-gitlab` — GitLab HTTPS via `download_file` + auth headers (replace `wget`) | Done (this branch / #165) |
| `dl-prog-zip` — zip extract progress (`Location.extract` / package zips) | After GitLab download |
| `dl-prog-conan` — stream Conan install output instead of capturing | Later |
| `dl-prog-git` — stream git clone/fetch `--progress` | Later |
| `dl-prog-curl` — optional curl/wget resume backend | Optional / later |

## Why

- Toolchain downloads had **no** live progress.
- Location / Boost used a location-branded `|=` bar that was weak for multi-gigabyte transfers.
- After a progressed download, **extraction** is often still silent (Boost tarballs, GitLab package archives, non-`.deb` toolchains).
- GitLab package fetch used `wget -nv` (not on every platform; no shared bar) — now
  `download_file` + auth headers.
- Conan install captures subprocess output — not a byte-transfer problem.
- Git clone/fetch buffers subprocess output — git’s own progress is enough if streamed.

## Goals

1. **One progress shape** for cuppa-owned byte transfers: percent, bar, done/total, rate, ETA.
2. **Same shape on every platform;** TTY rewrite vs CI newlines only.
3. **Shared helpers** for HTTP download and archive byte streaming (`download_file`, `transfer_file`).
4. **Honour log level** — progress at INFO; keep start/complete logger lines.
5. Keep **`.partial` + rename** for interrupted downloads.
6. **Subprocess tools** (Conan, git) stream their own output; do not invent a fake byte bar.

## Settled progress shape

**Interactive (controlling tty):** rewriting line (throttled), written to `/dev/tty`
(or `CONOUT$` on Windows) when available — not to piped scons stderr. The `cuppa`
launcher always pipes stdio for secret masking and consumes it with `readline`, so
stderr inside scons is never a TTY and `\r` updates would never appear if we wrote
there. The old location `|=` bar avoided mid-transfer newlines by appending without
`\n`; under the same pipe it still could stall until a newline or buffer flush.

Example (fixed-width percent, 20-cell ASCII bar, `done/total`, rate, ETA; percent
and bar glyphs are emphasised info; target size is emphasised only; transferred
size is info and becomes emphasised at 100%; brackets plain; rate subdued):
`Downloading gcc-snapshot_….deb  26% [=====>              ]   412M/1.6G   3.1M/s  ETA 6m20s`

**Non-TTY / CI:** same fields on stderr, new line every ~5% or every few seconds.

**Unknown size:** bytes + rate only (`412M transferred  3.1M/s`) — no bar.

**Extract:** INFO line with archive size, then the same reporter shape with action
`Extracting` while streaming archive bytes into `tar`, then INFO with elapsed time.

## API

Module: `cuppa/utility/download.py` — `download_file`, `transfer_file`, and `ProgressReporter`
(controlling tty when available; stderr otherwise).

Phase 2+ extensions (when each slice lands):

- `download_file(..., headers=None)` for GitLab `PRIVATE-TOKEN` / `JOB-TOKEN`.
- `extract_tar_archive` / `tar_stdin_argv` — stream archive bytes into `tar -x*f -`
  (falls back to `tarfile` when `tar` is missing).
- GitLab: `registry_auth_headers` / `download_registry_package` (token registered for masking;
  never logged on the progress line).

## Call sites (phase 1)

| Caller | After |
|--------|-------|
| `cuppa/location.py` archive download | `download_file` |
| `cuppa/location.py` `Location.extract` (tar) | `extract_tar_archive` |
| `cuppa/package_managers/gitlab.py` `extract_package_archive` (tar) | `extract_tar_archive` |
| `cuppa/toolchains/toolchain_archive.py` download | `download_file` |
| `cuppa/toolchains/toolchain_archive.py` `.deb` / non-`.deb` extract | `extract_tar_archive` / `Location.extract` |
| `cuppa/package_managers/gitlab.py` package download | `download_registry_package` → `download_file` + headers |

## Phases (ordered)

| Id | Work | Mechanism | Notes |
|----|------|-----------|-------|
| Phase 1 | Location + toolchain HTTP download; `.deb` extract; settled line/colour | `download_file` / `transfer_file` | Done on #165 |
| `dl-prog-extract` | `Location.extract` tar path; GitLab `extract_package_archive` tar path; toolchain non-`.deb` via `Location.extract` | Shared tar helper + `transfer_file` | Done on #165 |
| `dl-prog-gitlab` | `GitlabPackageDependency` + `GitlabPackageInstaller` download | `download_file` + headers; drop `wget` for the fetch | Done on #165 |
| `dl-prog-zip` | Zip extract in `Location.extract` / package zips | Per-member or external `unzip` with progress | Harder than tar; after GitLab download |
| `dl-prog-conan` | Conan consumer install | Stream subprocess (no `capture_output`) or parse live | Not a `ProgressReporter` byte bar |
| `dl-prog-git` | Git clone/fetch (location, develop) | Stream git with `--progress` via existing subprocess helpers | Not a fake byte bar |
| `dl-prog-curl` | Optional resume backend | curl/wget under `download_file` | Only if partial/resume becomes a real need |

## Settled decisions (phase 2+)

| Topic | Decision |
|-------|----------|
| Order | extract → GitLab download → zip → Conan → git (curl optional) |
| Extract helper | One shared tar-from-path helper used by location, GitLab packages, and toolchain non-`.deb`; mirror the `.deb` `transfer_file` → `tar -x*f -` pattern |
| Compression flags | Choose `tar` stdin flags from the archive suffix (same idea as `_tar_stdin_command` for `.deb`) |
| Zip | Explicit later slice (`dl-prog-zip`); do not block tar extract on zip |
| GitLab auth | Extend `download_file` with optional headers; do not put tokens on the progress line; launcher masking unchanged |
| Conan / git | Stream tool output; refuse inventing cuppa percent bars over opaque subprocess work |
| Out of scope | Tiny HTTP probes (Boost version HTML, PyPI check), publish/upload paths, local `copytree`, b2 (already streams) |
| Impact | Stay **patch** while there are no new public CLI flags |

## Refusal rules

- Do not replace Conan or git with a cuppa byte bar that guesses progress.
- Do not leave secrets in progress labels or logger lines.
- Do not require `wget`/`curl` on PATH for the GitLab fetch once `dl-prog-gitlab` lands (stdlib HTTP + headers).
- Do not expand zip progress into the first extract PR.

## Tests / docs

Phase 1: unit tests for formatter, bar states, reporter throttle modes, `download_file` /
`transfer_file` against local fixtures; toolchains Antora notes INFO transfer progress;
CHANGELOG under Changed.

Later slices: unit tests for header download and tar extract helper; dependency/package
docs only where user-visible fetch behaviour changes.
