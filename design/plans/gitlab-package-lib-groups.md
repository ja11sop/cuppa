# Plan: GitLab package named library groups

- **Status:** in progress
- **Related:** [`gitlab-package-transitive.md`](../archive/gitlab-package-transitive.md) (MVP `use_libs` tokens + `use_all_libs()`; was remainder of `gl-dep-lib-api`); [`archive/package-use-libs-defaults.md`](../archive/package-use-libs-defaults.md); ROADMAP Dependencies / packages — **1.13.0** opener; [#279](https://github.com/ja11sop/cuppa/issues/279)
- **Updated:** 2026-10-17
- **Impact:** minor — package author/consumer API for large multi-lib archives; leaf `use_libs` stays valid
- **Status note:** behaviour on master pending merge; promote to `done` on the feature PR. Boost / manifest-handler / flags follow-ons recorded below (not blocking this slice).

## Problem

Large GitLab packages expose many concrete libraries. Consumers and transitive
manifest edges need **named feature groups** (e.g. `"kms"`, `"cloud storage"`)
that expand to several leaves — the same idea as Boost’s dependent-lib
expansion, but author-defined and discoverable.

The transitive MVP already:

- applies edge `use_libs` leaf tokens (and Boost-style silent expansion inside
  `boost_package`);
- ships **`use_all_libs()`** for “link everything this package offers.”

It does **not** yet ship publisher-defined group tables or configure-time
discovery helpers.

## Intent

1. Let package authors declare **named groups** → concrete library lists
   (manifest and/or Python on the package factory).
2. Let `use_libs([...])` accept **leaves and/or group tokens** with the same
   vocabulary as transitive edge `use_libs`.
3. Provide discovery: **`show_libs_for(token)`** and **`show_all_libs()`**
   (print/return expansion; tree grouped by group names).
4. Keep empty `use_libs([])` = link nothing; `use_all_libs()` = full concrete set.

## Non-goals

- Changing transitive apply timing (`BuildWith` = includes; link on
  `use_libs` / `use_all_libs`).
- Version ranges (see [`gitlab-package-version-ranges.md`](../archive/gitlab-package-version-ranges.md)).
- Requiring every existing package to sprout groups.

## Direction (from parent settled API)

```python
env.BuildWith( 'mega_package' ).use_libs( [
    'kms libs',        # convenience group → several libraries
    'cloud storage',   # named group for a feature area
    # or cherry-pick leaf 'kms' when groups do not shadow stems
] )

env.BuildWith( 'mega_package' ).use_all_libs()

env.BuildWith( 'mega_package' ).show_libs_for( 'cloud storage' )
env.BuildWith( 'mega_package' ).show_all_libs()
```

| Call | Role |
|------|------|
| `use_libs([...])` | Leaves and/or groups; each token expands then links |
| `use_all_libs()` | Full concrete set (**already shipped**) |
| `show_libs_for(token)` | Expansion for one leaf or group |
| `show_all_libs()` | Whole map — groups → concrete libs |

Manifest edges use the **same** token vocabulary so A can declare
`use_libs: ["kms"]` against B and get the group expansion.

## Settled (this slice)

1. **Where groups live:** both — `GitlabPackagePublisher(..., lib_groups={...})`
   seeds traveling `cuppa-publish.json`; consumers expand from the traveling
   manifest (legacy `cuppa-dependency.json` also accepted).
2. **`show_*`:** return the Python value **and** log a configure-time summary.
3. **Boost:** remains silent dependent expansion only (no named groups yet).

Nested group members recurse with cycle detection. If a token names a group, the
group wins even when a same-named leaf stem exists. A group may still list that
same-named stem as a member (self-reference is treated as the leaf, not a cycle).

### Two authoring styles

| Style | Intent | Naming |
|-------|--------|--------|
| **Opaque / Boost-like** | Hide concrete stems; the group *is* the API. Consumer always gets the right set (and order). | Group name may match (and shadow) a primary leaf — e.g. `kms` → `[kms, kms_protos, …]`. Cherry-picking that leaf alone is intentionally unavailable. |
| **Convenience** | Feature shortcuts beside an open leaf catalogue. | Group names **avoid** leaf stems — e.g. `kms libs`, `cloud storage` — so `use_libs(['kms'])` still links only the client. |

`google_cloud_cpp` uses **convenience** groups. Prefer opaque naming only when
the package author wants consumers never to link a partial set.

## Follow-on: Boost vs `lib_groups` (thought experiment, 2026-10-17)

A typical Boost GitLab **publisher** builds a normal registry archive; consume
tips that need Boost link semantics still use
**`cuppa.packages.boost_package.define`** in parallel — expansion, defines, and
Test hooks live in Python, not in the traveling manifest. Could opaque
`lib_groups` on that archive replace `boost_package`?

### What maps

Opaque groups per library token (`log` → `[log, date_time, filesystem, thread]`,
nested `log_setup` → `log`, …) match the *user-facing* shape: ask for a name,
get a set. Discovery (`show_*`) would help. Membership for one pin (e.g. 1.92)
can be copied from `add_dependent_libraries`.

### Gaps vs `boost_package.use_libs` / `add_dependent_libraries`

| Concern | `boost_package` today | Generic `lib_groups` + GitLab `use_libs` |
|---------|----------------------|------------------------------------------|
| **Global link order** | Union required set → emit subset of **`boost_dependency_order()`** (dependents before deps for GNU ld). Token order irrelevant. | Expansion = **token order + group body**, then **first-seen dedupe**. `['filesystem','log']` ≠ master order of `['log','filesystem']`. |
| **Cross-call repeats** | **`Append`**, not unique — a later `use_libs` may **re-list** deps after earlier libs (#267 / quince). | Clears prior package contribution, then **`AppendUnique`**. Intentional repeats drop. |
| **Version / link-type / patched gates** | Driven by `float(version)`, `linktype`, `patched_test=`. | Static table for one published pin; no link-type or patched awareness. |
| **Aliases** | `'test'` → `unit_test_framework`. | Only if declared as a group. |
| **Artefact naming** | `static_library_name(...)` (toolchain / version / variant tags). | Generic stem resolve under `lib/`. |
| **Compile defines / Test API** | `MergeFlags` (`BOOST_PARAMETER_MAX_ARITY`, …), `numeric_version()`, `patched_test()`. | **Not in traveling manifest today** (see below). |

**Verdict:** convenience groups (google_cloud_cpp) fit `lib_groups`. Boost opaque
“always do the right thing” is only **partially** declarable; **master order**,
**Append-with-repeats**, and Boost package extras still need
`boost_package` (or equivalent) until the generic path grows those rules.
Keep Boost expansion in Python for now; opaque groups on the Boost archive are
optional documentation / discovery, not a replacement.

### Manifest-directed package handler (parallel → directed)

Today the registry package (`boost`) and the special consume wrapper
(`boost_package.define`) live **in parallel**: tip authors must know to import
the wrapper; a synthesized transitive factory from the traveling manifest is
plain `package_dependency` and **misses** Boost `use_libs` / defines unless a
`boost_package` factory was already registered under that name.

**Idea:** let the traveling manifest **select the consume handler**, e.g.:

```json
{
  "package": "boost",
  "version": "1.92",
  "consume": "boost_package"
}
```

or a small registry of well-known handlers (`"consume_handler": "boost"`).

On apply: prefer a registered factory for that handler; fall back to generic
GitLab package. Tip and transitive paths share one rule — the archive says how
it wants to be consumed. Related: resolve / Quince selector gaps in
[`boost-updates.md`](boost-updates.md) and
[`../archive/dependency-resolve.md`](../archive/dependency-resolve.md).

**Status:** open follow-on (not this PR). Does not remove the need for the
handler implementation; it **binds** archive → handler instead of relying on
tip-side parallel knowledge.

### Traveling manifest compile defines / flags

`boost_package.__call__` imbues the env with Boost-specific `MergeFlags`
defines. The traveling manifest today carries identity, dependency edges,
`default_use_libs`, `link`, and `lib_groups` only — **no** compile-flag /
define payload.

| Option | Notes |
|--------|-------|
| **A. Handler-owned** (status quo for Boost) | Defines stay in `boost_package` (or future handler). Manifest only selects the handler. Safest for Boost-specific / patched semantics. |
| **B. Declarative flags in manifest** | e.g. `cppdefines: ["BOOST_…"]`, optional `ccflags` / `cxxflags`. Generic apply on `BuildWith` / initialise. Good for “this archive always needs these macros”; weaker for patched-vs-clean, toolchain conditionals, or secrets. |
| **C. Hybrid** | Manifest may list **additive** defines; handler may still MergeFlags for behaviour tied to identity (`patched`). |

**Assessment:** supporting **B** (or hybrid **C**) is reasonable for ordinary
packages and would close part of the Boost gap for tips that only
`package_dependency('boost')`. Prefer a narrow MVP (`cppdefines` list applied
via `MergeFlags` / `AppendUnique` to `CPPDEFINES`) before free-form flag soup.
Boost should still lean on **A/C** so patched Test and arity defines stay
aligned with handler identity ([`boost-updates.md`](boost-updates.md)).

### Delegate link-line append **policy** to the toolchain (2026-10-17)

Not “the toolchain adds libraries” as a package feature — call sites still
resolve what to put on the line; they **stop hard-coding** `Append` vs
`AppendUnique`. That choice is linker / toolchain behaviour.

Boost is one **example** of needing order + repeats for **static** archives on
GNU ld, not an exceptional one-off. Wrong Unique often fails only at **link
time**.

**`use_libs` API (settled):** call once per package with the required set; a
later call **clears** that package’s prior contribution and re-applies.
Clearing stays. Stacking additive `use_libs` calls is not the API.

**Same idea for `STATICLIBS`, `LIBPATH`, and `SHAREDLIBS`** — three optional
toolchain hooks, not a hard base-class API. Prefer **opt-in via attribute
check** with today’s behaviour as the default when the hook is absent:

```python
# Shared helper sketch (one place; all call sites use it)
toolchain = env['toolchain']  # or env.Toolchain()
append = getattr( toolchain, 'append_static_libs', None )
if append:
    append( libs )            # or append( env, libs )
else:
    env.AppendUnique( STATICLIBS = libs )   # current default

append = getattr( toolchain, 'append_shared_libs', None )
if append:
    append( stems )
else:
    env.AppendUnique( SHAREDLIBS = stems )

append = getattr( toolchain, 'append_libpath', None )
if append:
    append( paths )
else:
    env.AppendUnique( LIBPATH = paths )
```

| Hook | Default if absent | gcc / clang likely opt-in |
|------|-------------------|---------------------------|
| `append_static_libs` | `AppendUnique(STATICLIBS=…)` (today) | `Append` — order + repeats |
| `append_shared_libs` | `AppendUnique(SHAREDLIBS=…)` | Usually keep Unique (or omit hook) |
| `append_libpath` | `AppendUnique(LIBPATH=…)` | Usually keep Unique (or omit hook) |

**Why opt-in, not abstract-required:** toolchains without an opinion stay
unchanged; gcc/clang (and later others) opt in where policy differs; no forced
stub on every toolchain; easier incremental rollout and tests.

**Why Unique on `STATICLIBS` is wrong even with clear-once (when gcc opts into
Append):** clear only removes *this* package’s nodes. `AppendUnique` still drops
archives already on the line from **another** package. Re-listing after a later
archive is a general static need on GNU ld.

**Sketch — gcc static policy:**

```python
def append_static_libs( self, libs ):
    # env captured by toolchain, or passed in
    self.env.Append( STATICLIBS = libs )
```

**Audit:** route package link apply, legacy installer `build_with`, Boost, and
other library-append sites through the shared helpers so policy stays in one
place. Group expand first-seen dedupe stays separate (within one expansion);
opaque **order** may still need a handler.

**Determinism** of expand/sort outputs (#267) stays a separate requirement.

**Follow-on (not blocking lib-groups merge):** add shared getattr helpers;
implement gcc/clang `append_static_libs` (Append); leave shared/libpath hooks
unimplemented until a toolchain needs them; switch call sites; optionally route
Boost through the static helper.

## Progress

| Item | Status |
|------|--------|
| Split from transitive MVP | Done — this proposal |
| `use_all_libs()` | Done on parent MVP |
| Named groups + `show_*` | Done — this PR (**1.13.0**) |
| Implementation | Done — expand in `use_libs`; manifest `lib_groups`; `show_libs_for` / `show_all_libs` |
| Boost opaque via `lib_groups` alone | **Rejected as replacement** — gaps above; keep `boost_package` expander |
| Manifest-directed consume handler | Open follow-on |
| Manifest `cppdefines` / flags | Open follow-on (narrow MVP plausible; Boost hybrid) |
| Toolchain owns link append **policy** (static / shared / libpath), opt-in via getattr | Done this PR — ``link_append`` helpers; gcc/clang ``append_static_libs`` → Append; call sites routed |
