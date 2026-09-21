# Plan: Metadata-only GitLab package amend / republish

- **Status:** done
- **Related:** [#299](https://github.com/ja11sop/cuppa/issues/299); [`ROADMAP.md`](../../ROADMAP.md) — `package-metadata-amend`; [`package-use-libs-defaults.md`](package-use-libs-defaults.md); [`package-download-refresh.md`](package-download-refresh.md); [`package-build-publish-deps.md`](package-build-publish-deps.md) Phase 2d; project **D** google-cloud-cpp soak
- **Updated:** 2026-09-21
- **Impact:** `minor` (new opt-in amend / republish path; full rebuild unchanged)

## Problem

Shipping a traveling metadata change (for example `default_use_libs: []` on
**google-cloud-cpp**, or correcting a dependency pin) used to mean a **full**
publisher rebuild: DownloadExtract → CMake configure/build/install → stage →
tarball → upload. For multi-hour packages that is disproportionate when only
Cuppa metadata changed and the binary layout is identical.

Operators already had a painful manual escape hatch: download the registry
archive, untar, edit the traveling JSON, retar, `curl` upload. That is now a
first-class Cuppa path.

## Intent

Opt-in **metadata-only amend**: take an existing toolchain-scoped package
archive (local final/ or registry download), update traveling metadata
(`cuppa-publish.json`), rewrite the archive, and optionally `--publish-package`
— **without** re-running the upstream build.

## Shape

```shell
# From a publisher tree that already has a built archive, or with explicit paths:
cuppa --rel --toolchains=gcc15 --amend-package-manifest --publish-package
```

Publisher kwargs already carry `default_use_libs`, `dependencies`, `link`. Amend
writes `cuppa-publish.json` into the staged `final/<pkg>/<ver>/` tree (or after
extracting the existing archive), removes any legacy `cuppa-dependency.json`
twin, then `create_package_archive` + the usual publish Command.

With `--amend-package-manifest`, `DownloadExtract`, `RemoveEmptyDirs`, and
`CMakeConfigure` / `CMakeBuild` / `CMakeInstall` register no-op stamps so the
publisher sconscript graph still links without fetching or rebuilding.

| Mode | Input | Rebuild CMake? |
|------|--------|----------------|
| **A. Stage amend** | Existing `final/<pkg>/<ver>/` + optional old `.tar.gz` | No — rewrite manifest, retar, publish |
| **B. Archive amend** | Only `.tar.gz` (or download from registry) | No — extract under `final/`, write manifest, retar |
| Full publish (today) | Sources / CMake install | Yes |

Prefer **A** when the publisher working tree still has the stage from the last
build; **B** when only the registry artefact exists (google-cloud-cpp one-off).

## Settled refusals

| Refuse | Why |
|--------|-----|
| Silently changing include/lib payloads in “metadata-only” mode | Binary drift without a real rebuild |
| Same-version upload without an explicit amend/publish flag | Accidental overwrite of registry contents |
| Requiring a full clean to change `default_use_libs` | That is the problem this plan removes |

## Couples with

- [`package-download-refresh.md`](package-download-refresh.md) — consumers must
  re-fetch after same-version overwrite
- [`package-use-libs-defaults.md`](package-use-libs-defaults.md) — primary
  motivation (`default_use_libs: []` on fat packages)
- [`package-build-publish-deps.md`](package-build-publish-deps.md) Phase **2d** —
  single traveling `cuppa-publish.json`; amend is the metadata shortcut and
  removes the legacy dependency twin on retar

## Acceptance

1. Amend updates only metadata files inside the package layout (`cuppa-publish.json`).
2. Retar + `--publish-package` uploads; publish stamp depends on the archive.
3. Docs name the path clearly vs full rebuild.
4. Fat-package example: google-cloud-cpp can ship explicit empty `default_use_libs`
   without a multi-hour CMake rebuild (private one-off after Cuppa lands).

## Progress snapshot

| Item | State |
|------|-------|
| Problem from google-cloud-cpp / use_libs defaults | Captured |
| Provisional A/B amend modes | Captured |
| `--amend-package-manifest` + `GitlabPackagePublisher.amend_package` | **Done** ([#300](https://github.com/ja11sop/cuppa/pull/300)) |
| Skip DownloadExtract / RemoveEmptyDirs / CMake under amend | **Done** |
| Unit tests + Antora + CHANGELOG | **Done** |
| Issue filed | [#299](https://github.com/ja11sop/cuppa/issues/299) |
| Single traveling file (`cuppa-publish.json`; drop twin) | Coupled to cascade Phase **2d** |
| Project D google-cloud-cpp amend soak | Parked — private one-off republish after 2d lands |
