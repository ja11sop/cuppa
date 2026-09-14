# Plan: Cascade build-and-publish of package dependencies

- **Status:** proposal
- **Related:** [`ROADMAP.md`](../../ROADMAP.md) — `package-build-publish-deps`; [`package-download-refresh.md`](package-download-refresh.md); [`gitlab-package-transitive.md`](gitlab-package-transitive.md); [`cmake-drive-and-package-staging.md`](cmake-drive-and-package-staging.md) (`package-publish-cli`); project **D** soak (google-cloud-cpp stack)
- **Updated:** 2026-09-14
- **Impact:** `minor` (new opt-in CLI / orchestration; default single-package publish unchanged)
- **Defer:** after [#294](https://github.com/ja11sop/cuppa/pull/294) (Option B `cmake_configure_args`) lands — design only until then

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
| **0 — Design** | This plan; settle manifest schema + skip policy + flag name (**parked until after #294**) |
| **1 — MVP** | Author `package_source` on publisher deps → stage **`cuppa-publish.json`** (bridge `cuppa-dependency.json`) + cascade flag + optional `--publisher-root` + refresh + fail-stop |
| **2 — Ergonomics** | Dry-run plan; skip-if-registry-current; clone from `package_source` when the working tree is missing; converge to one traveling file if still bridged |
| **3 — Consume-site parity** | `package_dependency(…, package_source=…)` mirrors publisher-edge metadata |
| **Later** | Parallel independent leaves; Conan parity if needed |

## Open questions

1. **Skip policy:** always rebuild+publish every node, or skip when registry
   already has this package/version/stem and `--force` is off?
2. **Field name:** `package_source` vs `publisher` vs `publisher_location`?
3. **File convergence:** extend `cuppa-dependency.json` in place vs new
   `cuppa-publish.json` with a derived consume file during bridge? (Direction:
   one SoT; exact filename/format bump TBD with transitive plan.)
4. **Develop during cascade:** local `final/` edges vs registry→refresh only?
5. **Flag without `--publish-package`:** build-all-deps-only for local smoke?
6. **Root layout rule:** Cuppa name / package id → subdir under
   `--publisher-root`?

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
| Bridge / converge with `cuppa-dependency.json` | Provisional — one authoring input; exact file layout TBD |
| Defer implementation until after #294 | Settled |
| Project D tip (google-cloud-cpp **3.9.0**) build + publish | Done (manual bottom-up; motivates this feature) |
| Implementation | Not started |
| Issue filed | No |
