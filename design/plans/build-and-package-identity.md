# Plan: build and package identity (toolchain major, OS omit, consume matching)

- **Status:** in progress
- **Related:** [`ROADMAP.md`](../../ROADMAP.md) — `tc-identity-coarsen`; original point-release problem [`ignore-toolchain-point-release.md`](ignore-toolchain-point-release.md); package stems [`cuppa/package_managers/gitlab.py`](../../cuppa/package_managers/gitlab.py); layout [`cuppa/core/build_layout.py`](../../cuppa/core/build_layout.py) / [`cuppa/construct.py`](../../cuppa/construct.py); global conf [`cuppa/configure.py`](../../cuppa/configure.py)
- **Updated:** 2026-09-01
- **Impact:** minor — new identity policy and GitLab lookup overrides; existing globals grandfather `full`

This document is the **settled product shape** for 1.9. Point-release encoding, vocabulary, and code hooks stay in [`ignore-toolchain-point-release.md`](ignore-toolchain-point-release.md); do not duplicate that problem statement here.

**Priority:** toolchain **major** identity is the key win (layout churn + package fleets). OS omit and consume overrides are secondary slices.

**Sequencing:** toolchain identity + global-config migration → consume overrides / dual lookup → OS omit at publish.

## Two concerns (keep distinct)

| Concern | Surfaces | User need |
|---------|----------|-----------|
| **A. Identity policy** | What we *key* as (layout + publish stems) | **Major** toolchain token so 15.2/15.3 share trees; optional OS omit when the **package builder** is confident |
| **B. Consume matching** | What we *look up* in the registry | Try a **similar** or **specific** archive when host identity differs (ubuntu → debian package; gcc154 → gcc152 or gcc15 stem) |

B is not the same as A: a project can keep full layout identity locally and still override package lookup for one dependency.

## How identity works today

GitLab archive stem is `{package}_{os}_{tool_variant}` (`tool_variant` = `{package_name}_{variant}_{arch}_{abi}`). OS appears **only in archive filenames**, not in `_build/` or extract dirs. `toolchain.package_name()` currently equals `name()`.

## Settled decisions

### Toolchain identity (layout + default package stems)

| Decision | Choice |
|----------|--------|
| Values | `full` \| `major` (`gcc153`→`gcc15`; keep stdlib tags e.g. `clang21-libc++`) |
| CLI / project config | `--toolchain-identity=` / `toolchain_identity=` in `cuppa.run` and project `configure.conf` (explicit project pin OK) |
| Scope (v1) | One switch coarsens **both** `name()` and `package_name()` |
| Reporting | `--list-toolchains` / describe still show the **real** compiler |
| MSVC | `full` = toolset alias (`vc145`); `major` = `vc` + toolset major (`vc14`, plus `e` if experimental) |

### Defaulting and global `~/.cuppaconfig` only

Intent: **major is the default for new installs**; existing machines with a global conf stay on **full** until they opt in. Do **not** put the grandfather flag in project `configure.conf`.

**Detecting a new install:** absence of `~/.cuppaconfig` ([`Configure.global_config_path()`](../../cuppa/configure.py)). That is **not** “never ran Cuppa.” Cuppa does not create the file on first run; it only loads it if present. Writes today: `--save-global-conf` / `--update-global-conf`, Boost latest persistence when downloads are not under the project, `--clear-global-conf` (delete).

So “file missing” means **this home has no persisted global settings**. That is still the right 1.9 signal:

| Reality | File missing? | Desired identity |
|---------|---------------|------------------|
| Fresh machine / new `$HOME` | Yes | `major` |
| Long-time user who never saved global conf | Yes | `major` — they already live on Cuppa *built-in* defaults |
| User with `~/.cuppaconfig` (any keys) | No | Grandfather `full` if `toolchain_identity` absent; else honour stored value |
| `--clear-global-conf` | Yes again | Treated as new → `major`. Document: clearing global conf opts into the current product default |
| CI / empty `$HOME` | Usually yes | `major` — desirable for new images |

Worse proxies: project `configure.conf` (most trees have one); presence of `~/.cuppa/` storage (would keep veterans who never saved global conf on `full` forever).

**Implementation:** on first 1.9 configure load, if the global file is missing, **create** `~/.cuppaconfig` with at least `toolchain_identity=major` (merge; do not clobber). If the file exists and the key is missing, backfill `full`. The heuristic runs once; the file becomes the source of truth.

| Situation | Effective policy | Config write |
|-----------|------------------|--------------|
| Global file **does not exist** | `major` | Create `~/.cuppaconfig` with `toolchain_identity=major` |
| Existing global file, key absent | Grandfather `full` | Write `toolchain_identity=full` into `~/.cuppaconfig` only |
| Key already present | Honour stored value | Unchanged unless CLI / project / `cuppa.run` overrides |
| Explicit CLI / `cuppa.run` / project conf | Wins per existing precedence | Project pin is **not** the grandfather mechanism |

Notes:

