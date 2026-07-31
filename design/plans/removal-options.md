# Plan: removal options for build folders and dependencies

- **Status:** proposal
- **Related:** [`ROADMAP.md`](../../ROADMAP.md) — Storage roots, listing, and removal options
- **Updated:** 2026-07-31

Nothing here is implemented. Follow-on from the `--clean` work in `cuppa/location.py` and `cuppa/package_managers/gitlab.py`,
where a clean could not complete because a dependency was missing, and where the advice for
leftover artefacts was "remove the folder by hand". Telling people to run `rm -rf` is
unsatisfying: it is platform-specific, it is easy to aim at the wrong path, and cuppa already
knows exactly which folders belong to which variant and which dependency.

This plan proposes renaming the storage roots, a way to list what is in them, a family of
explicit removal options, and the safety model that governs all of it.

The storage rename comes **first** (§6, Phase 1). Every later phase talks about paths, so doing
the rename up front means each subsequent discussion and changeset uses one vocabulary, instead
of every review having to translate between the old and new names. Throughout this document the
new names are used: `dependencies_root` for what is currently `download_root`, and
`downloads_root` for what is currently `cache_root`.

---

## 1. Goals and non-goals

**Goals**

- Give the storage roots names that say what is in them, before building anything on top.
- Let people **see** what is on disk — dependencies and downloads, with human-readable sizes —
  so they can decide what is worth removing.
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
- Touching `--develop` working copies or anything outside the storage roots (see §5).

---

## 2. Current behaviour

### 2.1 What exists today

| Need | Today |
|------|-------|
| Remove built targets | SCons `--clean` / `-c`, variant-scoped, graph-driven |
| Remove a variant folder | manual `rm -rf _build/...` |
| Remove all build output | manual `rm -rf _build` |
| See what dependencies are on disk and how big they are | manual `du -sh` |
| Remove one stale dependency | manual `rm -rf` under the download root |
| Remove all dependencies | manual |
| Remove cached archives | manual, under `cache_root` |

The listing gap matters as much as the removal gap. Working across branches leaves
branch-qualified trees (`…@feature_x`) behind indefinitely, and nothing ever reports them, so
they accumulate unnoticed until a disk fills.

### 2.2 Storage roots

From `cuppa/core/storage_options.py`:

| Key | Default | Set by |
|-----|---------|--------|
| `build_root` / `abs_build_root` | `_build` | `--build-root` |
| `download_root` | `_cuppa` (project-relative) | `--download-root` |
| `cache_root` | `~/_cuppa/_cache` | `--cache-root` |

Many users point `download_root` at a shared location (for example `~/_cuppa/_download` via
`~/.cuppaconfig`), which is what makes stale dependency trees shared across projects and
therefore worth a managed removal command.

This table describes today. Phase 1 renames these to `dependencies_root` and `downloads_root`
and changes where they default to; see §8.

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

### 2.4 Download root layout

Written by several subsystems, all under `download_root`:

| Producer | Path shape |
|----------|-----------|
| `cuppa/location.py` (VCS) | `<download_root>/<folder_name_from_path(url)>[@<branch or tag>]` |
| `cuppa/location.py` (archives) | `<download_root>/<folder_name_from_path(url)>` (extracted) |
| `cuppa/package_managers/gitlab.py` | `<download_root>/<tool_variant>/<package>/<version>/` |
| `cuppa/build_with_conan.py` | `<download_root>/conan/<dependency name>/` |

The `@<branch>` suffix is decided by relative versioning plus `--location-match-current-branch`
/ `--location-match-branch` / `--location-match-tag`, so the *same* dependency can legitimately
have several sibling folders. Removal has to be explicit about which of those it is deleting.

### 2.5 Cache root layout

| Producer | Path shape |
|----------|-----------|
| `cuppa/location.py` | `<cache_root>/<local folder name>` — the raw downloaded archive |
| `cuppa/package_managers/gitlab.py` | `<cache_root>/packages/<package>/<version>/<package file>.tar.gz` |

Note the asymmetry that motivates §8: the folder called `_download` holds *extracted, ready to
use* trees, and the folder called `_cache` holds the *actual downloaded files*.

