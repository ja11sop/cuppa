# Plan: Drive CMake from Cuppa + GitLab package staging (#209)

- **Status:** in progress
- **Related:** [`ROADMAP.md`](../../ROADMAP.md) — 1.11.0 / [#209](https://github.com/ja11sop/cuppa/issues/209); [`cmake-to-cuppa-migration.md`](cmake-to-cuppa-migration.md) (migrate *onto* Cuppa — orthogonal); packages / custom-commands Antora; [`gitlab.py`](../../cuppa/package_managers/gitlab.py) `GitlabPackagePublisher`; preferred `Toolchain()`/`Variant()`, `Has*` inspection, deprecate `Using` / keyed `Toolchain`
- **Updated:** 2026-09-11
- **Impact:** staging refresh `patch` (`cmake-pkg-stage-min` done); accessors done (#293); Option B helper `minor`; in-place packaging later (power-user / E)

## Intent

Two related pains show up in real publisher sconscripts:

1. **Cuppa→CMake mismatch** — authors hardcode `CMAKE_BUILD_TYPE=Release`, absolute `g++-N`, and ad-hoc `-B` trees instead of mirroring `--dbg`/`--rel`, the active toolchain, and Cuppa layout (`abs_build_dir` / `abs_final_dir` / `publisher.package_variant()`).
2. **#209 staging** — historically `build_package` copytreed only when staging was **missing** (stale after CMake reinstall); large install prefixes also **double** disk use on first package. **Min refresh + broader `sources()` shipped**; in-place packaging remains (opt-in E).

### Suggested product sequence

1. **`toolchain-variant-accessors`** — preferred vocabulary for B/C.
2. **Option B** — `cmake_configure_args` (teach with accessors).
3. **Then** choose from real friction: missing Command ergonomics → lean **C**; multi-GB stage copy → lean **E** (power-user staging knob; not on the CMake teaching ladder). Do not treat E as step 3 by default.

**Public docs:** generic names (`widget`, “external CMake library”). Do not name private consumer trees. Citing [#209](https://github.com/ja11sop/cuppa/issues/209) is fine.

**Related:** [`cmake-to-cuppa-migration.md`](cmake-to-cuppa-migration.md) remains the *migrate a CMake project onto Cuppa* tutorial outline. This plan is *drive CMake from a Cuppa publisher sconscript*.

## Evidence from publisher shapes (anonymised)

```mermaid
flowchart TD
  subgraph smallLib [Small CMake lib]
    A1[Command cmake -B under dep tree] --> A2[Command cmake --build]
    A2 --> A3[Command copy .a into abs_build_dir]
    A3 --> A4[Install include+lib into package_dir]
    A4 --> A5[PublishPackage]
  end
  subgraph largeInstall [Large CMake install prefix]
    B1[Download/extract] --> B2[cmake -S/-B + CMAKE_INSTALL_PREFIX]
    B2 --> B3[cmake --build + install]
    B3 --> B4["PublishPackage source_include/lib = install prefix"]
    B4 --> B5["build_package copytree into final/pkg/ver"]
  end
```

| Pattern | Typical Cuppa wiring today | Gaps |
|---------|---------------------------|------|
| Small lib | `-B _build/<package_variant()>`, active toolchain `.binary()`, copy `.a` into `abs_build_dir`, `Install` into `final/.../package`, then publish | Often hardcodes `Release`; `-B` under the **dependency** checkout |
| Large install | `CMAKE_INSTALL_PREFIX` → `final/.../installed`, publish with `source_*` = that prefix | Hardcoded compiler + standard + Release; **#209** double-copy remains (stale staging fixed by min refresh) |

Current staging: [`GitlabPackagePublisher.build_package`](../../cuppa/package_managers/gitlab.py) — refresh include/lib/modules when source is newer than stage (identity path skipped); then tar (or skip via `.packaged` / mtime). `publisher.sources()` lists include **and** lib when outside `abs_final_dir`.

## Method return patterns (align accessors with existing Cuppa)

Cuppa sconscript methods fall into clear return families. Proposed `Toolchain()` / `Variant()` must sit in the right family so authors get an intuitive pattern.

### Families today

| Family | What the caller gets | Examples | Progress / graph |
|--------|----------------------|----------|------------------|
| **Graph nodes** | SCons node(s) for build/install/publish | `Build()`, `Compile()`, `Build*Lib()`, `Install()` / `CopyFiles()`, `Command()`, `CreateVersion()`, `PublishPackage()`, `RenderJinjaTemplate()` | Yes when action nodes are created |
| **Configure-time node lists** | Existing `File` nodes (no new builders) | `RecursiveGlob()`, `Filter()`, `GlobFiles()` | No |
| **Configure-time handles** | Non-env, non-node **objects** the caller keeps using | `BuildWith()` → dependency instance(s); `Using(name)` → dependency factory; `Toolchain(name)` → toolchain object; `ExportShared` / `ImportShared` → published values | No |
| **Mutate only** | `None` (side effects on `env` / flags) | `StdCpp()`, `ReplaceFlags()`, `RemoveFlags()`, `BuildProfile()`, `CxxModules()`, `CxxProfiles*()`, `CxxErrorLimit()` | No |
| **Scalars** | strings / paths / bools | `TargetFrom()`; `CollateCxxProfilesIndex()` path; `ImportModules()` success | No |
| **Return `env` for chaining** | Mutated environment | **SCons** builtins (`AppendUnique()`, `MergeFlags()`, `Replace()`, …) — **no Cuppa-registered method in `cuppa/methods/` returns `env`** | N/A |

Important: Cuppa does **not** follow a “return `env`” pattern for its own methods. Flag helpers document “typically `None` or the env” only where SCons underneath returns `env`; Cuppa wrappers that call them still present as mutators. Do **not** make `Toolchain()` / `Variant()` return `env`.

### Closest cousins for the redesign

| Method | Pattern | Similarity to proposed accessors | Difference |
|--------|---------|-----------------------------------|------------|
| `Using(name)` *(today)* | Registry **lookup** → factory / `None` | Inspection, not apply | Name sounds like a go-to; unused in consumers; **deprecate** |
| `BuildWith(name)` | Resolve + **apply**; return **instance** | Handle you call methods on | Always named; mutates `env` |
| `ImportShared(name)` | Read a bound configure-time value | “What this env already has” | Keyed by product name |
| `StdCpp(...)` | Mutate dialect | Same domain | Returns `None` |
| Construction vars | Path / layout plumbing | Active toolchain/variant live here today | Session identity should not require `env['…']` |

### Settled alignment: preferred accessors vs registry inspection

**Preferred (teach everywhere):** configure-time **active handles** — zero-arg only:

| Call | Behaviour |
|------|-----------|
| `env.Toolchain()` | Return active `env['toolchain']` |
| `env.Variant()` | Return active `env['variant']` |

**Registry inspection (non-preferred names on purpose):** boolean existence checks — must not look like everyday dependency/toolchain APIs:

| Call | Behaviour | Replaces |
|------|-----------|----------|
| `env.HasToolchain(name_or_key)` | `True` if registered (key or `toolchain.name()`, same match rules as today’s keyed `Toolchain`) | `env.Toolchain(name)` |
| `env.HasDependency(name)` | `True` if a dependency factory is registered under that exact registry key | `env.Using(name)` |

**Deprecate (warn on call; remove from Antora; remove in a future major, e.g. 2.0):**

| Call | Notes |
|------|-------|
| `env.Using(name)` | Entire method — it always took a name |
| `env.Toolchain(name)` when `name` is provided | Keep implementing until removal, but log deprecation → prefer `HasToolchain` / zero-arg `Toolchain()` |

Teaching shape once shipped:

```python
Import( 'env' )

cxx = env.Toolchain().binary()       # preferred: active handle
build_type = env.Variant().name()    # preferred: active handle

if not env.HasDependency( 'boost' ):
    raise Exception( 'boost not registered in cuppa.run()' )
env.BuildWith( 'boost' ).use_libs( ['filesystem'] )
```

Refuse: returning `env` from accessors; inventing `UseToolchain()`; teaching `Using` / keyed `Toolchain` as primary; giving inspection APIs soft names like `GetToolchain` / `Dependency` that compete with `BuildWith` / `Toolchain()`.

### Assumptions assessment (challenge the lean)

| Assumption | Assessment |
|------------|------------|
| Zero-arg `Toolchain()` / `Variant()` match how people already think | **Strong** — consumers already use `env['toolchain']` / `env['variant']`; methods are a cleaner spelling |
| Keyed `Toolchain(name)` / `Using(name)` are safe to demote | **Strong** — zero consumer call sites; cuppa only uses them in docs + one existence assert |
| Bool `Has*` is enough (no factory/object return) | **Acceptable** — the only real use of `Using` was `is not None`; nobody needed the factory object. If a future need appears, add `GetDependencyFactory` under an equally “non-preferred” name — do not revive `Using` |
| `HasDependency` = registry key membership, **not** “`BuildWith` would succeed” | **Must document** — `BuildWith` has typed tokens and supply-chain precedence; `Using`/`HasDependency` are dumb registry checks. Do not pretend they share resolve logic |
| `HasToolchain` should accept both registry key and `name()` (e.g. `clang` vs `clang-libc++`) | **Yes** — preserve today’s keyed-`Toolchain` match rules so libc++ identity checks keep working |
| Dropping factory return is fine | **Yes for now** — custom pre-`BuildWith` factory wiring was never observed |
| Docs removal can be immediate while code warns | **Yes** — matches cxx-modules / Boost method deprecations (`logger.warn` … removed in 2.0) |
| Need `HasVariant(name)` | **No** for this slice — variants are selected by CLI; active `Variant()` is the gap. Revisit only if someone needs “is `cov` enabled in this session” as a named registry probe |
| `HasDependency` naming vs profiles | **OK** — do not add `HasProfile` unless asked; `BuildProfile` / auto-enable stay separate |

## Active toolchain / variant API (survey)

### Consumer survey (conclusions only)

Local develop consumer sconscript trees (including package publishers):

- **`env.Toolchain(...)` / `env.Using(...)`: zero call sites**
- **Widespread** `env['toolchain']` and `env['variant']`

Cuppa’s own tree: keyed `Toolchain` / `Using` only in lookup tests, Antora examples, and one `Using(...) is not None` assert.

### Redesign lean (accessors + inspection)

| Surface | Role | Docs |
|---------|------|------|
| `env.Toolchain()` / `env.Variant()` | Preferred active handles | Teach |
| `env.HasToolchain(name)` / `env.HasDependency(name)` | Explicit registry inspection | Brief “advanced / optional” note only |
| `env.Using(name)` / `env.Toolchain(name)` | Deprecated | Remove from Antora; warn at runtime |

Impact: **`minor`**, own PR (`toolchain-variant-accessors`). Keep off an `impact:none` CMake-docs PR if that PR stays docs-only.

Deprecation text style (match existing Cuppa warnings): e.g. `env.Using() is deprecated; use env.HasDependency() (removed in cuppa 2.0)` and `env.Toolchain(name) is deprecated; use env.Toolchain() for the active toolchain or env.HasToolchain(name) (removed in cuppa 2.0)`.

## Cuppa → CMake mapping (docs core)

Antora section under [`packages.adoc`](../../docs/modules/ROOT/pages/packages.adoc) (“Publishing from an external CMake build”), cross-link from [`custom-commands.adoc`](../../docs/modules/ROOT/pages/methods/custom-commands.adoc).

| Cuppa surface | Typical CMake flag / use | Notes |
|---------------|--------------------------|-------|
| `env.Toolchain().binary()` (or `env['toolchain'].binary()` / `env['CXX']`) | `-D CMAKE_CXX_COMPILER=…` | Prefer method |
| `env['CC']` | `-D CMAKE_C_COMPILER=…` | When the project builds C |
| `env.Variant().name() == 'dbg'` (or `env['variant']`) | `-D CMAKE_BUILD_TYPE=Debug` | |
| `'rel'` | `-D CMAKE_BUILD_TYPE=Release` | |
| `'cov'` | `-D CMAKE_BUILD_TYPE=RelWithDebInfo` (+ project coverage flags if needed) | Cuppa `--cov` does **not** instrument a pure CMake compile unless the project adds flags |
| `StdCpp` / `--stdcpp` / toolchain default | `-D CMAKE_CXX_STANDARD=…` | Map when possible; document `c++2c` / latest gaps |
| `publisher.package_variant()` / `tool_variant(env)` | `-B` subdirectory token | Avoid dbg/rel/cov clobber |
| `env['abs_build_dir']` | Cuppa-side copy/marker targets | |
| `env['abs_final_dir']` + `final/...` | `CMAKE_INSTALL_PREFIX` and/or `Install()` | |
| `--parallel` / SCons `-j` | `cmake --build … --parallel` / `-j N` | Separate from Cuppa’s job server |
| Generator | `-G Ninja` vs default | Author choice |

Worked examples (generic `widget`): (1) configure + build + `Install` + `PublishPackage`; (2) install-prefix + `PublishPackage` with honest #209 copy callout.

Keep [`cuppa.utility.command.run`](../../cuppa/utility/command.py) + `env.Command`.

## Helper options (analysis — do not implement in the docs PR)

### Option A — Docs-only recipe

Hand-built `cmake …` strings; Antora table is the product.

- **Pros:** Zero API; fast. **Cons:** Easy to regress to hardcoded Release/compiler.

### Option B — `cmake_configure_args(env, **opts)` (preferred later)

Pure function / small module; argv fragments or structured object; no SCons nodes.

- **Pros:** Unit-testable; composes with `run()`; `extra_defines={}`. **Cons:** Callers still own `Command` graph; no staging fix.

**Settled API (this slice):** module [`cuppa/utility/cmake.py`](../../cuppa/utility/cmake.py)

| Symbol | Role |
|--------|------|
| `cmake_configure_args(env, …)` | List of configure tokens (`-B`, `-DCMAKE_…=…`, …) without leading `cmake` |
| `cmake_configure_command(env, …)` | Shell string for `cuppa.utility.command.run` (`shlex.quote`) |
| `cmake_build_type_for_variant(name)` | `dbg`→`Debug`, `rel`→`Release`, `cov`→`RelWithDebInfo` |
| `cmake_cxx_standard_for_stdcpp(token)` | int or `None` (omit `c++latest`) |

Keyword opts: `build_dir`, `source_dir`, `generator`, `install_prefix`, `c_compiler`, `cxx_standard`, `extra_defines`, `include_build_type`, `include_cxx_compiler`. Reads `env['toolchain']` / `env['variant']` / `env['stdcpp']` / `env['CC']` (not `env.Toolchain()`), so tests stay SCons-free.
### Option C — `env.CMakeConfigure` / `CMakeBuild` / `CMakeInstall`

Full methods with progress wiring.

- **Pros:** Ergonomics. **Cons:** Large surface (MSVC multi-config, generators, escape hatches). Defer until B has callers.

### Option D — Publisher-integrated CMake mode

`GitlabPackagePublisher(..., cmake=…)`.

- **Reject** — mixes packaging with orchestration; hides the graph; poor fit for download/extract trees.

### Option E — Staging knobs only

`stage='copy'|'sync'|'inplace'` on the publisher.

- Orthogonal to CMake teaching; addresses #209 directly.

### Settled lean

| Topic | Decision |
|-------|----------|
| Sequence | Accessors → Option B → then C *or* E from friction (not both as “next”) |
| Accessors | Preferred: zero-arg `Toolchain()` / `Variant()`; inspection: `HasToolchain` / `HasDependency`; **deprecate** `Using` and keyed `Toolchain(name)` (warn + strip from docs) |
| Helper | Option **B** preferred after accessors; not C/D yet |
| **C** | End-state ergonomics after B has callers |
| **E** | Opt-in power-user staging (`stage='inplace'`); side quest, not default step 3 |
| `--cov` | Default map to `RelWithDebInfo`; say Cuppa coverage does not auto-instrument CMake |

Refuse: pretend `--cov` covers pure CMake builds; silent `Release` under `--dbg`; private project names in Antora; accessors returning `env`; soft names for inspection (`GetToolchain`, bare `Dependency`) that compete with preferred APIs.

## #209 staging — fold-in?

**Yes as an optional follow-on in the same PR after docs**, if kept minimal (independent of B vs C):

1. Refresh staging when source trees are newer than staging.
2. Broaden `publisher.sources()` to include lib (and install root) so `.packaged` invalidates correctly.
3. Document copy behaviour beside the CMake section.

**Defer:** in-place tar without `final/<pkg>/<ver>/` copy; full rsync delete policy.

If minimal refresh grows, **split**: docs+plan first; staging as #209-only PR.

## Work slices

| ID | Deliverable | Target |
|----|-------------|--------|
| `cmake-pkg-plan` | This design plan + design README / ROADMAP pointers | **Done** (docs PR) |
| `cmake-pkg-docs` | Antora mapping + two generic patterns | **Done** (docs PR) |
| `cmake-pkg-stage-min` | Optional refresh-when-stale + broader `sources()` | **Done** (#292) |
| `toolchain-variant-accessors` | Zero-arg `Toolchain()` / `Variant()`; `HasToolchain` / `HasDependency`; deprecate `Using` + keyed `Toolchain`; strip docs; warn at runtime | **Done** (#293) |
| `cmake-pkg-args-helper` | Option B + unit tests | **In progress** (`minor`) |
| `cmake-pkg-stage-inplace` | Opt-in no-double-copy packaging (E) | Side quest when disk friction appears |
| (later) Option C | `env.CMake*` methods | After B has callers |

## Acceptance

1. Design index lists this plan; links resolve.
2. Antora table is usable for CMake-novice authors; `--cov` honesty present.
3. Accessors: zero-arg `Toolchain()` / `Variant()`, `Has*`, deprecations, Antora strip of `Using` / keyed `Toolchain` as primary; unit + integration coverage (#293).
4. Option B: unit tests for configure argv mapping; Antora patterns use `cmake_configure_command`.
5. Staging min: unit tests for refresh-when-newer and broader `sources()`; Antora NOTE matches behaviour (#292).
