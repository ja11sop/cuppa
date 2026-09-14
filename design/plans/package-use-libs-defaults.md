# Plan: Default and shared-aware `use_libs` for GitLab packages

- **Status:** in progress
- **Related:** [#294](https://github.com/ja11sop/cuppa/pull/294); [`ROADMAP.md`](../../ROADMAP.md) — `package-use-libs-defaults`; [`gitlab-package-transitive.md`](gitlab-package-transitive.md) (edge `use_libs`); [`package-build-publish-deps.md`](package-build-publish-deps.md) (`cuppa-publish.json`); [`package-metadata-amend.md`](package-metadata-amend.md) (metadata-only republish); [`package-runtime-paths.md`](../archive/package-runtime-paths.md); project **D** / `business_rules` fmt+date soak
- **Updated:** 2026-09-14
- **Impact:** `minor` (link behaviour for auto-enable / `use_libs`; opt-in metadata)

## Problem

Consuming a small shared GitLab package today forces manual link glue:

```python
env.BuildWith( 'fmt' )
env.BuildWith( 'date' )
env.AppendUnique( LIBPATH = [
    env.PackageLib( 'fmt' ),
    env.PackageLib( 'date' ),
] )
env.AppendUnique( SHAREDLIBS = [
    'fmt',
    'date-tz',
] )
```

That is the wrong layer: the **package** knows (or should know) what to link.
`AppendUnique` in every test sconscript is a last resort.

### What Cuppa does today

| Call | Includes | Runtime lib ENV | Link |
|------|----------|-----------------|------|
| Auto-enable / bare `BuildWith('pkg')` | Yes (`SYSINCPATH`) | Yes | **No** |
| `BuildWith('pkg').use_libs([...])` | Yes | (already) | **Static `.a` paths only**, unless `pkg_config_dir` is set |
| `use_all_libs()` | Yes | | Every **static** stem under `lib/` |

So:

1. **Shared-only** packages (`libfmt.so`, `libdate-tz.so`) fail `use_libs('fmt')` —
   `use_static_libs` looks for `libfmt.a` and never adds `LIBPATH` / `SHAREDLIBS`.
2. **pkg-config** helps only when `.pc` exists **and** relocates; fmt’s installed
   `.pc` still embeds the publisher’s absolute `CMAKE_INSTALL_PREFIX` → brittle
   after extract on another machine.
3. **Auto-enable** never links, so header-only “works” until the first TU needs
   `date::locate_zone` (undefined reference) — the `business_rules` soak failure.

Ideal consumer shapes:

```python
# Small packages: auto_enable alone is enough
# (sconstruct lists fmt + date in auto_enable_dependencies)

# Or explicit, still no AppendUnique:
env.BuildWith( 'fmt' ).use_libs( 'fmt' )
env.BuildWith( 'date' ).use_libs( [ 'date-tz' ] )

# Fat packages: auto_enable = headers only; opt in to what you need
env.BuildWith( 'google_cloud_cpp' ).use_libs( [ 'kms' ] )
```

## Intent

1. Make **`use_libs` do the right thing** for static *and* shared artefacts
   without hand-rolled `LIBPATH` / `SHAREDLIBS`.
2. Let packages declare a **default link set** so auto-enable / bare `BuildWith`
   can link common cases.
3. Keep **explicit `use_libs(...)` as an override** (replace, not silently union
   with “link the world”) — essential for google-cloud-cpp-scale archives.
4. Prefer **manifest metadata** over guessing; allow a **narrow heuristic** when
   metadata is missing so already-published packages improve without a republish.

## Design options

### A. Fix `use_libs` resolution only (shared + static)

`use_libs(['fmt'])` looks under `lib/` for `libfmt.a` **or** `libfmt.so*` (and
Windows equivalents). Static → `STATICLIBS` with `env.File(...)`. Shared →
`LIBPATH` + `SHAREDLIBS` (name stem). Prefer static if both exist (matches Boost
package tradition) unless the package declares `link: shared`.

**Pros:** Unblocks `use_libs('fmt')` immediately; no manifest change.  
**Cons:** Auto-enable still does not link; consumers must call `use_libs`.

### B. Default link set on auto-enable / bare `BuildWith`

Package metadata carries `default_use_libs: ["fmt"]` (or publisher kwarg). On
`initialise_build_variant`, apply that set via the same linker as A. Explicit
`use_libs([...])` **replaces** the default contribution for that package on
the env (does not append on top of defaults).

**Pros:** Matches “auto_enable and do nothing” for fmt/date.  
**Cons:** Needs replace bookkeeping; fat packages must ship **empty** defaults.

### C. Heuristic when metadata missing

If no `default_use_libs` in the manifest:

| `lib/` contents | Default |
|-----------------|--------|
| No linkable libs | `[]` (headers-only) |
| Exactly one stem | That stem |
| Multiple stems, one equals Cuppa name / package slug (`fmt`) | That stem |
| Otherwise | `[]` (refuse to guess — google-cloud-cpp) |

**Pros:** Helps already-published fmt/date without republish.  
**Cons:** Heuristics can surprise; always prefer explicit metadata when present.

### D. Rely on pkg-config only

**Refuse as sole path:** relocatable `.pc` rewriting is a separate problem and an
**upstream** packaging concern when the installed `.pc` embeds absolute
`CMAKE_INSTALL_PREFIX` (e.g. fmt). Cuppa does **not** rewrite `.pc` files.
Many packages (date) ship CMake config only. Keep pkg-config as an optional
fast path when `pkg_config_dir` is set **and** `.pc` resolves under the extract
prefix.

**Provisional preference:** **A + B**, with **C** as a bridge for packages
already in the registry; **D** optional when `.pc` is trustworthy.

## Metadata (one authoring input)

Extend the traveling publish/dependency manifest (today
`cuppa-dependency.json`; converging with `cuppa-publish.json` in
[`package-build-publish-deps.md`](package-build-publish-deps.md)):

```json
{
  "cuppa_dependency_format": 1,
  "default_use_libs": [ "fmt" ],
  "link": "prefer_static",
  "dependencies": [ … ]
}
```

| Field | Meaning |
|-------|---------|
| `default_use_libs` | Stems applied on auto-enable / bare `BuildWith`. Omit or `[]` = headers (+ runtime ENV) only |
| `link` | Optional: `prefer_static` (default) \| `prefer_shared` \| `static` \| `shared` |

Publisher API sketch:

```python
GitlabPackagePublisher(
    …,
    default_use_libs = [ 'date-tz' ],  # not 'date' (header-only interface)
    dependencies = [ … ],
)
```

Notes:

- **date:** default is `date-tz`, not `date` — the CMake `date` target is
  INTERFACE-only; requesting it as a link stem should fail clearly or be
  documented as invalid.
- **google-cloud-cpp:** `default_use_libs=[]` (or omit). Auto-enable never
  links hundreds of libs; sconscripts keep
  `BuildWith('google_cloud_cpp').use_libs(['kms', …])`.
- **nlohmann-json:** omit / `[]`.
- Transitive edges already have per-edge `use_libs` when A is *linked*; defaults
  on B still apply when B is only pulled for includes unless A’s edge lists
  `use_libs` (edge wins when applying transitive link closure — same as today).

## Replace vs append (override semantics)

Desired:

| Sequence | Result |
|----------|--------|
| Auto-enable only, `default_use_libs=['fmt']` | Link `fmt` |
| Then `use_libs(['fmt'])` | Still just `fmt` (idempotent) |
| Then `use_libs([])` | **Unlink** package defaults — headers only |
| Fat package, default `[]`, then `use_libs(['kms'])` | Link only `kms` (+ prefix rules) |
| Never call `use_libs` on fat package | Link nothing from it |

Implementation sketch:

1. Track per `(env, package_id)` the list of link contributions Cuppa added
   (`_cuppa_package_link_contrib`).
2. Applying a new set **removes** prior contribution from `STATICLIBS` /
   `SHAREDLIBS` / package-specific `LIBPATH` entries, then adds the new set.
3. `initialise` applies `default_use_libs` once (or marks pending and flushes
   before the first Program/SharedLibrary — pending is nicer if sconscripts
   always call `use_libs` immediately after `BuildWith`, but auto-enable has no
   sconscript hook; **apply-on-initialise** is the practical MVP).

## `use_libs` resolution algorithm (A)

For each requested stem `name` (after `library_prefix` rules):

1. If `pkg_config_dir` set and `.pc` usable under package dir → `ParseConfig`
   (optional; skip if prefix does not live under extract root).
2. Else search `lib/`:
   - static: `lib{name}.a` / toolchain static suffix
   - shared: `lib{name}.so` / `.dylib` / import lib patterns
3. Honour package `link` preference when both exist.
4. Missing stem → `StopError` naming package id and searched paths (do not
   silently skip — except a documented headers-only allowlist later).

`use_all_libs()` becomes “all linkable stems” (static *and* shared), still
dangerous for fat packages — docs keep the warning; defaults remain the safe
auto path.

## Phases

| Phase | Deliverable |
|-------|-------------|
| **1** | Shared-aware `use_libs` / richer `use_all_libs` (no consumer `AppendUnique`) |
| **2** | `default_use_libs` on publisher → manifest; apply on initialise; explicit `use_libs` replaces |
| **3** | Heuristic C for packages without metadata; Antora + fix fmt/date READMEs / `business_rules` sconscripts back to bare auto-enable or one-line `use_libs` |
| **Later** | Relocatable `.pc` rewrite on stage/extract (**upstream-first**; Cuppa will not invent a general rewrite unless soak proves otherwise); align with `cuppa-publish.json` schema |

## Settled refusals (for exploration)

| Refuse | Why |
|--------|-----|
| Auto-linking every stem under `lib/` for fat packages | google-cloud-cpp / Boost-scale archives |
| Manual `LIBPATH`/`SHAREDLIBS` as the documented happy path | Package should own link knowledge |
| Treating INTERFACE / header-only target names as link stems without error | Hides misconfiguration (`date` vs `date-tz`) |
| Making pkg-config mandatory | date has none; `.pc` prefixes often wrong after relocate |

## Open questions

1. **Empty `use_libs([])`:** **Settled — clear** the package's prior link contribution
   (headers / runtime ENV remain).
2. **String vs list:** `use_libs('fmt')` already Flatten-friendly; keep.
3. **Should transitive `BuildWith(B)` apply B's `default_use_libs`?** **Settled — no.**
   Apply B defaults only for primary / auto-enable (empty apply stack).
4. **Static republish vs shared:** defaults work for either once resolution is
   shared-aware; soak can stay shared.
5. **SCons `$SHLIBPREFIX`:** **Settled** — always `env.subst` lib naming vars before
   scanning `lib/` (otherwise only static `.a` stems are seen).

## Acceptance (when implemented)

1. `env.BuildWith('fmt').use_libs('fmt')` links without `AppendUnique`.
2. Auto-enable of fmt/date with `default_use_libs` (or heuristic) builds
   `business_rules` tests with **no** per-sconscript link glue.
3. Auto-enable of google-cloud-cpp does **not** link all libs; explicit
   `use_libs(['kms'])` still required.
4. Missing stem fails with a clear StopError.
5. Design index + ROADMAP + Antora packages/gitlab pages updated.

## Progress snapshot

| Item | State |
|------|-------|
| Problem from `business_rules` fmt/date soak | Captured |
| Provisional A+B (+ heuristic C) | Captured |
| Phase 1 — shared-aware `use_libs` / `use_all_libs` | Done (`package_link_libs.py`) |
| Phase 2 — `default_use_libs` / `link` on publisher + initialise replace | Done |
| Phase 3 — heuristic when metadata omitted; Antora; `business_rules` glue removed | Done |
| Explicit refusals: no Cuppa `.pc` rewrite; transitive BuildWith skips defaults | Settled |
| Issue filed | Landed on [#294](https://github.com/ja11sop/cuppa/pull/294) |
