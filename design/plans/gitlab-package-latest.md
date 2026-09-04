# Plan: GitLab package `latest` and consume docs

- **Status:** in progress
- **Related:** [`ROADMAP.md`](../../ROADMAP.md) — 1.10.0 packages; [`boost-updates.md`](boost-updates.md) (Boost package identity / patched-clean; source Boost latest is separate); [`archive/boost-latest-persistence.md`](../archive/boost-latest-persistence.md) (source Boost scrape persistence — not registry latest); [`archive/build-and-package-identity.md`](../archive/build-and-package-identity.md) (lookup overrides); [`run-default-dependency-objects.md`](run-default-dependency-objects.md) (`default_dependencies` accepts objects); [#209](https://github.com/ja11sop/cuppa/issues/209) (CMake publish staging — parallel)
- **Updated:** 2026-09-04
- **Impact:** minor — new `version="latest"` consume behaviour; Boost package default changes; Antora consume docs

## Why

Projects often want “whatever is newest **in this registry** for this package,” not “whatever is
newest upstream, then hope the registry has that version.”

Today:

- Generic `cuppa.package_dependency(..., version='1.2.3')` requires a concrete version.
- `boost_package.define(..., version=None|"latest")` calls `determine_latest_boost_version()`
  (boost.org / remembered source-Boost latest), then asks the GitLab registry for that version.
  The registry may not have it → configure `404`. That is a poor default for a **registry**
  package.

Lookup overrides (OS / toolchain stem, identity fallback) already say: resolve against what the
registry can serve. Registry `latest` is the version-axis complement of that story.

Antora is skewed: `gitlab.adoc` leads with Boost; the ordinary
`package_dependency` path is thin; the extension interface (`define`, `default_version`,
`use_libs`, runner hooks) is not taught as a pattern with Boost as the example.

## Goals

1. **`version = "latest"`** on GitLab `package_dependency` means: resolve to the newest version
   **available in that registry** for that package (subject to current lookup stem / overrides).
2. **Normalize `boost_package`** so `None` / `"latest"` use registry latest, not boost.org scrape.
3. **Opt-in upstream latest** for packages that can implement it, via
   `boost_package.latest_release()` (callable), not as the default for `"latest"`.
4. **Uniform failure** when latest cannot be resolved (empty registry, offline with no cache,
   unsupported token).
5. **Docs:** general GitLab depend-on first; then overrides; then `latest`; then extension
   interface with `boost_package` as the worked example; thin note on pip-installable custom
   packages. Prefer examples that pass the dependency **object** into both `dependencies` and
   `default_dependencies` once [`run-default-dependency-objects.md`](run-default-dependency-objects.md)
   lands; until then show `.name()` as the safe form.

## Non-goals

- Changing source Boost (`BuildWith('boost')`) unpinned / `--boost-latest` scrape behaviour —
  that stays under builtins Boost docs and [`boost-latest-persistence.md`](../archive/boost-latest-persistence.md).
- Implementing full `-patched` / `-clean` package identity ([`boost-updates.md`](boost-updates.md))
  in the same PR — but define how `latest` interacts (see settled decisions).
- Magic string `"latest_release"` as a generic GitLab feature (packages that need upstream
  latest expose a callable; optional later string that dispatches to that hook with uniform
  “not supported” failure).
- Full tutorial for publishing a third-party Cuppa dependency on PyPI (stub / pointer only in
  1.10.0).
- Conan `latest` (separate supply chain).

## Settled decisions

| Topic | Decision |
|-------|----------|
| `"latest"` / unpinned package version | **Registry latest**: newest version published under that GitLab generic package name that matches the current consume lookup rules (auth, OS/toolchain overrides, identity fallback). Not “latest upstream software release.” |
| `None` as version | Same as `"latest"` for GitLab packages once this lands (including `boost_package`). |
| Boost package default today | **Wrong** for registry consume. Retarget `default_version` to registry latest. Stop calling `determine_latest_boost_version` for package `latest`. |
| Upstream Boost release | Opt-in: `cuppa.packages.boost_package.latest_release()` (or equivalent) returns a concrete version string for `version=`. Callers who want “track boost.org, then fetch that from the registry” choose this explicitly and accept 404 if unpublished. |
| Magic `"latest_release"` string | **Not** in the first cut. Prefer the callable. A later well-known string may mean “invoke the package’s `latest_release` hook or fail with not supported” — never silently alias to registry `latest`. |
| How to discover registry versions | Prefer GitLab Packages API (list package versions for the project/package). Exact endpoint and pagination in implementation notes; must work with existing `GITLAB_REGISTRY_TOKEN` / `CI_JOB_TOKEN`. |
| Offline | If a previous resolve cached a concrete version for this package identity, reuse it when offline (or fail clearly if none). Do not scrape boost.org. Persistence design may mirror downloads-root scoping; do not reuse `boost_latest_version` for registry packages without a distinct key. |
| Interaction with lookup overrides | Resolve latest **among versions that have (or could have) an archive for the preferred stem**; if listing is version-only, attempt download with current stem rules and fail uniformly on 404 after fallback — document honesty if the API cannot filter by stem. |
| Interaction with `-patched` / `-clean` | Until identity lands: latest among version strings as published today. After identity: latest among versions matching the session’s package flavour (patched default for Boost). Do not block registry `latest` on identity shipping. |
| Failure shape | Configure-time StopError / clear logger error: not available, not supported, offline with no remembered version — same family of messages as missing pinned package. |
| Docs order | (1) Ordinary `package_dependency` + BuildWith; (2) lookup overrides; (3) `version="latest"`; (4) extension interface (`define`, `default_version`, `use_libs`, …) with Boost as example; (5) optional pip plugin stub. Ideal `cuppa.run` examples use the dependency object in `default_dependencies` — see [`run-default-dependency-objects.md`](run-default-dependency-objects.md). |

## Example shapes

### General GitLab package (target teach path)

```python
google_cloud_cpp = cuppa.package_dependency(
    'google_cloud_cpp',
    registry       = 'https://git.example.com/api/v4/projects/registry',
    package        = 'google-cloud-cpp',
    version        = 'latest',
    library_prefix = 'google_cloud_cpp_',
    pkg_config_dir = 'lib/pkgconfig',
)

cuppa.run(
    dependencies = [ google_cloud_cpp ],
    # Ideal (needs run-default-dependency-objects): pass the object again.
    # Today: default_dependencies = [ google_cloud_cpp.name() ]
    default_dependencies = [ google_cloud_cpp ],
)
```

Meaning: newest **registry** version of `google-cloud-cpp` for the current lookup stem.

Until [`run-default-dependency-objects.md`](run-default-dependency-objects.md) ships, sconstructs
must keep using `.name()` or a string name in `default_dependencies`. Docs for registry `latest`
should call that out and prefer `.name()` over duplicating the magic string.

### Boost package — registry latest (new default for unpinned)

```python
boost_package = cuppa.packages.boost_package.define(
    registry = 'https://git.example.com/api/v4/projects/registry',
    version  = 'latest',  # or omit; registry latest
)
```

### Boost package — opt-in upstream release then registry fetch

```python
boost_package = cuppa.packages.boost_package.define(
    registry = 'https://git.example.com/api/v4/projects/registry',
    version  = cuppa.packages.boost_package.latest_release(),
)
```

## Work slices

| ID | Slice | Notes |
|----|--------|-------|
| `pkg-latest-rules` | This plan + ROADMAP / boost-updates cross-links | **This change** |
| `pkg-latest-gitlab-api` | List/select newest version for a generic package; unit tests with mocked HTTP | |
| `pkg-latest-wire` | `package_dependency` / GitLab `default_version` honour `"latest"` / `None` | |
| `pkg-latest-boost` | Retarget `boost_package.default_version`; add `latest_release()` helper | |
| `pkg-latest-offline` | Remembered concrete version for offline reuse (scoped; not `boost_latest_version`) | Can ship with wire or immediately after |
| `pkg-latest-docs` | Restructure `packages.adoc` / `gitlab.adoc`; extension section; Boost as example | Same release; can be same PR as wire if small. Note object vs `.name()` for `default_dependencies` until run-default-dependency-objects lands |
| `pkg-latest-issue` | File GitHub issue with `impact:minor` from this plan | When starting implementation |

Related (separate plan): [`run-default-dependency-objects.md`](run-default-dependency-objects.md) —
`default_dependencies = [ google_cloud_cpp ]` without `.name()`.

## Refusal rules

- Do not keep boost.org scrape as the meaning of package `"latest"`.
- Do not treat `"latest"` as “latest upstream of the software” for generic packages.
- Do not silently map an unimplemented `"latest_release"` string to registry `"latest"`.
- Do not require `-patched` / `-clean` identity to land before registry `latest`.
- Do not expand this plan into Conan or source-Boost scrape redesign.

## Progress snapshot

| Slice | Status |
|-------|--------|
| `pkg-latest-rules` | Done |
| `pkg-latest-gitlab-api` | Done — `cuppa/package_managers/gitlab_latest.py` + unit tests |
| `pkg-latest-wire` | Done — `base.default_version` for GitLab `None` / `"latest"` |
| `pkg-latest-boost` | Done — registry latest default; `latest_release()` callable |
| `pkg-latest-offline` | Done — `gitlab_package_latest_*` remembered keys |
| `pkg-latest-docs` | Done — `packages.adoc` / `gitlab.adoc` registry-latest section |
| `pkg-latest-issue` | Pending — file when opening PR |

## Open questions (non-blocking for the plan)

- Exact GitLab API path and sorting (semver vs string sort) for “newest.”
- Whether `None` and `"latest"` both stay supported long-term or docs push `"latest"` only.
- Cache key shape for remembered registry latest (per registry URL + package name + flavour).
