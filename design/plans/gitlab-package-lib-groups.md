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

### AppendUnique / dedupe / order stability (general caution)

Boost taught that **link-line multiset and order** are ABI/link correctness,
not just tidy lists:

1. **Missing repeats** — `AppendUnique` / contribution replace can drop a
   dependent that must appear **again** after a later library on GNU ld.
2. **Wrong order** — first-seen dedupe after token-order expansion is not a
   global topological / master order.
3. **Spurious rebuilds** — unstable ordered outputs (e.g. `set` iteration /
   `PYTHONHASHSEED`) change SCons signatures (#267). Any expand → link path
   must emit **deterministic** sequences (sorted unknown tails, fixed master
   lists, insertion-stable JSON).

**Assessment for generic GitLab `use_libs` today:**

| Behaviour | Risk | Guidance |
|-----------|------|----------|
| Expand groups with first-seen dedupe | Fine for **convenience** groups and most shared/DT_NEEDED stacks; **unsafe** as the sole rule for Boost-like static opaque graphs | Keep; document that opaque static graphs may need a package order policy or a dedicated handler |
| `clear` + re-apply contribution | Good for “replace defaults with this `use_libs`”; **bad** if callers rely on stacking multiple `use_libs` with intentional repeats | Stacking / repeats remain Boost-handler territory unless we add an explicit `Append` mode |
| `AppendUnique` on `STATICLIBS` / `SHAREDLIBS` | Hides duplicate **identical** nodes; also hides **needed** re-lists | Acceptable default for generic packages; do **not** silently migrate Boost onto it |
| Hash-unstable ordering | Signature churn / flaky CI | Already fixed for Boost expander; any new manifest-driven expand/sort must stay deterministic |

**Do not** treat AppendUnique/dedupe as universally correct. Default generic
path can keep them for typical packages; **special handlers** (Boost) and any
future “opaque static graph” policy must opt into Append + ordered expand.
Revisit if real non-Boost packages hit the same GNU ld repeat/order class of
bug — that would argue for an optional manifest `link_policy: append_ordered`
(or similar), not for weakening Boost.

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
| Generic AppendUnique vs Boost Append | Documented caution; no change this PR |
