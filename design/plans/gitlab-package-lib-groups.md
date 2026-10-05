# Plan: GitLab package named library groups

- **Status:** proposal
- **Related:** [`gitlab-package-transitive.md`](gitlab-package-transitive.md) (MVP `use_libs` tokens + `use_all_libs()`; was remainder of `gl-dep-lib-api`); [`archive/package-use-libs-defaults.md`](../archive/package-use-libs-defaults.md); ROADMAP Dependencies / packages; [#279](https://github.com/ja11sop/cuppa/issues/279)
- **Updated:** 2026-10-05
- **Impact:** minor — package author/consumer API for large multi-lib archives; leaf `use_libs` stays valid

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
- Version ranges (see [`gitlab-package-version-ranges.md`](gitlab-package-version-ranges.md)).
- Requiring every existing package to sprout groups.

## Direction (from parent settled API)

```python
env.BuildWith( 'mega_package' ).use_libs( [
    'kms',             # may expand to several libraries
    'cloud storage',   # named group for a feature area
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

## Open questions

1. Where group tables live first: only mega-package wrappers (Python), or also
   in `cuppa-dependency.json` / publish metadata for generic packages.
2. `show_*` return vs print (configure console report vs Python API).
3. Whether Boost remains silent expansion only, or grows named groups later.

## Progress

| Item | Status |
|------|--------|
| Split from transitive MVP | Done — this proposal |
| `use_all_libs()` | Done on parent MVP |
| Named groups + `show_*` | Proposal |
| Implementation | Not started |
