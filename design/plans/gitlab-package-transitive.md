# Plan: Transitive GitLab package dependencies

- **Status:** proposal
- **Related:** [`ROADMAP.md`](../../ROADMAP.md) — Dependencies / packages; [`archive/gitlab-package-latest.md`](../archive/gitlab-package-latest.md); [`archive/dependency-resolve.md`](../archive/dependency-resolve.md); [`archive/conan-consumer-plan.md`](../archive/conan-consumer-plan.md) (transitive `requires` as contrast); [`run-default-dependency-objects.md`](run-default-dependency-objects.md) (import vs auto-enable); scratchpad graduate
- **Updated:** 2026-09-05
- **Impact:** minor — new publish/consume behaviour for GitLab packages; existing flat declarations stay valid

## Problem

GitLab `package_dependency` archives are **standalone**. If package **A** needs package **B**
at build or link time, the consumer must declare both in the sconstruct:

```python
A = cuppa.package_dependency( 'a', registry=…, package='a', version='1.2' )
B = cuppa.package_dependency( 'b', registry=…, package='b', version='3.0' )

cuppa.run(
    import_dependencies = [ A, B ],
    auto_enable_dependencies = [ A, B ],  # or BuildWith both in sconscripts
)
```

That duplicates publisher knowledge in every consumer and is easy to get wrong (forgotten B,
mismatched versions). The desired ergonomics: the consumer knows about **A**, and A already
carries enough information to fetch and apply **B**.

Today there is **no** package-to-package graph for GitLab:

| Mechanism | What it does | Transitive packages? |
|-----------|--------------|----------------------|
| `use_libs(..., depends_on=[])` | SCons `env.Depends` on include/lib nodes | No — build-order only |
| Boost `add_dependent_libraries` | Intra-Boost static link closure | No — same archive |
| `dependency_resolve` | Pick GitLab vs archive for one *name* | No — supply-chain choice |
| Conan `requires` | Conan install graph | Yes — Conan only |
| Published archive | `include/`, `lib/`, optional `modules/` | No dependency manifest |

Key code: `cuppa/build_with_package.py`, `cuppa/package_managers/gitlab.py`
(`GitlabPackageDependency`, `GitlabPackagePublisher`), consume docs under
`docs/modules/ROOT/pages/dependencies/gitlab.adoc` and publish under `packages.adoc`.

## Goals

1. Let a GitLab package **declare** dependencies on other GitLab packages so a consumer that
   `BuildWith`s / auto-enables **A** also gets **B** without listing B in the sconstruct.
2. Keep the existing flat model working (explicit A+B remains valid and is the escape hatch).
3. Fail clearly for cycles, missing factories, and offline cache misses.
4. Document publish and consume shapes; cover with an integration round-trip.

## Non-goals (MVP)

- A full constraint solver (version ranges, backtracking) — Conan already covers that niche.
- Implicit `auto_enable` of transitive deps as session defaults (surprise global includes).
- Cross-registry deps in the first cut (same registry / `registry: "same"` only).
- Replacing Conan for multi-package graphs from ConanCenter.
- Changing BuildWith type-selector / `dependency_resolve` precedence
  ([`dependency-resolve.md`](../archive/dependency-resolve.md)).

## Semantics (settled for exploration)

Align with import vs auto-enable ([`run-default-dependency-objects.md`](run-default-dependency-objects.md)):

| Layer | Role for transitive B |
|-------|------------------------|
| Consumer still **imports / auto-enables A** | A remains the only name the project must know |
| When A is `BuildWith`'d (or auto-enabled) | Cuppa reads A's dependency metadata and `BuildWith`s B |
| B is **not** added to `auto_enable_dependencies` by default | Avoid pulling B into every sconscript that never uses A |
| Consumer may still import B explicitly | Pins, develop paths, or overrides win over transitive discovery |

So “declare A only” means: **register A**; applying A pulls B. It does **not** mean B becomes a
session-wide default unless the consumer listed B in `auto_enable_dependencies`.

## Where the edge is declared

| Option | Pros | Cons |
|--------|------|------|
| **A. Manifest inside the published archive** (recommended MVP) | Travels with the artefact; offline-friendly; versioned with A | Needs publish + consume changes; schema evolution |
| **B. Only `define()` / publisher kwargs in Python** | Familiar to Cuppa authors | Consumer never runs publisher code unless metadata is written into the archive anyway |
| **C. Separate registry index / API** | No archive format change | Extra infra; weaker offline story |
| **D. Consumer-only `requires=[B]` on A's factory** | Easy to prototype | Defeats “A carries B”; duplicates publisher knowledge |

**Recommendation:** **A**, fed by publisher kwargs (**B** at authoring time). Publisher writes
something like `cuppa-package.json` (name TBD) next to `include/` / `lib/` when staging the
tarball. Consumer reads it after extract.