- Store a real value (`toolchain_identity=full|major`), not a separate boolean.
- Precedence: CLI > project conf > global conf > built-in.
- **Cuppa 2.0 (later):** may make `major` the silent built-in default for everyone. By then new installs will already have lived on `major`; grandfathered globals holding `full` are an explicit choice. Do not flip existing globals in 1.x.

### Package OS identity (publish-time opt-in)

| Decision | Choice |
|----------|--------|
| Values | `include` (default) \| `omit` |
| When chosen | **At package build/publish time** when the builder is confident the artefact is not OS-scoped (or consumers will override OS on lookup) |
| CLI / config | `--package-gitlab-os-identity=` / `package_gitlab_os_identity=` (and/or `PublishPackage` argument — settle in PR C) |
| Omit stem | `{package}_{tool_variant}` (no empty OS segment) |

**Often workable:** ABI-stable static lib / headers; controlled fleets; ubuntu↔debian via **explicit** consume override; Windows/macOS already coarse.

**Risky:** silent cross-distro or glibc↔musl; omit as product-wide default.

### Consume overrides and “try similar”

Lookup overrides use a reserved package/backend namespace. The semantic prefix is fixed and the
dependency name is an opaque suffix, avoiding collisions between project-selected dependency
names and future top-level option families:

| Option | Role |
|-----------------|------|
| `--package-gitlab-os-override=<id>` | Project-wide OS segment for **lookup** |
| `--package-gitlab-os-override-<name>=<id>` | Force OS segment for one dependency (e.g. `debian` while host is `ubuntu`) |
| `--package-gitlab-toolchain-override-<name>=<token>` | Force toolchain token for one dependency (e.g. `gcc152` or `gcc15`) |

Dual-lookup during toolchain transition: if the preferred stem 404s, try the other toolchain
identity (full vs major) before failing — on by default
(`--package-gitlab-identity-fallback=on|off`, default `on`).

**Resolution order:**

1. Explicit per-dependency toolchain / OS override (then project-wide OS override if set)
2. Stem from current effective toolchain identity + host OS (or omitted OS if that is the published shape)
3. Fallback: alternate toolchain token (full ↔ major) with same OS choice
4. Fail listing stems tried

Publish emits **one** stem. Dual-try is **consume-only**. Success is an ABI bet the project owns.

## Work slices

| ID | Deliverable | Notes |
|----|-------------|-------|
| `tc-id-vocab` | CLI / config names as in settled table | Done |
| `tc-id-helper` | Reported version → full vs major token (GCC/Clang/MSVC) | Shipped in PR A |
| `tc-id-apply` | Wire into `name()` / `package_name()` | Shipped in PR A |
| `tc-id-config-migrate` | Absent `~/.cuppaconfig` → create `major`; existing missing key → backfill `full` | Shipped in PR A |
| `tc-id-tests` | Unit + integration: full vs major; conf cases | Shipped in PR A |
| `tc-id-docs` | Toolchains + Packages; CHANGELOG; 2.0 outlook one sentence | Shipped in PR A |
| `pkg-consume-override` | Per-dep OS/toolchain lookup; dual-stem 404 fallback | This PR (PR B) |
| `pkg-os-apply` | Publish-time include \| omit; parsers accept both shapes | After consume overrides |
| `pkg-os-docs` | Builder confidence; when omit/cross-OS is sane | Antora |

## Implementation PRs

**PR A** (`minor`) — toolchain identity + global config migration (primary win). **Shipped.**

**PR B** (`minor`) — consume overrides + dual-stem lookup. **This PR.**

**PR C** (`minor`) — package OS omit at publish; align with OS override from B.

## Refusal rules

| Request | Response |
|---------|----------|
| Silent `major` for existing globals without backfill | Refuse in 1.x |
| Auto-grandfather in project `configure.conf` | Refuse |
| Auto-rewrite registry archives or `_build` trees | Refuse |
| OS `omit` as 1.x product default | Refuse |
| Coarsen without documenting ABI risk | Refuse |

## Out of scope

- Encoding musl/glibc explicitly
- Changing Conan package identity
- Making `major` the silent built-in default for **existing** globals in 1.x (2.0 candidate)

## Acceptance (PR A)

1. Missing `~/.cuppaconfig` → `major` and the file is created with that key.
2. Existing global file without the key → `full` and the key is written.
3. `--list-toolchains` / describe still expose the real compiler version.
4. Docs: new-install major, grandfather full, not Boost patched/clean or product SemVer.

## Acceptance (PR B)

1. `--package-gitlab-os-override[-<name>]=` changes the OS segment used for lookup only.
2. `--package-gitlab-toolchain-override-<name>=` selects the preferred toolchain token; dual-try coarsens or pairs full vs major.
3. Preferred stem `404` retries the alternate token; other HTTP errors do not.
4. Failure messages list every stem attempted.
5. `--package-gitlab-identity-fallback=off` disables dual-try.
6. Publish still emits a single stem.