---

## 3. Proposed CLI surface

All options are opt-in, and all of them are *actions* rather than modifiers.

### 3.1 Storage roots (Phase 1)

| Option | Env key | Default |
|--------|---------|---------|
| `--dependencies-root` | `dependencies_root` | `~/_cuppa/dependencies` |
| `--downloads-root` | `downloads_root` | `~/_cuppa/downloads` |
| `--build-root` | `build_root` | `_build` (unchanged, project-relative) |

`--download-root` and `--cache-root` keep working as deprecated aliases, as do the
`download_root` and `cache_root` environment keys. See §8 for the naming rationale, the default
location change, and migration.

### 3.2 Listing

Read-only, and useful on their own:

| Option | Reports |
|--------|---------|
| `--list-dependencies` | Every dependency tree under `dependencies_root`, with size, which dependency name owns it, and which branch or tag qualifier it carries |
| `--list-downloads` | Every archive under `downloads_root`, with size and the dependency it feeds |
| `--list-builds` | Every variant subtree under `build_root`, with size |

Each listing ends with a total and, where cuppa can tell, marks entries the current build does
*not* reference as `unreferenced` — the transient-branch trees that are the usual reason a
storage root has quietly grown. Sizes are human readable by default (`1.2G`, `340M`); a
`--list-format=json` variant makes the output scriptable without parsing columns.

```
cuppa: storage: [info] Dependencies in /home/user/_cuppa/dependencies
cuppa: storage: [info]   1.4G  widget            @master
cuppa: storage: [info]   1.4G  widget            @release_1.14   unreferenced
cuppa: storage: [info]   1.3G  widget            @feature_x      unreferenced
cuppa: storage: [info]   860M  boost             1.91.0
cuppa: storage: [info]   210M  gadget            2.28.0/rel  (gcc153_rel_x86_64_cxx2c)
cuppa: storage: [info] 5 entries, 5.2G total, 2.7G unreferenced
```

Two lines of that output answer the question people currently answer with `du` and guesswork,
and the last line is the one that prompts a `--remove-dependencies=widget`.

### 3.3 Removal

| Option | Removes |
|--------|---------|
| `--remove-build` | Every `<tool_variant_dir>` subtree under `build_root` matching the current toolchain / variant / arch / ABI selection |
| `--remove-all-builds` | The `build_root` folder itself |
| `--remove-dependencies=dep1,dep2` | The `dependencies_root` folders for the named dependencies, for the current selection |
| `--remove-all-dependencies` | As above for every dependency the current build knows about |
| `--purge-dependencies=dep1,dep2` | As `--remove-dependencies` plus the matching archives under `downloads_root` |
| `--purge-all-dependencies` | As `--remove-all-dependencies` plus every download those dependencies own |

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

---

## 4. Scope resolution

### 4.1 `--remove-build`

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
typo that silently removes nothing is worse than a failed command.

`--remove-all-dependencies` covers dependencies known to *this* build: the union of
`default_dependencies` and anything reached through `BuildWith`. It deliberately does not sweep
the dependencies root for unknown folders — that would delete other projects' dependencies from
a shared root. Those unknown folders are exactly what `--list-dependencies` marks as
`unreferenced`, so the workflow is "list, look, then remove by name" rather than a blind sweep.
A `--remove-unreferenced-dependencies` could follow once the listing has proved its inventory is
trustworthy.

### 4.4 Branch-qualified folders

When relative versioning is active, the folder carries an `@<branch>` / `@<tag>` suffix. Removal
targets the folder the current options select, and **reports the siblings it is leaving alone**:

```
cuppa: remove: [info] Removing dependency [widget]
cuppa: remove: [info]   /home/user/_cuppa/dependencies/git_ssh_..._widget@master  1.4G
cuppa: remove: [info]   leaving 2 sibling branches in place: @release_1.14 (1.4G), @feature_x (1.3G)
cuppa: remove: [info]   (use --list-dependencies to review them, or name them to remove them)
```

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

Deliberately *not* proposed: an interactive confirmation prompt. These flags are explicit, and
prompts break CI. `-n` covers the "let me check first" case.

