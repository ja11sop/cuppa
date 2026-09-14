# Plan: Metadata-only GitLab package amend / republish

- **Status:** proposal
- **Related:** [`ROADMAP.md`](../../ROADMAP.md) — `package-metadata-amend`; [`package-use-libs-defaults.md`](package-use-libs-defaults.md); [`package-download-refresh.md`](package-download-refresh.md); project **D** google-cloud-cpp soak
- **Updated:** 2026-09-14
- **Impact:** `minor` (new opt-in amend / republish path; full rebuild unchanged)

## Problem

Shipping a `cuppa-dependency.json` change (for example `default_use_libs: []` on
**google-cloud-cpp**, or correcting a dependency pin) today means a **full**
publisher rebuild: DownloadExtract → CMake configure/build/install → stage →
tarball → upload. For multi-hour packages that is disproportionate when only
Cuppa metadata changed and the binary layout is identical.

Operators already have a painful manual escape hatch: download the registry
archive, untar, edit `cuppa-dependency.json`, retar, `curl` upload. That should
be a first-class Cuppa path.

## Intent

Opt-in **metadata-only amend**: take an existing toolchain-scoped package
archive (local final/ or registry download), update traveling metadata
(`cuppa-dependency.json` / future `cuppa-publish.json`), rewrite the archive,
and optionally `--publish-package` — **without** re-running the upstream build.

## Shape (provisional)

```shell
# From a publisher tree that already has a built archive, or with explicit paths:
cuppa --rel --toolchains=gcc15 --amend-package-manifest --publish-package
```

Publisher kwargs already carry `default_use_libs`, `dependencies`, `link`. Amend
reuses `write_manifest` into a temporary extract of the existing archive (or the
staged `final/<pkg>/<ver>/` tree when present), then `create_package_archive` +
the usual publish Command (which now depends on the `.tar.gz`).

| Mode | Input | Rebuild CMake? |
|------|--------|----------------|
| **A. Stage amend** | Existing `final/<pkg>/<ver>/` + old `.tar.gz` | No — rewrite manifest, retar, publish |
| **B. Archive amend** | Only `.tar.gz` (or download from registry) | No — extract to temp, write manifest, retar |
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
- [`package-build-publish-deps.md`](package-build-publish-deps.md) — cascade
  still rebuilds when sources change; amend is the metadata shortcut

## One-off today (before Cuppa ships amend)

Until the feature lands, operators can:

1. Download `google-cloud-cpp_*_<toolchain>_….tar.gz` from the registry (or use
   the local `_build/.../final/` archive).
2. Extract; write `cuppa-dependency.json` with existing edges plus
   `"default_use_libs": []`.
3. Recreate the archive with the same basename; upload with the same generic
   package URL (same version).
4. Refresh consumer caches (`--refresh-downloads` when it exists; otherwise
   delete the extract under the dependencies root).

## Acceptance

1. Amend updates only metadata files inside the package layout.
2. Retar + `--publish-package` uploads; publish stamp depends on the archive.
3. Docs name the path clearly vs full rebuild.
4. Fat-package example: google-cloud-cpp ships explicit empty `default_use_libs`
   without a multi-hour CMake rebuild.

## Progress snapshot

| Item | State |
|------|-------|
| Problem from google-cloud-cpp / use_libs defaults | Captured |
| Provisional A/B amend modes | Captured |
| Implementation | Not started |
| Issue filed | Pending |
