# Download / extract acquire helpers (general, not CMake-specific)

- **Status:** shipped
- **Related:** [`ROADMAP.md`](../../ROADMAP.md) — 1.11.0; [`cmake-drive-and-package-staging.md`](../plans/cmake-drive-and-package-staging.md); [`package-runtime-paths.md`](package-runtime-paths.md); [`download-progress.md`](download-progress.md)
- **Updated:** 2026-09-13
- **Impact:** `minor` (new `env.DownloadExtract`; relocate `RemoveEmptyDirs` / `remove_empty_dirs` to acquire)

## Problem

Publisher sconscripts repeat the same wget + tar plumbing before
`CMakeConfigure` (protobuf, gRPC, OpenTelemetry, google-cloud-cpp, …). That
block:

- duplicates path math (`build_dir`, `Dir`, basename)
- uses raw `wget` / `tar` shell strings (no Cuppa download progress; same
  `shlex` footgun class as ad-hoc patch commands)
- obscures the real publisher story (acquire → optional empty-dir cleanup →
  drive build → publish)

Separately, `env.RemoveEmptyDirs` / `cuppa.buildsys.cmake.remove_empty_dirs`
landed next to Option C CMake methods. The **operation** is filesystem /
archive staging, not CMake — only the first soak was a CMake `NOT EXISTS`
download gate (gRPC). Names that stay general are fine; **placement** under
`buildsys.cmake` / `methods.cmake` over-associates them with CMake.

## Settled decisions

| Topic | Decision |
|-------|----------|
| Naming | Keep **general** names: `DownloadExtract`, `RemoveEmptyDirs`. Do **not** prefix `CMake…`. |
| Generality | These are **acquire / staging** facilities that CMake (and later b2 / Meson) publishers compose with. |
| Home | `cuppa.buildsys.acquire` (pure helpers) + `cuppa.methods.acquire` (`env.*` methods). |
| CMake module | `cuppa.buildsys.cmake` / `methods.cmake` keep configure/build/install + RPATH helpers only. Re-export `remove_empty_dirs` from `cmake` for one cycle so existing imports do not break. |
| Download | Use `cuppa.utility.download.download_file` (progress, `.partial`). No raw `wget` in the method. |
| Extract | Use `extract_tar_archive` / `extract_zip_archive`, then flatten top directory `strip_components` times (same idea as `Location.extract`). Default `strip_components=1` for GitHub-style archives. |
| v1 scope | HTTP(S) URL → archive on disk → extract into `extract_dir` → marker stamp. No git-clone mode. |
| Refuse | Turning `DownloadExtract` into a location dependency; baking CMake marker defaults into the method name. |

## API sketch

```python
extracted = env.DownloadExtract(
    'https://github.com/grpc/grpc/archive/v1.84.0.tar.gz',
    extract_dir='grpc',
    marker='CMakeLists.txt',   # target under extract_dir
    strip_components=1,        # default
)
# Clean(extract_dir); feed extracted into RemoveEmptyDirs / CMakeConfigure

archives = env.RemoveEmptyDirs(
    extracted,
    parent=os.path.join(working, 'third_party'),
    gitmodules=True,
)
```

Optional: `archive=` basename override when the URL path is not a useful filename.

## Work slices

| ID | Deliverable |
|----|-------------|
| `acquire-plan` | This plan + design README / cmake-drive pointer |
| `acquire-module` | Move `remove_empty_dirs` (+ gitmodules helpers) to `buildsys.acquire`; re-export from `cmake` |
| `download-extract` | `env.DownloadExtract` + unit tests |
| `docs-changelog` | Packages Antora pattern; method index; CHANGELOG |
| `adopt-private` | Switch Clearpool publisher sconscripts (protobuf, grpc, otel, cloud-cpp) |

## Progress snapshot

| Item | State |
|------|--------|
| Settled naming / placement | **Done** |
| `buildsys.acquire` + method move | **Done** |
| `DownloadExtract` | **Done** |
| Docs / tests | **Done** |
| Private adopt (protobuf / grpc / otel / cloud-cpp) | **Done** |
