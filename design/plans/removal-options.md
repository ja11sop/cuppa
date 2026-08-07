# Plan: removal options for build folders and dependencies

- **Status:** in progress
- **Related:** [`ROADMAP.md`](../../ROADMAP.md) — Storage roots, listing, and removal; GitHub [#132](https://github.com/ja11sop/cuppa/issues/132), [#133](https://github.com/ja11sop/cuppa/issues/133), [#134](https://github.com/ja11sop/cuppa/issues/134), [#135](https://github.com/ja11sop/cuppa/issues/135), [#138](https://github.com/ja11sop/cuppa/issues/138), [#145](https://github.com/ja11sop/cuppa/issues/145), [#146](https://github.com/ja11sop/cuppa/issues/146), [#148](https://github.com/ja11sop/cuppa/issues/148), [#153](https://github.com/ja11sop/cuppa/issues/153)
- **Updated:** 2026-08-07

`--list-develop` and `--update-develop` (§3.5, §3.6), the storage rename (§3.1, §8, Phase 1),
build listing/removal (`--list-builds`, `--remove-builds`, `--remove-all-builds`, Phase 2),
Phase 3 **listing** (`--list-dependencies` hierarchical tree, inventory, verbose LOCATION /
`[D]`, docs examples), Phase 3 **removal Slice D** (`--remove-dependencies` /
`--remove-all-dependencies` under `dependencies_root`, project-used name gate, no purge), and
archive clean-by-variant (§4.14.3 — optional `storage_clean`, Boost stage/`bin.<abi>` product
clean, lazy exact inventory sizes on list) are implemented (listing
[#141](https://github.com/ja11sop/cuppa/pull/141) and removal
[#142](https://github.com/ja11sop/cuppa/pull/142) on `master`; archive clean
[#143](https://github.com/ja11sop/cuppa/pull/143)). `--clone-develop` (§3.7) and develop branch
alignment (§3.8) shipped in [#154](https://github.com/ja11sop/cuppa/pull/154) (closes #138 / #153).
Artefact removal (Phase 6) remains open. Phase 4 listing + purge
(`--list-downloads` / `--purge-dependencies` / `--purge-all-dependencies`) is implemented in
[#144](https://github.com/ja11sop/cuppa/pull/144) (closes #134).
Follow-on from the `--clean` work in `cuppa/location.py` and `cuppa/package_managers/gitlab.py`,
where a clean could not complete because a dependency was missing, and where the advice for
leftover artefacts was "remove the folder by hand". Telling people to run `rm -rf` is
unsatisfying: it is platform-specific, it is easy to aim at the wrong path, and cuppa already
knows exactly which folders belong to which variant and which dependency.

This plan proposes a way to list what is in the storage roots, a family of explicit removal
options (Phases 1–4 listing / removal / archive clean / purge done), conservative ways
to create and align develop copies (§3.7, §3.8), and the safety model that governs deletion.

The storage rename came **first** (§6, Phase 1) so every later phase talks about one vocabulary.
Throughout this document the new names are used: `dependencies_root` (was `download_root`) and
`downloads_root` (was `cache_root`). Both default to subfolders of a single `storage_root`,
which defaults to `~/.cuppa` and can be moved with one option.

### Progress snapshot (2026-08-07)

Phases **1**, **2**, **4**, and **5**, Phase **3 listing**, Phase **3 removal Slice D**,
archive clean-by-variant (§4.14.3), **wipe / §4.15**, and develop clone + branch alignment
(§3.7 / §3.8) are **done** or landing
([#141](https://github.com/ja11sop/cuppa/pull/141) /
[#142](https://github.com/ja11sop/cuppa/pull/142) /
[#143](https://github.com/ja11sop/cuppa/pull/143) on `master`;
Phase 4 in [#144](https://github.com/ja11sop/cuppa/pull/144);
wipe in [#150](https://github.com/ja11sop/cuppa/pull/150), closes
[#146](https://github.com/ja11sop/cuppa/issues/146);
§3.7 / §3.8 in [#154](https://github.com/ja11sop/cuppa/pull/154), closes
[#138](https://github.com/ja11sop/cuppa/issues/138) /
[#153](https://github.com/ja11sop/cuppa/issues/153)). #144 closed
umbrella [#134](https://github.com/ja11sop/cuppa/issues/134). Phase **6** and the
deferred Phase 3 polish items remain open and do not keep #134 open.

| Area | State | Notes |
|------|--------|-------|
| Phase 1 — storage rename / shared roots | **done** | #133 / #139 |
| Phase 2 — `--list-builds` / `--remove-builds` / `--remove-all-builds` | **done** | #140 |
| Phase 5 — `--list-develop` / `--update-develop` | **done** | #132 / #137; realistic integration example + docs for which listing to use |
| Phase 3 — `storage_paths()` + resolve-only | **done** | location, GitLab package, Conan, Boost; skips when undeclared |
| Phase 3 — inventory + `--list-dependencies` | **done** | Walk, sizes, `type`, JSON `tree` + flat `entries`, `referenced` / `unreferenced` / `missing`; ANSI-safe column padding; listing does not stamp `last_used`; `Collating dependency tree...` before the walk (text/verbose); lazy exact upgrade for missing/sampled inventory (§4.5); `--list-scope` (alias `--list-dependencies-scope`) |
| Phase 3 — native `du` for exact bytes (§4.5.1) | **future** | Parked; first exact list upgrade felt fine in practice on large Boost extracts — revisit only if that changes |
| Phase 3 — `--list-dependencies` **table presentation** | **done** | Hierarchical tree (§4.9 P1–P4): REMARK / rollups / colour; missing vs stale summaries; `--list-format=verbose` LOCATION; `[D]` + footer (§4.12); GitHub archive grouping; GitLab registry LOCATION on unreferenced too; Windows `.zip` + OS label for package archives; docs examples match real ruled output |
| Phase 3 — inventory `used_by` on resolve | **done** | [#145](https://github.com/ja11sop/cuppa/issues/145) — `BuildWith` stamps `used_by` / `last_used`; listing must not. Empty-map remarks (§4.10) still parked |
| Phase 3 — short-name / stem derivation | **done** | Git remote, gitlab path, Boost + GitHub archive heuristics; inventory `remote_location` / `source_url` |
| Phase 3 — Conan install metadata (§4.7) | **done** | [#145](https://github.com/ja11sop/cuppa/issues/145) — sidecar + `storage_tool_variant()` + list reads `tool_variant` |
| Phase 3 — default-branch quirk (§4.8) | **done** | [#145](https://github.com/ja11sop/cuppa/issues/145) — Canonical `stem@branch` going forward; keep unqualified-only; both → canonical + warn; listing `@master (unqualified)`. No auto-delete |
| Phase 3 — `--remove-dependencies` / `--remove-all-dependencies` | **done** | Slice D on `master` (#142 / §4.13): project-used name gate, hierarchical remove report, multi-toolchain packages, unknown-name in-use tree hint; no purge |
| Phase 3 — archive / Boost clean-by-variant (§4.14) | **done** | #143 — optional `storage_clean` + Boost b2 stage/`bin.<abi>` clean; source-assets leaf + remaining archive size; whole-extract only when unsupported |
| Phase 3 — **dependencies documentation split** (§7.1) | **done** | [#145](https://github.com/ja11sop/cuppa/issues/145) — Hub + children; `packages.adoc` publish focus; `include`/`sys_include` drift fixed |
| Phase 3 — `--list-develop --list-format=json` | **done** | [#148](https://github.com/ja11sop/cuppa/issues/148) — Shared `--list-format=json` parity for develop copies (agents / scripts); text unchanged |
| Phase 4 — downloads list / purge | **done** | `--list-downloads` + `--purge-dependencies` / `--purge-all-dependencies` in [#144](https://github.com/ja11sop/cuppa/pull/144); that PR closes #134 |
| `--wipe-dependencies` / §4.15 | **done** | [#146](https://github.com/ja11sop/cuppa/issues/146) / [#150](https://github.com/ja11sop/cuppa/pull/150) — wipe + force-wipe, selectors, repository rename, shared tokens, summary → type → identity → version → leaves |
| §3.7 — `--clone-develop` | **done** | [#154](https://github.com/ja11sop/cuppa/pull/154) closes [#138](https://github.com/ja11sop/cuppa/issues/138) — refuse pins; recurse submodules; dedicated `Git.clone`, unexpanded URL |
| §3.8 — develop branch alignment | **done** | [#154](https://github.com/ja11sop/cuppa/pull/154) closes [#153](https://github.com/ja11sop/cuppa/issues/153) — checkout / reset; `--location-base-branch`; optional reset target |
| Phase 6 — artefacts | **open** | Sketch only (§4.6) / [#135](https://github.com/ja11sop/cuppa/issues/135) |

**Next focus:** [#135](https://github.com/ja11sop/cuppa/issues/135) (artefacts) when that design pass starts.
Nothing else in this plan is required for the develop/storage listing family to be usable.
Boost package identity stays on [`boost-updates.md`](boost-updates.md). Age-gated unreferenced
GC (`--older-than`) remains deferred (§9). `--develop-root` remains an open question under §3.7
(not required for #138 / #154).

**Deferred Phase 3 polish** ([#145](https://github.com/ja11sop/cuppa/issues/145); parallel branches fine):

1. Inventory `used_by` on resolve (§4.10) — **done** (stamp only; empty-map remarks still parked)
2. Conan install metadata `.cuppa_conan_meta.json` (§4.7) — **done**
3. Default-branch quirk (§4.8) — **done** (canonical `stem@branch`, labels; no auto-delete)
4. Dependencies documentation split (§7.1) — **done**
5. `--list-develop --list-format=json` — **done** ([#148](https://github.com/ja11sop/cuppa/issues/148))

Deferred listing follow-ons remain §4.10 / §4.11 presentation details beyond `used_by`.
Native `du` for exact byte totals (§4.5.1) stays parked — practice on large Boost extracts did
not show a need after the lazy exact upgrade shipped.

---

## 1. Goals and non-goals

**Goals**

- Give the storage roots names that say what is in them, and one option that relocates both,
  before building anything on top.
- Let people **see** what is on disk — dependencies and downloads, with human-readable sizes and
  when each was last used — so they can decide what is worth removing.
- Let people see the state of the local working copies `--develop` substitutes, relative to the
  branch being built, so a mismatched or stale copy is found before it confuses a build (§3.5),
  and bring the out-of-date ones forward where that cannot lose work (§3.6).
- Create a develop working copy that is configured but not yet on disk, so a new machine, or a
  dependency added since you last looked, does not need a clone worked out by hand (§3.7).
- Align those develop copies onto a shared feature branch and back to a configured develop home
  without guessing git parents (§3.8).
- Remove the build output for the *currently selected* variant / toolchain combination.
- Remove the whole build root.
- Remove the on-disk copies of dependencies cuppa manages, either all of them or by name.
- Optionally also remove the downloaded archives those dependencies came from (`--purge-*`).
- Make the selection rules follow the same options that decide where things were written
  in the first place (toolchain, variant, target architecture, ABI, branch matching).
- Log precisely what was removed, what was skipped, and why.

**Non-goals**

- Replacing SCons `--clean`. `--clean` removes *targets*; these options remove *folders*.
  They are complementary: `--clean` is precise and graph-driven, removal is coarse and
  path-driven, and works when the graph can no longer be described.
- Managing storage owned by third-party tools (the Conan home cache, pip caches, system
  package managers). Cuppa only removes what it created.
- Removing output a project writes outside the build root. That is a real need, but it is a
  separate option with a separate design pass (§4.6), not a widening of `--remove-builds`.
- Touching `--develop` working copies or anything outside the storage roots (see §5).

---

## 2. Current behaviour

### 2.1 What exists today

| Need | Today |
|------|-------|
| Remove built targets | SCons `--clean` / `-c`, variant-scoped, graph-driven |
| Remove a variant folder | `--remove-builds` (Phase 2); else manual `rm -rf _build/...` |
| Remove all build output | `--remove-all-builds` (Phase 2) |
| See what dependencies are on disk and how big they are | `--list-dependencies` (Phase 3 listing); missing/sampled inventory sizes upgrade to exact on list (#143) |
| Remove one stale dependency | `--remove-dependencies=name` (Slice D / #142); selection-scoped |
| Remove archive build products without wiping the extract | `storage_clean` / Boost stage + `bin.<abi>` (#143 / §4.14.3) |
| Remove all dependencies used by this project (current selection) | `--remove-all-dependencies` (Slice D / #142); leftovers for other selections reported |
| Remove cached archives | `--purge-dependencies` / `--purge-all-dependencies` (Phase 4); selection-scoped, project-used names |

The listing gap matters as much as the removal gap. Working across branches leaves
branch-qualified trees (`…@feature_x`) behind indefinitely, and nothing ever reports them, so
they accumulate unnoticed until a disk fills.

### 2.2 Storage roots

From `cuppa/core/storage_options.py` **after Phase 1**:

| Key | Default | Set by |
|-----|---------|--------|
| `build_root` / `abs_build_root` | `_build` | `--build-root` |
| `storage_root` | `~/.cuppa` | `--storage-root` |
| `dependencies_root` | `<storage_root>/dependencies` | `--dependencies-root` |
| `downloads_root` | `<storage_root>/downloads` | `--downloads-root` |

`download_root` and `cache_root` remain as aliases of the resolved `dependencies_root` and
`downloads_root` (and `--download-root` / `--cache-root` as deprecated CLI aliases) so plugins and
`~/.cuppaconfig` entries keep working. Where an older tree already exists — project-local `_cuppa`,
or `~/_cuppa/_download` / `~/_cuppa/_cache` — and no root is named, that tree is kept in use so an
upgrade does not re-fetch; see §8.5.

Shared dependency trees are now the default, which is what makes stale trees across projects
worth a managed removal command in later phases.

### 2.3 Build root layout

`cuppa/construct.py` (`call_project_sconscript_files`) composes, per sconscript and variant:

```
tool_variant_dir = <toolchain.name()>/<variant>/<target_arch>/<abi>
build_dir        = <build_root>/<sconscript path without ext>/<tool_variant_dir>/working
final_dir        = .../final
```

Two consequences matter for removal:

1. Variant folders are **nested per sconscript**, not top-level. A project with
   `test/orders/sconscript` writes to `_build/test/orders/gcc153/dbg/x86_64/cxx2c/…`,
   while a root sconscript writes to `_build/gcc153/dbg/x86_64/cxx2c/…`. Removing
   "the current variant" therefore means finding every `<tool_variant_dir>` subtree under
   the build root, not deleting one known path.
2. Location dependencies that compile their own sources write to
   `<abs_build_root>/<location folder>/<tool_variant_working_dir>` (see
   `build_library_from_source` in `cuppa/build_with_location.py`). Those folders are keyed by
   the location folder name, and are exactly the leftovers the current `--clean` warning
   points at.

### 2.4 Dependencies root layout

Written by several subsystems, all under `dependencies_root`:

| Producer | Path shape |
|----------|-----------|
| `cuppa/location.py` (VCS) | `<dependencies_root>/<folder_name_from_path(url)>[@<branch or tag>]` |
| `cuppa/location.py` (archives) | `<dependencies_root>/<folder_name_from_path(url)>` (extracted) |
| `cuppa/package_managers/gitlab.py` | `<dependencies_root>/<tool_variant>/<package>/<version>/` |
| `cuppa/build_with_conan.py` | `<dependencies_root>/conan/<dependency name>/<fingerprint[:16]>/` |

The `@<branch>` suffix is decided by relative versioning plus `--location-match-current-branch`
/ `--location-match-branch` / `--location-match-tag`, so the *same* dependency can legitimately
have several sibling folders. Removal has to be explicit about which of those it is deleting.

Conan install directories are keyed by a content hash of Conan settings (and the conanfile /
lock), not by cuppa's `tool_variant` string — see §4.7. Without persisted metadata, a listing
can only show the dependency name and an opaque fingerprint prefix.

### 2.5 Downloads root layout

| Producer | Path shape |
|----------|-----------|
| `cuppa/location.py` | `<downloads_root>/<local folder name>` — the raw downloaded archive (extension preserved; often `.tar.gz`, `.zip` on Windows Boost downloads) |
| `cuppa/package_managers/gitlab.py` | `<downloads_root>/packages/<package>/<version>/<package file>.zip` on Windows, `.tar.gz` elsewhere (download also accepts the alternate extension) |

The names after Phase 1 match the contents: `dependencies` holds extracted, ready-to-use trees;
`downloads` holds the archives they came from. Older layouts used `_download` / `_cache` under
`_cuppa` for the same split (§8.5).

---

## 3. Proposed CLI surface

All options are opt-in, and all of them are *actions* rather than modifiers.

### 3.1 Storage roots (Phase 1)

| Option | Env key | Default |
|--------|---------|---------|
| `--storage-root` | `storage_root` | `~/.cuppa` |
| `--dependencies-root` | `dependencies_root` | `<storage_root>/dependencies` |
| `--downloads-root` | `downloads_root` | `<storage_root>/downloads` |
| `--build-root` | `build_root` | `_build` (unchanged, project-relative) |

`--storage-root` exists because the two roots are almost always moved together: a machine with a
small home partition, a CI image with a warm cache on another volume, or a user who wants
everything cuppa manages under one visible folder should say that once rather than twice, and
should not have to keep the two halves consistent by hand.

Precedence is the obvious one, and worth stating because both can come from `~/.cuppaconfig` as
well as the command line: `dependencies_root` and `downloads_root` are derived from
`storage_root` unless they are set explicitly, in which case the explicit value wins and is used
exactly as given. Setting `--storage-root=/mnt/cache/cuppa --downloads-root=/fast/ssd/downloads`
therefore puts dependencies under `/mnt/cache/cuppa/dependencies` and downloads on the SSD, and
cuppa reports both resolved paths when either is not at its default.

`--storage-root` deliberately does **not** move `build_root`. Build output is project-relative,
belongs beside the sources it came from, and is the one root people already expect to find in
their working copy.

`--download-root` and `--cache-root` keep working as deprecated aliases, as do the
`download_root` and `cache_root` environment keys. See §8 for the naming rationale, the default
location change, and migration.

### 3.2 Listing

Read-only, and useful on their own:

| Option | Reports |
|--------|---------|
| `--list-dependencies` | Every dependency tree under `dependencies_root`, with size, which dependency name owns it, which branch or tag qualifier it carries, and when it was last used |
| `--list-downloads` | Every archive under `downloads_root`, with size and the dependency it feeds |
| `--list-builds` | Three views of `build_root`: folder summary, toolchain → variant tree, and sconscript tree, plus an explicit command for the selected builds |

A fourth listing, `--list-develop`, answers a different question — the state of local working
copies rather than what storage costs — and is covered separately in §3.5.

#### Which listing for which question

These options are easy to conflate because `--develop` is both a build switch and a word that
appears in `--list-develop`. They answer different questions:

| You want to know… | Use | Looks at |
|-------------------|-----|----------|
| What is under the shared dependencies root, and which trees this sconstruct would use | `--list-dependencies` | `dependencies_root` |
| What state the configured develop *working copies* are in (branch, dirty, behind) | `--list-develop` | Develop paths from the sconstruct |
| What is under `_build` | `--list-builds` | `build_root` |

**Normal dependency storage listing does not need `--develop`:**

```
cuppa -Q -D --list-dependencies
```

Resolve marks the tree this project would use without develop as `referenced`, and sibling
branches / other projects' leftovers as `unreferenced`. Registry names appear when resolve (or a
prior inventory touch) bound them.

**`--list-develop` does not need `--develop` either.** It reports every dependency that *has* a
develop path configured, and says whether `--develop` is currently active. Passing `--develop`
only changes that banner line; the table is the same working copies.

```
cuppa -Q -D --list-develop
```

**`--list-dependencies --develop` is optional and uncommon.** `--develop` is a build switch:
resolve location deps to working copies instead of the cache. `--list-dependencies` reuses that
resolve for remarks, so with `--develop` active those identities show REMARK `develop` on the
dependency name (branch leaves unmarked) rather than `in use` on a cache leaf — the cache trees
remain listed under the identity. That is useful only when you care how the storage table would
look *as if* you were about to build with `--develop`. It is not how you inspect develop
checkouts (use `--list-develop`) and not the default way to reclaim disk (omit `--develop`).

Motivating examples:

```
# How much of ~/_cuppa/_download (or ~/.cuppa/dependencies) is mine vs leftover?
cuppa -Q -D --list-dependencies

# Are my develop checkouts on the right branch / clean / behind?
cuppa -Q -D --list-develop

# Only if you specifically want storage remarks under a develop resolve:
cuppa -Q -D --list-dependencies --develop
```

Each listing ends with a total and, where cuppa can tell, partitions entries the current build
does *not* reference as `unreferenced` — the transient-branch trees that are the usual reason a
storage root has quietly grown. Sizes are human readable by default (`1.2G`, `340M`), come from
the inventory rather than a fresh walk of the whole root, and carry a leading `~` when they were
estimated by sampling (§4.5); a `--list-format=json` variant makes the output scriptable without
parsing columns.

`--list-dependencies` prints a **ruled hierarchical table** (referenced then unreferenced; type
→ identity → branch / version / toolchain children) with rolled-up SIZE and LAST USED, REMARK
on useful nodes, and full-width partition rules. Default columns omit on-disk paths;
`--list-format=verbose` adds LOCATION (remotes, registry URLs, archive basenames) and prefixes
regenerating downloads with `[D]` (§4.12). Columns are padded by visible width so ANSI colour
does not stretch the rules. Shape detail and implementation history live in §4.9; the Antora
Dependencies page carries annotated examples that match real output.

```
Dependencies in /home/user/.cuppa/dependencies
Default dependencies: boost_package
  ---------------------------------------------------------------------
      SIZE  LAST USED  REMARK   DEPENDENCY
  ---------------------------------------------------------------------
    299.3M  today      1 total  referenced
                                │
    299.3M  today      1 used   ├── dependencies in use
                                │
    299.3M  today      1 used   └── gitlab packages
                                    │
    299.3M  today                   └── boost_package
    299.3M  today                       └── 1.91
    299.3M  today      in use               └── gcc153_rel_x86_64_cxx2c
  ---------------------------------------------------------------------
      5.8M  today               unreferenced
                                │
      5.8M  today               └── source archives
                                    │
      2.9M  today                   ├── boost
      2.9M  today                   │   └── 1.91.0
                                    │
      2.9M  today                   └── github.com/fmtlib/fmt
      1.4M  today                       ├── 11.1.4
      1.5M  today                       └── 12.2.0
  ---------------------------------------------------------------------
  3 entries, 305.1M total, 5.8M unreferenced
```

`TOOLCHAIN VARIANT` is no longer a separate column: GitLab and similar trees nest the toolchain
string under the version. Location trees nest `@branch` (or `@` for an unqualified stem — see
§4.8). Conan install dirs do not encode a toolchain string in the path; until install metadata
is persisted (§4.7), Conan children stay fingerprint-labelled, which is not enough to act on.
`LAST USED` comes from the inventory (§4.5) and is the column that turns a listing into a
decision — a tree last used in March, by a project you finished, is an easy reclaim.
`--list-downloads` uses the same ruled hierarchical language as `--list-dependencies`, oriented
around each identity’s archive and the extract/package it feeds (flat `SIZE | ARCHIVE | FEEDS`
is superseded):

```
Downloads in ~/.cuppa/downloads
Default dependencies: boost, boost_package
  ---------------------------------------------------------------------------------
      SIZE  LAST USED  REMARK   DEPENDENCY / DOWNLOAD
  ---------------------------------------------------------------------------------
    180.0M  today      2 total  referenced from downloads
                                │
    142.0M  today      1 used   ├── source archives
                                │
    142.0M  today               │   └── boost
    142.0M  today      in use   │       └── boost_1_91_0.tar.bz2
       2.1G  today      in use   │           └── [E] boost/1.91.0
                                │
     38.0M  today      1 used   └── gitlab packages
                                │
     38.0M  today               └── boost_package
     38.0M  today                   └── 1.91
     38.0M  today      in use           └── boost_…_gcc153_rel_….tar.gz
    299.3M  today      in use               └── [E] gcc153_rel_x86_64_cxx2c
  ---------------------------------------------------------------------------------
     36.0M  today               unreferenced downloads
                                │
     36.0M  today               └── gitlab packages
                                    │
     36.0M  today                   └── boost_package
     36.0M  today                       └── 1.91
     36.0M  today                           └── boost_…_clang211_rel_….tar.gz
  ---------------------------------------------------------------------------------
  3 archives, 216.0M download total, 36.0M unreferenced

[E] = dependency extracted from the download above
```

`--list-builds` is three related views of the same walk, not a flat table:

```
  --------------------------------------------------------------------
      SIZE  LAST BUILD    BUILD FOLDER
  --------------------------------------------------------------------
    229.5M  today         ~/coding/project/_build
    124.5M  today         └── selected (25 of 39 entries)
  --------------------------------------------------------------------

  --------------------------------------------------------------------
      SIZE  LAST BUILD    BY TOOLCHAIN VARIANT
  --------------------------------------------------------------------
     51.4M  2 years ago   ├── --- clang211
     51.4M  2 years ago   │       └── --- dbg/x86_64/cxx2c
     14.6M  today         └── ✓✓✓ gcc153
     14.6M  today                 └── ✓✓✓ dbg/x86_64/cxx2c
  --------------------------------------------------------------------

  --------------------------------------------------------------------
      SIZE  SELECTED      BY SCONSCRIPT
  --------------------------------------------------------------------
     41.1M                ├── test
     20.4M      ✓         │   └── gcc153
     14.6M      ✓         │       └── dbg/x86_64/cxx2c
  --------------------------------------------------------------------

  Selected 124.5M of 229.5M (25 of 39 entries)

  Explicit command for the selected builds:

  cuppa -D --dbg --toolchains=gcc153

  Append --remove-builds to clear those folders.
```

The folder section hangs the **selected** subset under the build root with the same branch
notation (`all N entries selected` when every entry matches). The toolchain section is the prune
view: age and size without per-sconscript noise, grouped as `toolchain` → `variant/arch/abi`,
with `✓✓✓` / `-✓-` / `---` for full, partial, and unselected (ASCII `*`). Toolchain names and
marks use the info colour; fully selected name rows also emphasise size, mark, and name.
Partial and unselected rows are dimmed. The sconscript section is a rollup tree with the same
marks; toolchain children are listed before nested folders under a mixed parent. Sconscript
names (the folder above the toolchain variants) and their marks use the info colour, subdued
when not fully selected, and emphasised when fully selected. Tree branch glyphs are always
subdued. A closing summary emphasises the selected size (info-coloured when it is less than the
total) and prints an explicit `cuppa -D …` command for the selected builds that exist on disk
(formatted like `--show-conf`), so appending `--remove-builds` clears those folders without
naming absent variants.

In `--list-format=json` the same structures appear as `folder`, `by_toolchain_variant`,
`by_sconscript`, `summary`, and a flat `entries` list (`size_bytes` alongside human-readable
`size`), so scripts read fields by name and people read columns.

The summary command is the prompt to reclaim space: the tables show what is selected; the
command is what you append `--remove-builds` to.

### 3.3 Removal

| Option | Removes |
|--------|---------|
| `--remove-builds` | Every `<tool_variant_dir>` subtree under `build_root` matching the current toolchain / variant / arch / ABI selection |
| `--remove-all-builds` | The `build_root` folder itself |
| `--remove-dependencies=dep1,dep2` | The `dependencies_root` folders for the named dependencies, for the current selection |
| `--remove-all-dependencies` | As above for every dependency the current build knows about |
| `--purge-dependencies=dep1,dep2` | As `--remove-dependencies` plus the matching archives under `downloads_root` |
| `--purge-all-dependencies` | As `--remove-all-dependencies` plus every download those dependencies own |
| `--remove-artefacts` | Sconscript-generated output written **outside** `build_root` (needs its own design; §4.6, Phase 6) |

The build options are confined to `build_root`. Everything a project writes elsewhere — the
conventional `_artifacts/` tree that collated coverage indexes and reports land in, generated
sources, copied runtime files — is `--remove-artefacts`' problem, not `--remove-builds`'s. That
separation keeps the build options describable in one sentence each and keeps the harder
discovery question (§4.6) out of their way.

Modifiers:

- **`-n` / `--no-exec`** (SCons built-in, read via `GetOption('no_exec')`) turns any removal into
  a dry run: cuppa reports exactly what it would remove and removes nothing. This reuses an
  option people already know rather than inventing `--dry-run`.
- Existing selection options (`--toolchains`, `--dbg` / `--rel` / `--cov`, `--location-match-*`,
  `--build-root`, `--dependencies-root`, `--downloads-root`) narrow the scope, exactly as they
  narrow where cuppa writes. Target architecture and ABI are not options: they come from the
  toolchain (`toolchain.make_env` / `toolchain.abi`), so removal must derive them the same way
  rather than asking the user for them.

Naming rationale: `remove` says what happens without implying the graph-driven meaning that
`clean` already has in SCons; `purge` reads as "and don't keep a copy to restore from", which is
exactly the difference between a dependency tree that can be re-extracted from a local archive
and one that has to be fetched again.

### 3.4 Interaction with building

First implementation: listings and removals run **instead of** a build. Cuppa resolves
configuration and scope, reports, removes, and exits with a summary. This avoids the surprise of
deleting a tree that the same invocation is about to populate, and avoids ordering questions
with `--test`.

If a "remove then rebuild" workflow proves wanted, it can be added later as an explicit
`--and-build`, rather than making it the default.

### 3.5 `--list-develop`

A related question, answered by `--list-develop` (shipped): when `--develop` is active — or when
develop paths are configured at all — **what state are the local working copies actually in?**

`--develop` swaps a retrieved dependency for a working copy on disk (`cuppa/location.py`, the
`develop` branch of `Location.__init__`). That is the right tool for changing two repositories
together, and it is silent about everything that can go wrong with it. You can be building your
feature branch against a dependency parked on someone else's spike branch, or against a copy
that has not been pulled since March, and the only symptom is a compile error that makes no
sense, a test that fails only on your machine, or worse, one that passes only on your machine.
The retrieved-dependency equivalent of this problem is already handled — that is what
`--location-match-current-branch` is for — but nothing checks the develop copies that replace
them.

This is a different problem from the rest of this plan: nothing is measured, nothing is
inventoried, and nothing is removed. It belongs here because it completes the family of
read-only "tell me what I am actually building against" options, and because it shares their
wiring.

**Name.** `--list-develop`, because `develop` is already the noun cuppa uses (`--develop`,
`--<name>-develop`), and the entries are develop locations rather than a distinct kind of
dependency. `--list-develop-dependencies` would be more symmetrical beside `--list-dependencies`
/ `--list-downloads` / `--list-builds`, but it is longer for no gain in clarity.

**What it reports.** One row per dependency that has a develop location configured, whether or
not `--develop` is currently active, plus a count of the dependencies that have none:

```
cuppa: develop: [info] Building on branch [feature_orders]; --develop is active
cuppa: develop: [info]   DEPENDENCY  BRANCH          UPSTREAM              STATE               PATH
cuppa: develop: [info]   widget      feature_orders  origin/feature_orde…  modified, 2 ahead   ~/coding/widget
cuppa: develop: [info]   gadget      master          origin/master         clean               ~/coding/gadget
cuppa: develop: [warn]   sprocket    master          origin/master         modified            ~/coding/sprocket
cuppa: develop: [warn]   flange      spike_cache     origin/spike_cache    clean, 12 behind    ~/coding/flange
cuppa: develop: [warn]   doodad      (detached)      -                     clean               ~/coding/doodad
cuppa: develop: [warn]   thing       master          -                     not a working copy  ~/coding/thing
cuppa: develop: [error]  gizmo       -               -                     path does not exist ~/coding/gizmo
cuppa: develop: [info] 7 develop locations: 2 ok, 4 warnings, 1 error; 4 dependencies not using develop
cuppa: develop: [warn] [sprocket] has uncommitted changes on the default branch [master]; a build that does not use --develop resolves [sprocket] to published [master] and will not see them
cuppa: develop: [warn] [flange] is on [spike_cache], which is neither [feature_orders] nor the default branch
cuppa: develop: [warn] [flange] is 12 commits behind [origin/spike_cache] as of your last fetch
```

The table is the inventory of what you are building against; the lines after it are the
judgements, repeated in full so that the reason is readable without decoding a column.

**Classification.** Severity is the whole value of the option, so the rules should be explicit:

| Situation | Severity | Why |
|-----------|----------|-----|
| Branch equals the branch being built | ok | The matching-branch workflow, done by hand |
| Branch equals the default branch (`--location-default-branch`, or the remote's default) | ok | The normal case for a dependency you are not changing |
| Any other branch | **warning** | The case that silently produces inexplicable builds |
| Detached HEAD | **warning** | Works today, forgotten tomorrow |
| Behind upstream | **warning** | "Not up to date" — the second failure mode, and invisible without asking |
| Diverged from upstream | **warning** | Behind *and* ahead; a merge or rebase is pending |
| Ahead of upstream, on the branch being built | note | Unpushed local work is the point of `--develop` |
| Modified working tree, on the branch being built | note | Likewise expected; worth showing, not worth warning about |
| Ahead of upstream, on the default branch | **warning** | Local work nobody else will see (below) |
| Modified working tree, on the default branch | **warning** | Same |
| No upstream tracking branch | note | Ahead and behind cannot be answered, and the report should say so rather than imply "clean" |
| Not a working copy | **warning** | A directory that is not under version control cannot be reasoned about |
| Path does not exist | **error** | Nothing checks this today: the develop swap does not verify the path, so the failure surfaces much later as a missing include |

Local work is only benign where the rest of the world will find it. Uncommitted or unpushed
changes on a branch that matches the branch being built are the intended workflow: when that
branch is pushed, `--location-match-current-branch` selects it and everyone else's build sees
the same code. The same changes sitting on the default branch are a trap. Your build works,
because `--develop` reads the working copy; every build that does not use `--develop` resolves
the dependency to the *published* default branch and compiles something else. That failure
arrives late, in CI or on a colleague's machine, and it is expensive to diagnose from the far
end. So the warning names the remedy rather than only the symptom: put the work on a branch
named for the branch you are building, commit it, and push it.

The same reasoning is why local work on any *other* branch is already a warning: the copy is
neither what your build will publish nor what an ordinary build resolves.

Two rules keep the report honest. Ahead and behind are relative to the **last fetch**, and the
output says so rather than implying live remote state; no network access happens, consistent
with how `--offline` and the rest of these read-only options behave. And for Subversion,
Mercurial, and Bazaar copies, branch and revision come from the existing `info()` support while
ahead / behind / modified are reported as `unknown` rather than guessed.

**Implementation notes.**

- Register with the other location options in `cuppa/core/location_options.py`, carry it into
  the environment in `process_location_options()`, run it after dependency registration in
  `cuppa/construct.py`, and exit the way `--dump` does.
- Enumerate `cuppa_env['dependencies']`. Location dependencies expose the develop location
  through `location_id( env )`, which returns `(location, develop, branch_path, use_develop)`,
  and through `_default_develop`; GitLab package dependencies keep their own `develop` handling
  in `cuppa/package_managers/gitlab.py` and should appear in the same table.
- Resolve the develop path exactly as `Location.__init__` does — `expanduser`, then the `#`
  anchor to `sconstruct_dir` — through a shared helper, so a listing can never disagree with the
  swap it is describing. This is the same anti-drift argument as the `tool_variant_dir` helper
  in §4.1.
- The branch being built is already in `cuppa_env['current_branch']` and
  `cuppa_env['current_revision']`, populated during startup.
- Working-copy state comes from `cuppa.scms.scms.get_current_rev_info( path )`, which returns
  `(url, repository, branch, remote, revision)` for every supported backend. Ahead, behind, and
  modified need two more git commands, which `Git.execute_command()` already supports:
  `git status --porcelain` for cleanliness and
  `git rev-list --left-right --count @{upstream}...HEAD` for the two counts. Adding them as a
  `Git.get_working_copy_state( path )` helper keeps the option from shelling out on its own,
  and other backends can return `unknown` until someone needs better.
- Exit status is zero for a report, non-zero only when a develop path does not exist, because
  that build cannot succeed and a CI job should hear about it.

**The natural follow-on.** Once the classification exists, the warning lines — not the table —
are worth printing at the start of *any* build with `--develop` active. That is where they
prevent the wasted hour, rather than requiring you to suspect the problem first and then ask.
That should be a small, separate change once the rules have proved themselves, and it needs a
way to silence it for people who know exactly what their tree looks like.

### 3.6 `--update-develop`

`--list-develop` tells you a copy is twelve commits behind. The obvious next question is "then
bring it up to date", and answering it by hand means visiting several directories and running
the same two commands in each.

**In scope: fetch and fast-forward.** `--update-develop` takes no value. For each develop copy
it fetches, and then fast-forwards the checked-out branch **only** when the copy is clean and
strictly behind its upstream. Everything else is skipped and reported with the reason: ahead,
diverged, modified, detached, no upstream, not a working copy, path missing.

That is deliberately the whole of it, and it is in scope precisely because it cannot go wrong.
A fast-forward of a clean tree discards nothing, invents no commits, and leaves no state to
recover from; the worst outcome is that a copy people wanted to leave alone moves forward, and
`git reflog` undoes even that. It also covers the two scenarios that prompt the option: a copy
on the **default branch** or on the **branch being built** that is simply out of date.

It reuses `--list-develop` wholesale. The classification in §3.5 already decides what state each
copy is in; this option adds a fetch, one decision per copy — fast-forward or skip — and the
reporting.

**What it never does.** It does not touch a copy with uncommitted changes, and there is no
stashing: a stash is a state a person has to remember they are in, and a build system leaving
one behind on a failed run is exactly the kind of surprise these options exist to avoid. Nothing
is force-updated, nothing is reset, no history is rewritten, and no branch is switched — a copy
on the wrong branch is a decision for a person, and `--list-develop` has already explained why
it matters. A copy whose warning is "local work on the default branch" is deliberately **not**
fixable here: the remedy is a branch, and creating branches on someone's behalf is a step too
far.

**Network and offline.** This is the one option in the family that reaches the network, so it
must be explicit about it: `--offline` makes `--update-develop` an error rather than a silent
no-op, and the report says what was fetched.

**Reporting and dry runs.** It prints the `--list-develop` table before acting, the actions it
took, and the table again afterwards, so the effect is visible rather than inferred. `-n` shows
the plan and changes nothing, exactly as it does for removal (§3.3). Updating several
repositories is not atomic: a failure in one is reported, the rest continue, and the exit status
is non-zero.

**Future modes, informed by use.** Everything beyond fast-forwarding is a judgement about
someone's unpublished work, so it should be designed after `--list-develop` *and*
`--update-develop` have shown which states people actually reach and which skips they find
themselves working around by hand. Recorded here so the shape is not invented in a hurry:

| Form | Behaviour | Waiting on |
|------|-----------|-----------|
| `--update-develop=fetch-only` | Fetch and update remote-tracking refs, change no working copy, so the ahead / behind counts in `--list-develop` are current without touching anything | Evidence that people want fresh counts without any update at all |
| `--update-develop=allow-rebase` | As the default, plus: when a copy is *ahead* or *diverged* and the tree is clean, rebase the local commits onto the upstream, refusing if any commit being replayed is already published | How often "diverged" actually occurs, and whether the published-commit check can be made reliable enough to trust |
| `--update-develop=allow-merge` | As the default, plus merge rather than rebase, for teams that prefer merge commits | Whether anyone asks; it is only worth two code paths if both are used |

Two things follow from adding values later rather than now. Modes must be **additive to the
default** — fast-forward what can be fast-forwarded, and the value says what else you are
willing to tolerate — so that the option people already know keeps behaving the way they learned
it. And because the value slot is spoken for, per-dependency scoping would need its own option
(`--update-develop-only=dep1,dep2`), which is a further reason to wait until there is evidence
that scoping is wanted at all.

### 3.7 Cloning a develop copy that is not there yet

Tracked as GitHub [#138](https://github.com/ja11sop/cuppa/issues/138). The surface is settled —
a first-class `--clone-develop` — and the remaining design questions are **settled** below;
implementation can proceed.

Using `--list-develop` on real projects surfaced a case the two options above only report on: a
dependency has a develop path configured, and there is nothing at that path. Today that is the
one row `--list-develop` calls an `error`, because a build with `--develop` active cannot
succeed, and the remedy is entirely manual — find the remote, clone it into exactly the right
directory, and check out a branch that will not immediately be flagged as wrong.

Three situations produce that row, and all three are ordinary:

- **A new machine.** Someone joins, or rebuilds their laptop, has their SSH key working, and
  wants the set of repositories the project develops against.
- **A dependency added since you last looked.** The project grew a new component; everyone
  else's tree has it, yours does not, and the first sign is a failed build.
- **A dependency you have never needed to edit until now.** It was being retrieved into the
  dependencies root and that was fine, until the change you are making spans it.

**Cuppa already knows all three of the things a person has to work out by hand.** The location
dependency carries the remote and, often, the branch (`git+ssh://…/widget.git@master`); the
develop clause carries the destination, resolved by the same `develop_location()` helper the
report and the swap both use; and §3.5's classification already produces the row that says the
destination is empty. So this is a new *action* over observation that exists, in the same shape
as §3.6: one decision per copy, taken from state already gathered.

**Surface.** Three candidates, and the choice matters because it decides what `--update-develop`
promises:

| Form | For | Against |
|------|-----|---------|
| Fold into `--update-develop` | One command makes the environment right, which is what a newcomer wants | Changes the option's character. Fast-forwarding is seconds and reversible; cloning is minutes, megabytes, and network. A missing path is also what a **typo** in a develop clause looks like, and answering a typo by cloning a repository into it is the wrong reflex |
| `--update-develop=clone-missing` | Fits the additive-modes idea already set out in §3.6 | The modes slot was reserved for *how much of someone's unpublished work you are willing to disturb*. Creating a copy is a different axis, and overloading the slot makes both harder to explain |
| A first-class `--clone-develop` (**recommended**) | Keeps `--update-develop`'s promise intact; composes — `cuppa -D --clone-develop --update-develop` is the onboarding command, and either half is useful alone; leaves the mode slot for tolerance levels; says plainly what it does | One more option in the family, and people have to learn that update does not clone |

The third is the one taken. The family then reads as three verbs over one observation:
`--list-develop` looks, `--clone-develop` creates what is missing, `--update-develop` moves
forward what is behind. §3.8 adds branch-alignment verbs on the same observation.

**Which branch a fresh copy lands on.** A clone that is born a warning is a poor introduction, so
the checkout has to satisfy §3.5's rules rather than merely succeed. The order should be: the
branch being built, when the remote has it and the project is using branch matching; otherwise
the branch the location names; otherwise the remote's default branch. What it must **never** do
is leave a detached HEAD, which is what checking out a tag or a revision produces. That is a real
difference from managed retrieval, where a detached checkout at a pinned revision is exactly
right: a copy in the dependencies root is read, and a develop copy is worked in. Where the
location pins a tag or a revision, **refuse with an explanation** (settled) — do not invent a
containing branch.

**Credentials must not end up in the clone.** `Location.expand_secret` puts tokens into HTTPS
URLs so retrieval can authenticate. A develop copy lives in someone's home directory for months,
so writing `https://oauth2:<token>@host/…` into its `.git/config` would persist a credential
where nobody thinks to look for one, keep working after the token should have been rotated, and
travel into the first support paste that includes `git remote -v`. The clone must therefore use
the **unexpanded** URL and let SSH or the user's git credential helper answer, and refuse with a
clear message rather than quietly embedding a secret. This also argues against cuppa growing a
protocol option: git already rewrites remotes through `url.<base>.insteadOf`, so a developer who
wants SSH where the project names HTTPS can say so once in their own git configuration, and both
cuppa and every other tool honour it.

**Do not reuse pip VCS retrieval** (`Location.obtain_from_repository`). Retrieval may expand
secrets and may detach at a pin — both wrong for develop clones. Use a dedicated `Git.clone` on
the unexpanded repository URL.

**Where it must refuse.** Cloning is the one write in this family with no destructive potential,
but only because it never touches anything that already exists:

| Situation | Response |
|-----------|----------|
| Destination is a working copy already | Nothing to do; that is `--update-develop`'s job |
| Destination exists and is not empty | Refuse and report. Emptying it is a person's decision |
| Destination exists and is empty | Clone into it |
| Parent directories are missing | Create them, and say which were created |
| Dependency has no develop clause | Skip. Nothing says where the copy should go (see the follow-on below) |
| Location is an archive, a plain path, or an unsupported VCS | Skip with the reason; there is nothing to clone |
| Location pins a tag or revision | Refuse; develop copies must land on a branch |
| `--offline` | An error, exactly as for `--update-develop` — this option is nothing but network |
| Authentication or remote failure | Report per dependency, continue with the rest, exit non-zero |

Nothing is ever removed, moved, or overwritten, which is what makes the option safe enough to
run without a dry run first — though `-n` still prints the plan: what would be cloned, from
where, to where, and on which branch.

**Submodules and depth.** Recurse (`submodule update --init --recursive`) by default. Shallow
clones are not offered.

**Reporting.** The same shape as §3.6 — the table before, a line per copy saying what was cloned
and where, and the table afterwards. A successful clone turns an `error` row into an `ok` row,
which is the proof the reader wants, and the closing suggestion that names what
`--update-develop` would do next follows naturally from it.

**Follow-on: the one-command fresh machine.** Everything above assumes the develop paths are
already configured, which in practice means a shared `configure.conf` or the clauses being in the
`sconstruct`. That covers the second and third situations completely and the first one as soon as
the newcomer has the project's configuration. It does not cover the truly bare machine, where
nothing yet says where copies should live. A `--develop-root=<path>` that clones every dependency
to `<root>/<name>` and treats those as the develop locations would close that gap, but it turns
cuppa from something that reads your configuration into something that writes it, so it deserves
its own design pass rather than being smuggled in here.

**Follow-on: name the option in the failure.** When a `--develop` build fails because a develop
path does not exist, the message should say which option creates it. That is a one-line change
once the option exists, and it is how most people will discover it. **In scope for #138.**

**Testing sketch.** The decision is a third pure function over the state §3.5 already observes —
`clone_action(copy, location)` returning create-or-skip and a reason — so every row of the
refusal table above is a unit test with no network. Integration tests clone from a local origin:
one landing on the branch being built, one falling back to the remote default, one refusing on a
non-empty directory, and one asserting that no token appears in the resulting `.git/config`.

### 3.8 Aligning develop copies onto a feature branch

Tracked as GitHub [#153](https://github.com/ja11sop/cuppa/issues/153) (sibling of
[#138](https://github.com/ja11sop/cuppa/issues/138)). Motivation: you start
a feature branch on the consumer project (repo A) and depend on several locally checked-out
develop copies. You want those copies on the **same** branch name so related edits share a
branch, then return everyone to the **develop home** after the work merges.

Git does not record “branched from X”, so cuppa does not guess a parent. Home is **policy**:

| Notion | Option | Role |
|--------|--------|------|
| Published / repo default | `--location-default-branch` (default `master`) | Non-`--develop` resolution story; “local work on default is a trap” in `--list-develop` |
| Develop base (home) | `--location-base-branch` | Where new feature branches are **created from**, and where bare `--reset-develop-branch` returns. When unset, base ≡ default |

Long-running integration lines set base once (`--location-base-branch=integration` or conf).
Simple repos leave it unset.

**Surface.** Two first-class flags (not modes of `--update-develop`):

| Flag | Role |
|------|------|
| `--checkout-develop-branch=NAME` | Create if needed and switch every develop git working copy to `NAME`. Special value **`current`** means the consumer project's `current_branch`. |
| `--reset-develop-branch[=NAME\|current\|default\|base]` | Return copies to a target, then fetch + ff-only (same gates as `--update-develop`). **Bare** flag (or `=base`) → develop base. `=default` → `location_default_branch`. `=current` / `=NAME` → that branch. |

Philosophy matches §3.6: **act where safe; skip and report where a person must decide.** The
before/after report is the same `--list-develop` table. Unpushed commits and dirty trees stay
visible there — guide the user to commit and push before abandoning a feature branch or before
considering a reset “done”.

`--list-develop` treats a copy as on an acceptable branch when it is on the consumer's current
branch, the published default, **or** the develop base (when base ≠ default).

**`--checkout-develop-branch` per copy**

| State | Action |
|-------|--------|
| Missing path | Skip; point at `--clone-develop` |
| Already on `NAME` | Skip (“already on …”) |
| Dirty, diverged, or ahead in a way that switching would lose work | Refuse |
| Detached / non-git | Refuse |
| Clean; remote has `NAME` | Fetch; checkout tracking `origin/NAME` (do not recreate from base) |
| Clean; no remote `NAME` | Via **develop base**: checkout base → fetch + ff → `checkout -b NAME` (or local `NAME` if it already exists) |

**`--reset-develop-branch` per copy:** resolve target (bare → base); if not on target, checkout
target (refuse if unsafe); then fetch + ff-only. Do **not** delete leftover feature branches —
leave them for manual cleanup.

**`--offline`:** error (network required). `-n`: print the plan. Package develop paths without a
VCS remote are skipped with a reason (same as clone).

**Out of scope:** `--develop-root`; inventing develop paths; force-deleting feature branches;
rebase/merge modes on `--update-develop`; inferring parent branch from merge-base / reflog / forge.

---

## 4. Scope resolution

### 4.1 `--remove-builds`

1. Compute `tool_variant_dir` for each active toolchain / variant / arch / ABI, using the same
   composition as `construct.py` so the two cannot drift. Factor that composition into a shared
   helper (for example `cuppa/core/build_layout.py`) and call it from both places. Architecture
   and ABI have to come from the same `create_build_envs` path that the build uses, since ABI is
   toolchain-derived and sanitised (`c++2c` becomes `cxx2c`).
2. Walk `abs_build_root` and collect any directory whose path ends with a computed
   `tool_variant_dir`. This catches per-sconscript nesting and per-location dependency build
   folders in one pass.
3. Report the list, remove it, then prune directories that are left empty so the tree does not
   fill with skeletons.

Selecting several toolchains (`--toolchains=gcc,clang`) removes several subtrees; that follows
the build semantics and needs no special case.

Nothing outside `abs_build_root` is a candidate, even when the build put it there. A project
that collates coverage into `_artifacts/` keeps that tree; §4.6 covers it.

### 4.2 `--remove-all-builds`

Remove `abs_build_root` outright. Only one guard is interesting: refuse when `build_root` has
been pointed somewhere unexpected (see §5).

### 4.3 Dependency removal

Dependency paths are only fully known once locations have been resolved, and resolution
normally implies retrieval. The plan is to add a **resolve-only pass**, in the same spirit as
`--dump`:

- Dependencies are created with retrieval disabled (the `retrieval_disabled_reason()` mechanism
  added for `--clean` already expresses this; extend it to cover removal actions).
- Each dependency contributes its removable paths through a small optional protocol, so that
  removal does not have to reverse-engineer each subsystem's layout:

```python
def storage_paths( self ):
    """Return the on-disk paths this dependency owns."""
    return {
        'dependencies': [ ... ],   # extracted / working trees under dependencies_root
        'downloads':    [ ... ],   # archives and package files under downloads_root
        'build':        [ ... ],   # artefacts under build_root, if it builds from source
    }
```

The same protocol drives `--list-dependencies` and `--list-downloads`, so listing and removal
can never disagree about what a dependency owns.

Implementations needed: `location_dependency` (from `Location.base_local()` and
`local_folder()`), `GitlabPackageDependency` (`_package_dir`, `_download_target`,
`_extraction_dir`), the Conan consumer (`<dependencies_root>/conan/<name>`; the Conan home cache
is explicitly out of scope and should be reported as "not managed by cuppa"), and Boost.

Dependencies that do not implement the protocol are reported as **skipped, reason: layout not
declared**, never guessed at.

Names accepted by `--remove-dependencies=` are the names used in the `sconstruct`, that is the
keys of `cuppa_env['dependencies']`. Unknown names are an error listing the known ones, since a
typo that silently removes nothing is worse than a failed command. Concrete Slice D decisions,
examples, and checklist: §4.13.

`--remove-all-dependencies` covers dependencies known to *this* build: the union of
`default_dependencies` and anything reached through `BuildWith`. It deliberately does not sweep
the dependencies root for unknown folders — that would delete other projects' dependencies from
a shared root. Those unknown folders are exactly what `--list-dependencies` marks as
`unreferenced`, so the workflow is "list, look, then remove by name" rather than a blind sweep.
A `--remove-unreferenced-dependencies` can follow once the inventory (§4.5) has proved its
picture is trustworthy.

**Scoped to the current selection.** Within those known dependencies, `--remove-all-dependencies`
removes what the current selection would *use* and reports what it is leaving behind. Package
trees are per toolchain, so `--toolchains=gcc` removes the gcc trees and reports the clang ones;
VCS trees are not per toolchain, so they are removed once, and branch-qualified siblings follow
the rule in §4.4. This is the same principle as the branch handling: never delete something the
options given did not select, always say what remains and how to reach it.

```
cuppa: remove: [info] Removing dependencies for gcc153_dbg_x86_64_cxx2c
cuppa: remove: [info]   removed 4 trees, 3.1G
cuppa: remove: [info]   leaving 6 trees, 4.4G, for other selections:
cuppa: remove: [info]     clang211 (3 trees, 2.9G), gcc153_rel (2 trees, 1.2G), @feature_x (1 tree, 0.3G)
cuppa: remove: [info]   (--toolchains=gcc,clang widens this, --list-dependencies shows everything)
```

### 4.4 Branch-qualified folders

When relative versioning is active, the folder carries an `@<branch>` / `@<tag>` suffix. Removal
targets the folder the current options select, and **reports the siblings it is leaving alone**:

```
cuppa: remove: [info] Removing dependency [widget]
cuppa: remove: [info]   /home/user/.cuppa/dependencies/git_ssh_..._widget@master  1.4G
cuppa: remove: [info]   leaving 2 sibling branches in place: @release_1.14 (1.4G), @feature_x (1.3G)
cuppa: remove: [info]   (use --list-dependencies to review them, or name them to remove them)
```

### 4.5 The inventory

A shared dependencies root is written by many projects and read by none of them. Sizes alone
cannot answer the question people actually have, which is not "how big is this" but "is anything
still using it". An inventory turns the listing from a directory walk into an account of what
cuppa did.

**Location and shape.** One JSON file per entry, under
`<dependencies_root>/.cuppa-inventory/<entry key>.json`, rather than a single shared file.
Per-entry files make concurrent builds safe with an atomic write (write to a temporary file in
the same directory, then `os.replace`) and no lock, and a corrupt or unreadable entry costs one
row of listing detail instead of the whole inventory. The directory is hidden so it never
appears as a dependency in a listing or a glob.

Each entry records what cannot be recovered by looking at the folder:

```json
{
  "path": "/home/user/.cuppa/dependencies/git_ssh_..._widget@master",
  "type": "location",
  "kind": "location",
  "dependency": "widget",
  "qualifier": "@master",
  "tool_variant": null,
  "source_url": "ssh://git@git.example/org/widget.git",
  "remote_location": "git+ssh://git@git.example/org/widget.git@master",
  "downloads": [ "/home/user/.cuppa/downloads/..." ],
  "first_seen": "2026-03-02T09:14:11Z",
  "last_used": "2026-07-30T18:02:44Z",
  "used_by": { "/home/user/coding/project-a": "2026-07-30T18:02:44Z",
               "/home/user/coding/project-b": "2026-06-11T10:21:03Z" },
  "size": { "bytes": 1503238553, "measured": "2026-07-30T18:02:44Z", "method": "sampled" }
}
```

`type` is one of `gitlab`, `conan`, `location`, or `archive`. It is classified from path shape
(plus a cheap `.git` check) on today's flat root so a later namespaced layout migration can move
trees without re-guessing. `kind` is kept as an alias of `type` while older readers catch up.

`source_url` is typically a live git remote; `remote_location` is the configured identity
(pip-style VCS URL, or GitLab `registry/package/version`). Disk layout alone cannot invent a
GitLab registry host/project path — listing stamps `remote_location` when resolve knows it, and
sibling versions of the same package inherit that base with their version segment substituted so
unreferenced GitLab rows can still show a registry URL under `--list-format=verbose`.

**When it is written.** On every successful resolve, cuppa touches `last_used` and the
`used_by` entry for the current sconstruct directory. That is one small write per dependency per
build, which is negligible beside the resolve itself, and it is the only write on the hot path.
Removal deletes the entry with the tree.

**Advisory, never authoritative.** The inventory informs reporting; it never authorises a
deletion. Every path is re-checked on disk and re-tested for containment (§5) before anything is
removed, and an inventory entry whose path no longer exists is reported and dropped. This is
what keeps stale state from becoming dangerous state: the worst a wrong entry can do is produce
a wrong number in a listing.

**What it buys.** `--list-dependencies` gains a `LAST USED` column and can say "last used by
project-a, three months ago" instead of only a size. `--remove-unreferenced-dependencies`
becomes defensible, because "unreferenced" stops meaning "this build does not mention it" and
starts meaning "nothing has used it since a given date". A `--remove-dependencies-older-than=90d`
falls out of the same data if it proves wanted.

**Prerequisite for empty-`used_by` remarks.** Listing today creates inventory entries with
`update_last_used=False`, so `used_by` is often `{}` even for trees that builds have used.
Do **not** surface an "unrecorded" / "no record" remark (or similar) until resolve/build stamps
`used_by` reliably — otherwise almost every row would claim to be unrecorded. See §4.10.

**Recorded paths are local.** `used_by` holds absolute project paths. That is exactly the point
on a personal machine, and it is why the inventory stays inside the storage root — it is never
uploaded, packaged, or shared, and a multi-user shared root is already outside what this plan
supports.

**Sizing is sampled on resolve, then upgraded to exact on list.** Walking a multi-gigabyte
shared root on every resolve would make ordinary builds feel slow, so sizes come from the
inventory:

- A size is measured when an entry is first created during resolve/build (sampled for large
  trees), and re-measured when the entry is used and the recorded size is older than the tree's
  most recent modification, so a tree that has not changed is never walked twice for that path.
- Large trees may be **sampled** during resolve: walk to a bounded number of entries, then
  estimate the remainder from the mean file size seen, and record `"method": "sampled"`. A
  sampled cell is marked with a leading `~` (`~1.4G`) so an estimate never masquerades as a
  measurement.
- `--list-dependencies` **lazily upgrades** missing or sampled inventory sizes to exact on
  encounter (one notice when that pass may take a while). Subsequent listings reuse the exact
  cache unless the tree changes or `--exact-sizes` forces a full remeasure of every tree.
- A listing with no inventory yet still works: it measures exact sizes as it goes and writes
  entries, so the first list is the slow one and subsequent runs are effectively instant.

Exact measurement today uses Python `os.walk` + `lstat` (`cuppa.utility.storage.directory_stats`).
That is correct and portable. A faster native path is recorded below as a **future optimisation
only** — do not implement unless practice shows the first exact upgrade (or `--exact-sizes`) is
painful enough to justify the platform surface.

#### 4.5.1 Future optimisation — native `du` for exact byte totals (not scheduled)

**Status:** proposal / park. Ship nothing from this subsection until sizing latency is a
measured problem on real dependency roots (large archive extracts such as Boost are the likely
trigger). The inventory cache and lazy exact upgrade already avoid repeating the deep walk on
every list; this subsection is only about making that **first** exact pass cheaper.
**Practice note (2026-08-05):** after lazy exact upgrade landed, a first `--list-dependencies`
on a large Boost extract felt no slower than the previous sampled path in interactive use —
keep this parked.

**Do not conflate discovery with sizing.** Listing already uses two different walks:

| Purpose | Code | Depth |
|---------|------|-------|
| Discover ownership units under `dependencies_root` | `_walk_dependency_trees` | Shallow: VCS tops, `tool/package/version`, archive extract roots. Does **not** descend into Boost headers/libs. |
| Measure bytes for one ownership unit | `measure_size` → `directory_stats` | Deep: every regular file under that path when measuring or upgrading. |

We do **not** walk all of Boost to *find* it. We walk Boost only when we need an **exact** size
and the inventory lacks a fresh exact entry. There is no portable OS call that returns
“recursive bytes under this folder” without visiting the tree: `stat`/`lstat` on a directory is
directory metadata only, not the sum of children. Tools such as `du` look fast because they are
native walkers; they still traverse. Approximate sampling, or trusting a prior exact inventory
entry, are the only ways to avoid a deep visit for a total.

**What a `du` path would buy.** Not a different cost model — still one deep traversal — but a
potentially faster implementation for huge trees (native C, better dentry caching) versus
Python `os.walk`. Calling `du` as a subprocess is therefore an **acceleration of exact byte
totals**, not a way to skip walking Boost.

**Recommended shape if ever needed** (narrow; low–moderate effort):

```text
directory_bytes(path) -> int
  if a recognised usable `du` is on PATH:
      run it, parse one integer
  else:
      existing os.walk / lstat sum (current directory_stats bytes path)
```

Wire that into exact `measure_size` and optionally removal’s byte helper only. Leave
`directory_stats` on `os.walk` until mtime is redesigned: that helper returns **both** total
bytes and newest mtime, and build listing (`--list-builds`) uses both for `SIZE` and
`LAST BUILD`. Putting `du` behind all of `directory_stats` forces a second strategy for mtime
(another walk, or weaker “top dir only” semantics) and is where complexity and behaviour drift
appear. Exact dependency sizing only needs bytes — that is the sweet spot.

**Effort ballpark**

| Scope | Rough effort |
|--------|----------------|
| Prefer GNU `du` when `du --version` looks GNU; else walk; exact inventory + removal bytes only | Small (~half day including tests/docs) |
| + macOS/BSD apparent-size where flags exist | Small add-on |
| + threshold / “use `du` only for large trees” | Small |
| + change `directory_stats` so builds also use `du` **and** keep newest-mtime meaning | Medium |

**Fiddly points to get right (not hard, but must not be hand-waved)**

| Issue | Detail |
|--------|--------|
| Semantics | Today cuppa sums `st_size` and does not follow directory symlinks. Prefer GNU `du -sb --apparent-size` (or equivalent). Plain `du -sb` is **disk blocks** (`st_blocks`), which will disagree with current numbers and with human expectations for “how big is this tree”. |
| Platform flavours | GNU coreutils ≠ BSD/macOS `du` flags. Feature-detect once per process; unknown `du` → walk. Do not pretend every `du` on `PATH` is the same. Windows CI has no `du` by default — fallback keeps that green. |
| Symlinks | Match “don’t follow directory symlinks” or document a deliberate difference. |
| Spawn cost | Hundreds of tiny trees: many `du` processes can lose to one Python walk. Optional heuristic: use `du` only above a size/file threshold, or always for exact upgrades (Boost-sized extracts are the case that matters). |
| Failure modes | Non-zero exit, odd locale output, paths with spaces — catch and fall back to walk. |

**Rationale for parking.** The correct optimisation for day-to-day listing is already in place:
cache exact sizes in `.cuppa-inventory/` and upgrade missing/sampled entries once with a notice.
A native `du` helper is worthwhile only if that first exact pass (or forced `--exact-sizes` over
many large trees) is still too slow in practice. Until then, extra platform surface is pure cost.

### 4.6 Artefacts outside the build root — sketch only

Projects write generated output beyond `build_root`: collated coverage indexes under
`_artifacts/`, generated sources, copied runtime files, reports. Removing those is a real need,
but it needs its own design pass, and this plan deliberately stops at a sketch rather than
guessing.

The name is `--remove-artefacts`, with `--remove-artifacts` accepted as a spelling alias, since
cuppa's prose uses "artefacts" while the conventional folder is `_artifacts`.

Two candidate mechanisms, not yet chosen:

1. **Ask SCons.** The build graph knows every target cuppa's methods created, including ones
   outside the build root, so a resolve-and-walk pass could collect them. This is attractive
   because it needs no project cooperation and cannot drift from what was actually built. It is
   also where the overlap with `--clean` lives: SCons `--clean` already removes tracked targets,
   so the honest question is what is left over that `--clean` misses — directories rather than
   files, outputs from `Command` actions whose targets are not fully declared, and anything
   produced by an invocation whose graph can no longer be constructed. That question should be
   answered with evidence before an option is added.
2. **Let the project declare it.** Something like `artefact_roots=[ '_artifacts' ]` in the
   `sconstruct`, or an `env.ArtefactRoot(...)` call, giving an explicit list that removal treats
   the way it treats the storage roots — with the same containment rule, so a declared root must
   resolve inside the project.

The likely answer is both: declaration for the coarse trees a project knows it owns, discovery
for the rest, with removal reporting which mechanism found each path. Until that is worked out,
`--remove-builds` and `--remove-all-builds` stay confined to `build_root`, and the documentation
says plainly that artefact trees are not removed.

### 4.7 Conan install metadata (for useful `--list-dependencies`)

GitLab package trees encode the toolchain variant in the path
(`gcc153_rel_x86_64_cxx2c/capy/1.0`). Conan trees do not. Without extra metadata,
`--list-dependencies` can only report something like `conan` / `fmt` / `ada9fefffbb67043` —
enough to know a package exists, not enough to decide whether it belongs to this project's
clang debug build or yesterday's gcc release experiment. That makes Conan rows in the listing
nearly pointless until the install directory can describe itself.

#### How selection works today

Cuppa does **not** look up Conan packages by tool-variant folder name. On each
`env.BuildWith` for a Conan dependency (`cuppa/build_with_conan.py`):

1. The active env's toolchain and variant are mapped to a Conan settings dict
   (`conan_settings_for`: `os`, `arch`, `build_type`, `compiler`, `compiler.version`,
   `compiler.cppstd`, `compiler.libcxx` / MSVC runtime, …).
2. A **fingerprint** is `sha256` over the dependency name, those settings, and the conanfile
   (and `conan.lock` when present). The install directory is
   `<dependencies_root>/conan/<name>/<fingerprint[:16]>`.
3. If that directory already has `.cuppa_conan_ok` whose contents equal the full fingerprint
   (and `SConscript_conandeps` is present), the install is reused; otherwise cuppa runs
   `conan install` with the matching `-s` flags and writes `.cuppa_conan_ok` as a plain hash
   string.
4. Flags are applied from `SConscript_conandeps` via `MergeFlags`.

The fingerprint is one-way. Path walking cannot recover compiler, ABI, or cuppa's
`tool_variant_dir` string. Heuristics from generator filenames
(`conanbuildenv-debug-x86_64.sh`) only yield build type and arch. `.cuppa_conan_ok` stores
only the hash. `storage_paths()` can compute the *current* selection's install dir during
resolve-only, but Conan does not yet implement `storage_tool_variant()`, and unreferenced
trees never see a resolve.

The Conan home cache (`~/.conan2`) remains out of scope — cuppa only manages the generators
install directories under `dependencies_root`.

#### Change required

Persist a small **sidecar** next to each successful install, written when cuppa already knows
the truth:

**When (primary).** Immediately after a successful `conan install`, in the same place that
writes `.cuppa_conan_ok` today (`_run_conan_install`). At that point `settings`, `fingerprint`,
toolchain, and variant are all in hand — no extra Conan queries.

**When (backfill).** On the reuse path (fingerprint already matches), if the sidecar is
missing, write it from the current resolve's settings. That repairs older install trees the
next time a project uses them. Pure disk walks still cannot invent metadata for leftovers that
are never reused; those keep showing fingerprint-only until removed or touched by a build.

**What.** Keep `.cuppa_conan_ok` as the plain fingerprint so the existing equality check stays
simple. Add `.cuppa_conan_meta.json` beside it, for example:

```json
{
  "fingerprint": "ada9fefffbb670432cd7e59cc73d6ec1…",
  "name": "fmt",
  "tool_variant": "gcc153_dbg_x86_64_cxx2c",
  "settings": {
    "os": "Linux",
    "arch": "x86_64",
    "build_type": "Debug",
    "compiler": "gcc",
    "compiler.version": "15",
    "compiler.cppstd": "20",
    "compiler.libcxx": "libstdc++11"
  }
}
```

`tool_variant` is cuppa's familiar folder id (same shape as GitLab package paths) so the
listing column stays uniform. `settings` is the Conan dict actually hashed into the
fingerprint — useful if a later migration or debug needs the authoritative consumer profile.
Optional later fields: requires summary, remote, conanfile hash id.

**How listing uses it.** For `type=conan` trees, `describe_tree_path` / inventory touch reads
the sidecar when present and fills **TOOLCHAIN VARIANT** (and may copy `settings` into the
inventory entry). Resolve-touched Conan deps should also implement `storage_tool_variant()`
from the active env so referenced rows are complete even before a re-install rewrites the
sidecar. Inventory `type` stays `conan`; the sidecar does not replace path-shape classification.

**Compatibility.** Absence of the sidecar is normal for installs created before this change:
list fingerprint + `-` for tool variant, and backfill on next use. Corrupt or partial JSON is
ignored the same way a bad inventory entry is — report what you can, never refuse the listing.

**Phase placement.** This is part of making Phase 3 listing trustworthy for Conan, not a
separate product feature. Prefer landing the write path in `build_with_conan.py` in the same
workstream as `--list-dependencies` polish (or immediately after), before treating Conan rows
in the table as something users can act on with confidence. Unit tests: meta written on
install; reuse backfill; describe/list reads tool_variant; missing meta still lists.

**Non-goals for this slice.** Rewriting the Conan layout to nest under `tool_variant` folders;
decoding fingerprints; managing `~/.conan2`; showing Conan package revisions beyond what
SConsDeps already exposes in version summaries.

### 4.8 Location identity: registry name, stem, short name, and two listing bugs

A location dependency has more than one useful name. Listing today mostly shows the encoded
folder, which hides relationships that cuppa already knows (or can know) at resolve time.

#### Identities

| Identity | Example | Source |
|----------|---------|--------|
| Registry name | `widget` | `location_dependency('widget', …)` in the sconstruct |
| Folder stem | `git_ssh_git@host__org_widget` | `Location.folder_name_from_path` (URL with `/` → `_`) |
| Branch variants | stem, stem`@master`, stem`@feature_x`, … | Relative versioning / `--location-match-*` |
| Short name | `org/widget` | URL path at resolve time (authoritative) |

Sibling rows in `--list-dependencies` that share a stem are the same repository at different
branch/tag checkouts. The registry name binds to **one** of those variants (the directory
resolve selects). Presentation should prefer the registry name (and short name) in the
DEPENDENCY column, put the encoded folder in JSON / a detail field, and show VERSION/BRANCH as
the qualifier family — including which variant this sconstruct currently selects.

**Short names from the folder alone are lossy.** `/` and `_` both become `_` in the encoding,
so `org/widget` and `org_widget` cannot be distinguished from the directory name. Prefer the
URL path (or location string) recorded at resolve; use heuristics only for trees with no
registry binding.

Inventory fields worth adding when this lands: `stem`, `short_name`, and `registry_names`
(or a single `dependency` plus `aliases`). Path-shape `type` stays `location`.

#### Default-branch quirk (should address — real storage win)

When a location is specified without an explicit branch (often a trailing `@` for relative
versioning), the first retrieve commonly lands in the **unqualified** stem. Later, when the
default branch is known, resolve **prefers** an existing `stem@<default_branch>` if present
(`location.py`: try `local_directory + "@" + default_branch`, else fall back to the unqualified
directory). Builds that encode the default branch in the URL create the `@master` (or
`@main`) form. Over time both directories exist as full working copies — often near-duplicates —
and the listing shows two "masters".

**Yes, this should be fixed.** It is not only a display wart; it is a sizeable and avoidable
doubling of VCS trees under a shared dependencies root.

Recommended direction (location behaviour + listing/cleanup, not listing alone):

1. **Canonical form going forward.** Once the resolved branch is known, always use
   `stem@<branch>` — including the default branch — so the unqualified stem is not a second
   spelling of master/main. (The opposite convention, "default branch is always unqualified",
   also works if applied consistently; encoding the branch is clearer next to `@feature_x`
   siblings.)
2. **Resolve when both exist.** Prefer the canonical directory; warn that the duplicate is
   unused by this selection (and is a removal candidate).
3. **Listing.** Treat unqualified + `stem@<default_branch>` as the same logical branch family
   member; label the unqualified row as the default branch (e.g. `@master (unqualified)`) so
   the doubling is obvious.
4. **Cleanup.** A later removal affordance (or a note under `--list-dependencies`) to delete
   the non-canonical duplicate after the user confirms — do not auto-delete on resolve.

This can land as a focused change in `cuppa/location.py` plus listing awareness; it is related
to Phase 3 presentation but is also a standalone storage fix.

#### Develop hides the cached stem (listing / inventory gap)

With `--develop`, `Location.storage_paths()` correctly puts the working copy in `develop` (not
removable) and leaves `dependencies` empty. `--list-dependencies` then would not mark the
cached stem under `dependencies_root` as referenced unless it also binds that stem.

This is **not** a removal safety bug — skipping develop paths remains mandatory. It **is** a
reporting concern when `--develop` is passed on the listing command. Normal storage inspection
should omit `--develop` (§3.2); `--list-develop` is the command for working copies.

**Status.** Listing bind shipped: `Location` keeps `_cache_folder_stem` across the develop swap,
`storage_paths()['cached']` lists matching stem / stem`@*` trees, and `--list-dependencies`
with `--develop` shows REMARK `develop` on the identity (branch leaves unmarked; still never a
removal of the develop path). Tree presentation (§4.9) has shipped; default-branch quirk and
Conan meta (§4.7 / §4.8) have shipped.

#### Expected but absent (STATE `missing`)

When resolve-only listing runs, a default dependency may declare an expected path that is not
on disk. Location used to **raise** in that case (unlike GitLab packages, which already return
early under resolve-only), so the failure appeared only as log + skip tree — and the skip tree
itself crashed on a `glyphs` attribute bug.

**Shipped.** Under `storage_resolve_only`, Location returns the expected directory (warn once)
so `storage_paths()` can report it; `--list-dependencies` emits an error-coloured row with
STATE `missing`, size `-`, and includes `missing_count` in the footer and JSON. Exit status
stays 0 (inspect tool). True skips (unknown name, undeclared layout) remain below the table.

### 4.9 Hierarchical `--list-dependencies` presentation

The earlier flat ruled table fought the mental model: people care about *which dependencies
this sconstruct uses* and *which stale variants of those same identities sit on disk*, not
about one row per encoded folder. The hierarchical tree (referenced first, then unreferenced;
type groups; short-name families; qualifier / version / toolchain children) matches how
`--list-builds` already presents selection with rollups.

#### Verdict

**Shipped** (Phase 3 listing on `134_list_and_remove_dependencies`). The sketch was the right
presentation: grouping + rendering, not new storage layouts. Default columns hide on-disk
paths; LOCATION sits behind `--list-format=verbose`. Remaining polish is §4.8 / §4.7 / removal
naming (P5), not reopening the tree shape.

#### Target shape (default columns)

```
SIZE | LAST USED | REMARK | DEPENDENCY
```

Hierarchy (outer → inner):

1. **Section:** `referenced` (includes `missing` and `cached` under the identities this
   sconstruct cares about) then `unreferenced` (orphans with no registry binding in this run).
2. **Type group:** repository dependencies, gitlab packages, conan, source archives (omit empty
   groups). See §4.15 for the `location` → `repository` rename and wipe/remove selectors.
3. **Identity:** registry name for referenced (`baa [clearpool.io/cplx_core/baa]`); short name
   alone for unreferenced (`clearpool.io/cplx_core/transport_layer`). For **missing** referenced
   identities, replace the short name with `remote_location()` (configured location URL, or
   `registry/package/version` for GitLab packages).
4. **Variants:**
   - **repository** (was `location`): one child per qualifier (`@` for unspecified / unqualified
     stem, `@master`, `@feature_x`, …). Prefer `@` over inventing `<default_branch>` — until the
     §4.8 quirk fix makes unqualified stems go away, `@` correctly means "branch not encoded in
     the folder".
   - **gitlab:** version (descending) → toolchain variant children
   - **conan:** fingerprint children until §4.7 meta improves labels
   - **archive:** version / archive id children (Boost heuristic → `boost` + `1.86.0`)

**REMARK** (leaf and useful rollups only; blank elsewhere):

| Remark | Meaning |
|--------|---------|
| `in use` | This leaf is the path resolve selected for the current selection |
| `develop` | Identity row under `--develop`: working copy is active; branch leaves unmarked |
| `N used` | Rollup: N>1 descendant leaves are in use (type / section); omit when N is 1 |
| `missing` | Expected by this sconstruct, not on disk |
| (blank) | Present, not selected; or a single-in-use identity/type rollup; or develop-shadowed branch |

**LOCATION** (encoded folder, registry URL, relative package path): **not** in the default
`--list-format=text` view. Extend the shared `--list-format` option with `verbose` (text tree
plus LOCATION column) so power users can map a row to disk when pruning without a separate
flag. `--list-format=json` always includes location / path fields for machines. The point of
the default view is that most readers never need on-disk representation.

#### Rationale (why this grouping)

- Referenced first: current work and its stale siblings, so you can prune `@2671_…` next to
  the `@master` you are using without hunting the whole root.
- Unreferenced later: other projects' leftovers; less need for a "work list" framing.
- Pulling **all** stem/short-name siblings under a referenced identity (even when not in use)
  is intentional — that is the prune view. Do **not** leave stale `baa@feature` only in
  unreferenced when `baa` is a default dependency.

#### Rollups (align with `--list-builds`)

`--list-builds` puts **SIZE** and **age** on every node: parent size = sum of children; parent
mtime = max child mtime; selection marks show what the current run cares about.
`--list-develop` is a flat status table plus a judgement tree — worse analogue here.

For dependencies:

- **SIZE:** roll up at every non-leaf (sum of descendant leaf bytes). Missing leaves contribute 0
  and show `-` at the leaf.
- **LAST USED:** roll up as **newest** child age at identity and type rows (same as builds'
  max mtime). Leave blank only if we later find it noisy — default to rollup for consistency
  with `--list-builds`.
- Section rows (`referenced` / `unreferenced`) also carry rolled size (and optional newest age).

Colour: section rows (`referenced` / `unreferenced`) stay normal (layout). Referenced
dependency names are emphasised info (bracketed short names / remotes muted); unreferenced
dependency names are emphasised in normal colour. Identity SIZE and LAST USED are muted in
referenced so branch/version leaves carry the primary figures. Type grouping names stay normal.
Other referenced leaves (siblings / cached) and the "potentially stale" summary subdued.
Unreferenced leaves subdued. Missing dependencies: name is emphasised error, all subnodes error
(not emphasised), `missing` remark only on the absent leaf. Blank spacer rows sit below type
headings and between each dependency. A horizontal rule partitions the referenced and
unreferenced sections.

Referenced section remarks: `N total` on the section, plus summary rows for dependencies in use
(`N used` + size) and potentially stale dependencies (`N unused` + size), with empty spacer rows
above/below type group names.

#### Capability vs gaps

| Need | Status |
|------|--------|
| Flat walk + sizes + type | **Have** |
| `referenced` / `unreferenced` / `missing` per path | **Have** |
| Registry name when resolve binds | **Have** (owned paths) |
| Short name for git (from `origin`) | **Have** |
| Short name for gitlab (package segment) | **Have** |
| Short name for Boost archives | **Have** — regex on encoded folder; reconstruct download URL |
| Short name for GitHub archives | **Have** — `github.com/<owner>/<repo>` + tag; reconstruct download URL |
| Stem family = all `stem` / `stem@*` siblings | **Have** — grouped under referenced identity when any leaf binds |
| Which leaf is `in use` | **Have** — owned/referenced path from resolve |
| Unspecified qualifier on unqualified stem | Show `@` (not `<default_branch>`); §4.8 quirk fix removes the need long-term |
| Registry name vs extract folder (`boost_package` → disk `boost/`) | **Partial** — registry name on referenced GitLab identities; bracketed short path still a polish item when they differ |
| Tree renderer (glyphs, hang, width) | **Have** |
| JSON tree | **Have** — nested `tree` plus flat `entries` |
| Verbose LOCATION via `--list-format` | **Have** — `verbose` column; `[D]` mark + footer (§4.12); JSON carries paths / `download_path` |
| Conan human labels | **Blocked** on §4.7 meta; show name + fingerprint until then |

#### Implementation slices (Phase 3 presentation)

**P1 — Identity enrichment.** **Done.** `short_name`, `stem`, `source_url` / `remote_location`
on walk / resolve; inventory persistence; unit + integration coverage.

**P2 — Tree model.** **Done.** Referenced vs unreferenced partition; type → identity →
variants; stem siblings under referenced identities.

**P3 — Text renderer (default).** **Done.** Ruled hierarchical table; REMARK + rollups;
footer counts; no LOCATION for `--list-format=text`.

**P4 — Verbose + JSON tree.** **Done.** `--list-format=verbose` LOCATION + `[D]`; JSON
`tree` + enriched flat `entries`.

**P5 — Polish tied to other open items.** Still open: §4.8 quirk fix; Conan children when
§4.7 meta lands. Removal naming / UX decided in §4.13 (registry keys + selection options).

#### Non-goals for the first tree ship

- Changing on-disk layout / namespaced folders.
- Auto-deleting stale variants.
- Making `missing` a non-zero exit (still an inspect tool).
- Showing LOCATION under `--list-format=text`.
- Labelling unqualified stems as `<default_branch>` — use `@` for unspecified instead.

#### Sketch corrections / watch-outs

- Example LOCATION paths under an unreferenced `google-cloud-*` package that still say `boost/…`
  are sketch typos; real paths must follow `{tool_variant}/{package}/{version}`.
- Referenced gitlab identity should prefer the **registry** name (`boost_package`) with short
  package folder in brackets (`[boost]`) when they differ — same pattern as location
  `baa [clearpool.io/…]`.
- `cached` (develop shadow) belongs with the referenced identity as a remark variant, not a
  second section — **shipped** as REMARK `develop` on the identity (branch leaves unmarked);
  footer points at `--list-develop`.

### 4.10 Deferred: all-dependencies view and empty-`used_by` remark

Not for the current listing polish pass. Capture so it is not forgotten once inventory stamping
is trustworthy.

#### Inventory remark when `used_by` is empty

After resolve/build stamps `used_by` (§4.5), unreferenced (and optionally all-dependencies)
identity or leaf rows whose inventory entry has an empty `used_by` map can carry a REMARK that
means "no project has recorded a resolve against this tree."

**Preferred wording (not settled):** `unrecorded` or the slightly shorter `no record`. Avoid
`unused` (collides with referenced-section `N unused` / potentially stale) and `orphan` (sounds
absolute / safe-to-delete). Empty `used_by` is inventory state, not authorisation to remove.

**Do not ship** this remark while listing is the main writer of inventory entries with
`update_last_used=False` — that would mark nearly everything.

#### All-dependencies listing mode

Goal: a single disk-centric view of everything under `dependencies_root`, without this
sconstruct's resolve semantics (`in use` / `missing` / `develop` / referenced vs unreferenced
partition). Same hierarchical formatting as today's unreferenced section (type → identity →
variants), with one section labelled roughly **all dependencies**, plus the inventory remark
above where appropriate.

**CLI shape (not settled):** prefer extending the shared `--list-format` rather than a second
top-level flag — e.g. `--list-dependencies --list-format=all` — unless discoverability later
argues for `--list-all-dependencies`. Keep one renderer and one docs page either way.

**Sequencing:** (1) stamp `used_by` on real resolve/build; (2) then add the remark and/or the
all-dependencies mode.

### 4.11 Deferred: LOCATION URL spelling (`git+` vs bare remote)

Observed while using verbose `--list-dependencies`: some LOCATION values show pip-style VCS
URLs (`git+ssh://…`, `git+https://…`) and others show the live git remote without the `git+`
prefix (`ssh://…`, `https://…`).

**Cause (not a colouring bug).** The tree prefers `remote_location` (the configured sconstruct
string from `Location.remote_location()` / `_configured_location`) when present, then falls
back to `source_url` from `Git.info` / `origin` when enriching a disk tree. Same repository,
two spellings — both valid for their source.

**Decision deferred.** Decide later whether to normalise (always strip `git+`, always prefer
configured, always prefer `origin`, or leave mixed) based on experience using the listing.
No code change until that call is made.

### 4.12 Settled: no downloads-root path under `[D]` in verbose LOCATION

Verbose `--list-dependencies` prefixes LOCATION with `[D]` when a regenerating archive exists
under `downloads_root` (HTTP/Boost extract rows; GitLab toolchain archive basenames — not the
registry URL on the version row). A footer explains the mark.

**Not doing:** nesting a second LOCATION line with the path relative to `--downloads-root`
(for example `packages/google-cloud-cpp/2.28.0/….tar.gz`) under each `[D]` leaf.

**Rationale.** Verbose LOCATION already answers *what* the leaf is (URL or archive basename);
`[D]` answers *whether* a regenerating file is present. The useful action is remove/re-fetch by
dependency identity (package + version + toolchain), which listing and later purge should name
without teaching on-disk layout under downloads. A per-row path doubles vertical noise on every
toolchain leaf and fights the point of managed removal: users should not need to know where the
file lives. Absolute or relative download paths remain available in `--list-format=json`
(`download_path`) and belong in a dedicated `--list-downloads` (Phase 4), not as default verbose
tree chrome. Until purge exists, the `[D]` footer pointing at the downloads root is enough for
occasional hand deletion.

### 4.13 Slice D — concrete plan for `--remove-dependencies`

Umbrella [#134](https://github.com/ja11sop/cuppa/issues/134). Flags are already registered and
stubbed in `cuppa/core/dependency_actions.py` (`--remove-dependencies=…`,
`--remove-all-dependencies`). This section turns §4.3–§4.4 into an implementable slice:
decisions with rationale, worked examples, UX, tests, and an ordered checklist.

#### Goal and non-goals for this slice

**Ship**

- Delete **dependency trees under `dependencies_root`** that match the named dependency (or
  every dependency this build knows) **and** the current selection (toolchain / variant /
  branch-matching options).
- Mirror `--remove-builds`: announce → act (or `-n`) → post-remove report → leftovers →
  verification command.
- Honour §5: containment, no develop-path deletion, no symlink traversal, refuse suspicious
  roots, report-before-acting, dry-run, non-zero on failure.

**Do not ship in Slice D**

| Deferred | Why |
|----------|-----|
| `--purge-*` / touching `downloads_root` | Phase 4; listing already points at `[D]` for hand cleanup |
| `--remove-unreferenced-dependencies` | Needs more trust in the inventory picture; age gate later (§9) |
| `--remove-dependencies-older-than` | Same |
| Qualifier / toolchain filters in the CLI value | First cut is identity-level; selection options already narrow packages and branches |
| Deleting unreferenced trees by short name alone | Avoid deleting another project's leftover when the name is ambiguous; see naming below |
| Inventory `used_by` stamping | Parallel polish; not required to delete selected paths |
| Conan meta / default-branch quirk | Parallel; Conan removal still works on fingerprint paths `storage_paths()` returns |

#### Decision D1 — What a “name” means

**Proposal (preferred): project-used dependency names only** (sconstruct keys that this build
declares or defaults — not every factory cuppa can load).

```
cuppa -Q -D --remove-dependencies=boost_package,widget
cuppa -Q -D --remove-all-dependencies
```

Cuppa keeps two maps:

| Map | Key | Contents |
|-----|-----|----------|
| **Registry** | `cuppa_env['dependencies']` | Every factory cuppa can instantiate (built-ins from module scan — `boost`, `qt4`, `qt5`, `quince` — plus plugins and the sconstruct’s `dependencies=[…]`) |
| **Project-used** | `default_dependencies` ∪ `declared_dependencies` | What *this* project names: defaults passed to `cuppa.run`, plus keys registered when walking the sconstruct’s `dependencies=[…]` list |

| Accepted | Rejected (Slice D) | Rationale |
|----------|--------------------|-----------|
| `boost_package` when listed in `default_dependencies` or `dependencies=[…]` | `boost` when only auto-registered via module scan | Same as BuildWith intent; a shared root must not lose another project’s Boost extract because a package-only sconstruct typed the short built-in name |
| Comma-separated list of project-used keys | Encoded on-disk folder | Users never type `git_ssh_…_widget@master` |
| | `widget@feature_x` as a CLI token | Branch selection already comes from `--location-match-*` / current options; a second grammar fights that |
| | Toolchain leaf as a name | Use `--toolchains=` / `--dbg` / `--rel` / `--cov` |
| | Short name / extract folder (`boost` as unreferenced archive label) | Listing shows short names for unreferenced trees; removal stays on registry keys the project actually uses |

**Unknown or not used by this project → error** with the rejected name emphasised, then a ruled
**in-use** dependency tree for the current selection (same presentation as
`--list-dependencies` referenced section). Example: a sconstruct that only declares
`boost_package` rejects `--remove-dependencies=boost` even though `Boost.create` sits in the
registry.

**`--remove-all-dependencies`** = every **project-used** name (defaults ∪ declared), still
selection-scoped — **not** every folder under the root, and **not** every auto-scanned built-in.
Unreferenced leftovers stay until named in a later flag or removed by hand after
`--list-dependencies`.

**Rationale.** Listing already teaches registry names in the DEPENDENCY column for referenced
trees. Short names appear for unreferenced archives (`boost`, `github.com/…`); deleting those
by short name without a project binding is how a shared root loses another project's tree.
Built-in factories are always *available* for `BuildWith('boost')` when a project opts in via
`default_dependencies`; they must not be *removable* merely because the factory exists.
Workflow for leftovers: list → identify → if it is *your* dependency, remove by project-used
name with a selection that matches that leaf; if it is not yours, leave it (or a future
`--remove-unreferenced-dependencies` with stronger guards).

**Open to verify:** should `--remove-dependencies=` also accept a short name when **exactly one**
referenced identity in this resolve maps to it? **Recommendation: no in Slice D** — keep one
grammar; revisit if real use shows registry names are hard to discover.

#### Decision D2 — Selection scope (what gets deleted for a named dependency)

Reuse the same resolve-only + `storage_paths()` picture listing uses. For each named dependency:

| Kind | Remove | Leave and report |
|------|--------|------------------|
| **GitLab / toolchain package** | Trees whose `tool_variant` matches the current selection (same composition as builds) | Other toolchains / variants of the same package+version |
| **Location (VCS)** | The folder the current options would use (qualified stem from match-branch / tag / current branch) | Sibling `@other` folders under the same stem |
| **Location under `--develop`** | **Nothing** for that identity's develop path; skip + report | Cache stems may still be removable if present and selected — never the develop working copy |
| **Archive / Boost extract** | The extract tree(s) `storage_paths()` lists for this dependency under the current selection | Unrelated archive identities |
| **Conan** | Install dirs `storage_paths()` lists for this dependency (fingerprint paths until §4.7) | Other fingerprints / other deps |

**`--remove-all-dependencies`** applies that rule to every known dependency, then summarises
leftovers across them.

**Rationale.** Matches §4.3 and Phase 2: options that decide where cuppa *writes* also decide
what removal *targets*. A blind “delete every folder whose name contains widget” would cross
toolchain and branch boundaries and fight shared roots.

#### Decision D3 — UX shape (mirror builds)

Stdout is the product (same as `--list-dependencies` / `--remove-builds`): not only logger
lines. Sketch (sizes and paths illustrative):

```
Removing 2 dependency trees (860.0M) under ~/.cuppa/dependencies
(dry run; pass without -n to remove)

  ---------------------------------------------------------------------
      SIZE  LAST USED  REMARK    DEPENDENCY
  ---------------------------------------------------------------------
    560.0M  today      removed   boost_package
    560.0M  today                    └── 1.91
    560.0M  today                        └── gcc153_dbg_x86_64_cxx2c
    300.0M  today      removed   widget
    300.0M  today                    └── @master
  ---------------------------------------------------------------------

Leaving 3 trees (1.2G) for other selections:
  boost_package 1.91 / clang211_dbg_… (560.0M)
  widget @release_1.14 (400.0M), @feature_x (280.0M)

Removed 2 trees freeing 860.0M

Verify with:

cuppa -Q -D --list-dependencies
```

On failure, keep removed vs failed marks (reuse builds’ REMOVED / ballot vocabulary where it
fits) and a short reason tree. Exit non-zero if any requested removal failed; exit 0 when
nothing matched, with an explicit “nothing to remove” line.

**Dry-run (`-n`):** identical report, no deletes, announce line says dry run.

**After success:** delete matching inventory entry files for removed paths (best-effort); do
not treat inventory failure as a removal failure.

#### Decision D4 — Interaction with listing footer and docs

Listing already suggests:

```
cuppa -D --remove-dependencies=<name>
```

Slice D makes that real. Document on the Dependencies “Managing” section (and CLI reference)
in the **same PR** as the implementation: one announce example, one leftovers example, one
develop-skip example. Full §7.1 docs split stays optional / parallel.

#### Decision D5 — Implementation sketch

1. **Resolve-only** (already used by listing): build dependency objects with retrieval disabled;
   collect `storage_paths()` for requested names.
2. **Filter** paths to the current selection (tool_variant / location qualifier); drop develop
   paths; `ensure_contained` under `dependencies_root`.
3. **Plan list** deepest-first; measure sizes before delete (for the report).
4. **Act** via `storage.remove_path` + `prune_empty_parents` (same helpers as builds).
5. **Report** hierarchical or compact table of removed leaves + leftovers summary + verify
   command.
6. **Tests:** unit tests for name parsing / selection filter / develop skip (pure where
   possible); integration: plant multi-toolchain GitLab + multi-branch location under a temp
   dependencies root, remove with `-n` then for real, assert leftovers and develop path
   untouched.

Likely modules: `dependency_actions.py` (orchestrate), reuse `utility/storage.py`, possibly a
small `dependency_removal.py` if selection filtering gets thick. Prefer not to fork a second
tree renderer — stamp outcomes onto the same row model listing builds, or a thinner table.

#### Worked examples (expected behaviour)

**E1 — Package, one toolchain**

Disk: `boost_package` 1.91 for `gcc153_dbg_…` and `clang211_dbg_…`.

```
cuppa -Q -D --dbg --toolchains=gcc --remove-dependencies=boost_package
```

Removes only the gcc tree; reports clang left. Re-run with `--toolchains=gcc,clang` (or a
second invocation) to clear both.

**E2 — Location siblings**

Disk: `widget@master`, `widget@feature_x`. Current branch / match selects `@master`.

```
cuppa -Q -D --remove-dependencies=widget
```

Removes `@master` only; reports `@feature_x` left. To remove the feature folder, check out /
match that branch (or a later qualifier CLI — out of Slice D).

**E3 — Develop must not delete the working copy**

`widget` has `develop=` pointing at `~/coding/widget`.

```
cuppa -Q -D --develop --remove-dependencies=widget
```

Skips the develop path with an explicit reason. If a cache stem still exists under
`dependencies_root` and is selected, it may be removed; the working copy never is.

**E4 — Unknown name / built-in not used by this project**

```
cuppa -Q -D --remove-dependencies=widgt
```

Exit non-zero. Message:
`error: widgt is not a used dependency for the specified build variants in this project.`
(the rejected name is error-coloured and emphasised). Then a ruled **in-use / referenced**
dependency tree for the current selection (same renderer as `--list-dependencies`, no
unreferenced section), introduced by `Known dependencies which can be removed are:` and
`Collating dependency tree...`.

```
cuppa -Q -D --remove-dependencies=boost
```

when the sconstruct only declares `boost_package` (built-in `boost` is in the registry but not
project-used): same error shape — rejected name emphasised; hint tree shows `boost_package` and
other project-used identities.

**E5 — Nothing selected**

Named dependency exists only as another toolchain’s tree.

```
cuppa -Q -D --dbg --toolchains=gcc --remove-dependencies=boost_package
```

(when only clang trees exist): `nothing to remove` for that selection; still mention what was
left for other selections if useful.

**E6 — `--remove-all-dependencies`**

Same as naming every known dependency; still selection-scoped; still does not sweep
unreferenced strangers.

#### Implementation checklist

1. Replace stub in `dependency_actions.run` with real remove path. **Done**
2. Name resolution + errors (D1 / project-used gate). **Done** (unknown-name hint tree)
3. Path collection + selection filter + develop skip (D2). **Done**
4. Announce / dry-run / delete / prune (D3). **Done**
5. Post-remove report + leftovers + verify command (D3). **Done** (hierarchical remove tree)
6. Inventory cleanup best-effort. **Done**
7. Unit + integration tests (E1–E6, multi-toolchain, name gate). **Done**
8. Docs: Dependencies Managing + CLI reference; CHANGELOG under Added. **Done**
9. Update this plan’s progress snapshot when the PR merges; do **not** close #134 until purge /
   remaining Phase 3 goals are agreed (message like #141: “completes the dependency removal
   half…” without `fixes` / `closes`). **Done** — Slice D merged as #142; archive clean as #143.

#### Settled for Slice D (summary)

| Topic | Decision |
|-------|----------|
| Names | Project-used keys only (`default_dependencies` ∪ `declared_dependencies`); not the full factory registry |
| Unknown name UX | Emphasised error name + in-use tree hint (not a flat key list) |
| Scope | Current selection only; leftovers muted in the same tree (`Leaving … as shown`) |
| Develop | Never delete develop paths |
| Downloads | Untouched (no purge) |
| Archive / Boost | Selection-scoped `storage_clean` for Boost (§4.14.3); whole extract when unsupported |
| Unreferenced sweep | No |
| UX | Builds-like report on stdout; checks/ballots; `-n` supported; info-coloured freed size |
| Docs | Managing + CLI in same PR |

#### Still verify while implementing (small)

Settled in implementation:

- Leftovers live in the remove tree (muted) with `Leaving N trees (…) for other selections as shown.`
- Dedicated hierarchical remove table (not a full `--list-dependencies` REMOVED overlay).
- `--remove-all-dependencies` with zero project-used names → nothing to remove (not an error).

### 4.14 Project-used name gate and archive-style clean-by-variant

Umbrella [#134](https://github.com/ja11sop/cuppa/issues/134). Two related findings from exercising
Slice D against a package-only consumer (GitLab `boost_package`, no source `boost` in
`default_dependencies`):

1. **`--remove-dependencies=boost` succeeded** and planned deletion of a multi-gigabyte shared
   Boost extract under the dependencies root, even though the sconstruct never named `boost`.
2. **Archive layout** means that when source `boost` *is* project-used, today’s removal deletes
   the entire extract — every toolchain and variant that b2 staged inside it — which is correct
   for “wipe this Boost install” but surprising if selection (`--toolchains=`, `--dbg`) is
   assumed to narrow the target the way it does for GitLab packages.

#### 4.14.1 Name gate (Slice D — **done** on `master` / #142)

**Bug (fixed).** `known_dependency_names` read the full factory registry. Module scan always
registers `boost` (and `qt4` / `qt5` / `quince`). Resolve then called `Boost.create()` →
`storage_paths()` → the shared archive folder. On a shared root that was a cross-project
deletion hazard.

**Fix (shipped).** Track `declared_dependencies` when walking the sconstruct’s
`dependencies=[…]` list in `construct.py`. For remove name resolution:

```
project_used = default_dependencies ∪ declared_dependencies
```

Validate `--remove-dependencies=` against `project_used` only. Rejected names print an
emphasised error plus a ruled in-use dependency tree for the current selection (not a flat
key list). `--remove-all-dependencies` iterates the same set (still selection-scoped).
Built-in factories remain in the registry for `BuildWith('boost')` when a project opts in via
`default_dependencies=['boost']`.

**Tests.** Package-only sconstruct → `--remove-dependencies=boost` exits non-zero and does not
plan the archive tree; sconstruct with `default_dependencies=['boost']` still removes the
extract. Same gate for other auto-scanned built-ins.

**Non-goal for the gate.** Changing how listing discovers unreferenced archives on disk (short
name `boost` in the unreferenced section remains a listing heuristic, not a remove handle).

#### 4.14.2 Why archives differ from GitLab packages

| Kind | On-disk ownership | Selection today |
|------|-------------------|-----------------|
| **GitLab / toolchain package** | `{tool_variant}/{package}/{version}/` | `--toolchains=` / variants select which trees `storage_paths()` returns |
| **Location (VCS)** | Stem / `@branch` folders | Match options select one qualifier; siblings reported as leftovers |
| **Archive / source Boost** | One encoded extract folder; b2 stages libs under `build[.abi]/<toolchain>/<variant>/<arch>/` inside it | `storage_paths()` returns the **top-level extract** only — selection does not narrow |

So `--remove-dependencies=boost` (when allowed) frees the whole tree. Ideal follow-on: clean
*variant build products* inside the extract when selection is set, without always deleting
headers and the b2 binary.

#### 4.14.3 Proposed protocol (done — #143)

Optional peer to `storage_paths()`:

```python
def storage_clean(self, env, selection):
    """Clean variant build products for this dependency under the current selection.

    Returns None if unsupported (caller falls back to whole-tree remove via storage_paths).
    Otherwise a dict with ``paths`` (absolute dirs to remove) and optional ``extract``
    (archive root left in place; used for leftovers / containment).
    """
```

| Responsibility | Owner |
|----------------|--------|
| Map cuppa selection → clean targets | Dependency (Boost: stage dirs + `bin.<abi>` trees from `library_naming.stage_directory` / `b2_command`) |
| Measure before / after | Cuppa removal (b2 will not report bytes reliably) |
| Dry-run (`-n`) | Prefer deterministic path enumeration without invoking b2 when layouts are known |
| Report | Same removal tree: identity = archive; leaves = cleaned variant dirs; muted leftovers for other internal variants; freed space from measured delta |
| Full extract removal | Only when `storage_clean` is absent/`None`, or via a later explicit “remove whole archive” / purge-adjacent mode |

GitLab packages and plain Location deps return `None` / omit the method — behaviour unchanged
(whole extract / tree remove as today).

**Boost.** For each active toolchain × variant × arch: remove
`stage_directory(...)` and matching Boost.Build toolset directories under `bin.<abi>`
(path deletion; toolset-scoped, not the whole `bin.<abi>`; no `b2 --clean` in this slice).
`storage_clean` returns labelled `targets` (`paths` + `label` + `tool_variant`) so the remove
report can show e.g. `clean/bin.c++2c [clang-linux-21*/debug]` alongside
`clean/build.c++2c [clang211/debug/x86_64]` (bin = b2 major family; stage = cuppa-precise).
The identity SIZE is the full extract (aligned with `--list-dependencies`); a muted
`source assets` leaf covers non-product bytes; the freed-space line reports the remaining
archive size after product removal. Live cleans rewrite that extract's inventory size exactly;
the verify hint uses `--list-dependencies` (listing upgrades missing or estimated sizes).
Sizes are measured live per target; after a live product clean the extract's inventory size is
rewritten exactly. Leave the source tree and b2 executable.

**Phasing.** Name gate shipped with Slice D (#142). Archive clean (§4.14.3) is **done**
(#143): optional `storage_clean`, Boost stage / `bin.<abi>` clean, docs, and tests.
Dependencies without `storage_clean` still remove the whole owned tree under the dependencies
root.

#### 4.14.4 Settled vs open

| Topic | State |
|-------|--------|
| Project-used name gate | **Done** (Slice D) |
| Unknown-name in-use tree hint | **Done** (Slice D) |
| Document whole-extract archive remove | **Done** (Slice D docs; superseded for Boost by storage_clean) |
| `storage_clean` / b2 per-variant clean | **Done** — #143 |
| Short-name remove when uniquely referenced | **Rejected for Slice D** (unchanged) |

### 4.15 Selectors, repository rename, and shared dependency tokens

**Status:** **done** — [#150](https://github.com/ja11sop/cuppa/pull/150) (closes [#146](https://github.com/ja11sop/cuppa/issues/146)).

Wipe already supported leaf tokens and fnmatch (`boost/1.8*`), but (1) untyped tokens mixed
**source archives** and **gitlab packages** under one identity parent, (2) the list type group
**location dependencies** named the retrieve *mechanism* (`location_dependency`), not the
on-disk *bucket*, and (3) only force-wipe was gaining richer tokens while remove / purge / wipe
still took bare project-used names.

§4.15 locked vocabulary and token grammar for the list/remove/purge/wipe surface. The
long-standing Python API `cuppa.location_dependency()` **stays**.

#### Mechanism vs storage bucket

| Layer | Role | Example |
|-------|------|---------|
| Retrieve mechanism | How the sconstruct declared / fetched the dep | fmt via `location_dependency` from GitHub |
| Storage / list bucket | How `--list-dependencies` / `--list-downloads` classify on-disk trees | That fmt often under **source archives** (zip + `[E]`) |

Selectors and type groups follow the **bucket**, not the factory. A location-fetched zip is
still `[source]` / `archive`.

#### Rename `location` → `repository` (list / storage)

| Layer | Decision |
|-------|----------|
| List / downloads type label | **`repository dependencies`** (VCS / checkout trees with `@branch` leaves) |
| Internal `storage_type` | **`repository`** (JSON, classify, inventory writes) |
| Inventory compat | **Read** legacy `type: location` as `repository`; **write** `repository` |
| Python API | **Keep** `location_dependency` / module paths |

#### Selector grammar (shared)

```
token := [ selector ] dependency_match
dependency_match := name [ '/' qualifier ]
```

- **Primary spelling:** `[selector]name` or `[selector]name/qualifier` (quote for shell when
  using `*`, `?`, or `[`).
- **Identity form:** `[source]boost`, `boost`, `boost*` (fnmatch on name).
- **Leaf form:** `[source]boost/1.8*`, `boost/1.8*` (fnmatch on name and/or qualifier).
- **Untyped** (no `[selector]`): match across **all** buckets — intentional (e.g. source Boost
  *and* GitLab packages). Dry-run / reports **must** show type partitions.
- **Typed:** restrict to that canonical type only.
- Rejected: slash type-prefix (`archive/boost/…` clashes with dependency names); single-letter
  selectors; shipping `#` / paren forms in this cut. Regex `r'…'` deferred.

**Alias map** (canonical = `storage_type`; no single-letter selectors):

| Canonical | List label | Selectors |
|-----------|------------|-----------|
| `archive` | source archives | `archive`, `source`, `source_archive`, `source-archive`, `sa` |
| `gitlab` | gitlab packages | `gitlab`, `gitlab_package`, `gitlab-package`, `gl` (`gh` reserved for a future GitHub package kind) |
| `repository` | repository dependencies | `repository`, `repo`, `vcs`, `vcs_dependency`, `repository_dependency`; quiet alias `location` |
| `conan` | conan packages | `conan`, `conan_package`, `cn` |

#### Verb behaviour

| Flag family | Identity / leaf tokens | Notes |
|-------------|------------------------|-------|
| `--force-wipe-dependencies` | Both | No referenced gate; develop never deleted; sibling context in report |
| `--wipe-dependencies` | Both (selection-scoped) | Project-used + selection gate |
| `--remove-dependencies` | Both (selection-scoped) | Project-used + selection gate |
| `--purge-dependencies` | Both + matching downloads | Same gates as remove |
| `--*-all-*` / `--force-wipe-unreferenced-*` | Unchanged for now | Optional `[selector]` on all-flags deferred |

Exact leaf with multiple paths in one type → ambiguous error. Glob → all matches (including
cross-type when untyped).

#### Report shape

Nest **summary → type → identity → version → leaves** (identity/version axis matches
`--list-dependencies`). Summary children are **wiped** / **removing** / **removed** vs
**remaining**. Version marks match extract rollups (`✔✔✔` full, `-✔-` partial, `---` untouched).
Spacers sit under the summary, under types, under identities, and between version siblings —
not between a version and its leaves. Partial force-wipe keeps unmatched same-`(type, identity)`
siblings visible (no parent `would rm`); final size includes what remains. Purge / wipe reports
that nest ``[E]`` under downloads print the same extract legend as ``--list-downloads``.
`AGE_WIDTH` must fit `relative_age` (13 for `N months ago`).

#### Implementation order

1. Rename classify / `TYPE_LABELS` / tree / downloads / identity paths; inventory compat-read. **done**
2. Shared token parser + alias registry. **done**
3. Force-wipe match + type-partitioned report + sibling context. **done**
4. Remove / purge / wipe accept the same grammar. **done**
5. Docs, CHANGELOG, tests, PR #150. **done**

#### Out of scope for §4.15

Regex tokens; renaming `location_dependency()`; implementing a GitHub package kind; `[selector]`
on `--force-wipe-all-*` / unreferenced unless trivial.

---

## 5. Safety model

These options delete directories, so the rules should be explicit and testable.

1. **Containment.** Every candidate path must resolve (after `realpath`) to something inside
   `abs_build_root`, `dependencies_root`, or `downloads_root`. Anything else is refused with an
   error naming the path and the root it escaped.
2. **Never touch develop paths.** When `--develop` is active a location points at a working
   copy the user owns. Those are skipped and reported, never removed, even though they are
   reachable through the dependency.
3. **No symlink traversal.** Resolve symlinks and refuse to remove through one; remove the link
   itself only when it lives directly under a managed root.
4. **Refuse suspicious roots.** Decline to remove a root that is `/`, the user's home, the
   sconstruct directory itself, or a filesystem root, regardless of how it was configured.
5. **Report before acting.** Build the full list first, log it, then remove. A failure part-way
   through reports what was and was not removed.
6. **Dry run is free.** `-n` produces the same report with no removals, which is also how the
   integration tests assert scope without deleting anything.
7. **Exit status.** Non-zero if any requested removal failed; zero when nothing matched, with
   an explicit "nothing to remove" message rather than silence.
8. **The inventory is advisory.** Nothing is removed because the inventory says so. Every path
   from the inventory is re-checked on disk and put through rules 1 to 4 like any other
   candidate, so stale or hand-edited inventory state can only produce a wrong report, never a
   wrong deletion.
9. **Declared artefact roots are contained too.** When artefact removal arrives (§4.6), a
   declared root must resolve inside the project directory; a declaration pointing elsewhere is
   an error, not an instruction.

Deliberately *not* proposed: an interactive confirmation prompt. These flags are explicit, and
prompts break CI. `-n` covers the "let me check first" case.

---

## 6. Implementation outline

Phased so each phase is useful alone, with the rename first so every later phase, review, and
discussion uses one set of names. Phases 1 to 4 form one chain: each needs the vocabulary and
machinery of the one before it. Phases 5 and 6 do not — Phase 5 touches no storage at all and
could land at any point, and Phase 6 needs a design pass this plan does not attempt.

| Phase | Delivers | Depends on | Status |
|-------|----------|-----------|--------|
| 1 | `--storage-root` and the renamed roots | — | **done** ([#133](https://github.com/ja11sop/cuppa/issues/133)) |
| 2 | `--remove-builds`, `--remove-all-builds`, `--list-builds` | 1 | **done** ([#134](https://github.com/ja11sop/cuppa/issues/134) / #140) |
| 3 | Inventory, `--list-dependencies`, `--remove-dependencies` / `--remove-all-dependencies` | 1, 2 | **listing done** (#141); **Slice D removal done** (#142 / §4.13); archive clean §4.14.3 **done** (#143) |
| 4 | `--list-downloads`, `--purge-*` | 3 | **done** ([#144](https://github.com/ja11sop/cuppa/pull/144); closes #134) |
| 5 | `--list-develop`, `--update-develop` | nothing in this plan | **done** ([#132](https://github.com/ja11sop/cuppa/issues/132)) |
| 6 | `--remove-artefacts` | its own design pass first | |

**Phase 1 — storage naming** (§8, §3.1) — **done**

- `cuppa/core/storage_options.py`: `--storage-root`, `--dependencies-root` /
  `--downloads-root` and the matching keys; `--download-root` / `--cache-root` and their keys
  kept as deprecated aliases of the resolved values.
- Resolution in one place (`resolve_root`): explicit option, else deprecated alias, else an
  existing older folder, else derived from `storage_root`. Both the project-local `_cuppa` and
  the shared `~/_cuppa/_download` are considered for dependencies, project-local first.
- Internal readers moved to the new keys; the old keys remain as aliases for plugins.
- Roots reported at info level on the first retrieval of a run.
- Docs and `CHANGELOG.md` updated under Changed and Deprecated.

**Phase 2 — build removal and `--list-builds`** (§3.3, §4.1, §4.2) — **done**

- `cuppa/core/build_layout.py`: shared `tool_variant_dir` composition, extracted from
  `construct.py` and used by both.
- `cuppa/core/storage_actions.py`: `--list-builds` / `--remove-builds` / `--remove-all-builds`,
  the three-section report (folder, toolchain tree, sconscript tree), selection marks, and the
  explicit-command summary.
- `cuppa/utility/storage.py`: directory sizing and ages, human-readable formatting, containment
  checks, removal, empty-directory pruning, tree glyphs, and `--list-format=json` helpers that
  later listings reuse.
- The safety model (§5) lands here too, since Phase 2 is the first phase that deletes anything:
  containment, symlink and suspicious-root refusal, report-before-acting, `-n`, exit status.
- Wire into `cuppa/construct.py` after option processing, before `self.build(...)`; report and
  exit.
- Scope stays inside `build_root`. Nothing here knows about artefact trees; that is Phase 6.

**Phase 3 — dependency listing, inventory, and removal** (§3.2, §4.3, §4.5, §4.7, §4.8)

Listing half **done** on `master` (#141). Removal Slice D **done** on `master` (#142 /
§4.13 / §4.14.1); archive clean-by-variant (§4.14.3) **done** (#143); purge is Phase 4 (**done**).

- `storage_paths()` + resolve-only: **done** (location, GitLab package, Conan, Boost).
- Inventory (§4.5): **done** for sizes / type / remote fields; `used_by` stamping on real
  resolve/build still **open** (§4.10). Listing does not stamp `last_used`.
- `--list-dependencies` hierarchical tree (§4.9 P1–P4): **done** (REMARK, rollups, missing vs
  stale summaries, verbose LOCATION / `[D]`, JSON `tree` + flat `entries`, collating message,
  docs examples).
- **Done — removal Slice D:** `--remove-dependencies` / `--remove-all-dependencies` under
  `dependencies_root` only; project-used name gate; hierarchical remove report; unknown-name
  in-use tree hint. Purge is Phase 4 (**done**).
- **Done — archive clean (§4.14.3 / #143):** optional `storage_clean`; Boost cleans
  selection-scoped stage / `bin.<abi>`; source-assets leaf + remaining archive size; lazy exact
  list sizes; whole-extract only when `storage_clean` is absent/`None`.
- **Done — Conan install metadata (§4.7):** `.cuppa_conan_meta.json` on install + backfill;
  listing reads `tool_variant`; Conan `storage_tool_variant()`.
- **Done — default-branch quirk (§4.8):** canonical `stem@branch` going forward; unqualified-only
  kept; both → canonical + warn; listing `@<default> (unqualified)`. No auto-delete. Develop bind
  / REMARK `develop` already shipped.
- Removal must re-verify every path on disk and re-apply the §5 containment rules; the inventory
  informs the report and never authorises a deletion.
- **Documentation split (§7.1):** **done** — hub + children; `packages.adoc` publish focus.

**Phase 4 — downloads listing and purge** (§3.3) — **done**

- Hierarchical `--list-downloads` (archive + `[E]` extract children, referenced / unreferenced,
  archive-only footer totals, JSON `kind`). `--list-scope` is shared with `--list-dependencies`.
- `--purge-dependencies` / `--purge-all-dependencies`: same name gate and selection as remove,
  then delete matching downloads; Boost `storage_clean` extract stays, download file is deleted;
  leftover other-selection archives stay; verify with `--list-downloads`.
- `--boost-patched` selects the source-Boost `patched/` home (deprecated alias
  `--boost-patch-boost-test`). Empty `bin.<abi>` husks are omitted from reports.
- **Not in this phase (at ship time):** `--wipe-dependencies` was deferred to
  [#146](https://github.com/ja11sop/cuppa/issues/146) (now **done** — selection wipe + force-wipe
  leaf/all/unreferenced). Boost GitLab package patched/clean identity remains on
  [`boost-updates.md`](boost-updates.md).

**Phase 5 — develop copies** (§3.5–§3.8 — independent of Phases 1 to 4) — **done**
(§3.7 / §3.8 on [#154](https://github.com/ja11sop/cuppa/pull/154))

- Landed ahead of Phase 2 ([#132](https://github.com/ja11sop/cuppa/issues/132) / #137): touches no
  storage root, needs no inventory, and removes nothing.
- Develop-path resolution is shared (`develop_location`); `Git.get_working_copy_state()` feeds
  the classification; `--list-develop` reports to stdout and exits; `--update-develop` fetches and
  fast-forwards only clean, strictly-behind copies.
- `--clone-develop` (§3.7) and `--checkout-develop-branch` / `--reset-develop-branch` with
  `--location-base-branch` (§3.8) shipped in [#154](https://github.com/ja11sop/cuppa/pull/154)
  (closes [#138](https://github.com/ja11sop/cuppa/issues/138) /
  [#153](https://github.com/ja11sop/cuppa/issues/153)).
- The `=fetch-only` / `=allow-rebase` / `=allow-merge` values are still out of scope until there
  is evidence from using the shipped update option (§3.6).

**Phase 6 — artefacts outside the build root** (§4.6)

- Needs its own design pass first: measure what SCons `--clean` already removes, decide between
  graph discovery and project declaration, then add `--remove-artefacts`.
- Everything before this phase is useful without it, which is why it is last rather than
  blocking.

---

## 7. Testing and documentation

**Unit tests** (`tests/unit/`, no filesystem side effects beyond `tmp_path`):

- New and deprecated root options resolve to the same value, the new one wins when both are
  given, and the old-folder fallback triggers only when the new folder is absent.
- `--storage-root` derives both subroots; an explicit `--dependencies-root` or
  `--downloads-root` overrides its half and leaves the other derived; values from
  `~/.cuppaconfig` and the command line combine with the same precedence.
- Listings render a header row, pad columns to their widest value, print the header for an empty
  result, and omit it in `--list-format=json` where the same fields appear as keys.
- `tool_variant_dir` composition matches what `construct.py` produces for representative
  toolchain / variant / arch / ABI combinations.
- Scope resolution finds nested per-sconscript variant folders and location build folders, and
  ignores other variants.
- Size formatting and totals, including the `unreferenced` marking.
- Containment guards reject paths outside the roots, develop paths, symlink escapes, and
  suspicious roots.
- Unknown dependency names produce an error listing known names.
- Inventory: entries are created and updated on resolve, two concurrent writers leave a valid
  file, a corrupt entry degrades one row rather than the listing, an entry whose path is gone is
  reported and dropped, and an inventory that claims a path outside the roots is refused.
- Sizing: a cached size is reused while the tree is unmodified, re-measured after a change,
  sampled sizes are marked until listing upgrades them; `--exact-sizes` still forces a full
  remasure.
- `--remove-all-dependencies` removes only what the current selection uses and reports the rest,
  for a mix of per-toolchain package trees and toolchain-independent VCS trees.
- Develop classification (§3.5) is a pure function from `(project branch, default branch, copy
  branch, upstream, ahead, behind, modified, path exists)` to a state and a severity, so every
  row of the table in §3.5 is a unit test with no repository involved, including the pair that
  differ only by branch: local work on the branch being built is a note, the same local work on
  the default branch is a warning. Path resolution is tested against the same helper the develop
  swap uses, including a relative path anchored to the sconstruct directory and a `~` path.
- The `--update-develop` decision is a second pure function over the same state: fast-forward
  only when clean and strictly behind, skip with a reason in every other case, and refuse
  outright under `--offline`.
- The `--clone-develop` decision is a third pure function over the same state plus the location:
  clone only into a missing or empty destination, skip with a reason for a working copy, a
  non-empty directory, a missing develop clause, or a location with nothing to clone, and refuse
  outright under `--offline` (§3.7). The branch a fresh copy would land on is chosen by the same
  rules `--list-develop` judges by, so a clone cannot be born a warning, and the remote recorded
  in the clone never carries an expanded secret.

**Integration tests** (`tests/integration/`):

- A project configured with `--download-root` / `--cache-root` still builds after Phase 1, and
  the same project configured with the new options produces identical layout.
- A project built with `--storage-root=<tmp>` writes both roots underneath it, and adding
  `--downloads-root` moves only the downloads half.
- Build two variants, `--remove-builds` one, assert the other survives.
- Build, `--remove-all-builds`, assert the build root is gone.
- `--list-builds` / `--list-dependencies` report the expected entries and totals and change
  nothing on disk.
- `-n` reports paths and removes nothing.
- Dependency removal against a location dependency backed by a local archive, then a rebuild to
  prove re-fetch works.
- `--clone-develop` against a local origin: a missing develop path becomes a working copy on the
  expected branch and the following `--list-develop` reports it as `ok`; a non-empty destination
  is refused and left untouched.

**Documentation:**

- `docs/modules/ROOT/pages/build-layout.adoc` — the storage roots under their new names, a
  prominent explanation that dependencies and downloads are **shared between projects by
  default** with the one option that makes them project-local, and a "Listing and removing build
  output and dependencies" section next to the existing Cleaning section, replacing the current
  "remove the folder by hand" advice. It should also state that artefact trees outside the build
  root are not removed by the build options.
- `docs/modules/ROOT/pages/cli-reference.adoc` — the new flags, including `--storage-root` and
  how it relates to the two derived roots, and the deprecated aliases.
- `docs/modules/ROOT/pages/configuration.adoc` — the renamed keys in `~/.cuppaconfig`, the new
  `storage_root` key, and the precedence between them.
- Dependency topic pages — today a single large `dependencies.adoc` plus overlapping
  `packages.adoc` / `extending.adoc`. Partition as in §7.1; listing presentation is stable enough
  that Managing will not need an immediate rewrite for the tree shape.
- `CHANGELOG.md` per phase; Phase 1 under both Changed and Deprecated.

### 7.1 Partitioning the Dependencies documentation

**Problem.** `dependencies.adoc` is one long page that mixes overview, built-ins (Boost source,
Qt, Quince), location libraries, develop/list workflows, Conan consuming, and custom deps.
`packages.adoc` covers `package_dependency`, GitLab auth, `boost_package`, and both GitLab and
Conan **publishing**. `extending.adoc` also teaches writing dependency plugins. Readers looking
for "how do I consume a GitLab package" vs "how do I publish one" vs "how do I list leftover
trees" have to hunt across sections that grew with the code rather than with a map.

**Code shape to mirror.** The public surface and modules already partition naturally:

| Kind | Code | Today in docs |
|------|------|----------------|
| Location / header | `location_dependency`, `location.py`, `build_with_location.py` | Mid-page in `dependencies.adoc` |
| GitLab package (consume) | `package_dependency` → `package_managers/gitlab.py` | Mostly `packages.adoc` |
| Conan (consume) | `conan_deps` / `conan_dependency`, `build_with_conan.py` | End of `dependencies.adoc` |
| Conan / GitLab (publish) | `PublishPackage`, `ConanPackagePublisher`, gitlab publisher | `packages.adoc` |
| Built-ins | `cuppa/dependencies/*` (boost, qt4/5, quince*) | Thin stubs in `dependencies.adoc` |
| `boost_package` | `packages/boost_package.define` (not auto-registered) | `packages.adoc` |
| Manage on disk | `develop.py`, `dependency_actions` / inventory / storage | Mid-page listings in `dependencies.adoc`; removal not documented |
| Author your own | factories + `cuppa.dependency.plugins` | End of `dependencies.adoc` + `extending.adoc` |

**Proposed Antora structure** (hub + children; filenames kebab-case under `pages/`):

```
dependencies.adoc                 Hub — what a dependency is, kinds table, declare + BuildWith,
                                  where trees live (link build-layout), which page next
dependencies-location.adoc       Location dependencies — URLs/archives/paths, folder naming,
                                  relative `@`, --location-match-*, develop swap, storage_paths
dependencies-packages.adoc       Package dependencies (consume) — package_dependency overview,
                                  toolchain-variant layout, develop vs download, auth pointer
dependencies-gitlab.adoc         GitLab generic packages — consume detail; link to publish page
dependencies-conan.adoc          Conan 2 — consume (SConsDeps, offline, limitations); link publish
dependencies-builtins.adoc       Built-ins **index** — registered names table, when to use a
                                  built-in vs location/package/Conan, links to child pages
dependencies-boost.adoc          Boost (source / b2) — flags, BoostStaticLibs / SharedLibs,
                                  patches, location overrides; contrast with boost_package
                                  (link packages / GitLab consume); decide which way to get Boost
dependencies-qt.adoc             Qt4 / Qt5 — MOC/UIC/RCC; thin until surface grows
dependencies-quince.adoc         Quince + backends — ORM location wiring; thin until surface grows
dependencies-managing.adoc      Managing — which listing for which question, --list-dependencies,
                                  --list-develop / --update-develop, --remove-* / purge when they
                                  ship, inventory sizing (lazy exact upgrade; --exact-sizes
                                  forces remasure) at user level
dependencies-extending.adoc     Writing your own — location/package/Conan factories,
                                  storage_paths / optional storage_clean contract, pip plugins
                                  (move or deeply link from extending.adoc)
packages.adoc                    Retitle focus to **Publishing** (GitLab generic + Conan export-pkg),
                                  or rename to packages-publishing.adoc and leave a stub redirect
```

Nav sketch:

```
* Dependencies
** Overview (hub)
** Location dependencies
** Package dependencies
** GitLab packages
** Conan packages
** Built-in dependencies          # index
*** Boost
*** Qt
*** Quince
** Managing dependencies
** Writing your own dependencies
* Packages (publishing)     # or nest under Dependencies as "Publishing packages"
```

**Nesting built-ins further.** Yes for anything with real surface area; not every registered
name needs a page on day one.

- **Boost** should be its own page from the start. The code already is a mini-product
  (`cuppa/dependencies/boost/` — version/location, b2, library naming, patches, static/shared
  methods, many `--boost-*` flags). The current docs bury that in ~25 lines plus a
  `boost_package` aside on `packages.adoc`. A dedicated page can teach *source Boost vs
  `boost_package`* without making the built-ins index or the publishing page carry both stories.
- **Qt and Quince** can start as short child pages (or even sections on the index) and grow
  later. Today they are nearly undocumented; inventing long pages would over-promise. Prefer
  honest stubs that name the dependency, the prerequisites, and the module — expand when
  someone documents real usage.
- **Rule of thumb:** nest under Built-ins when the topic has its own CLI options, `env.*`
  helpers, or a non-trivial choose-your-flavour decision (Boost source vs package). Keep the
  index as a directory of registered names + one-line purpose + xref; do not dump tutorials
  there.
- **`boost_package`** stays a *package* dependency in the code sense; its how-to belongs with
  package consume / GitLab (or a short "Boost from the registry" section on the Boost page that
  links out). Do not pretend it is the built-in `boost` dependency.

**Principles.**

  1. **Consume vs publish** Consuming a registry/Conan package belongs with Dependencies;
   publishing Cuppa-built libraries belongs with Packages (or a Publishing child). Cross-link
   the round-trip; do not duplicate the full Conan/GitLab story on both sides.
  2. **Managing is its own page** List / update / remove / inventory are workflows over storage
   and develop copies, not a footnote on "declaring". This is where §3.2 listing-mode rationale
   and Phase 3 removal docs land.
  3. **Hub stays short** Kinds table + `cuppa.run` / `BuildWith` + pointers. No deep tutorials.
  4. **Built-ins: index + nest by surface area** Boost gets a full child page; Qt/Quince start
   thin (or on the index) and graduate when documented properly — never invent depth that the
   product does not yet teach.
  5. **`storage_paths()` and inventory** belong on Writing your own (authors) and Managing
   (users), not only in a design plan.
  6. **Fix known doc/code drift** while moving (e.g. `include_root` vs `include` / `sys_include`
   in location examples).
  7. **Integration test pages** stay under Integration tests; the Managing page links them.

**When to do it (phase).**

This is a **Phase 3 documentation track**, not a separate product phase and not a blocker for
removal code:

1. **Ready for the split** — `--list-dependencies` hierarchical presentation (§4.9) is shipped
   and Managing examples match the tree; do not wait for further listing polish.
2. **In parallel with or just before** documenting `--remove-dependencies` (Slice D), so
   Managing ships as one coherent page rather than list-only then remove bolted on.
3. **Originally before Phase 4** so downloads management could extend Managing instead of
   growing the old monolith again. Phase 4 shipped on the existing `dependencies.adoc`
   Managing sections; the split is still open polish and is not a closer for #134.

Scaffolding the hub + stub children earlier is fine if links are kept honest ("content moving
here").

**Out of scope for the split itself:** changing CLI behaviour, inventing new dependency kinds,
or merging `extending.adoc` entirely into Dependencies — keep Extending as the plugin/entry-point
home and make Writing your own the dependency-specific tutorial that links there.

**Lasting guidance.** The partitioning rules of thumb above (hub short, consume vs publish,
manage separate, nest by surface area, honest stubs) are also recorded in
[`AGENTS.md`](../../AGENTS.md) under Documentation — *Where topics live* and *Documentation
partitioning*, and in the AsciiDoc style-guide block (*Page partitioning*) — so agents keep
applying them after this plan is archived.

---

## 8. Renaming `_download` and `_cache`

### 8.1 Why the current names confuse

Under a shared root the layout reads:

```
~/_cuppa/_download/    extracted, ready-to-use dependency trees, per toolchain
~/_cuppa/_cache/       the archives that were actually downloaded
```

The names are close to backwards. `_download` does not hold downloads, it holds *unpacked
working copies and extracted packages*. `_cache` is where the downloaded files live. Both sit
under a root named `_cuppa`, which says who made the folder rather than what is in it, and both
use a leading underscore, which reads as "generated" in the project tree but is unusual in a
home directory.

### 8.2 Candidates

For `download_root` (extracted, usable trees):

| Name | Rationale | Against |
|------|-----------|---------|
| `dependencies` | Says exactly what is inside; matches the vocabulary in the docs and the `--remove-dependencies` flag | Long to type in paths |
| `deps` | Short, universally understood | Slightly informal |
| `external` | Familiar from other build systems; distinguishes "not ours" | Says where it came from, not what it is |
| `thirdparty` | Matches the existing `--thirdparty` option | Overloads a flag that means something narrower today |
| `packages` | Accurate for the package-manager trees | Wrong for VCS working copies |

**Recommendation: `dependencies`**, with `deps` accepted as an alias. It matches the word used
everywhere else in cuppa, and it makes the shared root self-describing.

For `cache_root` (raw downloaded archives):

| Name | Rationale | Against |
|------|-----------|---------|
| `downloads` | This is literally what is in it, and it recovers the word the other folder was misusing | Could be confused with the old `_download` during migration |
| `archives` | Precise about the content being packed files | Not obviously a cache that can be deleted safely |
| `download-cache` | Unambiguous on both counts | Verbose |

**Recommendation: `downloads`**, because the swap resolves the confusion rather than papering
over it, and because the migration is a good moment to make the distinction obvious. If the
risk of confusion during migration is judged too high, `archives` is the safe second choice.

### 8.3 Decision

```
--storage-root        ~/.cuppa                 parent of both roots below
--dependencies-root   ~/.cuppa/dependencies    was ~/_cuppa/_download
--downloads-root      ~/.cuppa/downloads       was ~/_cuppa/_cache
--build-root          _build                   unchanged, project-relative
```

Three aspects of this are worth stating explicitly, because they are changes rather than renames.

**One option moves both.** `--storage-root` sets the parent, and the two roots derive from it
unless set individually (§3.1). This is what makes the hidden default in §8.4 comfortable: a
person who wants their dependency trees somewhere visible, or on another volume, says
`--storage-root=~/cuppa-storage` once, in `~/.cuppaconfig`, and never thinks about it again.

**The default moved from project-relative to shared (Phase 1).** Before the rename,
`download_root` defaulted to `_cuppa` *inside the project*. Defaulting to
`~/.cuppa/dependencies` matches what people configured in practice, and means a second checkout
of the same project reuses trees instead of re-cloning them. The cost is coupling: one bad tree
now affects every project on the machine, and branch-qualified trees from every project pile up
in one place. That cost is precisely what the listing options in §3.2 are there to make visible,
which is another reason they belong in this plan rather than a later one. A project that wants
isolation still says `--storage-root=_cuppa` and gets both roots inside the project, or
`--dependencies-root=_cuppa/dependencies` to keep only the trees local while still sharing
downloaded archives.

Sharing by default is the right trade for most people and the wrong one for some — a project
that patches a dependency tree in place, an air-gapped or audited build, a machine where two
projects need different revisions of the same branch. Those cases are not obscure enough to
leave to discovery, so the shared default carries a documentation obligation rather than a
footnote:

- `build-layout.adoc` states it where the roots are introduced, not further down: dependencies
  and downloads are shared between every project on the machine unless you say otherwise, here
  is what you gain, here is what you give up, and here is the single option that changes it.
- The same statement appears in `install.adoc` / `quickstart.adoc`, where a first-time reader
  finds out where their disk is about to be used.
- A project pins containment by storing `--storage-root=_cuppa` in its `configure.conf`, so the
  choice lives with the project rather than with each person who clones it. The docs should show
  that, not just the command-line form.
- The first retrieval of a run reports the resolved roots at info level, so the location is
  visible in build output rather than only in documentation.
- `CHANGELOG.md` says plainly that the default location changed and gives the one option that
  restores the old behaviour.

**Per-OS equivalents.** The root should be the platform's normal per-user location, with the
same two subfolder names everywhere so documentation and support answers stay identical:

| Platform | Root |
|----------|------|
| Linux, macOS | `~/.cuppa/` |
| Windows | `%USERPROFILE%\.cuppa\` |

Windows could instead use `%LOCALAPPDATA%\cuppa\`, which is where Windows expects per-user
machine-local data to live. The reason to keep `%USERPROFILE%\.cuppa\` is consistency: cuppa's
configuration file is already `~/.cuppaconfig` on every platform, support answers and
documentation then read the same everywhere, and anyone who prefers the platform location can
set `--storage-root=%LOCALAPPDATA%\cuppa` in their config.

### 8.4 Hidden or visible root

**Decision: hidden — `~/.cuppa`.** A folder that lives in someone's home directory should follow
the conventions of a home directory, and every comparable tool's storage is hidden there. The
worry that a hidden folder is a forgotten folder is real, but it is answered by tooling rather
than by visibility: `--list-dependencies` / `--list-downloads` report what is on disk and what
it costs, and `--storage-root` lets anyone who disagrees put the whole thing somewhere visible
in one option.

The case for `~/.cuppa`:

- **A home directory is a user's workspace, not a tool's.** Every visible entry in `~` is a
  small tax on everyone who lists it. Tools that put visible folders there (`_cuppa`, and the
  handful of others that do it) are the exception; `.cargo`, `.gradle`, `.m2`, `.npm`, `.conan2`,
  `.ccache` are the rule. Following the convention means cuppa costs a new user nothing in a
  place they did not choose to give up.
- **Consistency with what cuppa already does.** The configuration file is already `~/.cuppaconfig`.
  Having hidden config beside a visible cache is the inconsistent option, not the hidden one.
- **Hidden does not mean inaccessible.** It is hidden from a bare `ls` and from a file manager's
  default view. It is not hidden from `cd`, from a path in an error message, from a bookmark, or
  from tab completion once you type the dot.
- **Discoverability is a tooling problem, not a visibility problem.** Making the folder visible
  is a weak fix for "I want to know what is in there": it tells you the folder exists, not that
  three transient branch trees are costing 4GB. Even with a visible folder, answering the real
  question means `du -sh *` and knowing which entries are still referenced.
- **`--list-dependencies` and `--list-downloads` are the strong fix.** They answer the question
  directly — sizes, owning dependency, branch qualifier, referenced or not — and they work
  identically whether the root is hidden, visible, or somewhere unusual. Every listing line
  prints the absolute path, so the listing is also how you *find* the folder.
- **Being visible has actively cost something here.** The current names are confusing partly
  because they were chosen to look tidy in a visible listing (`_download`, `_cache` as siblings
  under `_cuppa`) rather than to describe their contents.

The case against, which is stronger than it is for a package manager: a build system's
dependency trees are not disposable cache. People do read them — to check which revision was
fetched, to compare a patched tree against a clean one, to point an editor or a debugger at
dependency sources. Debugging with sources under a hidden path is a small but real friction, and
it recurs. There is also a discovery cost for a newcomer who has never read the docs: a visible
folder beside their projects invites the question "what is this?", which is the moment they
learn cuppa manages storage on their behalf.

Three things settle it in favour of hidden:

- **Every path cuppa prints is absolute.** Listings, retrieval messages, and removal reports all
  name the full path, so an editor or debugger is one copy away regardless of a leading dot. The
  friction is in typing the path, not in reaching it.
- **`--storage-root` makes the choice personal rather than global.** Anyone who wants their
  dependency sources in plain sight sets it once in `~/.cuppaconfig`. That is a better outcome
  than a cuppa-wide default that taxes everyone else's home directory, and it is the reason this
  decision no longer has to wait for evidence from the listing options.
- **Discovery is better served by the docs and by the first build's output** than by a folder
  someone might notice. The first retrieval already prints where it is writing.

The old visible root (`~/_cuppa`) keeps working through the fallback in §8.5, so nobody is moved
against their will; the change is to what a new installation chooses for itself.

### 8.5 Migration

Renaming storage silently would strand existing trees and force re-downloads. Phase 1 shipped
the following; what remains is optional tooling once listing and removal exist.

1. **Done.** `--storage-root`, `--dependencies-root`, and `--downloads-root` are the primary
   options; `--download-root` / `--cache-root` remain documented aliases.
2. **Done.** The environment keys `download_root` / `cache_root` alias the resolved new keys for
   at least one minor release so third-party dependency plugins keep working.
3. **Done.** On startup, if an old folder exists and the new one does not, use the old one and
   log once at info level explaining the new name and how to move. This matters more than a pure
   rename would, because the default location changed too: an existing `~/_cuppa/_download` full
   of trees must not silently become an empty `~/.cuppa/dependencies` and a machine-wide
   re-fetch.

   The fallback considers **two** old dependency locations, not one. Before Phase 1,
   `download_root` defaulted to `_cuppa` *inside the project*, so the tree a project had by
   default was `<project>/_cuppa`, and only a person who configured `download_root` themselves
   had the shared `~/_cuppa/_download`. Checking the shared path alone would leave every
   unconfigured project re-fetching into `~/.cuppa/dependencies` with a perfectly good tree
   sitting beside its sconstruct. Both are checked, project-local first.

   A root kept by the fallback is kept in the form it was written in. A relative `_cuppa` stays
   relative rather than being resolved to an absolute path, because `construct.py` excludes the
   dependencies root from sconscript discovery by folder name and only a relative name matches:
   resolving it would quietly start scanning every retrieved tree for sconscripts.
4. **Done.** `CHANGELOG.md` under Deprecated / Changed, and the docs describe the new defaults
   and how to keep a project self-contained.
5. **Still open.** Consider a `--migrate-storage` action that performs the moves, once the
   listing and removal machinery in this plan exists, since it needs the same containment and
   reporting code.

---

## 9. Decisions taken and questions still open

Settled while reviewing this plan, and folded into the sections above:

| Question | Decision |
|----------|----------|
| Artefacts written outside the build root | Not the build options' job. A separate `--remove-artefacts` with its own design pass (§4.6, Phase 6); `--remove-builds` and `--remove-all-builds` stay inside `build_root` |
| Scope of `--remove-all-dependencies` | Remove what the current selection uses, report what is left for other selections (§4.3) |
| An inventory under the dependencies root | Yes — per-entry JSON, updated on resolve, advisory only (§4.5) |
| Exact or sampled sizing | Resolve may sample; `--list-dependencies` upgrades missing/sampled to exact (with notice); `--exact-sizes` forces remasure (§4.5) |
| Native `du` for exact bytes | Future only, if practice needs it — GNU/`du` prefer + `os.walk` fallback for **bytes**, not behind full `directory_stats` (§4.5.1) |
| Shared or project-relative default | Shared, with a documentation obligation rather than a footnote, and one option to make a project self-contained (§8.3) |
| Whether cloning a missing develop copy is its own option or a mode of `--update-develop` | Its own option, `--clone-develop`, so that updating keeps its narrow promise and the mode slot stays reserved for tolerance levels (§3.7, [#138](https://github.com/ja11sop/cuppa/issues/138)) |
| What a pinned develop location should clone to | **Refuse** with an explanation — develop copies must not be detached (§3.7) |
| Submodules / shallow clones for `--clone-develop` | Recurse by default; no shallow clones (§3.7) |
| Reuse pip VCS retrieval for develop clones | **No** — dedicated `Git.clone` on the unexpanded URL (§3.7) |
| Aligning develop copies onto a feature branch | First-class `--checkout-develop-branch=NAME\|current` and `--reset-develop-branch[=NAME\|current\|default\|base]`; develop home via `--location-base-branch` (defaults to published default) (§3.8) |
| Inferring feature-branch parent automatically | **No** — Git does not record it; wrong guesses move every develop copy. Home is `--location-base-branch` / explicit reset target (§3.8) |
| Downloads-root path under verbose `[D]` LOCATION | No. `[D]` + basename (+ footer) only; paths stay in JSON / `--list-downloads` (§4.12) |

Still open after Slice D (#142) and archive clean (#143):

- **Native `du` for exact byte totals (§4.5.1).** Parked future optimisation — not open work.
  Practice after #143 did not show a need; revisit only if first exact upgrades or
  `--exact-sizes` prove too slow later.
- **How `--remove-artefacts` finds paths.** Graph discovery, project declaration, or both, and
  what it adds over SCons `--clean`. This wants measurement on a real project before an option
  is designed (§4.6).
- **When `--remove-unreferenced-dependencies` / age gates ship.** Partially answered by
  `--force-wipe-dependencies` and `--force-wipe-unreferenced-dependencies` (#146): list-driven
  clear-down of chosen leaves (including unused siblings under referenced identities) and of
  orphan leaves. **§4.15** adds `[selector]` + shared tokens and `location`→`repository`. An
  `--older-than` age gate remains a later tightening.
- **All-dependencies view and empty-`used_by` remark (§4.10).** Deferred. After `used_by` is
  stamped on resolve/build, consider REMARK `unrecorded` or `no record` (prefer those over
  `unused` / `orphan`) for empty maps, and a disk-only listing mode tentatively
  `--list-format=all` (not settled; same tree as unreferenced, section "all dependencies", no
  resolve remarks). Not for the current polish pass.
- **LOCATION URL spelling (§4.11).** Verbose LOCATION mixes configured `git+…` URLs with bare
  remotes from `origin`. Not a bug; normalise or not after more listing use.
- **Conan listing without install metadata.** Decided: persist `.cuppa_conan_meta.json` at
  install time (§4.7). Until that lands, Conan rows under `--list-dependencies` stay weak
  (name + fingerprint). Treat the meta write/read as Phase 3 polish, not an optional nice-to-have.
- **Location listing identity and hierarchical presentation.** **Done** for the tree UI
  (§4.8 / §4.9 P1–P4): short_name / stem; referenced→type→identity→variant tree; REMARK;
  rollups; LOCATION when verbose; `[D]` settled (§4.12). **Default-branch quirk** (§4.8) **done**
  (canonical `stem@branch`, `@<default> (unqualified)` labels, warn; no auto-delete).
  **Develop vs cached stem** bind shipped. **Dependencies documentation split (§7.1) done.**
- **Whether the inventory should record anything else.** `type` (`gitlab` / `conan` /
  `repository` / `archive`; legacy inventory may still say `location`) is already recorded from
  path shape so a namespaced layout migration can move trees without re-guessing. Stem /
  short_name / registry binding follow §4.8 / §4.9. A coarse `class` (`package` / `repository` /
  `archive`) can wait until listing or migration needs it as a field rather than a helper over
  `{gitlab,conan}`. Revision or commit for VCS trees would still let a listing say which revision
  a tree holds without shelling out to git, at the cost of another field to keep honest. Archive
  subtypes (e.g. Boost with custom build steps) are a later classification if behaviour diverges.
- **Whether the `--list-develop` warnings should appear automatically** during any `--develop`
  build once the classification has proved itself, and how they are silenced (§3.5). The option
  name itself is settled.
- **Which `--update-develop` modes are worth adding** beyond the fast-forward default, and
  whether per-dependency scoping is wanted once the value slot is spoken for (§3.6). Both should
  be answered by using `--list-develop` and `--update-develop`, not by guessing now.
- **Whether `--develop-root` should exist** (§3.7), letting a bare machine clone every dependency
  into one root without develop clauses being configured first. It would make onboarding a single
  command, at the cost of cuppa writing configuration rather than reading it.
- **What happens to the inventory when the roots move.** A `--migrate-storage` action (§8.5)
  would need to rewrite recorded paths, or simply discard the inventory and let it rebuild —
  which is cheap, and probably the right answer.
