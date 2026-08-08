# Shared HTTP download progress

- **Status:** proposal
- **Related:** [`ROADMAP.md`](../../ROADMAP.md) (follow-on polish after toolchains-as-deps); location archive downloads (Boost etc.); toolchain archives ([#160](https://github.com/ja11sop/cuppa/issues/160) / [#164](https://github.com/ja11sop/cuppa/pull/164)); GitLab package `wget` path
- **Updated:** 2026-08-08
- **Impact:** patch (UX / internal helper; no new public CLI flags)

Large toolchain archives (for example a ~1.6 GiB Debian `gcc-snapshot` `.deb`) currently download
with a single INFO line and then silence until completion. Location / Boost downloads already show
a custom progress bar, but it is branded for `location`, lacks size/rate/ETA, and is not reused.
This plan replaces that with one shared reporter used everywhere cuppa fetches a large HTTP file.

## Why

- Toolchain `urlretrieve` in [`toolchain_archive._download_archive`](../../cuppa/toolchains/toolchain_archive.py) has **no** `reporthook`.
- Location / Boost uses [`ReportDownloadProgress`](../../cuppa/location.py) (`|=` ticks, 10% labels on raw stdout). Usable, but not shared and weak for multi-gigabyte transfers.
- GitLab packages use `wget -nv` (tool-native progress; not on every platform).
- Conan install captures subprocess output (silence until done) — out of scope for the first slice unless we stop capturing.

## Goals

1. **One progress shape** for cuppa-owned HTTP downloads: bytes done, total if known, percent, rate, ETA.
2. **Same shape on every platform**; rendering may differ (TTY rewrite vs CI newlines) but fields stay identical.
3. **Shared helper** used by location archive downloads and toolchain archives first.
4. **Honour log level** — no progress spam when INFO is off; always keep start/complete logger lines.
5. Keep **`.partial` + rename** semantics for interrupted downloads.

## Non-goals (first slice)

- Replacing Conan’s own download UX
- Requiring `wget` / `curl` as the only downloader (optional later accelerator is fine)
- Fancy TUI libraries
- Mixing with [`cuppa.progress.NotifyProgress`](../../cuppa/progress.py) (build-phase callbacks, not HTTP)

## Settled progress shape

**TTY (interactive):** single rewriting line, throttled (~0.25–0.5 s):

```text
Downloading gcc-snapshot_20260725-1_amd64.deb  412 MiB / 1.6 GiB  (26%)  3.1 MiB/s  ETA 6m20s
```

**Non-TTY / CI:** same fields, emit a **new line** every ~5–10% or every N seconds (no `\r` spam in logs).

**Unknown `Content-Length`:** show bytes + rate only (`412 MiB downloaded  3.1 MiB/s`) — never divide by zero.

**Complete:** finish the line (or a final newline) then the existing INFO “successfully downloaded / cached” message.

## API sketch

New module, for example `cuppa/utility/download.py` (created when this ships):

```python
def download_file( url, dest_path, *, label=None, show_progress=None ):
    """Download ``url`` to ``dest_path`` (via ``.partial`` then rename).

    ``show_progress`` defaults to True when the cuppa logger is at INFO or finer
    and stderr/stdout is appropriate for progress.
    """
```

Internals:

- Prefer streaming with `urllib.request.urlopen` + chunked write (clearer than `urlretrieve` for
  progress and unknown sizes). Keep a thin compatibility path if needed.
- `ProgressReporter` class: `begin(label, total)`, `update(bytes_so_far)`, `done()`.
- Detect TTY with `sys.stderr.isatty()` (or stdout — pick one stream and stick to it; prefer
  **stderr** so progress does not interleave with redirected stdout captures).

## Call sites (phase 1)

| Caller | Today | After |
|--------|-------|-------|
| [`location.py`](../../cuppa/location.py) archive download | `ReportDownloadProgress` + `urlretrieve` | `download_file` |
| [`toolchain_archive._download_archive`](../../cuppa/toolchains/toolchain_archive.py) | bare `urlretrieve` | `download_file` |

Delete or thin-wrap `ReportDownloadProgress` once unused.

## Later (optional phases)

| Id | Work |
|----|------|
| `dl-prog-gitlab` | GitLab HTTPS package fetch via `download_file` (or pass-through when wget is preferred) |
| `dl-prog-curl` | Optional curl/wget backend when on PATH for resume/`-C -` |
| `dl-prog-conan` | Decide whether to stream Conan output instead of `capture_output=True` |

## Tests

- Unit: reporter formatting (known/unknown size, throttle, percent steps) with a fake clock / fake stream.
- Unit: `download_file` against a local `http.server` or `file://` / mocked `urlopen` writing chunks and invoking the reporter.
- Keep location / toolchain archive unit coverage green; no need for a multi-GB integration fixture.

## Docs / changelog

- Short note under location or toolchains docs that large HTTP fetches show transfer progress at INFO.
- `CHANGELOG` patch entry under Changed / Fixed (UX).
- No new CLI flags.

## Implementation order

1. Add `cuppa.utility.download` + unit tests for the reporter.
2. Switch `toolchain_archive._download_archive` (validates the gcc-snapshot case).
3. Switch location archive download; remove `ReportDownloadProgress`.
4. Docs + CHANGELOG; `impact:patch` PR.
