# Plan: GitLab package dependency version ranges

- **Status:** proposal
- **Related:** [`gitlab-package-transitive.md`](gitlab-package-transitive.md) (MVP concrete pins; was `gl-dep-ranges`); [`archive/package-build-publish-deps.md`](../archive/package-build-publish-deps.md) (open question 10 — floating `latest` ≠ constraint solver); [`archive/gitlab-package-latest.md`](../archive/gitlab-package-latest.md); ROADMAP Dependencies / packages; [#279](https://github.com/ja11sop/cuppa/issues/279)
- **Updated:** 2026-10-05
- **Impact:** minor — richer manifest / consume pins; existing exact-version edges stay valid

## Problem

Transitive GitLab MVP pins **concrete** versions in `cuppa-dependency.json`
(publish may resolve `latest` into a pin). Publishers often want a softer
contract such as “need package B at least 1.28.0” without republishing A for
every B patch:

```json
{
  "name": "widget_core",
  "package": "widget-core",
  "version": ">=1.28.0",
  "registry": "same"
}
```

Today two concrete pins that disagree are a hard conflict. Ranges need a clear
resolve + diamond policy without becoming a full Conan-style solver (MVP
non-goal of the parent plan).

## Intent

1. Allow **minimum** (and possibly exact / equality) spellings on manifest
   edges and, if useful, on consumer `package_dependency(..., version=…)`.
2. Keep **absent / exact** behaviour unchanged.
3. Fail clearly when no cached or registry candidate satisfies the range, or
   when two parents demand incompatible bounds on the same package identity.
4. Stay offline-friendly: prefer remembered / on-disk extracts that satisfy the
   range before network `latest`.

## Non-goals

- Full constraint solving, backtracking, or version ranges across ConanCenter.
- Replacing Conan for multi-package graph resolution.
- Changing BuildWith type-selector / `dependency_resolve` precedence.

## Direction (sketch)

| Topic | Lean |
|-------|------|
| Spelling (MVP of this plan) | `1.28.0` / `==1.28.0` exact; `>=1.28.0` minimum. Defer `^` / `~` / comma lists until needed |
| Publish | May still pin concrete when the author used `latest`; may also write a range when the publisher declared one |
| Consume | Among candidates (registry list + cache), pick the **highest** version that satisfies all active bounds for that `(registry, package)` — or the single remembered pin if it still satisfies |
| Diamond | Intersect bounds; empty intersection → `StopError` with both parents named |
| Offline | Only cached / remembered versions that satisfy the range; no silent upgrade past cache |

## Open questions

1. Should consumer-declared `version=">=…"` on `package_dependency` use the same
   grammar as manifest edges, or stay exact-only at first?
2. Interaction with `--refresh-downloads` / same-version republish when a
   higher satisfying version appears upstream.
3. How `--list-dependencies` displays a range edge vs the resolved concrete
   extract (label vs bound leaf).

## Progress

| Item | Status |
|------|--------|
| Split from transitive MVP | Done — this proposal |
| Schema + resolve rules | Proposal |
| Implementation | Not started |
