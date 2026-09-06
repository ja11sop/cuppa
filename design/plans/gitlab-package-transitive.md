# Plan: Transitive GitLab package dependencies

- **Status:** in progress
- **Related:** [`ROADMAP.md`](../../ROADMAP.md) — Dependencies / packages; [`archive/gitlab-package-latest.md`](../archive/gitlab-package-latest.md); [`archive/dependency-resolve.md`](../archive/dependency-resolve.md); [`archive/conan-consumer-plan.md`](../archive/conan-consumer-plan.md) (transitive `requires` as contrast); [`run-default-dependency-objects.md`](run-default-dependency-objects.md) (import vs auto-enable); scratchpad graduate
- **Updated:** 2026-09-06
- **Impact:** minor — new publish/consume behaviour for GitLab packages; existing flat declarations stay valid
- **Issue:** [#279](https://github.com/ja11sop/cuppa/issues/279)
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
`cuppa-dependency.json` next to `include/` / `lib/` when staging the tarball (see settled
decisions). Consumer reads it after extract.

Illustrative schema (not final):

```json
{
  "cuppa_dependency_format": 1,
  "dependencies": [
    {
      "name": "boost_package",
      "package": "boost",
      "version": "1.91.0",
      "registry": "same",
      "use_libs": ["system", "filesystem"]
    }
  ]
}
```

- **`name`** — Cuppa **BuildWith / registry name** (what `BuildWith('…')` looks up).
- **`package`** — GitLab Packages API package slug when it differs from `name`.
- **Concrete versions in MVP** — no ranges; publish-time resolve of `latest` into a pin is
  allowed so offline consumers do not re-resolve B.
- `registry: "same"` means A's registry URL (or an explicit URL later).
- **`use_libs`** — libraries to request from B when A is applied (see link closure below).
  Omit or `[]` when B is headers-only.

## How consume applies B

1. After A is extracted (or develop path selected), read the manifest if present.
2. For each dependency entry, obtain a factory:
   - Prefer a factory already registered under `name` (consumer or plugin).
   - Else **synthesize** `package_dependency(name, registry=…, package=…, version=…)` when the
     manifest has enough identity (MVP: same registry + package + version).
3. Call `env.BuildWith(B)` during A's initialise / first apply path (not global auto-enable) so
   B's includes (`SYSINCPATH`) land with A's.
4. When linking A (A's `use_libs` / package link step), also apply each dep's `use_libs` against B
   (e.g. `BuildWith('boost_package').use_libs(['system', 'filesystem'])`), including any
   *intra*-package expansion B already does (Boost `add_dependent_libraries`).
5. **Cycle detection** on the apply stack (A→B→A → `StopError`).
6. **Diamond:** same `(registry, package, version, tool_variant)` reuses the existing
   package instance / cache (today's identity caching already helps).
7. **Conflict:** two concrete versions of the same package name → fail clearly in MVP
   (first-wins is too silent for prebuilt ABI).

### Link / include closure (intended behaviour)

The product win is a **chained** include and link picture, not headers alone.

Example: A depends on `boost_package` and asks for `use_libs: ["P", "S"]`. Boost expands that to
`P, Q, R, S`. A itself also contributes shared libs `D` and `E`. Then a consumer that only
`BuildWith`s / links A should see on the link line (conceptually):

`A, D, E, P, Q, R, S`

— subject to how each artefact is linked:

| Situation | What the user typically sees |
|-----------|------------------------------|
| Shared / dynamic libs for A and B | Separate `.so`/`.dll` (or import libs) for A, D, E and the Boost closure |
| Static libs, not absorbed | `STATICLIBS` nodes for A plus B's expanded set |
| Everything statically linked *into* A's archive at publish time | Often only `A` on the consumer link line |

Cuppa's GitLab `use_libs` today appends **static** library files by default
(`use_static_libs`); Boost package `use_libs` expands dependents then does the same. Shared
runtime is a separate path (Conan already models this more fully). The transitive feature must
**compose** those existing behaviours — not invent a third linker.

### Develop / offline

- **`--offline`:** every transitive archive must already be under downloads; no network
  `latest` for B unless a remembered pin exists and the archive is cached.
- **`--develop`:** if the consumer configured a develop path for B, use it; otherwise use the
  packaged extract. Do not invent develop paths for transitive deps.
- **`--list-dependencies`:** show A with B as a child edge when the manifest was applied
  (presentation; inventory already has a tree shape).

## Contrast with Conan and pip

**Conan** already models transitive `requires`. This plan is **GitLab registry packages only** —
prebuilt Cuppa-shaped archives (`include/` / `lib/` / `modules/`), not a second Conan.
Keep Conan for ConanCenter graphs; keep GitLab transitive for org-published Cuppa packages.
A later bridge (manifest → Conan `requires` on publish) is out of scope for MVP.

**Pip** is a different layer (and should stay so):

| Layer | What it requires | When it resolves |
|-------|------------------|------------------|
| Pip `install_requires` / package deps | Other **Python** distributions (e.g. a `cuppa-boost-package` plugin wheel) | `pip install` time |
| `cuppa-dependency.json` inside a GitLab archive | Other **Cuppa BuildWith** packages (GitLab tarballs) | Cuppa configure / `BuildWith` after the archive is present |

A sensible stack: pip can pull a plugin that *registers* a custom GitLab package factory (today's
`boost_package`-style story). That factory's published archives still carry
`cuppa-dependency.json` for C++/link closure. Pip cannot satisfy those GitLab edges; Cuppa reads
the manifest once the package is imported and the archive is fetched. Develop trees without an
archive yet may declare the same edges in Python on the factory; the packaged manifest remains
the consumer-facing source of truth for registry artefacts.

## Phases

| ID | Slice | Notes |
|----|--------|-------|
| `gl-dep-rules` | This plan: semantics, schema sketch, refusal rules | **This document** — open questions settled 2026-09-06 |
| `gl-dep-publish` | Publisher always writes `cuppa-dependency.json` when deps are declared | Omit file when there are no deps |
| `gl-dep-consume` | Read manifest; synthesize or reuse factory; `BuildWith` + transitive `use_libs`; cycles / conflicts | |
| `gl-dep-tests` | Integration: publish A+B fixture → consume A only → compile/link/run with closure | |
| `gl-dep-docs` | `gitlab.adoc` + `packages.adoc`; teach vs flat declare | |
| `gl-dep-list` | `--list-dependencies` / inventory edges from manifest | After consume |
| `gl-dep-lib-api` | `use_all_libs()`; named groups + `show_libs_for` / `show_all_libs` on package instances | Can parallel mega-package wrappers; shares token vocab with manifest |
| `gl-dep-ranges` | Version ranges / softer diamond policy | Deferred |
| `gl-dep-issue` | File `impact:minor` issue when implementing | |

## Settled decisions (2026-09-06)

| Topic | Decision |
|-------|----------|
| Manifest filename | **`cuppa-dependency.json`**. Long-term this is Cuppa *package artefact* metadata (BuildWith-name edges + optional `use_libs`), not GitLab transport. MVP only GitLab publish/consume read/write it; Conan keeps its own `requires`. Prefer this over `cuppa-gitlab-package.json` so we do not rename when location/other Cuppa archives grow the same file later. |
| When to write | **Always write when the publisher was given dependencies.** No opt-in flag. Omit the file when there are no deps (absent file = today's standalone behaviour). A present file with an empty `dependencies` list is unnecessary. |
| Includes | **`BuildWith(A)` pulls `BuildWith(B)`** so B's `SYSINCPATH` (and modules load) apply. That is required for chained headers. |
| Libraries | **Transitive `use_libs` as declared on each edge.** Manifest entries carry `use_libs` for B; applying/linking A applies those against B, including B's own expansion (e.g. Boost dependents). Headers-only B omits `use_libs`. |
| Link-line picture | Consumer should see the **composed** set (A's libs + each dep's expanded `use_libs`), except where static linking has already absorbed objects into A at publish time — then only A may appear. Matches the A→boost(P,S→P,Q,R,S)+D,E example. |
| Manifest `name` | The **BuildWith / Cuppa registry name** (`package_dependency('boost_package', package='boost', …)` → `"name": "boost_package"`). GitLab slug stays in `"package"` when different. |
| `boost_package` | Ordinary transitive entry; Boost's *intra*-archive lib graph stays inside `boost_package.use_libs`. |
| Pip vs manifest | **Separate layers.** Pip requires other wheels/plugins; `cuppa-dependency.json` requires other Cuppa/GitLab packages after the archive exists. A pip plugin may deliver a GitLab-package factory; the archive still carries the manifest for link/include closure. |
| `BuildWith` vs link | **Match Boost today:** `BuildWith(A)` = includes (and transitive `BuildWith(B)`). **No** link-all on `BuildWith` / auto-enable alone. |
| When transitive `use_libs` run | When the consumer first **links A** via `A.use_libs(...)`. That call also applies each manifest edge's `use_libs` against B (including Boost expansion). Headers already landed at `BuildWith(A)`. |
| Empty `use_libs([])` | **Keep current meaning: link nothing** (empty selection). Do **not** redefine empty as “all libraries”. |
| “Link everything A offers” | **`use_all_libs()`** — explicit method name (not `use_libs([])` or a magic `'*'`). Settled spelling. |
| Named groups | **`use_libs` tokens may be leaf libs *or* publisher-defined groups** (e.g. `"kms"`, `"cloud storage"`) that expand to several concrete libraries — same idea as Boost’s dependent-lib expansion, but named by the package author. |
| Discovery | **`show_libs_for(group_or_lib)`** — print/return what a token expands to. **`show_all_libs()`** — full catalogue, ideally a tree grouped by macro / group names. Aids huge packages (e.g. `google_cloud_cpp`) without guessing. |
| Override | Consumer `A.use_libs(X)` selects **A's** libs/groups (replaces any future A-side default). Manifest edges for **B** are not a consumer choice — they always apply when A is linked. Consumer may still `BuildWith(B).use_libs(...)` explicitly; conflicting concrete sets → fail or union TBD (prefer fail in MVP if versions conflict; union of lib names if same B). |

### Library selection API (consumer-facing)

Aligned with Boost today, extended for large multi-lib packages:

```python
# Leaf and/or named group tokens — groups expand to several concrete libs
env.BuildWith( 'google_cloud_cpp' ).use_libs( [
    'kms',             # may expand to several libraries
    'cloud storage',   # named group for a feature area
] )

# Everything this package offers
env.BuildWith( 'google_cloud_cpp' ).use_all_libs()

# Discovery (configure-time / console helpers — exact return vs print TBD)
env.BuildWith( 'google_cloud_cpp' ).show_libs_for( 'cloud storage' )
env.BuildWith( 'google_cloud_cpp' ).show_all_libs()  # tree grouped by macro / group names
```

| Call | Role |
|------|------|
| `use_libs([...])` | Opt in to named **leaves and/or groups**; each token expands (package-defined) then links |
| `use_all_libs()` | Opt in to the full concrete set this package publishes |
| `show_libs_for(token)` | Show expansion for one leaf or group (what would be linked) |
| `show_all_libs()` | Show the whole map — groups / macros → concrete libs (tree) |

**Relation to transitive GitLab deps:** a manifest edge’s `use_libs` list uses the **same token vocabulary** (leaves or groups) so A can declare `use_libs: ["kms"]` against `google_cloud_cpp` and get the group expansion. `use_all_libs()` on A still triggers transitive edge application for B.

**Phasing:** transitive manifest + `use_libs` / `use_all_libs` on the generic package instance are in scope for this workstream. Named-group tables and `show_*` are the natural follow-on for mega-packages (can ship on `boost_package` / `google_cloud_cpp`-style wrappers first); Boost already has silent dependent expansion without named groups.

### `use_libs` timing — options considered

| Option | Pros | Cons |
|--------|------|------|
| **A. Boost-like (recommended)** — `BuildWith` = includes only; `A.use_libs([...])` selects A's libs and triggers transitive edge `use_libs` | Matches `boost` / `boost_package` today; no surprise fat link lines; auto-enable stays safe | Consumer must call `use_libs` even for “simple” single-lib A |
| **B. Default libs on `BuildWith(A)`** from manifest `default_use_libs` | Zero-call apps “just work” | Fights Boost; easy to over-link; harder for optional-feature packages |
| **C. `use_libs()` / `[]` means all** | One spelling for “give me everything” | Changes today's empty-list behaviour; easy to do by accident; ambiguous with “no libs” |
| **D. Explicit overrides defaults** — `BuildWith` applies `default_use_libs`; later `use_libs(X)` replaces A's defaults; edges still always apply | Convenience + escape hatch | Two link moments; docs must be very clear; still need a “all” spelling |

**Recommendation: A.** Same split Boost already teaches: includes early, libraries on purpose.
Transitive B libs are part of *A's* link contract (declared by the publisher in the manifest), so
they ride along with `A.use_libs(...)`, not with bare `BuildWith(A)`.

### Publisher API

`GitlabPackagePublisher(..., dependencies=[...])` — list of dicts (or objects with
`name` / `version` / optional `package`, `registry`, `use_libs`). Writes
`cuppa-dependency.json` when non-empty; omits the file otherwise.

## Open questions (remaining)

1. Same-B lib union vs error when consumer also calls `B.use_libs` with a different set (lean:
   union of lib names if same package identity; error on version conflict only). MVP applies
   edge `use_libs` once per parent link; explicit consumer `B.use_libs` still runs separately.

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
| `gl-dep-rules` | Done — proposal + settled decisions 2026-09-06 |
| `gl-dep-publish` | Done — `dependencies=` → `cuppa-dependency.json` |
| `gl-dep-consume` | Done — `BuildWith` + transitive `use_libs`; cycles / version conflict |
| `gl-dep-tests` | Done for MVP unit/publish — A→B→C apply chains; live consume E2E still deferred |
| `gl-dep-docs` | Done — `gitlab.adoc` / `packages.adoc` / integration page |
| `gl-dep-list` | Not started |
| `gl-dep-lib-api` | Partial — `use_all_libs()` shipped; named groups / `show_*` deferred |
| `gl-dep-ranges` | Deferred |
| `gl-dep-issue` | Done — [#279](https://github.com/ja11sop/cuppa/issues/279) |