---

## 6. Implementation outline

Phased so each phase is useful alone, with the rename first so every later phase, review, and
discussion uses one set of names.

**Phase 1 — storage naming** (§8)

- `cuppa/core/storage_options.py`: add `--dependencies-root` / `--downloads-root` and the
  `dependencies_root` / `downloads_root` keys; keep `--download-root` / `--cache-root` and their
  keys as deprecated aliases that resolve to the same values.
- Fallback: when an old folder exists and the new one does not, keep using the old one and log
  once at info level explaining the new name.
- Update every internal reader (`cuppa/location.py`, `cuppa/package_managers/gitlab.py`,
  `cuppa/build_with_conan.py`, `cuppa/dependencies/…`) to the new keys.
- Docs and `CHANGELOG.md` (Deprecated) in the same change.

Landing this alone is low risk and self-contained: no behaviour changes beyond where the
defaults point, and the alias layer keeps existing `~/.cuppaconfig` files and dependency plugins
working.

**Phase 2 — build removal and `--list-builds`**

- `cuppa/core/build_layout.py`: shared `tool_variant_dir` composition, extracted from
  `construct.py` and used by both.
- `cuppa/core/storage_actions.py`: option registration and scope resolution for listing and
  removal.
- `cuppa/utility/storage.py`: directory sizing, human-readable formatting, containment checks,
  removal, empty-directory pruning, reporting.
- Wire into `cuppa/construct.py` after option processing, before `self.build(...)`; report and
  exit.

**Phase 3 — dependency listing and removal**

- Add the `storage_paths()` protocol and implement it for location, GitLab package, Conan, and
  Boost dependencies.
- Add the resolve-only mode (retrieval disabled) and reuse `retrieval_disabled_reason()`.
- Implement `--list-dependencies` first, then `--remove-dependencies` /
  `--remove-all-dependencies` on top of the same inventory.

**Phase 4 — downloads listing and purge**

- Extend the protocol results with download entries, add `--list-downloads` and the `--purge-*`
  variants.

---

## 7. Testing and documentation

**Unit tests** (`tests/unit/`, no filesystem side effects beyond `tmp_path`):

- New and deprecated root options resolve to the same value, the new one wins when both are
  given, and the old-folder fallback triggers only when the new folder is absent.
- `tool_variant_dir` composition matches what `construct.py` produces for representative
  toolchain / variant / arch / ABI combinations.
- Scope resolution finds nested per-sconscript variant folders and location build folders, and
  ignores other variants.
- Size formatting and totals, including the `unreferenced` marking.
- Containment guards reject paths outside the roots, develop paths, symlink escapes, and
  suspicious roots.
- Unknown dependency names produce an error listing known names.

**Integration tests** (`tests/integration/`):

- A project configured with `--download-root` / `--cache-root` still builds after Phase 1, and
  the same project configured with the new options produces identical layout.
- Build two variants, `--remove-build` one, assert the other survives.
- Build, `--remove-all-builds`, assert the build root is gone.
- `--list-builds` / `--list-dependencies` report the expected entries and totals and change
  nothing on disk.
- `-n` reports paths and removes nothing.
- Dependency removal against a location dependency backed by a local archive, then a rebuild to
  prove re-fetch works.

**Documentation:**

- `docs/modules/ROOT/pages/build-layout.adoc` — the storage roots under their new names, and a
  "Listing and removing build output and dependencies" section next to the existing Cleaning
  section, replacing the current "remove the folder by hand" advice.
- `docs/modules/ROOT/pages/cli-reference.adoc` — the new flags and the deprecated aliases.
- `docs/modules/ROOT/pages/configuration.adoc` — the renamed keys in `~/.cuppaconfig`.
- `docs/modules/ROOT/pages/dependencies.adoc` — the `storage_paths()` protocol for dependency
  authors.
