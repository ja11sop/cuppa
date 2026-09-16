# Plan: Cascade build-and-publish of package dependencies

- **Status:** in progress
- **Related:** [#297](https://github.com/ja11sop/cuppa/issues/297); [`ROADMAP.md`](../../ROADMAP.md) — `package-build-publish-deps`; [`package-download-refresh.md`](package-download-refresh.md); [`gitlab-package-transitive.md`](gitlab-package-transitive.md); [`cmake-drive-and-package-staging.md`](cmake-drive-and-package-staging.md) (`package-publish-cli`); project **D** soak (google-cloud-cpp stack)
- **Updated:** 2026-09-16
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
| `--publish-package` | Still required to upload; cascade without it is “build deps only” (optional later spelling) |
| `--build-and-publish-dependencies` | Enable cascade for declared GitLab package deps (and their transitive closure) |
| Existing variant / toolchain / identity / parallel flags | Forwarded into each nested publisher invocation |

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
| **2c — Skip and force** | Skip-if-registry-current + `--force`; settles “already up to date” vs “uploaded” in session banners |
| **2d — Converge** | One traveling manifest if `cuppa-publish.json` / `cuppa-dependency.json` are still bridged |
| **3 — Consume-site parity** | `package_dependency(…, package_source=…)` mirrors publisher-edge metadata |
| **Later** | Parallel independent leaves; Conan parity if needed |

## Phase 1 settled decisions

| Question | Decision |
|----------|----------|
| Skip policy | **Always** rebuild+publish every resolved node (no skip-if-registry-current) |
| Field name | **`package_source`** |
| File layout | **Bridge:** keep `cuppa-dependency.json` for consume (no `package_source`); write **`cuppa-publish.json`** with the same edges **plus** `package_source` / package identity. One authoring input (`dependencies=`). |
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
| Plan report shape | Judgement-intro conventions from [`console-report-patterns.md`](../archive/console-report-patterns.md): `Cascade plan: {N} package dependencies then tip [pkg]==[version]: [N errors][N warnings][N notes]`, then the publish order (leaf-first, numbered `n of N`) with each node’s resolved publisher tree hanging under it. Reuse `format_severity_count_brackets`, `emphasised_count_phrase`, `glyphs`, and `wrapped`. The rows stay in **publish order** rather than going through `_judgement_tree_lines`, which groups by severity — order is what this report exists to show, so grouping would destroy it. Unresolved nodes carry their reason inline as an error row. |
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
| Updating an existing clone | Out of scope for 2b: no fetch, pull, or reset. Cascade clones once; keeping trees current belongs to the operator, the develop commands, or a later slice. |
| `--offline` | Refuse to clone, as `--clone-develop` already does. |
| Submodules | Recurse, through the existing `Git.clone( …, recurse_submodules=True )`. |
| Inventory and listing | **Not in 2b.** A cloned tree is reported by path but not added to the dependency inventory or the `--list-*` reports, since a new inventory type reaches into listing-tree presentation. Tracked as an open item below, because storage-root trees are otherwise invisible disk usage. |
| Plan mode and unexpanded edges | `--cascade-plan` reports a node that would be cloned as a **note**, not an error, and says plainly that the node’s own dependencies are unknown until the tree exists: cascade reads `cuppa-publish.json` *from the tree*, so a plan cannot expand beneath a node it has not cloned. |

## Open questions (Phase 2+)

1. Skip-if-registry-current + `--force` (slice 2c; also settles no-op reporting)
2. Making cloned publisher trees visible — inventory entry, a `--list-*` view, and removal,
   so `{storage_root}/publishers/…` is not invisible disk usage (follow-on to 2b)
3. File convergence to a single traveling manifest
4. Flag without `--publish-package` (build-deps-only) — distinct from the
   `--cascade-plan` relaxation above, which builds nothing
5. Richer `--publisher-root` layout rules
6. Cascade under multiple active toolchains — one nested publish per toolchain
   today; whether to batch identities per publisher tree is unexamined

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
| Bridge / converge with `cuppa-dependency.json` | Settled for Phase 1 — dual file, one authoring input |
| Defer until after #294 | Done — unblocked |
| Phase 1 settled decisions (skip / flag / when) | Settled (2026-09-14) |
| Project D tip (google-cloud-cpp **3.9.0**) build + publish | Done (manual bottom-up; motivates this feature) |
| Implementation | Phase 1 shipped ([#302](https://github.com/ja11sop/cuppa/pull/302)): cascade flag, `--publisher-root`, nested argv from tip `sys.argv`, invalidate+re-fetch |
| Corosio→capy local soak | Worked end-to-end (nested capy was up-to-date no-op; tip published) |
| Phase 2 settled decisions (`--cascade-plan`, banners, `url@rev`) | Settled (2026-09-16) |
| Phase 2a — plan report + nested session banners | Shipped ([#303](https://github.com/ja11sop/cuppa/pull/303)) |
| Phase 2b settled decisions (`--clone-publishers`, storage root, no `--develop` role) | Settled (2026-09-16) |
| Phase 2b — clone on demand | In progress |
| Phase 2c / 2d | Not started |
| Issue filed | [#297](https://github.com/ja11sop/cuppa/issues/297) |