Illustrative schema (not final):

```json
{
  "cuppa_package_format": 1,
  "dependencies": [
    {
      "name": "fmt",
      "package": "fmt",
      "version": "12.1.0",
      "registry": "same"
    }
  ]
}
```

- **Concrete versions in MVP** — no ranges; publish-time resolve of `latest` into a pin is
  allowed so offline consumers do not re-resolve B.
- `registry: "same"` means A's registry URL (or an explicit URL later).
- Optional later fields: `link` (auto `use_libs` pull), supply-chain type, develop hints.

## How consume applies B

1. After A is extracted (or develop path selected), read the manifest if present.
2. For each dependency entry, obtain a factory:
   - Prefer a factory already registered under `name` (consumer or plugin).
   - Else **synthesize** `package_dependency(name, registry=…, package=…, version=…)` when the
     manifest has enough identity (MVP: same registry + package + version).
3. Call `env.BuildWith(B)` during A's initialise / first apply path (not global auto-enable).
4. **Cycle detection** on the apply stack (A→B→A → `StopError`).
5. **Diamond:** same `(registry, package, version, tool_variant)` reuses the existing
   package instance / cache (today's identity caching already helps).
6. **Conflict:** two concrete versions of the same package name → fail clearly in MVP
   (first-wins is too silent for prebuilt ABI).

### Develop / offline

- **`--offline`:** every transitive archive must already be under downloads; no network
  `latest` for B unless a remembered pin exists and the archive is cached.
- **`--develop`:** if the consumer configured a develop path for B, use it; otherwise use the
  packaged extract. Do not invent develop paths for transitive deps.
- **`--list-dependencies`:** show A with B as a child edge when the manifest was applied
  (presentation; inventory already has a tree shape).

## Contrast with Conan

Conan already models transitive `requires`. This plan is **GitLab registry packages only** —
prebuilt Cuppa-shaped archives (`include/` / `lib/` / `modules/`), not a second Conan.
Keep Conan for ConanCenter graphs; keep GitLab transitive for org-published Cuppa packages.
A later bridge (manifest → Conan `requires` on publish) is out of scope for MVP.

## Phases

| ID | Slice | Notes |
|----|--------|-------|
| `gl-dep-rules` | This plan: semantics, schema sketch, refusal rules | **This document** |
| `gl-dep-publish` | Publisher writes manifest from kwargs / `dependencies=` | Opt-in at first if safer |
| `gl-dep-consume` | Read manifest; synthesize or reuse factory; `BuildWith` transitive; cycles / conflicts | |
| `gl-dep-tests` | Integration: publish A+B fixture → consume A only → link/run | |
| `gl-dep-docs` | `gitlab.adoc` + `packages.adoc`; teach vs flat declare | |
| `gl-dep-list` | `--list-dependencies` / inventory edges from manifest | After consume |
| `gl-dep-ranges` | Version ranges / softer diamond policy | Deferred |
| `gl-dep-issue` | File `impact:minor` issue when implementing | |

## Open questions

1. **Manifest filename** — `cuppa-package.json` vs `cuppa.json` vs beside `module-map.json`?
2. **Opt-in publish** — always write when deps declared, or `--package-write-deps` until soak?
3. **Does `use_libs` on A imply transitive `use_libs` on B?** MVP: only `BuildWith` (headers /
   SYSINCPATH); linking B stays explicit unless a later `link: true` field exists.
4. **Naming of Cuppa registry names** — must manifest `name` match `package_dependency`'s
   registry name (`fmt` vs `fmt_package`)? Prefer the **BuildWith name** the consumer would use.
5. **Interaction with `boost_package`** — Boost's internal lib graph stays separate; Boost as a
   transitive *package* dep of A is an ordinary manifest entry.
6. **Pip plugins** — can a plugin's factory default-declare transitive deps without a published
   archive (develop / location hybrid)? Defer unless a concrete plugin needs it.

## Refusal rules

- Do not require every existing package to sprout a manifest (absent file = today's behaviour).
- Do not auto-add transitive names to `auto_enable_dependencies`.
- Do not invent a solver in MVP — concrete versions only.
- Do not silently pick one version when two concrete pins conflict.
- Do not put private project / registry host names in this plan's examples (use
  `gitlab.example` / `widget` / `fmt`).

## Progress snapshot

| Slice | Status |
|-------|--------|
| `gl-dep-rules` | Done — this proposal |
| `gl-dep-publish` | Not started |
| `gl-dep-consume` | Not started |
| `gl-dep-tests` | Not started |
| `gl-dep-docs` | Not started |
| `gl-dep-list` | Not started |
| `gl-dep-ranges` | Deferred |
| `gl-dep-issue` | Not filed |