- `CHANGELOG.md` per phase; Phase 1 under both Changed and Deprecated.

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
--dependencies-root   ~/_cuppa/dependencies    was ~/_cuppa/_download
--downloads-root      ~/_cuppa/downloads       was ~/_cuppa/_cache
--build-root          _build                   unchanged, project-relative
```

Two aspects of this are worth stating explicitly, because both are changes rather than renames.

**The default moves from project-relative to shared.** `download_root` currently defaults to
`_cuppa` *inside the project*. Defaulting to `~/_cuppa/dependencies` matches what people
configure in practice, and means a second checkout of the same project reuses trees instead of
re-cloning them. The cost is coupling: one bad tree now affects every project on the machine,
and branch-qualified trees from every project pile up in one place. That cost is precisely what
the listing options in §3.2 are there to make visible, which is another reason they belong in
this plan rather than a later one. A project that wants isolation still says
`--dependencies-root=_cuppa/dependencies`.

**Per-OS equivalents.** The root should be the platform's normal per-user location, with the
same two subfolder names everywhere so documentation and support answers stay identical:

| Platform | Root |
|----------|------|
| Linux, macOS | `~/_cuppa/` |
| Windows | `%USERPROFILE%\_cuppa\` |

### 8.4 Visible or hidden root

The recommendation above keeps the root **visible** (`~/_cuppa`), on the grounds that it is
something you will want to inspect, and a folder you cannot see is a folder you forget you are
paying for. The counter-argument deserves a fair hearing, because it is stronger than it first
appears.

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

The case against, and the reason the recommendation stands: a build system's dependency trees
are not disposable cache in the way a package manager's are. People do read them — to check
which revision was fetched, to compare a patched tree against a clean one, to point an editor or
a debugger at dependency sources. Debugging with sources under a hidden path is a small but real
friction, and it recurs. There is also a discovery cost for a newcomer who has never read the
docs: a visible folder next to their projects invites the question "what is this?", which is the
moment they learn cuppa manages storage on their behalf.

**Proposal: keep `~/_cuppa` visible, and ship `--list-dependencies` / `--list-downloads` as part
of the same work** (Phases 3 and 4). If the listing options land and prove that they, rather
than visibility, are how people actually inspect storage, revisit `~/.cuppa` then — the alias
and fallback machinery from Phase 1 makes a second move cheap, and by then there is evidence
instead of preference. A `--storage-root` option that sets the parent of both subfolders in one
place would let individuals choose either without a cuppa-wide decision.

### 8.5 Migration

Renaming storage silently would strand existing trees and force re-downloads, so:

1. Add `--dependencies-root` / `--downloads-root` as the primary options; keep
   `--download-root` / `--cache-root` working as documented aliases.
2. Keep the environment keys (`download_root`, `cache_root`) as aliases of the new keys for at
   least one minor release so third-party dependency plugins keep working.
3. On startup, if an old folder exists and the new one does not, use the old one and log once at
   info level explaining the new name and how to move.
4. Document the change in `CHANGELOG.md` under Deprecated, and give the `mv` commands in the docs.
5. Consider a `--migrate-storage` action that performs the moves, once the machinery in this plan
   exists, since it needs the same containment and reporting code.

---

## 9. Open questions

- Should `--remove-build` also remove collated artefacts a project writes outside the build
  root (for example `_artifacts/coverage`)? Those paths are a project convention passed to
  `CollateCoverageIndex`, not something cuppa owns, so the default should be no. A project could
  opt in by declaring artefact roots.
- Should `--remove-all-dependencies` be scoped to the current toolchain by default? Package
  trees are per toolchain, VCS trees are not; the honest answer may be "remove what the current
  selection would use, and report the rest", consistent with the branch handling in §4.4.
- Is an inventory file under the dependencies root worth keeping (which project pulled what,
  when, last used)? It would let `--list-dependencies` report "last used by <project>, three
  months ago" rather than only sizes, and would make `--remove-unreferenced-dependencies` safe.
  The cost is state that can go stale, and a write on every resolve.
- Should sizing be exact or sampled? Walking a multi-gigabyte shared root to total every entry
  takes noticeable time. Options are to compute lazily per entry, cache totals in the inventory
  above, or offer `--list-dependencies=quick` that reports entries without sizes.
- Should the default really move from project-relative to shared (§8.3)? Shared matches practice
  and saves refetching; project-relative keeps blast radius small and makes a project trivially
  self-contained.
