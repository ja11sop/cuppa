# Plan: Boost source and package updates

- **Status:** proposal
- **Related:** [`ROADMAP.md`](../../ROADMAP.md) — Boost source and packages; [#206](https://github.com/ja11sop/cuppa/issues/206) (package-only builds must not pull source Boost); [#248](https://github.com/ja11sop/cuppa/issues/248) (test runners must not pull source Boost); [#250](https://github.com/ja11sop/cuppa/issues/250) / [`dependency-resolve.md`](dependency-resolve.md) (Quince + BuildWith resolve); storage listing/removal stays in [`removal-options.md`](removal-options.md); offline “latest” persistence is [`boost-latest-persistence.md`](../archive/boost-latest-persistence.md) (separate)
- **Updated:** 2026-09-04

Source `boost` (b2 / extract homes) and GitLab `boost_package` share Boost.Test patch semantics
but not storage identity. This plan is the home for those Boost-specific follow-ups. List /
remove / purge / a future wipe mode stay in [`removal-options.md`](removal-options.md).

## Why

In the projects that publish and consume prebuilt Boost, **patched is the normal package**.
That is why `boost_package.define(..., patched=True)` defaults to on. Source Boost is the other
way around: `clean/` unless `--boost-patched`.

Today a GitLab Boost tarball does not say which it is. Archive name, extract path, download
cache, and `package_id` are all `boost` + version + tool variant. A clean build and a patched
build collide. Cuppa only remembers `patched` as a wrapper flag for a define and a test-runner
hook, so listing, remove, purge, and a later wipe cannot tell them apart.

We need the **package identity itself** (name and/or version) to carry patch status, so behaviour
and storage stay aligned.

### Immediate symptom ([#206](https://github.com/ja11sop/cuppa/issues/206))

Projects that declare **only** GitLab `boost_package` still hit **built-in source Boost** during
configure when something invokes the `boost` factory. The sharpest accidental trigger (fixed on
branch `fix-boost-package-use-libs-206`) was `boost_package.use_libs()` calling
`remove_system_static_lib()`, which invoked the built-in `boost` factory via
`env['dependencies']['boost']` only to learn
whether Boost ≥ 1.89 so `system` can be dropped from the static lib list. That downloaded or
re-extracted the full `archives.boost.io` source tree (~224 MB) even though linking used prebuilt
`.a` files from the GitLab package.

**Quince** is the same class of problem deliberately: built-ins hardcode `env.BuildWith('boost')`
and `env.BoostStaticLibs(…)` (see [§Quince and the selector gap](#boost-quince-selector-gap)).
Any project using `boost_package` for its own tests **and** Quince for DB access pays **both**
supply chains until untyped `BuildWith('boost')` resolves by precedence — see
[`dependency-resolve.md`](dependency-resolve.md).

That is why “name clash” is not only a **list/remove** UX issue — it is a **resolve** bug when
two registered names (`boost` built-in vs `boost_package`) both mean “Boost” but only one was
intended.

<a id="boost-quince-selector-gap"></a>

## Quince and the selector gap

**Concrete example** for cross-type BuildWith resolve
([`dependency-resolve.md`](dependency-resolve.md) — canonical plan).

Quince is a built-in location dependency (`cuppa/dependencies/build_with_quince.py`). Today it has
**no** awareness of which Boost supply chain the project chose:

| Built-in | Hard-coded Boost use |
|----------|----------------------|
| `build_with_quince` | `update_env` → `env.BuildWith('boost')`; `__call__` → built-in `boost` factory + `env.BoostStaticLibs([…])` |
| `quince_postgresql` | Same `BuildWith('boost')` in `update_env`; `BoostStaticLibs(['date_time'])` |
| `quince_sqlite` | Same pattern |

Effects when a sconstruct declares `boost_package` in `dependencies=[…]` and `default_dependencies`
but also `BuildWith('quince')` (or quince in `default_dependencies`):

1. **GitLab package** — headers/libs from the registry tarball (expected).
2. **Source Boost** — tarball extract under `dependencies_root`, b2 bootstrap, and b2 build of
   `filesystem`, `thread`, `system` (or subset), **duplicate** of libraries already in the package.
3. **Version skew** — Quince reads numeric version from the **source** `boost` factory, not from
   `boost_package._version`; unpinned/latest on either side can diverge silently.

**Direction (not a Quince-only fork):**

- Untyped `BuildWith('boost')` resolves by precedence among project-available candidates
  (GitLab / legacy `boost_package` before archive). See
  [`dependency-resolve.md`](dependency-resolve.md) settled decisions.
- Quince links only via `BuildWith('boost').use_libs([...])` — same API as sconscripts.
- Test runners already prefer package via `session_boost()` ([#249](https://github.com/ja11sop/cuppa/pull/249));
  that helper should share the same resolver.

Tracking issue for the Quince consumer slice:
[#250](https://github.com/ja11sop/cuppa/issues/250).

<a id="boost-type-selectors"></a>

## Today

### Source `boost`

| Piece | Behaviour |
|-------|-----------|
| `--boost-patched` (alias `--boost-patch-boost-test`) | Selects `patched/` instead of `clean/` under one extract |
| Build / `--remove-dependencies` / `--purge-dependencies` | Touch only the active home; the other home is leftover |
| `patched_test()` | True when the home has cuppa's Boost.Test patch applied |
| `use_libs` / b2 | Passes `patched_test=` into `add_dependent_libraries` (`timer` / `chrono` for Boost.Test) |

### GitLab `boost_package`

| Piece | Behaviour |
|-------|-----------|
| `define(..., patched=True)` | Default **True** (intentional: publishers always patch) |
| `_patched` | Adds `-DBOOST_TEST_USE_QUALIFIED_COMMANDLINE_ARGUMENTS`; `patched_test()` for runners |
| `--boost-patched` | Not read. Package flavour is fixed at `define()` time |
| Archive | `boost_{os}_{toolchain}_{variant}_{arch}_{abi}.tar.gz` — no patch token |
| Extract | `<tool_variant>/boost/<version>/` — no patch token |
| Download cache | `downloads/packages/boost/<version>/…` — no patch token |
| `package_id` | `(registry, package, version, variant, develop, tool_variant)` — no `_patched` |
| Publisher / installer | Same naming helpers; `_patched` is never forwarded |
| `use_libs` | Passes package version into `remove_system_static_lib` (≥ 1.89 drops `system` without invoking source `boost`) — [#206](https://github.com/ja11sop/cuppa/issues/206); still does **not** pass `patched_test=` into `add_dependent_libraries` |

Collision: last publish or extract wins. Listing shows `boost_package  1.91` either way.

## Goals

1. **Observable identity** — from the registry name and/or version string, a human and cuppa can
   tell a patched package from a clean one.
2. **Behaviour follows identity** — defines, test runner, and library dependency set match the
   artefact that was actually resolved.
3. **Patched stays the package default** — `define()` without `patched=` keeps today's meaning.
4. **Publish and consume agree** — `GitlabPackagePublisher` emits the same identity consumers
   resolve.
5. **Compat with unadorned patched tarballs** — registries that already publish patched Boost as
   plain `boost` / `1.91` must keep working until they republish.

## Non-goals

- Using `--boost-patched` as a GitLab package selector in the first slice (different supply
  chain; optional later).
- Changing source Boost's clean-by-default extract layout.
- Splitting source Boost into two downloads (still one tarball, two homes).
- Auto-wiping extracts or renaming `--purge-*` (see removal-options; future wipe mode).
- Requiring every non-Boost GitLab package to grow a patch axis.

## Recommended identity: version suffix

Keep the GitLab **package** name `boost`. Put flavour on the **version** cuppa already shows as
the qualifier:

| Flavour | Canonical version | Example extract / cache |
|---------|-------------------|-------------------------|
| Patched (default) | `{base}-patched` | `…/boost/1.91-patched/` and `downloads/packages/boost/1.91-patched/` |
| Clean | `{base}-clean` | `…/boost/1.91-clean/` |

Listing, remove, and purge then show `boost_package  1.91-patched` with no extra column.

Archive stem can stay `boost_{os}_{tool_variant}` **inside** that version folder. The version
directory is what prevents collision. Optionally also tag the stem (`…_patched`) later for
eyeballing a lone tarball; that is not required if version folders are correct.

### Why not package name `boost_patched`

Two registry packages (`boost` vs `boost_patched`) also work and are very visible in the GitLab
UI. Cost: every `define(package='boost')`, publisher call, and listing short-name heuristic
changes, and existing `packages/boost/…` caches do not line up. Version suffix keeps one
registry package and matches the qualifier we already print.

Revisit package-name split only if a registry cannot host two versions of `boost` side by side
(unlikely for GitLab generic packages).

### Why not archive-stem-only

Changing only the tarball basename while leaving extract at
`<tool_variant>/boost/<version>/` still collides on disk. Stem tags are optional decoration,
not sufficient identity.

## Resolve and publish rules

`numeric_version()` / `default_version()` / `float(version)` must strip a trailing `-patched`
or `-clean` before numeric use. Callers that need the storage version keep the full string.

**Patched (`patched=True`, the default)**

1. Request `{base}-patched`.
2. If missing (404 / not cached), fall back to bare `{base}` (legacy unadorned patched
   publishes).
3. Inventory and reports record **whichever version was actually used**.

**Clean (`patched=False`)**

1. Request `{base}-clean` only.
2. **Do not** fall back to bare `{base}`. Legacy bare tarballs in these codebases are patched;
   a clean consumer must not silently link them.

**Publisher**

When packaging a patched Boost tree, publish under `{base}-patched`. Clean publishes under
`{base}-clean`. Stop publishing new artefacts as bare `{base}` once consumers understand the
suffix (legacy fallback can remain for a release or two).

`define(version='1.91')` plus default `patched=True` means “base 1.91, patched flavour”, not
“refuse the suffix”. Passing `version='1.91-patched'` explicitly is also valid and should not
double-suffix.

## Behaviour that must follow identity

Once the resolved version (or an explicit `patched=` / suffix) is known:

- Wrapper `_patched` matches the artefact (True for `-patched` or legacy bare fallback).
- Compile define `-DBOOST_TEST_USE_QUALIFIED_COMMANDLINE_ARGUMENTS` stays gated on that.
- `patched_test()` stays in sync for `boost` / `patched_boost` runners.
- `boost_package.use_libs` passes `patched_test=` into `add_dependent_libraries` (parity with
  source Boost).
- `GitlabPackageDependency.package_id` / storage qualifier use the **resolved** version string
  so multi-flavour caches do not share one instance.

`--boost-patched` remains a **source Boost** selection axis. It does not switch `boost_package`
in this slice. A later optional hook: if a project declares both flavours, the flag could pick
which `define()` is active — only if someone needs both in one sconstruct.

## Source Boost notes (same plan, different slice)

Already shipped on the listing/removal branch:

- `--boost-patched` as the real name; `--boost-patch-boost-test` deprecated alias.
- Remove/purge reports nest under `[E]`; empty `bin.<abi>` husks hidden; other home is leftover.

Still in this plan if we touch source Boost again:

- Docs: `packages.adoc` should state the package default is patched, and that source Boost is
  clean unless flagged — opposite defaults, same patch *content*.
- Do not pretend `--boost-patched` changes a GitLab extract path.

## Work slices

| ID | Slice | Notes |
|----|--------|-------|
| `boost-use-libs-no-source` | `boost_package.use_libs` must not invoke source `boost` factory | **Shipped** — [#206](https://github.com/ja11sop/cuppa/issues/206) / [#207](https://github.com/ja11sop/cuppa/pull/207): pass package version to `remove_system_static_lib` |
| `boost-test-runner-no-source` | Test runners must not instantiate source `boost` when `boost_package` is declared | **Shipped** — [#249](https://github.com/ja11sop/cuppa/pull/249) / [#248](https://github.com/ja11sop/cuppa/issues/248): `session_boost()`; serialise source location cache |
| `boost-quince-package` | Quince uses session Boost via shared BuildWith resolve + `use_libs` | **Done** in [`dependency-resolve.md`](dependency-resolve.md) / [#250](https://github.com/ja11sop/cuppa/issues/250) |
| `boost-pkg-version` | Canonical `{base}-patched` / `{base}-clean`; strip suffix for numeric version; publisher + resolve + `package_id` | Core identity |
| `boost-pkg-compat` | Patched resolve falls back to bare `{base}`; record actual version; no clean→bare fallback | Needed before flipping publishers |
| `boost-pkg-use-libs` | Pass `patched_test=` from package `use_libs` | Small, can ship with identity or just before |
| `boost-pkg-docs` | `packages.adoc`, `dependencies.adoc`, CLI: identity, defaults, compat | Same PR as identity if small |
| `boost-pkg-list-tests` | Unit + integration: two flavours on disk, list/remove/purge select the right tree | Plant `-patched` and `-clean` folders |
| `boost-src-docs` | Cross-link source vs package defaults (if not covered in `boost-pkg-docs`) | Low |
| `boost-pkg-flag` | Optional later: `--boost-patched` selects among declared package flavours | Not in the first PR |

## Related observation: type selectors for name clashes

BuildWith-time type selectors and untyped precedence are specified in
[`dependency-resolve.md`](dependency-resolve.md). Storage list/remove/purge already uses the same
selector spelling ([`removal-options.md`](removal-options.md) §4.15).

Boost remains the sharpest case (`boost` archive vs GitLab `boost_package`). Quince is the
motivating built-in consumer — see [§Quince and the selector gap](#boost-quince-selector-gap).

## Suggested first PR

`boost-pkg-version` + `boost-pkg-compat` + `boost-pkg-use-libs` + docs/tests.

Leave `boost-pkg-flag` and wipe/purge naming alone.

## Open decision (confirm before coding)

Version suffix as above vs registry package name `boost_patched`. This plan assumes **version
suffix** unless we hit a registry constraint.
