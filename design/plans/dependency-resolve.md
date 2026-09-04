# Plan: BuildWith dependency resolve and type selectors

- **Status:** in progress
- **Related:** [`ROADMAP.md`](../../ROADMAP.md) — Dependencies; [`boost-updates.md`](boost-updates.md) (Boost identity / Quince motivation); [`removal-options.md`](removal-options.md) §4.15 (storage token grammar already shipped); [#250](https://github.com/ja11sop/cuppa/issues/250) (Quince first consumer); [#206](https://github.com/ja11sop/cuppa/issues/206) / [#248](https://github.com/ja11sop/cuppa/issues/248) (package-only must not pull source Boost); scratchpad note graduated from [`ideas/scratchpad.md`](../ideas/scratchpad.md)
- **Updated:** 2026-09-04
- **Impact:** minor — new opt-in resolve behaviour for untyped `BuildWith` names when multiple supply chains exist; Quince and runners become consumers

## Why

Cuppa already has two overlapping stories:

1. **Uniform link API** — `env.BuildWith('…').use_libs([...])` so the dependency owns transitive
   libs, ordering, and version-specific drops (e.g. Boost `system` ≥ 1.89). Documented for source
   Boost and `boost_package`; some built-ins (Quince) still call `BoostStaticLibs` / manual
   `STATICLIBS`.
2. **Type selectors** — `[source]` / `[archive]`, `[gitlab]`, `[repository]`, `[conan]` on the
   **storage** list/remove/purge surface ([`removal-options.md`](removal-options.md)). The same
   vocabulary is **not** yet used when resolving `BuildWith('boost')`.

Boost makes the gap concrete: the built-in archive factory is always registered as `boost`, while
projects register GitLab Boost as `boost_package` to avoid the name clash. Quince and similar
built-ins only know the short name “boost”; they must not hard-code `boost_package` vs `boost`.
A Quince-local `session_boost` / `uses_boost_package` fork would fix one symptom and encode the
wrong abstraction (superseded spike on branch work for [#250](https://github.com/ja11sop/cuppa/issues/250)).

This plan is the home for **BuildWith-time** resolve rules and selectors. Boost package
`-patched` / `-clean` identity stays in [`boost-updates.md`](boost-updates.md).

## Goals

1. **Untyped short names resolve by precedence** among project-available candidates of different
   supply-chain types (GitLab package before archive for Boost-shaped cases).
2. **Explicit type selectors** pin a supply chain: `[gitlab]boost`, `[archive]boost`, etc.
3. **Legacy registry names** remain usable (`boost_package` as a known GitLab Boost identity).
4. **`use_libs` is the link path** for dependents that need libraries from a resolved dependency.
5. **Quince is the first worked example** — only `BuildWith('boost')` + `use_libs`; Cuppa chooses
   the flavour.
6. **Same resolver** for Boost.Test runners (replace or thin-wrap today’s `session_boost()`).

## Non-goals

- Requiring type selectors on every `BuildWith` (untyped names stay valid).
- Selecting `[conan]…` for untyped short names until Conan deps expose the same APIs (`use_libs`,
  version helpers) — see [`archive/conan-consumer-plan.md`](../archive/conan-consumer-plan.md).
- Renaming the Python API `location_dependency` or changing storage bucket labels.
- Auto-registering GitLab packages under the short name `boost` without selectors (name clash with
  the built-in remains until typed registration exists).
- Broader “explicit import only” / `cuppa.import_dependencies` (scratchpad longer-term idea;
  not this slice).

## Settled decisions

| Topic | Decision |
|-------|----------|
| Link API | Dependents that need libraries call `BuildWith(<name>).use_libs([...])` (or `use_libs` on the instance `BuildWith` returned). No `BoostStaticLibs` / manual Boost `STATICLIBS` in Quince. |
| What Quince knows | Only that it needs “boost” and which logical libs it wants. It does not branch on archive vs GitLab vs legacy package name. |
| Untyped precedence (general) | For any short name `N`, among **project-available** candidates try in order: `[gitlab]N` (typed registry key, when used) → legacy `{N}_package` → short name / `[archive]N` / `[source]N`. Final fallback: short name `N` if present in the factory registry (covers always-on built-ins such as `boost`). |
| Legacy `{N}_package` | **General** GitLab naming convention when the short name is already taken (Boost’s `boost_package` is the motivating case, not a Boost-only rule). Prefer retiring it once packages register under `[gitlab]N`. |
| Explicit tokens | `[gitlab]N`, `[archive]N` / `[source]N`, or literal `{N}_package` bypass untyped precedence. `[gitlab]N` maps to `[gitlab]N` or `{N}_package`, not to an always-on built-in short name. |
| Conan | Never chosen for untyped short names until Conan deps share the link/version API. Explicit `[conan]…` errors for now. |
| Project-available | Declared (`dependencies=` / `default_dependencies`) **or** already `BuildWith`’d earlier in this sconscript session (`BUILD_WITH`). |
| Always-registered built-ins | e.g. built-in `boost`: registry presence alone is not project-available and does not beat a project-available GitLab candidate. |
| Selector spelling | Align with storage grammar ([`removal-options.md`](removal-options.md) §4.15). |
| Test runners | Same resolve helper as `BuildWith`. |
| First consumer | Quince on [#250](https://github.com/ja11sop/cuppa/issues/250); unit tests cover a generic `widget_lib` / `widget_lib_package` pair as well as Boost. |
| Docs | Antora precedence table is name-general; Quince is the worked example. |

## Vocabulary

| Term | Meaning |
|------|---------|
| **Factory registry** | `env['dependencies']` — factories Cuppa knows about (includes always-on built-ins). |
| **Project-available** | Declared by the project and/or already `BuildWith`’d on this env in the session (see table). |
| **Untyped name** | `boost`, `widget_lib` — no `[selector]` prefix. |
| **Typed token** | `[gitlab]boost`, `[archive]widget_lib`, … |
| **Legacy alias** | Registry key `{name}_package` treated as GitLab for that short name (e.g. `boost_package`). |

Storage list/remove tokens and BuildWith tokens should **mean the same selectors**; implementation
may share the parser already used for wipe/remove.

## Quince shape after this lands

```python
def update_env( env ):
    env.BuildWith( 'boost' )

# when linking
env.BuildWith( 'boost' ).use_libs( [ 'filesystem', 'thread', 'system' ] )
# backends: use_libs( [ 'date_time', ... ] ) as today logically requires
```

Boost’s `use_libs` owns dependents, ordering, and dropping `system` when version ≥ 1.89.
Quince does not call `ensure_session_boost` / `append_session_boost_static_libs` / package-vs-source
branches.

## Work slices

| ID | Slice | Notes |
|----|--------|-------|
| `dep-resolve-rules` | This document’s settled table + ROADMAP / boost-updates cross-links | **This change** |
| `dep-resolve-helper` | Shared resolve(name) used by `BuildWith` and runners; unit tests for precedence, `BUILD_WITH` availability, explicit selectors, Conan refusal | Implementation |
| `dep-resolve-buildwith` | `BuildWith` accepts typed tokens; untyped uses helper | |
| `dep-resolve-runners` | Point `session_boost` at helper or replace call sites | Closes parallel Boost-only policy |
| `dep-resolve-quince` | Quince → `BuildWith('boost').use_libs(...)` only | [#250](https://github.com/ja11sop/cuppa/issues/250) |
| `dep-resolve-docs` | Antora BuildWith / dependencies + quince stub | Same PR as Quince or immediately after |

Optional later: register GitLab Boost as `[gitlab]boost` without requiring the `boost_package`
legacy key; explicit-import-only built-ins (scratchpad).

## Refusal rules

- Do not teach Quince (or new built-ins) to branch on `boost_package` vs `boost`.
- Do not leave source path on `BoostStaticLibs` while package path uses `use_libs`.
- Do not treat “factory key present in the registry” as project-available for always-on built-ins
  when a GitLab candidate is also project-available.
- Do not select Conan for untyped short names in the first implementation.
- Do not invent a third Boost session helper; extend resolve once and reuse.

## Progress snapshot

| Slice | Status |
|-------|--------|
| `dep-resolve-rules` | Done (this plan) |
| `dep-resolve-helper` | Done — general name precedence in `cuppa/core/dependency_resolve.py` (not Boost-only) |
| `dep-resolve-buildwith` | Done — `BuildWith` uses resolve |
| `dep-resolve-runners` | Done — `session_boost` uses resolve |
| `dep-resolve-quince` | Done — `use_libs` only ([#250](https://github.com/ja11sop/cuppa/issues/250)) |
| `dep-resolve-docs` | Done — quince stub + methods page |

**Superseded:** Quince-local `uses_boost_package` / `ensure_session_boost` /
`append_session_boost_static_libs` approach drafted against [#250](https://github.com/ja11sop/cuppa/issues/250)
before this plan — do not merge that shape.

## Open questions (non-blocking)

- Exact error text when untyped `N` has **no** factory candidate.
- When packages routinely register under `[gitlab]N`, deprecate accepting new `{N}_package`
  registrations (keep resolve for compatibility).
- Whether more built-ins than `boost` need the always-on availability exception list.
