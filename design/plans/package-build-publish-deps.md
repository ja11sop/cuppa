# Plan: Cascade build-and-publish of package dependencies

- **Status:** in progress
- **Related:** [#297](https://github.com/ja11sop/cuppa/issues/297); [`ROADMAP.md`](../../ROADMAP.md) — `package-build-publish-deps`; [`package-download-refresh.md`](package-download-refresh.md); [`gitlab-package-transitive.md`](gitlab-package-transitive.md); [`cmake-drive-and-package-staging.md`](cmake-drive-and-package-staging.md) (`package-publish-cli`); project **D** soak (google-cloud-cpp stack)
- **Updated:** 2026-09-22
- **Impact:** `minor` (new opt-in CLI / orchestration; default single-package publish unchanged)

## Problem

Publishing a deep GitLab package stack (project **D**: Abseil → protobuf → gRPC → …
→ google-cloud-cpp) is a **manual bottom-up ritual**:

1. Open each leaf publisher tree.
2. `cuppa --rel --publish-package --toolchains=…`.
3. Remember order; wait for registry; purge/refresh caches when same-version
   contents change ([`package-download-refresh.md`](package-download-refresh.md)).
4. Repeat for parents; finally build the tip package.

That is error-prone (wrong order, stale cache, skipped leaf) and painful on a
**new OS / toolchain identity** (e.g. Manjaro): every stem must be rebuilt and
published before the tip can consume matching archives. Cuppa already knows the
*consume* graph (`package_dependency` + `cuppa-dependency.json`); operators
reasonably want one command from the tip:

```shell
cuppa --rel --parallel --toolchains=gcc15 \
  --publish-package --build-and-publish-dependencies
```

Meaning: build and publish every required package in dependency order, then
build and publish this project from the freshly published artefacts.

## Intent

Opt-in **cascade publish**: from a publisher (or any project that declares GitLab
package deps and itself publishes), resolve the package dependency DAG, ensure
each node is built and uploaded for the active toolchain/OS identity, then
publish the root — without the operator hand-walking leaves.

Not the default. Not a silent rebuild of the world on ordinary `--publish-package`.

## What already exists

| Piece | Role | Enough for cascade? |
|-------|------|---------------------|
| `package_dependency(…)` in sconstruct | Declared direct deps (name, package, version, registry) | Partial — names/versions only |
| `cuppa-dependency.json` + transitive apply | Edges published *with* an archive | Partial — needs an existing extract; empty/wrong-OS registry is a cold start |
| `--publish-package` + `PublishPackage` | Upload **this** tree’s staged archive | Root only |
| `--develop` + `develop=` on packages | Point consume at a **local package tree** (`include/` / `lib/`) | **No** — not a publisher sconstruct |
| `--list-develop` / `--clone-develop` / … | Location-dep git working copies | **No** — package publishers are a different object |
| `--purge-*` / wipe / planned `--refresh-downloads` | Make consume see a republish | Needed *after* each cascade step |
| OS / toolchain identity at publish | Stem for Manjaro vs Debian, major vs full | Cascade must pass the same identity flags into nested publishes |

**Critical gap:** Cuppa knows *which packages* and *which versions* a project
consumes. It does **not** know *where the publisher source trees* live that
produce those packages. Package `develop=` is a prebuilt prefix, not
`packages/…/sconstruct`. Without a publisher-location map, cascade cannot invoke
nested builds.

## Design options

| Option | Idea | Pros | Cons |
|--------|------|------|------|
| **A. Publisher-home map** | Config / CLI maps Cuppa dep name → directory with that package’s `sconstruct` (cuppaconfig, `--publisher-root=`, or per-dep `--<name>-publisher=`) | Explicit; matches how org publisher forests are laid out today | New config surface; operator must plant/clone trees first |
| **B. `package_source` / `publisher` on the edge** | Each dependency names where its **publisher project** lives (git URL or path), beside the consume pin | Travels with the graph; clone-friendly for a new OS host; one place to read | Couples publish layout into dependency metadata; branch / develop-path policy to invent |
| **C. Derive from a publisher root** | `--publisher-root=…` (or cuppaconfig) + name→subdir / known layout | Less per-edge boilerplate for monorepo forests | Heuristic; still needs overrides when layout is not 1:1 |
| **D. Registry-only rebuild** | No local publishers; somehow rebuild from source tarball metadata in the archive | No local trees | Archives are binaries today; not enough to rebuild; **refuse for MVP** |

**Settled direction (authoring + discovery):** prefer **B** — each dependency
edge carries a `package_source` (name TBD), with **C** as an optional root when
the forest layout is regular, and **A** as an operator escape hatch. **D** out
of scope.

Do **not** overload package `develop=` (prebuilt `include/`/`lib/`) for this.

### Source of truth: `cuppa-publish.json` (travels with the package)

**Settled:** cascade discovery should not depend on re-parsing SConstructs or on
a laptop-only config map. The **one source of truth** is a publish/rebuild
manifest that:

1. Is **authored** beside the publisher (checked-in `cuppa-publish.json` and/or
   generated from `GitlabPackagePublisher(…, dependencies=[…])`).
2. Is **staged into the GitLab archive** next to `include/` / `lib/` (same
   travel story as today’s `cuppa-dependency.json`).
3. Is **read for auto-discovery** after extract: dependency pins **and**
   `package_source` URLs/paths for rebuilding those deps on a new host/OS.

Illustrative shape (schema not final; generic host):

```json
{
  "cuppa_publish_format": 1,
  "package": "google-cloud-cpp",
  "version": "3.9.0",
  "dependencies": [
    {
      "name": "protobuf",
      "package": "protobuf",
      "version": "36.1",
      "registry": "same",
      "package_source": "https://gitlab.example/org/packages/protobuf.git"
    }
  ]
}
```

Publisher kwargs stay the ergonomic Python API; they must **write the same
graph** into that traveling file (not a second, divergent list).

```python
publisher = GitlabPackagePublisher(
    env,
    source_include_dir = os.path.join( str( install_location ), 'include' ),
    source_lib_dir     = os.path.join( str( install_location ), 'lib' ),
    registry           = 'https://gitlab.example/api/v4/projects/org%2Fregistry',
    package            = package,
    version            = version,
    dependencies = [
        {
            'name': 'protobuf',
            'package': 'protobuf',
            'version': '36.1',
            'package_source': (
                'https://gitlab.example/org/packages/protobuf.git'
            ),
        },
        # … further edges …
    ],
)
```

Today `dependencies` is a list of Cuppa **names** (strings). Structured entries
are a **schema bump** (string entries stay valid = name-only, no
`package_source`). Cascade refuses a node with no resolvable source (manifest
field, root derivation, or CLI/config map).

#### Relation to `cuppa-dependency.json`

[`gitlab-package-transitive.md`](gitlab-package-transitive.md) already ships
`cuppa-dependency.json` for **consume** / `BuildWith` closure. Rebuild metadata
must not fork a second incompatible dependency list.

**Provisional convergence:**

| Approach | Role |
|----------|------|
| **Preferred** | One traveling manifest family: `cuppa-publish.json` holds deps **including** `package_source` (and any future rebuild fields). Consume code reads dependency edges from it (or from a thin derived `cuppa-dependency.json` written from the same authoring input so existing readers keep working). |
| **Acceptable MVP bridge** | Keep writing today’s `cuppa-dependency.json` for consume; add `cuppa-publish.json` (or extend the dependency file) with `package_source`. **Refuse** two hand-maintained lists — publisher code generates both from one structure. |
| **Avoid** | Checked-in publish file that is not staged into the archive (breaks auto-discovery on a new host that only has registry packages). |

Cold start: an **other-OS** extract of a mid-graph package can still supply
`package_source` URLs even when the current OS stem is missing — cascade clones
those publisher projects and rebuilds for the new identity. Tip still needs an
entry point (its own manifest / sconstruct deps) to seed the first downloads.

Optional root derivation (C) when an edge omits `package_source`:

```shell
cuppa --rel --publish-package --build-and-publish-dependencies \
  --publisher-root=~/coding/packages
```

Resolve `protobuf` → `~/coding/packages/protobuf` (documented layout rule).

## Proposed CLI (provisional)

```shell
cuppa --rel --parallel --jobs=12 --toolchains=… \
  --publish-package --build-and-publish-dependencies
```

| Flag | Role |
|------|------|
| `--publish-package` | Still required to upload on a full cascade; see companion flags below |
| `--build-and-publish-dependencies` | Enable cascade for declared GitLab package deps (and their transitive closure) |
| `--cascade-plan` | Review only: resolve and report; no clone, no build, no upload |
| `--collect-cascade` | Stage 1 only: resolve + clone missing publisher trees (reuse existing); stop before nested builds/upload. Not `--publish-package -n`. |
| Existing variant / toolchain / identity / parallel flags | Forwarded into each nested publisher invocation |

**Companion flags for cascade** (exactly one intent for a given run):

```text
--build-and-publish-dependencies + one of:
  --cascade-plan      # review (no side effects)
  --collect-cascade   # resolve + clone/reuse trees; stop
  --publish-package   # full cascade (build + upload)
```

**Naming:** keep the user’s long form for clarity; shorter aliases
(`--cascade-publish`, `--publish-dependencies`) are bikeshed later — settle one
primary name before implementation.

**Refuse:** implying cascade from bare `--publish-package` (too surprising; long
builds; registry writes).

## Algorithm (MVP sketch)

```mermaid
flowchart TD
  root[Root publisher configure]
  graph[Build package DAG from declarations + manifests]
  map[Resolve each node to a publisher working tree]
  topo[Topological order leaves first]
  nested[For each node: nested cuppa build + publish-package]
  refresh[Refresh consume cache for that package]
  tip[Build + publish root against registry extracts]
  root --> graph --> map --> topo --> nested --> refresh --> nested
  refresh --> tip
```

1. **Configure the root** enough to enumerate GitLab package deps and read any
   local / already-extracted **`cuppa-publish.json`** (and today’s
   `cuppa-dependency.json` during the bridge).
2. **Union the DAG** from tip edges + auto-discovered manifest edges; fail on
   cycles (same vocabulary as transitive apply).
3. **Resolve publisher trees** from each edge’s `package_source` (clone if
   missing), else root derivation / map. Missing → StopError before any upload.
4. **Topological order**; skip a node only under an explicit policy (see open
   questions: “already in registry for this stem” vs always rebuild).
5. For each node, **subprocess** (or carefully isolated nested session):
   `cuppa -D --<same variant> --toolchains=… --publish-package` (+ parallel /
   offline rules) with cwd = publisher tree. Fail-stop on first non-zero.
   Nested publishes **write/update** `cuppa-publish.json` into their archives.
6. After each successful publish, **invalidate/re-fetch** that package’s
   download+extract ([`package-download-refresh`](package-download-refresh.md)
   or cascade-internal refresh) so parents see the new manifest + libs.
7. **Build and publish the root** against refreshed registry extracts.

Nested invokes must pass through: toolchain list, variant, `--toolchain-identity`,
package OS identity flags, registry token env, and parallelism. They must **not**
re-enter infinite cascade (`--build-and-publish-dependencies` off in children by
default; children rely on already-published leaves).

## Settled refusals (for exploration)

| Refuse | Why |
|--------|-----|
| Overloading package `develop=` as “publisher source” | Today it means prebuilt `include/`/`lib/`; breaking that breaks soak develop workflows |
| Silent cascade on `--publish-package` alone | Registry writes + multi-hour graphs need an explicit flag |
| Solving version ranges / backtracking | Same as transitive MVP — pins only |
| Rebuilding from binary archives without publisher trees | Insufficient input |
| Parallel nested publishes of independent leaves in v1 | Nice later; ordering bugs and registry races first |

## Interactions

| Concern | Notes |
|---------|--------|
| **New OS (Manjaro)** | Primary motivation: one tip command + publisher map + identity flags rebuilds the stem set. Host packages (curl, OpenSSL) remain the operator’s problem |
| **`--offline`** | Cascade publish needs network for registry upload (and usually download of upstream source tarballs inside publishers). `--offline` should error clearly, or allow “build all locally, skip upload” only under a separate future flag |
| **`--refresh-downloads`** | Cascade should refresh after each publish even if the global flag is off; document that coupling |
| **`package-publish-cli`** | Orthogonal tip version pin; cascade forwards the same publish pin story into nested trees when that ships |
| **Transitive / publish manifests** | **`cuppa-publish.json` in the archive** is the SoT for deps + `package_source` (auto-discovery). Bridge with existing `cuppa-dependency.json` without dual maintenance — see above. |
| **Conan** | Out of scope for this flag; Conan has its own graph |

**DAG expansion:** prefer manifest auto-discovery over parsing SConstruct Python.
Nested `--list-dependencies` remains a debug escape hatch, not the primary
design.

## Phases

| Phase | Deliverable |
|-------|-------------|
| **0 — Design** | This plan; settle manifest schema + skip policy + flag name — **done** (#294 / #300 landed) |
| **1 — MVP** | Author `package_source` on publisher deps → stage **`cuppa-publish.json`** (bridge `cuppa-dependency.json`) + cascade flag + optional `--publisher-root` + refresh + fail-stop — **shipped** ([#302](https://github.com/ja11sop/cuppa/pull/302)) |
| **2a — Plan and session visibility** | `--cascade-plan` dry run (judgement-tree report, collected resolution errors) + nested session banners; no registry writes |
| **2b — Clone on demand** | Clone from `package_source` URL (`url@rev`) when the working tree is missing, so a fresh host needs no hand-planted forest |
| **2c — Skip and force** | Skip-if-registry-current + `--force`; multi-toolchain once; sibling-stem-safe refresh; manifest seed key-order fix — **done** ([#323](https://github.com/ja11sop/cuppa/pull/323); not yet in a named release) |
| **2d — Converge** | Single traveling **`cuppa-publish.json`** (stop writing `cuppa-dependency.json`; read fallback for old extracts); amend coupled — **done** (not yet in a named release) |
| **3 — Consume-site parity** | `package_dependency(…, package_source=…)` mirrors publisher-edge metadata — **done** (feature with develop/cascade; polish aligns cascade resolve with `--clone-develop` precedence + `boost_package.define`) |
| **Later** | **Plan** pure-consume cascade (want / refuse / semantics); parallel independent leaves; Conan parity if needed |

## Phase 1 settled decisions

| Question | Decision |
|----------|----------|
| Skip policy | **Phase 1:** always rebuild+publish every resolved node. **Superseded by Phase 2c** (skip-if-current + `--force`) |
| Field name | **`package_source`** |
| File layout | **Phase 1 bridge (superseded by 2d):** dual file. **Phase 2d:** single traveling ``cuppa-publish.json``. |
| Develop during cascade | After each nested publish, **invalidate and re-fetch** that package’s download + extract under the tip’s storage roots (cascade-internal refresh; full `--refresh-downloads` is [#296](https://github.com/ja11sop/cuppa/issues/296)) |
| Flag without `--publish-package` | **Refuse** — require `--publish-package` |
| Flag name | **`--build-and-publish-dependencies`** (aliases later) |
| `--publisher-root` | Optional; resolve missing/`package_source` URL by trying `{root}/{name}`, `{root}/{package}`, then one-level `{root}/*/{name\|package}` |
| Nested recurse | Children run **without** the cascade flag (`CUPPA_CASCADE_NESTED=1`); fail-stop |
| When cascade runs | During tip `GitlabPackagePublisher` construction (SConscript time), **before** CMake Actions, so refreshed extracts are visible to the tip build |
| Missing local tree | StopError — Phase 2 clones from URL |

## Phase 2 settled decisions

Phase 2 is **ergonomics**, split into slices so a registry-writing change never
rides with a reporting change. Slice **2a** (plan + session visibility) writes
nothing to a registry; **2b** (clone) and **2c** (skip-if-current) do.

| Question | Decision |
|----------|----------|
| Dry-run spelling | **`--cascade-plan`** — a dedicated flag. SCons already owns `-n` / `--dry-run` for “do not build”, and cascade’s dry run is “show the resolved order, then stop”; one flag meaning both is a trap. Not a value on the cascade flag either (`--build-and-publish-dependencies=plan`) — `action='store_true'` today, and a value form invites `=false`. |
| `--cascade-plan` without the cascade flag | **Refuse**, same shape as the Phase 1 refusal: the plan describes what the cascade flag would do, so it needs that flag. |
| `--cascade-plan` without `--publish-package` | **Allowed** — this is the one relaxation. Nothing is built and nothing is uploaded, so demanding the publish flag to *inspect* a plan is ceremony. The Phase 1 refusal (cascade requires `--publish-package`) still holds for every real run. |
| Where plan mode stops | Resolve during tip publisher construction, report, then stop after the sconscript read — the `--dump` pattern (`construct.py`), because the DAG is only known once the publisher is constructed. Plan mode must not `Exit()` mid-read, or a multi-toolchain / multi-sconscript run reports only its first tip. |
| Unresolved publisher trees in plan mode | **Collect, do not fail fast.** A real run keeps the Phase 1 StopError on the first unresolvable node; plan mode gathers every unresolved node as a judgement **error** row so one command lists all the trees to plant. Exit non-zero when any error row is present. |
| Plan report shape | Judgement-intro conventions from [`console-report-patterns.md`](../archive/console-report-patterns.md): announce line, then `Cascade plan: {pkg} [{version}] (this package) with {N} package dependencies: [N errors][N warnings][N notes]`, then publish order (leaf-first, numbered `n of N`). Each **package** is a primary node; errors / warnings / notes hang beneath it as severity groups (heading coloured; only `[bracketed]` values coloured in prose) — not a severity-first judgement tree, which would destroy publish order. Unresolved nodes carry their reason under an error group. Console copy says **this package**, not “tip”. |
| Real runs print the plan too | **Yes** — the same report precedes the first nested session, so the operator sees the whole sequence before anything uploads. |
| Nested session banners | Each nested publish gets a begin and end banner carrying **ordinal / total**, label, publisher tree, and (on end) elapsed time and exit status; a closing banner says the tip is resuming. This answers “more than one `scons` ran” without the operator counting `Cascade:` lines. |
| Re-prefixing nested output | **No.** Cascade will not capture nested stdout to indent or tag each line: it would break colour, progress rewriting, and interleaved stderr, and it buffers a long build behind the parent. Strong banners at the boundaries instead. |
| “Already up to date” vs “uploaded” | **Deferred to slice 2c.** The parent cannot honestly tell a no-op nested publish from an upload without either parsing nested output (refused above) or asking the registry — which is exactly what skip-if-registry-current builds. Until then banners report exit status and elapsed, and claim nothing about upload. |
| `package_source` pinning (slice 2b) | Accept `url@rev`, reading like a location dependency pin. Slashy branches (`feature/x`) are safe on disk since [#302](https://github.com/ja11sop/cuppa/pull/302) flattened the folder suffix. No parallel `package_source_rev` field. **Not** reusable from `Location.get_scm_system_and_info`, which only splits a pin off a `vc+scheme` URL (`git+ssh://…`) and returns nothing for the scp-like `git@host:group/name` form `package_source` uses — so cascade splits the pin itself and unit-tests the ambiguous cases (`git@host:name` has no pin, `https://user@host/name` has no pin, `…@feature/x` does). |

## Phase 2b settled decisions (clone on demand)

| Question | Decision |
|----------|----------|
| Clone gate | **Opt-in `--clone-publishers`.** Without it cascade keeps the Phase 1 refusal. Cascade does not merely fetch a tree, it runs `cuppa` inside it, which executes that tree’s sconstruct — and deeper edges come from `cuppa-publish.json` inside **downloaded archives**, so a registry manifest would otherwise choose what a machine clones (with the operator’s SSH agent) and then builds. The operator opts in once, and `--cascade-plan` lists every URL and destination first so the run is reviewable rather than magic. |
| Destination, by default | `{storage_root}/publishers/{name}` — cuppa already owns that tree, so a bare cascade never writes into the operator’s working area unasked. |
| Destination with `--publisher-root` | `{root}/{name}`, the first shape the resolver already searches, so clone and lookup stay symmetric. A flag asking cascade to *read* a forest is taken as permission to *populate* it, which is also where an operator who wants to explore those trees would want them. |
| `--develop` | **No role in cascade.** It is a switch over per-dependency authored paths, not a location policy, and a package’s `develop=` is a *built prefix* — it replaces `_package_dir`, the directory `include/` and `lib/` hang off — not a publisher source tree, so cloning a repository there would break consume. Document the overlap with the develop family and cross-link it; revisit with `--publisher-clone-root=` only if ergonomics demand it. |
| Pins on a filesystem `package_source` | Not supported. A local tree is whatever the operator has checked out, and honouring a pin would mean switching their branch, which cascade refuses to do. Pins apply to URLs only. |
| Collision keying | Key by dependency name, matching the rest of the product — the consume cache is already `downloads_root/packages/{package}/{version}` with no registry in the key. Refuse when two edges want one destination from different URLs. Registry-qualified storage keys is a separate product-wide question, not something this slice solves in one corner. |
| Existing destination | Never clobber. A non-empty destination that is not already that repository is a refusal. An existing clone that is dirty or on another branch is **reported**, not switched, stashed, or reset — the develop family’s philosophy. |
| Updating an existing clone | **Superseded by `--update-publishers`** (below). 2b itself still does not fetch/pull on reuse. |
| `--offline` | Refuse to clone, as `--clone-develop` already does. |
| Submodules | Recurse, through the existing `Git.clone( …, recurse_submodules=True )`. |
| Inventory and listing | **Not in 2b.** A cloned tree is reported by path but not added to the dependency inventory or the `--list-*` reports, since a new inventory type reaches into listing-tree presentation. Tracked as an open item below, because storage-root trees are otherwise invisible disk usage. |
| Plan mode and unexpanded edges | `--cascade-plan` reports a node that would be cloned as a **note**, not an error, and says plainly that the node’s own dependencies are unknown until the tree exists: cascade reads `cuppa-publish.json` *from the tree*, so a plan cannot expand beneath a node it has not cloned. |

## Collect-cascade (shipped)

Soak need: get every publisher tree onto disk (clone where missing, accept paths that
already exist) so a later `--publish-package` cascade is warn/error-light — without
building or uploading, and without branding SCons `-n` as that workflow.

| Question | Decision |
|----------|----------|
| Spelling | **`--collect-cascade`** — gather publisher working trees into place. Rejected: `prepare` (implies build), `materialize`/`materialise` (precise but long; GB-first aliases are fine later if revisited). |
| What it does | Resolve the cascade graph; with `--clone-publishers`, clone missing URL sources into the publishers forest; reuse existing trees; print the usual plan report; **stop before nested builds and before tip build/upload**. |
| What it is not | Not `--publish-package -n` (that still starts nested dry-run sessions — and SCons configure cannot create `.sconf_temp` under `-n`, so a full cascade **refuses** `-n`/`--no-exec` up front). Not build-without-publish. Not a side-effecting `--cascade-plan`. |
| With the cascade flag | Required — same shape as `--cascade-plan`: refuse `--collect-cascade` alone. |
| Without `--publish-package` | **Allowed** — nothing is uploaded; collection is the point. |
| With `--clone-publishers` | Required to create missing trees from URLs; without it, behave like today’s resolve refusals / plan soft-grades for missing cloneable nodes. |
| Exit / finish copy | Exit non-zero on hard resolve errors; warning-only (unused develop, clone opt-in) matches plan-mode grading. Finish line names trees collected / already present; “nothing was built, published, or uploaded.” |
| Build-deps-only (no upload) | **Still deferred** — distinct from collect; needs local consume (slice D) or registry between nodes. |

## Update-publishers (settled 2026-09-18)

Soak: `--collect-cascade --clone-publishers` reuses `~/.cuppa/publishers/capy` and never
fetches — by 2b design — so a merged publisher sconscript on `master` stays invisible until
the operator deletes the forest tree or points `--publisher-root` at a curated checkout.
Currency needs its own verb, parallel to `--update-develop`.

| Question | Decision |
|----------|----------|
| Spelling | **`--update-publishers`** — fetch + fast-forward publisher working trees cascade would use. Not `--update-develop` (that surveys `develop=` paths only). |
| Gates | Same as `--update-develop`: fetch first, then fast-forward only when clean, tracking an upstream, and strictly behind. Dirty, ahead, diverged, detached, no-upstream, or **untracked paths that the FF would overwrite** → leave alone and say why. Never switch branch, stash, or reset. |
| Which trees | Resolved `_publisher_dir` for this tip’s cascade graph. **Skip** trees ranked from `--develop` / `develop=` — those stay under `--update-develop`. Forest (`<storage-root>/publishers`) and `--publisher-root` trees are in scope. |
| With the cascade flag | Required. Refuse `--update-publishers` alone. |
| With `--cascade-plan` | **Refuse** — plan is review-only; update mutates. |
| With `--collect-cascade` | **Allowed** — collect (clone missing) first, then update existing (including trees just cloned, which are already current). Stop before build/upload unless `--publish-package` is also set. |
| With `--publish-package` | **Allowed** — update trees, then run the nested publish cascade. |
| Without `--publish-package` (and without collect) | Resolve + update + **stop** (same exit pattern as collect). |
| `-n` / `--no-exec` | Allowed for update-only / collect+update stop modes. **Online dry-run still fetches quietly** so the ACTION table is honest; only the fast-forward is skipped. Offline dry-run falls back to the last observed ahead/behind (“judged from your last update”). Full cascade with nested sessions still refuses `-n`. |
| `--offline` | Refuse a live update — needs the network. Offline dry-run is allowed (stale judgment). |
| Pins (`url@branch`) | Update does not switch to the pin. If the working copy is on another branch, leave alone (or FF that branch’s upstream if clean+behind). Pin mismatch stays a report, not a checkout. |
| Finish / plan visibility | **ACTION** table shared with `--update-develop` (not `--list-develop`’s STATUS severity): live **updated** / **no change** / **left alone**; dry-run **would update** / **no change** / **leave alone**. Quiet fetch so the table is the only update surface. Finish counts trees updated. Collect finish should eventually distinguish **cloned now** vs **reused** (separate polish). |

## Phase 2c settled decisions (skip-if-current)

Project **D** dual-toolchain tip soak (`google-cloud-cpp` + `--toolchains=gcc15,gcc16`
+ `--publish-package --build-and-publish-dependencies --parallel`, 2026-09-21): a second
identical run still re-downloaded tip packages, ran all nested sessions twice, and
re-uploaded some packages. Operator expectation: **no-op**. That is this slice.

| Question | Decision |
|----------|----------|
| Skip policy (replaces Phase 1 “always publish”) | **Skip nested publish** when the tip’s consume archive for that pin+toolchain identity already matches what nested publish would upload (local `.packaged` / archive up to date **and** registry already has that stem — exact check TBD in implementation: prefer comparing local archive to registry object when cheap; `--force` overrides). Session banners must say **skipped (current)** vs **uploaded**. |
| `--force` | Opt-in: rebuild+upload every resolved node even when current. |
| When to invalidate + re-fetch tip consume | **Only after a nested session that actually uploaded** (or otherwise changed the registry object). Clean sessions already skip refresh; no-op / skipped sessions must too. Do not wipe tip caches “just in case.” |
| Shared download dir vs multi-toolchain | `invalidate_package_consume_cache` must **not** delete sibling toolchain stems under `downloads/packages/<pkg>/<ver>/`. Wipe only the stem (and extract) for the tip variant being refreshed, or refresh in place without deleting other identities. |
| Cascade once per tip command | With multiple tip toolchains, run the nested publish graph **once per publisher tree**, forwarding the tip’s full `--toolchains=` list (already today’s nested argv). Do **not** re-enter `maybe_run_cascade` once per tip `PublishPackage` variant. Tip variant publish still runs per identity after deps are current. |
| Honest second-run no-op | Tip configure must find existing consume archives; nested sessions that skip must not retouch stamps in a way that forces `.published` rebuild; tip must not re-upload when archive + registry are current. |
| `cuppa-publish.json` seed churn | **Bug (fix with or just before 2c).** Nested `build_package` seeds `cuppa-publish.json` into the publisher sconstruct dir via `json.dumps(…, sort_keys=True)`. Tracked manifests authored as `package`/`version` then `dependencies` (edge keys ending in `package_source`) are rewritten to alphabetical key order with **identical semantics** — git shows dirty, cascade warns “uncommitted changes”, and operators think they edited the file. Soak proof: protobuf / re2 / grpc `git diff` is key order only (`json.load` equal). **Fix:** treat on-disk manifest as current when the parsed document equals the document about to be written (do not rewrite for key order alone); prefer stable insertion order from `build_publish_document` over `sort_keys` for new writes. Do not require operators to commit sort-order noise. |

### Soak evidence (project D, 2026-09-21)

- Tip start: `Downloading package […]` for stems missing after the previous run’s last
  cascade wave wiped the shared version dir and re-fetched only one toolchain identity.
- Two full `cascade session 1 of 7` … `sessions complete` waves in one tip command
  (one per tip toolchain / `PublishPackage`).
- Mid-run: `Cascade: invalidated consume cache` + `re-fetched` after **every** nested
  session, including when nested only logged `Package archive […] is up to date; skipping recreate`.
- Re-upload: protobuf / re2 / grpc → `201 Created`; abseil / c-ares / nlohmann / otel →
  skip recreate and no publish. Dirty `cuppa-publish.json` warnings on the uploaders were
  sort-key rewrites from the seed, not operator edits.

## Phase 2d settled decisions (single traveling file)

Neither ``cuppa-dependency.json`` nor ``cuppa-publish.json`` is in a named Cuppa
release yet (both landed under open ``1.11.0.dev``). Converge **now** to one
traveling file rather than keep a derived twin for a release that never shipped.

| Question | Decision |
|----------|----------|
| Traveling SoT | **``cuppa-publish.json`` only** — identity, deps (incl. ``package_source``), ``default_use_libs`` / ``link`` |
| Stop writing | Do **not** emit ``cuppa-dependency.json`` from ``build_package`` / ``amend_package`` / seed |
| Legacy extracts | **Read fallback:** consume apply and ``--list-dependencies`` ``requires`` prefer publish; if absent, read ``cuppa-dependency.json`` |
| Both present | **Publish wins** |
| Amend | Rewrite publish; **remove** any leftover ``cuppa-dependency.json`` before retar |
| Private registry / source trees | Operator **one-off** amend/republish after this lands — not part of the Cuppa PR |
| Couples with | [`package-metadata-amend.md`](package-metadata-amend.md) (amend already on master via #300; single-file behaviour is this slice) |
| Boost ``latest`` | **Done** in [#328](https://github.com/ja11sop/cuppa/pull/328) — seed may keep ``latest``; stage/upload concrete (question 10) |

### Soak note (project D, after #324)

Amending/republishing a **dependency** (same version, new tarball — even when only
``cuppa-publish.json`` changed) still causes cascade to **invalidate + re-fetch**
that pin into the tip consume cache. Tip CMake then sees a newer prefix under
``CMAKE_PREFIX_PATH`` and may **fully rebuild** a fat tip such as google-cloud-cpp.
That is expected today, not a 2d regression. For a tip-only metadata soak, amend
the **tip** itself (``--amend-package-manifest``) and avoid leaf cascade /
``--force`` unless you want that rebuild. Tip no-op when a refreshed dependency
extract is payload-identical aside from traveling JSON is open question 11.

## Phase 3 settled decisions (consume-site parity)

Inventory (2026-09-22): the Phase 3 one-liner was already product behaviour
(``package_dependency(..., package_source=…)``, CLI override, develop + cascade
fallback, docs). Phase 3 closes with polish so cascade and ``--clone-develop``
share one precedence, plan labels stamp the effective source, and
``boost_package.define`` forwards ``package_source=``.

| Question | Decision |
|----------|----------|
| Intent | Consume-site ``package_source`` is the same metadata as publisher-edge / traveling-manifest fields |
| Status | **Feature already shipped**; this slice is polish + plan/ROADMAP honesty |
| Source precedence (cascade) | Match develop: **CLI → factory declaration → tip ``cuppa-publish.json`` edge**; publisher-edge field on the node still wins when set |
| Plan / node display | Stamp the effective source onto the cascade node so ``--cascade-plan`` shows it |
| ``boost_package.define`` | Optional ``package_source=`` forwarded like other ``package_dependency`` kwargs |
| Tip without publisher | Unchanged — cascade still requires tip ``GitlabPackagePublisher`` |
| Next after Phase 3 | **Plan** pure-consume cascade (decide want / refuse / exact meaning); then question 11 or ``--deep-clean`` |

## Open questions (Phase 2+)

1. Making cloned publisher trees visible — inventory entry, a `--list-*` view, and removal,
   so `{storage_root}/publishers/…` is not invisible disk usage (follow-on to 2b)
2. ~~File convergence to a single traveling manifest~~ — settled under Phase 2d (``cuppa-publish.json`` only)
3. Flag without `--publish-package` for **build**-deps-only — distinct from
   `--cascade-plan` (builds nothing) and `--collect-cascade` (clones only)
4. Richer `--publisher-root` layout rules
5. ~~Cascade under multiple active toolchains~~ — settled under Phase 2c (one nested graph
   per tip command; preserve sibling stems on refresh)
6. ~~Implementing `--collect-cascade`~~ — shipped
7. Collect finish: say **reused** vs **cloned** when a forest tree already existed
8. ~~Publisher forest currency~~ — `--update-publishers` (this section)
9. Exact registry comparison for skip-if-current — **done for 2c**: prefer
   local archive size vs registry ``HEAD`` ``Content-Length``; skip only when
   sure (missing length / HEAD failure → publish)
10. ~~**`cuppa-publish.json` + Boost `latest`**~~ — **done** on
    ``feature/boost-publish-latest``: ``GitlabPackagePublisher(version="latest")``
    resolves a concrete pin for ``final/<package>/<ver>/``, the traveling
    archive manifest, and the registry upload URL, while the publisher-tree
    seed may keep ``"version": "latest"`` (or ``current``). Resolution order:
    ``BuildWith`` pin → Boost latest (package ``boost``) → registry latest.
    Floating seed tokens are not used as ``final/…/<version>/`` folder names
    when locating a develop stage.

    **Related (do not conflate):** floating / non-exact package pins more
    generally — e.g. consume or traveling-manifest language for a **minimum**
    (`>=1.28.0`) versus an **exact** pin (`1.28.0` / `==1.28.0`). That sits with
    [`gitlab-package-transitive.md`](gitlab-package-transitive.md) (MVP is
    concrete versions only; ranges / backtracking refused). Boost publish-seed
    ``latest`` is a **named floating token** that resolves once to a concrete
    archive identity; it is a stepping stone toward richer constraint spelling,
    not a constraint solver.
11. **Tip no-op after metadata-only dependency refresh** — when cascade (or a
    same-version leaf amend) re-fetches a dependency whose ``include/`` / ``lib/``
    are unchanged and only traveling JSON differs, avoid dirtying tip CMake /
    a full tip rebuild. Not started; operators should amend the tip itself for
    tip-only metadata soaks (see Phase 2d soak note).

## Acceptance (when implemented)

1. Design index + ROADMAP row; Antora publish docs describe the flag and map.
2. Integration fixture: three-package forest; one command from the tip publishes
   leaves then tip; deliberate wrong order without the flag still documents the
   old pain.
3. After mid-graph republish, parent does not keep stale cache bits.
4. Missing `package_source` / unresolved publisher fails before any upload with
   an actionable error.
5. Nested cascade does not recurse forever.
6. Published archives carry rebuild metadata; a fresh host can auto-discover
   deeper edges from extracted manifests without parsing SConstructs.

## Progress snapshot

| Item | State |
|------|-------|
| Problem / gap (publisher location ≠ package develop) | Captured |
| Authoring: `package_source` on edges + optional root | Captured |
| SoT: traveling **`cuppa-publish.json`** (auto-discovery; one graph) | Settled (2026-09-14) |
| Bridge / converge with `cuppa-dependency.json` | Phase 1 dual-file bridge; **Phase 2d** single `cuppa-publish.json` |
| Defer until after #294 | Done — unblocked |
| Phase 1 settled decisions (skip / flag / when) | Settled (2026-09-14) |
| Project D tip (google-cloud-cpp **3.9.0**) build + publish | Done (manual bottom-up; motivates this feature) |
| Implementation | Phase 1 shipped ([#302](https://github.com/ja11sop/cuppa/pull/302)): cascade flag, `--publisher-root`, nested argv from tip `sys.argv`, invalidate+re-fetch |
| Corosio→capy local soak | Worked end-to-end (nested capy was up-to-date no-op; tip published) |
| Phase 2 settled decisions (`--cascade-plan`, banners, `url@rev`) | Settled (2026-09-16) |
| Phase 2a — plan report + nested session banners | Shipped ([#303](https://github.com/ja11sop/cuppa/pull/303)) |
| Phase 2b settled decisions (`--clone-publishers`, storage root, no `--develop` role) | Settled (2026-09-16) |
| Phase 2b — clone on demand | Shipped ([#305](https://github.com/ja11sop/cuppa/pull/305)) |
| `--collect-cascade` vocabulary (resolve + clone/reuse; stop before build/upload) | **Shipped** (2026-09-18) |
| `--update-publishers` (FF clean/behind forest trees; skip develop) | **Shipped** (2026-09-18) — settled decisions in this plan; ACTION table + quiet fetch; soak on corosio→capy forest |
| Corosio→capy clean + rebuild soak (`-c` then republish) | **Works.** Clean polish shipped (skip re-fetch on clean; clean banners; CMake `-B` survival note). Tip up-to-date / skip-if-current is Phase 2c. |
| Phase 2c settled decisions (skip-if-current, multi-toolchain once, sibling stems, manifest seed churn) | **Settled** (2026-09-21) from project D dual-toolchain tip soak ([#322](https://github.com/ja11sop/cuppa/pull/322)) |
| Phase 2c implementation | **Done** in [#323](https://github.com/ja11sop/cuppa/pull/323) (skip-if-current + `--force`, cascade-once, sibling-stem invalidate, upload-only refresh, semantic `cuppa-publish.json` seed); project D dual-toolchain tip soak confirmed — not yet in a named release |
| Phase 2d settled decisions (single `cuppa-publish.json`) | **Settled** (2026-09-21) — neither file in a named release yet |
| Phase 2d implementation | **Done** in [#324](https://github.com/ja11sop/cuppa/pull/324) — stop writing `cuppa-dependency.json`; consume prefers publish; amend removes twin |
| Issue filed | [#297](https://github.com/ja11sop/cuppa/issues/297) |
| Follow-on: resolve `latest` in publish manifests (Boost) | **Done** in [#328](https://github.com/ja11sop/cuppa/pull/328) (question 10; not ranges / `>=`) |
| Phase 3 consume-site parity | **Done** on `feature/phase3-consume-parity` — inventory + polish (shared resolve precedence, plan stamp, `boost_package.define`); next **plan** pure-consume cascade |
| Follow-on: tip no-op after metadata-only dependency refresh | Open — question 11; project D soak after #324 |
