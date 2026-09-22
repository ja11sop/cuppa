# Plan: `--deep-clean` as a modifier on `-c` / `--clean`

- **Status:** proposal
- **Related:** [`ROADMAP.md`](../../ROADMAP.md) — `deep-clean`; [#135](https://github.com/ja11sop/cuppa/issues/135) (`artefact-removal`); Boost stage `env.Clean` on [#326](https://github.com/ja11sop/cuppa/pull/326); [`removal-options.md`](removal-options.md); CMake `-B` Clean ([`cmake.py`](../../cuppa/methods/cmake.py)); Boost `storage_clean` / `b2_command` ([`build_with_boost.py`](../../cuppa/dependencies/build_with_boost.py), [`b2.py`](../../cuppa/dependencies/boost/b2.py))
- **Updated:** 2026-09-22
- **Impact:** `minor` (new CLI flag / opt-in clean scope)

## Problem

`cuppa -c` removes SCons targets under `_build/` and any paths registered with
`env.Clean`. That is the right **default**: shared dependency extracts must not
disappear on every clean.

Some product trees sit **outside** `_build` and are expensive to rebuild if wiped
by accident, but users sometimes want them gone with the same clean command:

| Tree | Today on `-c` | Why it hurts |
|------|---------------|--------------|
| Boost cuppa stage `build.<abi>/<toolchain>/…` | Removed when registered ([#326](https://github.com/ja11sop/cuppa/pull/326)) | Nice-to-have; rebuild still warm if `bin.*` remains |
| Boost.Build `bin.<abi>/…` toolset objects | Left in place | Next build looks incremental; `-c` feels incomplete vs CMake |
| CMake `-B` under a location download | Removed when using `CMakeConfigure` / `CMakeBuild` | Already the deep-ish path for publishers |
| Raw `Command` wrappers around cmake/ninja | Often left in place | Cascade clean note already warns about this |

`--remove-dependencies=boost` already wipes Boost stage + matching `bin.*` via
`storage_clean`, but that is an **inventory** verb, not “clean this build the
hard way.” Operators reach for `-c` first.

## Does this close a gap?

**Yes — a real UX gap, not a missing wipe capability.**

Cuppa can already delete Boost stage/`bin.*` products through
`--remove-dependencies=boost` (`storage_clean`). What is missing is tying that
class of wipe to the **normal clean gesture** (`-c`) with an explicit “go deeper”
modifier, so package/CI workflows do not have to remember a second inventory CLI
when they meant “make the next build cold for this selection.”

| Approach | Closes the gap? | Cost |
|----------|-----------------|------|
| **A. `-c --deep-clean` (this plan)** | Yes for graph-driven cleans | New flag; builders opt in; teach docs |
| **B. Document “use `--remove-dependencies=boost` after `-c`”** | Capability yes; gesture no | Two commands; easy to forget; not nested with cascade `-c` |
| **C. Always wipe `bin.*` on plain `-c`** | Too aggressive | Shared-cache thrash; surprises multi-toolchain hosts |
| **D. Only improve CMake; leave Boost to remove-deps** | Partial | Leaves the Boost package / CI asymmetry that prompted the discussion |
| **E. `--deep-clean` without requiring `-c`** | Confusing | Looks like a build mode; overlaps inventory verbs |

**Verdict:** A is worth doing. B remains available forever for extract-scoped
inventory work. C is rejected. Deep-clean is the bridge between “SCons clean”
and “out-of-tree products for this selection,” not a replacement for purge/wipe.

Related roadmap row `artefact-removal` ([#135](https://github.com/ja11sop/cuppa/issues/135))
asked how to remove artefacts outside `_build`. Prefer answering that question
**through** `deep-clean` rather than inventing a parallel story.

## Naming options

Working name in this plan: **`--deep-clean`**. Alternatives considered:

| Name | Pros | Cons |
|------|------|------|
| `--deep-clean` | Reads as a modifier on clean; familiar “deep clean” metaphor; short | Slightly informal; “deep” is vague without docs |
| `--clean-out-of-tree` | Precise about *where* | Long; sounds like it might clean *only* out-of-tree and skip `_build` |
| `--full-clean` | Strong | Implies extract/downloads too; collisions with “full” elsewhere |
| `--force-clean` | Familiar from other tools | In Cuppa, `force` already means different things (`--force` cascade, wipe); overloads |
| `--clean-products` | Matches `storage_clean` vocabulary | Unclear vs `_build` products; not obviously a `-c` modifier |
| `--aggressive-clean` | Honest | Pejorative; no clearer than deep |

**Prefer `--deep-clean`.** Help text must spell the contract: requires `-c`; expands
out-of-tree product clean; does not delete extracts. If review prefers a longer
precise name, `--clean-out-of-tree` is the runner-up — still a modifier, still
refuses alone.

## Settled approach

**`--deep-clean` is a modifier on existing clean behaviour**, not a separate mode
and not a synonym for `--remove-dependencies`.

```text
cuppa -c --deep-clean --toolchains=gcc15,gcc …
```

| Decision | Choice |
|----------|--------|
| Shape | Flag expands what `-c` deletes / runs; does not replace `-c` |
| Alone | `--deep-clean` without `-c` / `--clean` is a **refusal** (Options Error / StopError) — nothing to deepen |
| Wiring | Builders register safe `env.Clean` always; under deep-clean also register coarse paths **and/or** native tool cleans (below) |
| Nested sessions | Cascade / `--stage-develop` nests that forward `-c` also forward `--deep-clean` when present |
| Extract / downloads | Still **not** deleted (headers, tarballs, `b2` binary stay). Use `--remove-dependencies` / purge / wipe for those |
| vs `storage_clean` | Same *product* classes may overlap for Boost; different entry point. Do not make `-c --deep-clean` call the remove-dependencies planner |

Helper `deep_clean_enabled(env)` reads the Cuppa option (false unless clean mode
is active after the refusal gate).

### Two mechanisms under one flag

Deep-clean is allowed to use **either or both**:

1. **Path Clean** — `env.Clean(nodes, path)` (SCons removes files/dirs), same as
   today’s CMake `-B` and Boost stage registration.
2. **Native tool clean** — run the dependency’s own clean command with the same
   selection Cuppa used to build (e.g. `./b2 --clean …`, `cmake --build -B … --target clean`,
   `ninja -C … -t clean`). Prefer this when the external tool knows the product
   graph better than a directory list.

Path Clean alone is enough for “delete this folder.” Native clean is better when
layout is tool-owned, multi-rooted, or incompletely mirrored in Cuppa’s path
helpers. A builder may: native clean first, then `env.Clean` leftovers (stage
dir, stamps).

## Scope by layer (v1)

| Layer | Normal `-c` | `-c --deep-clean` |
|-------|-------------|-------------------|
| `_build/…` targets | Yes | Yes |
| Boost `build.<abi>/<toolchain>/…` stage | Yes (after #326) | Yes (path Clean; also after b2 clean) |
| Boost `bin.<abi>/…` for this selection | No | Yes — prefer **cooperative `b2 --clean`**, with path Clean as fallback/supplement |
| Boost extract / headers / `b2` | No | No |
| CMake `-B` via Cuppa methods | Yes | Yes; optional native `cmake --build --target clean` later if path Clean proves incomplete |
| Other location deps | No new behaviour until each opts in | Opt-in via the same helper |

**Major-toolset coarseness** under `bin.<abi>` (e.g. `gcc-16` vs `gcc162`) remains
a Boost.Build naming limit when using path Clean / `storage_clean`. Cooperative
`b2 --clean` with Cuppa’s exact `toolset=` / `variant=` / `--build-dir=` should
track **what that b2 invocation built**, which is the better default for deep-clean.

## Use case: Boost package, cold rebuild after `-c`

### Operator story

Publishing Boost (or iterating on the Boost package sconscript) on a runner or
laptop:

```text
# Warm shared extract under dependencies_root / downloads:
#   …/patched/b2
#   …/patched/bin.c++2c/…/gcc-15/…
#   …/patched/build.c++2c/gcc15/release/x86_64/…
#   project _build/gcc15/rel/…/libboost_*.a  (install copies)

cuppa --rel --parallel --toolchains=gcc15,gcc -c
# Today / after #326: _build copies + cuppa stage dirs gone.
# bin.c++2c object trees remain → next cuppa build is still a warm b2.

cuppa --rel --parallel --toolchains=gcc15,gcc -c --deep-clean
# Also asks Boost.Build to forget this selection’s products (see below).

cuppa --rel --parallel --toolchains=gcc15,gcc
# Meaningful rebuild of libraries for gcc15 + gcc16; headers/b2 reused.
```

CI that must prove a **cold library build** (without re-downloading the Boost
tarball) can standardize on `-c --deep-clean` before the publish job, instead of
`--remove-dependencies=boost` (which is easy to mis-scope) or deleting the whole
extract by hand.

### Cooperative `b2 --clean` (preferred Boost mechanism)

Cuppa already builds argv in `b2_command(…)`: `./b2`, `-j`, `--with-*`,
`toolset=`, `variant=`, arch flags, `cxxflags=`, `define=`, `link=`,
`--build-dir=./bin.<abi>`, `stage`, `--stagedir=./build.<abi>/…`,
`--ignore-site-config`, and on Linux `--user-config=<toolchain>._jam`.

Boost.Build accepts a **`--clean`** (and related) mode on that same command
shape: remove targets for the current request rather than update them. Deep-clean
should **reuse that argv** (or a thin variant) so clean and build stay aligned —
including `--user-config` and the same `--build-dir` / `--stagedir`.

Sketch:

```python
if deep_clean_enabled( env ):
    # Pseudocode: Action runs only when SCons is cleaning these nodes.
    clean_args = b2_command( … )   # same selection as the library build
    # Insert Boost.Build's clean switch in the agreed position, e.g.:
    #   ./b2 --clean -j N --with-… toolset=… --build-dir=… --stagedir=… --user-config=…
    env.Clean( installed, … )      # still remove stage / any leftovers
    # Plus a clean-time Action / AlwaysBuild Command that runs clean_args
    # when -c --deep-clean, Required by the installed library nodes.
```

Open implementation details (settle in the implementing PR):

| Detail | Lean toward |
|--------|-------------|
| `--clean` vs `--clean-all` | Prefer **`--clean`** scoped by the same properties as the build; avoid `--clean-all` (too wide for a shared extract) |
| When to run | Only under `-c --deep-clean`, once per distinct b2 invocation key (toolchain × abi × variant × linktype), not once per library file |
| Failure mode | Non-zero b2 clean → fail the Cuppa clean (do not silently fall back to rm-only without a log line) |
| Fallback | If `b2` missing or clean unsupported for ancient Boost: path Clean of `find_b2_build_dir_products` + stage (same as `storage_clean`) |
| Parallel `-j` multi-toolchain | Two toolchains → two b2 cleans (already separate user-config files); serialise if b2 cannot share the extract safely — measure; SideEffect on a lock node if needed |

### Why cooperative beat path-only for Boost

| | Path `env.Clean` on `bin.*` | Cooperative `b2 --clean` |
|--|----------------------------|---------------------------|
| Matches what Cuppa built | Approximate (toolset token heuristics) | Same argv Cuppa uses to build |
| Handles renamed/internal paths | Fragile | Tool-owned |
| Shared extract / multi-toolchain | Risk of over-deleting sibling patch levels | Scoped by `toolset=` / stagedir |
| Implementation | Already half-done via `storage_clean` helpers | Needs clean-time Action wiring |

**Recommendation:** v1 Boost deep-clean = cooperative `b2 --clean` with shared
`b2_command` + path Clean for the cuppa stage (and leftover stagedir). Keep
path-only `bin.*` deletion as fallback and as what `--remove-dependencies`
continues to use.

## Non-goals

- Automatic GC of unused downloads (`storage-gc`)
- Deleting whole dependency extracts on clean
- Replacing `--remove-dependencies` / `--purge-*` / `--wipe-*`
- `--deep-clean` as a build-time “always rebuild out of tree” without `-c`
- Defaulting to `b2 --clean-all` or wiping unrelated toolsets in the extract
- Solving every raw-Command CMake publisher in v1 (cascade note remains; prefer migrating to `CMakeConfigure` / `CMakeBuild`)

## Implementation sketch

1. **Option** — `AddOption('--deep-clean', …)`; help: requires `-c`; expands
   out-of-tree / native product clean.
2. **Gate** — if deep-clean and not clean → refuse.
3. **API** — `deep_clean_enabled(env)` for builders.
4. **Boost** — under deep-clean: schedule cooperative `b2 --clean` from
   `b2_command`; keep stage `env.Clean`; fallback path Clean for `bin.*`.
5. **Forwarding** — nested argv appends `--deep-clean` when the tip has it.
6. **Docs** — naming + Boost use case; CLI clean page; cascade clean note;
   contrast with `--remove-dependencies`.
7. **Tests** — refusal without `-c`; argv contains `--clean` (or agreed switch)
   when deep-cleaning; nested forward; fallback path registration.

## Progress snapshot

| Item | State |
|------|--------|
| Settled: modifier on `-c`, not standalone | Done |
| Naming commentary + gap assessment | Done (this revision) |
| Native tool clean + Boost `b2 --clean` use case | Done (design); code not started |
| Scratchpad note | Graduated here |
| Option + refusal gate | Not started |
| Boost cooperative clean + fallback | Not started |
| Nested forward | Not started |
| Docs + tests | Not started |

## Next focus

Land CLI + Boost cooperative `b2 --clean` (with path fallback) first. Revisit
other location deps / CMake native clean only when a concrete publisher needs them.
