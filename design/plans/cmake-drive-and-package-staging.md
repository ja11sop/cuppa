# Plan: Drive CMake from Cuppa + GitLab package staging (#209)

- **Status:** in progress
- **Related:** [`ROADMAP.md`](../../ROADMAP.md) — 1.11.0 / [#209](https://github.com/ja11sop/cuppa/issues/209); [`cmake-to-cuppa-migration.md`](cmake-to-cuppa-migration.md) (migrate *onto* Cuppa — orthogonal); packages / custom-commands Antora; [`gitlab.py`](../../cuppa/package_managers/gitlab.py) `GitlabPackagePublisher`; preferred `Toolchain()`/`Variant()`, `Has*` inspection, deprecate `Using` / keyed `Toolchain`
- **Updated:** 2026-09-11
- **Impact:** staging refresh `patch` (`cmake-pkg-stage-min` done); accessors done (#293); Option B helper `minor` (#294); Option C methods `minor` (in progress); package archive progress + variant match later; in-place packaging later (power-user / E)

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
| Large install | wget/tar (or similar) → `cmake -S/-B` + `CMAKE_INSTALL_PREFIX` under `final/.../installed` → `cmake --build` + `--target install` → `PublishPackage` with `source_*` = that prefix | Hardcoded `CMAKE_BUILD_TYPE` / dialect / no toolchain `.binary()`; fixed `-B` name (dbg/rel clobber); hand-rolled `-j` via `psutil`; **#209** double-copy of large prefix |
| Dependent package (Corosio-shaped) | Capylike `package_dependency` + Option B `extra_defines` for project-include + package dir | Variant default rel; provider script is upstream’s model, not Cuppa glue |

Current staging: [`GitlabPackagePublisher.build_package`](../../cuppa/package_managers/gitlab.py) — refresh include/lib/modules when source is newer than stage (identity path skipped); then tar (or skip via `.packaged` / mtime). `publisher.sources()` lists include **and** lib when outside `abs_final_dir`.

### Smoke lens — large install-prefix publisher (project C shape)

Third specimen for the Option B → C thought experiment (anonymised). Contrasts with Capylike/Corosio:

| Concern | What the sconscript does today | Option B covers? | Points at Option C / elsewhere? |
|---------|--------------------------------|------------------|----------------------------------|
| Acquire source | `wget` + `tar --strip=1` into `build_dir` (pinned version tarball) | No | Not CMake; location_dep or a download helper is a different story |
| System deps | Assumed installed (pkg-config / apt); empty `cuppa.run` deps | No | Out of scope for cmake helpers |
| Configure | Hardcoded `CMAKE_BUILD_TYPE=Debug`, `CMAKE_CXX_STANDARD=17`, install prefix, feature `-D`s; no `CMAKE_CXX_COMPILER` | **Yes** — `install_prefix=`, variant→build type, toolchain→compiler, `cxx_standard`, `extra_defines` | Mapping only; still `env.Command` + `run` |
| `-B` isolation | Fixed `cmake-out` under extract tree | Caller can pass `build_dir=…/publisher.package_variant()` | Method could default that |
| Build / install | `cmake --build` + `--target install`; `-j` from `os.cpu_count()-2` (was `psutil`) | **No** (configure-only helper) | Strongest C signal: `CMakeBuild` / `CMakeInstall` nodes + parallelism policy vs Cuppa `--parallel` |
| Publish | `source_include/lib` = large install prefix; silent multi-minute `tar` | N/A | Option E / #209; **package-archive-progress** |
| Env side effects | `os.environ['PREFIX']=…` | No | Leave to caller unless proven required |

**Takeaway:** Option B deletes the classic Cuppa↔CMake lies (Debug under `--rel`,
missing compiler, hand-built `-D` string). Most of the remaining bulk is **graph
orchestration** (download → configure → build → install → publish) and **large-prefix
staging** — exactly where a higher-level method (or E) has to justify itself, beyond
argv sugar.

**Operator friction (hours-scale builds):** this shape can take **hours** to compile
and **many minutes** to create the GitLab package archive. Today
`create_package_archive` runs a silent `tar -czf` (or zip walk) with no progress, so
a healthy package step looks hung. Rebuilds must **not** redo download, CMake, install,
staging copy, or tar when inputs are unchanged — `.packaged` / mtime skip and staging
refresh help, but silent multi-minute tar and any unnecessary re-stage remain product
gaps (progress-aware archive helper; Option E inplace / skip double-copy).

**Deep clean:** SCons `-c` only removes graph nodes. A CMake `-B` tree under a
location-dependency checkout is outside Cuppa `_build/` unless registered with
`env.Clean`. Option C methods register Clean on that absolute `-B` path so
`cuppa -c` forces a real reconfigure/rebuild rather than a no-op ninja copy.

| Gap | Why it hurts here | Candidate |
|-----|-------------------|-----------|
| Silent package `tar`/`zip` | Minutes with no console feedback | Progress-aware `create_package_archive` (bytes / entries / heartbeat) |
| Re-run of long steps | Hours wasted on noop rebuilds | Keep/strengthen `.packaged` + staging skip; avoid re-configure/build when stamps valid |
| Double-copy of install prefix | Disk + time before tar | Option E `stage='inplace'` when source *is* the package tree |

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

**Settled API (this slice):** module [`cuppa/buildsys/cmake.py`](../../cuppa/buildsys/cmake.py)

| Symbol | Role |
|--------|------|
| `cmake_configure_args(env, …)` | List of configure tokens (`-B`, `-DCMAKE_…=…`, …) without leading `cmake` |
| `cmake_configure_command(env, …)` | Shell string for `cuppa.utility.command.run` (`shlex.quote`) |
| `cmake_build_type_for_variant(name)` | `dbg`→`Debug`, `rel`→`Release`, `cov`→`RelWithDebInfo` |
| `cmake_cxx_standard_for_stdcpp(token)` | int or `None` (omit `c++latest`) |

Keyword opts: `build_dir`, `source_dir`, `generator`, `install_prefix`, `c_compiler`, `cxx_standard`, `extra_defines`, `include_build_type`, `include_cxx_compiler`. Reads `env['toolchain']` / `env['variant']` / `env['stdcpp']` / `env['CC']` (not `env.Toolchain()`), so tests stay SCons-free.

### Worked migration — small CMake lib publisher (project B shape)

A real publisher (Boost.Capy-shaped: location dep → CMake `-B` under the dep tree → copy `.a` into `abs_build_dir` → `Install` → `PublishPackage`) hard-codes the main footgun Option B targets.

**Before (problematic bits only):**

```python
Import( 'env' )
import os
from cuppa.utility.command import run
from cuppa.package_managers.gitlab import GitlabPackagePublisher

src = env.BuildWith( 'widget_src' ).local_sub_path()
version = env.BuildWith( 'widget_src' ).branch()
package_dir = os.path.join( env['abs_final_dir'], 'package' )

publisher = GitlabPackagePublisher(
    env,
    source_include_dir = os.path.join( package_dir, 'include' ),
    source_lib_dir     = os.path.join( package_dir, 'lib' ),
    registry           = 'https://gitlab.example/api/v4/projects/1',
    package            = 'widget',
    version            = version,
)

build_output = os.path.join( '_build', publisher.package_variant() )
compiler = env['toolchain'].binary()
# … paths for libwidget.a under build_output …

cmake_generator_command = (
    f'cmake -B {build_output}'
    f' -D CMAKE_CXX_COMPILER={compiler}'
    f' -G Ninja'
    f' -D CMAKE_BUILD_TYPE=Release'          # ← ignores --dbg / --cov
    f' -D WIDGET_BUILD_TESTS=OFF'
    f' -D WIDGET_BUILD_EXAMPLES=OFF'
)
cmake_build_command = f'cmake --build {build_output}'
# Command → copy .a → Install include/lib → PublishPackage (unchanged)
```

**After (configure line only — graph unchanged):**

```python
from cuppa.buildsys.cmake import cmake_configure_command

cmake_generator_command = cmake_configure_command(
    env,
    build_dir = build_output,
    generator = 'Ninja',
    extra_defines = {
        'WIDGET_BUILD_TESTS': False,
        'WIDGET_BUILD_EXAMPLES': False,
    },
)
cmake_build_command = f'cmake --build {build_output}'
```

| Change | Why |
|--------|-----|
| Drop hand-built `CMAKE_BUILD_TYPE=Release` | `--dbg` → `Debug`, `--rel` → `Release`, `--cov` → `RelWithDebInfo` |
| Drop `compiler = env['toolchain'].binary()` | Helper emits `CMAKE_CXX_COMPILER` from the active toolchain |
| `extra_defines` with bools | Same `-D…=OFF` tokens; clearer than string concat |
| Keep `-B` under `publisher.package_variant()` | Still avoids dbg/rel clobber |
| Keep copy / `Install` / `PublishPackage` | Option B does not own the graph |

Optional polish (not required for the helper): prefer `env.Toolchain()` in surrounding comments/docs; drop unused imports; do **not** pass `--publish-package` while smoke-testing.

**Smoke test (consumer tree, no registry upload):** done on the Boost.Capy-shaped publisher — `--dbg` configure showed `CMAKE_BUILD_TYPE=Debug`, `--rel` showed `Release`; local `.tar.gz` / `.packaged` created without `--publish-package`. Also: single `BuildWith`, drop unused `psutil`, optional Ninja via `shutil.which`, preferred `cuppa.run` kwargs on the matching `sconstruct`.
### Option C — `env.CMakeConfigure` / `CMakeBuild` / `CMakeInstall`

**Informed enough to specify a lean C** from the three publisher smokes (small lib,
dependent-package, large install-prefix). B already owns argv mapping; what remains
repeated in every sconscript is **graph wiring**:

```python
env.Command( stamp, sources, run( cmake_configure_command(...), working_dir=... ) )
env.Command( stamp, prev, run( f'cmake --build {build_dir} …' ) )
env.Command( install_node, prev, run( f'cmake --build {build_dir} --target install' ) )
```

#### What C should absorb (shared across all three)

| Concern | Lean method behaviour |
|---------|------------------------|
| Configure node | `env.CMakeConfigure(…)` → SCons node; internally uses Option B args + `run`; default `working_dir` / `-B` under `publisher.package_variant()` or explicit `build_dir` |
| Build node | `env.CMakeBuild(configure_node, build_dir=…, jobs=…)` → depends on configure; **`-j` from Cuppa parallel by default** (see below) |
| Install node | `env.CMakeInstall(build_node, build_dir=…, target='install')` → `cmake --build … --target install` (no extra `-j` unless install is a heavy custom target — default omit) |
| Stamps | Method-owned `generation.complete` / `build.complete` (or equivalent) so authors stop inventing them |
| Generator | Optional `generator=` / “Ninja if present” helper — same as B callers do today |
| Progress | Wire through Cuppa command reporting so long builds are not silent blanks |

#### Parallelism (`--parallel` → `cmake --build -j`)

Publisher CMake builds are usually **one** long SCons action. Cuppa `--parallel` alone only raises SCons `num_jobs`; without passing `-j` into `cmake --build`, that action stays effectively serial (the large-install pain).

**Default for `CMakeBuild`:** honour Cuppa’s existing parallel knobs (same idea as Boost.b2):

| Condition | Behaviour |
|-----------|-----------|
| `env['parallel']` and `env['job_count'] >= 2` | Pass `-j {job_count}` to `cmake --build` |
| Explicit `jobs=N` | Pass `-j N` (overrides) |
| `jobs=False` / `jobs=0` | Omit `-j` (generator default) |
| No `--parallel` and no `jobs=` | Omit `-j` |

`--parallel` already sets `env['job_count']` from `cpu_count()` when SCons `-j` was left at 1 (`construct.py`). Methods read those env keys — authors should not re-derive affinity/`psutil` in the sconscript.

**Caveat:** if a graph ever runs **several** `CMakeBuild` nodes under SCons `-j` at once, giving each full `job_count` can oversubscribe. Typical package publishers do not; document the escape hatch (`jobs=False` or a smaller `jobs=`) rather than inventing nested-job heuristics in v1 (Boost.b2’s split is for many library b2 invocations — different shape).

#### What C must **not** absorb (still caller-owned)

| Concern | Why leave it out |
|---------|------------------|
| wget / tar acquire | Not CMake; different helper if ever |
| `extra_defines` / project-includes | Project-specific; pass through to B |
| Copy `.a` into `abs_build_dir` + `Install` | Small-lib packaging shape; not universal |
| `PublishPackage` / publisher construction | Packaging, not CMake |
| System package deps | Host/CI concern |
| Silent multi-minute package `tar` | **`package-archive-progress`** — orthogonal to C |
| Double-copy of large install prefix | **Option E** — orthogonal to C |

#### Hypothetical after lean C (large-install sketch)

```python
configured = env.CMakeConfigure(
    extracted_release,
    working_dir = extraction_folder,
    build_dir = build_output,
    install_prefix = str( install_location ),
    generator = cmake_generator,
    cxx_standard = False,
    extra_defines = { … },
)
built = env.CMakeBuild( configured, build_dir=build_output, working_dir=extraction_folder )
installed = env.CMakeInstall(
    built,
    build_dir=build_output,
    working_dir=extraction_folder,
    target=install_location,
)
published = env.PublishPackage( installed, publisher )
```

(`CMakeBuild` picks up Cuppa `--parallel` → `--parallel N`; no hand-rolled `jobs=`.)

Small-lib / Corosio-shaped scripts keep the same three calls, then their own copy/`Install`
loop. That is enough simplification to justify C; a mega-`CMakePackage` that also stages
libs would fight the two packaging shapes.

#### Still open (specify before implementing, not blockers to “enough info”)

| Open | Lean default to propose |
|------|-------------------------|
| MSVC multi-config | Single-config generators first; document multi-config as escape hatch (`--config`) later |
| `-j` vs Cuppa `--parallel` | **Settled:** `CMakeBuild` passes `-j env['job_count']` when `--parallel` (or explicit `jobs=`); omit otherwise — see table above |
| Return type | **Graph nodes** (same family as `Command` / `PublishPackage`) |
| One method vs three | Prefer three small methods (compose); reject one god-method that hides the graph |

**Verdict:** enough information to design and sequence lean C. Do **not** wait for more
publisher shapes for the configure/build/install core. Do ship **archive progress** and
consider **E** from the large-install pain — those are not C.

### Option D — Publisher-integrated CMake mode

`GitlabPackagePublisher(..., cmake=…)`.

- **Reject** — mixes packaging with orchestration; hides the graph; poor fit for download/extract trees.

### Option E — Staging knobs only

`stage='copy'|'sync'|'inplace'` on the publisher.

- Orthogonal to CMake teaching; addresses #209 / large-install double-copy directly.

### Settled lean

| Topic | Decision |
|-------|----------|
| Sequence | Accessors → Option B → then **lean C** *and/or* archive-progress / E from friction (not a single “next”) |
| Accessors | Preferred: zero-arg `Toolchain()` / `Variant()`; inspection: `HasToolchain` / `HasDependency`; **deprecate** `Using` and keyed `Toolchain(name)` (warn + strip from docs) |
| Helper | Option **B** in ``cuppa.buildsys.cmake``; feeds C |
| **C** | Lean `CMakeConfigure` / `CMakeBuild` / `CMakeInstall` graph nodes; **informed enough** from three smokes; do not absorb acquire / copy-Install / Publish / tar progress |
| Package include←lib | ``Requires(installed_include, installed_lib)`` (order-only); not ``Depends`` |
| **E** | Opt-in power-user staging (`stage='inplace'`); large install-prefix |
| Archive progress | Separate slice; hours-scale package `tar` must not look hung |
| `--cov` | Default map to `RelWithDebInfo`; say Cuppa coverage does not auto-instrument CMake |

Refuse: pretend `--cov` covers pure CMake builds; silent `Release` under `--dbg`; private project names in Antora; accessors returning `env`; soft names for inspection (`GetToolchain`, bare `Dependency`) that compete with preferred APIs; Option D; a C that also owns packaging.

## #209 staging — fold-in?

**Yes as an optional follow-on in the same PR after docs**, if kept minimal (independent of B vs C):

1. Refresh staging when source trees are newer than staging.
2. Broaden `publisher.sources()` to include lib (and install root) so `.packaged` invalidates correctly.
3. Document copy behaviour beside the CMake section.

**Defer:** in-place tar without `final/<pkg>/<ver>/` copy; full rsync delete policy.

If minimal refresh grows, **split**: docs+plan first; staging as #209-only PR.

## Dependent packages — variant matching + CMake wire-up

Explored against a Boost.Corosio-shaped publisher that `BuildWith`s a Capylike
`package_dependency` (registry archive) while driving Corosio via Option B.

### Variant matching (dbg consumer → rel dependency)

**Today:** if `package_dependency(…)` omits `variant=`, `GitlabPackageDependency.package_id`
forces `_variant = "rel"`. A `--dbg` Corosio build therefore pulls a **rel** Capylike
archive. That is intentional-enough for many static libs (ABI / headers dominate;
debug symbols live in the consumer’s own objects), and it matches what the smoke
run already did.

**Product intent (default):** building a dbg (or cov) package **may** consume
**rel** dependency packages. Exact/strict same-variant matching is opt-in, not
the default.

| Policy | Behaviour |
|--------|-----------|
| **Default (allow cross-variant)** | Unspecified `variant` → prefer `rel` (current), *or* later: try env variant then fall back to `rel` if the archive is missing |
| **Strict / exact** | Match `env.Variant()` (or an explicit `variant=`); fail closed if that archive is absent |

**Cuppa slice (later, `minor`):** document the default; add an explicit strict switch
(CLI and/or `package_dependency(…, match='exact')` — exact spelling TBD). Do **not**
break existing “omit variant → rel” publishers without a migration note.

**Refuse:** silently switching the default to “always match env variant” (that would
404 many dbg/cov consumers that only publish rel dependency archives).

### Corosio Capylike wire-up (not a Cuppa workaround)

Corosio’s standalone CMake expects `Boost::capy` to already exist (“provided by the
consumer”). It does **not** `find_package(boost_capy)` for the in-tree build. The
supported consumer integration is therefore:

- `CMAKE_PROJECT_boost_corosio_INCLUDE` → a cmake script that creates `Boost::capy`
- plus custom inputs that script understands (`COROSIO_CI_CAPY_PACKAGE_DIR` for a
  Capylike package tree, or `COROSIO_CI_CAPY_SOURCE_DIR` for `add_subdirectory`)

`provide-capy.cmake` is that script. With a Capylike **GitLab package**, Cuppa still
needs both `-D`s: the package supplies files on disk; the include script turns
`package_dir()` into an `IMPORTED`/`ALIAS` target. Path-only defines are not enough —
Corosio links **targets**, not bare include/lib paths.

Calling that “hacky” reflects an upstream design preference (`find_package` would be
nicer), **not** a Cuppa gap to paper over in this workstream. Rewriting Corosio’s
dependency model is out of scope here.

**This workstream’s job:** keep driving publishers with Option B
(`cmake_configure_command` / `extra_defines`, accessors, package deps) to see how far
utilities go, what stays awkward in the sconscript, and whether that friction justifies
a higher-level Option C (`env.CMake*`) — and what that method would need to absorb
(configure argv, project-includes, dep package dirs, generators, build/install graph).

`CMAKE_PREFIX_PATH` + shipping Capylike cmake package config remains a possible
*upstream* improvement later; it is **not** the success criterion for Option B/C.

### Settled lean (this section)

| Topic | Decision |
|-------|----------|
| dbg → rel deps | **Allowed default**; strict/exact is opt-in |
| `provide-capy.cmake` | **Legitimate Corosio integration**; keep for package and source paths |
| Package + provider | Capylike `package_dependency` + the two `-D`s is the intended smoke path |
| Exercise | Stress-test Option B → judge Option C value from real publisher friction |
| Upstream rewrite | Out of scope (Corosio `find_package` / Capylike cmake Install) |

## Work slices

| ID | Deliverable | Target |
|----|-------------|--------|
| `cmake-pkg-plan` | This design plan + design README / ROADMAP pointers | **Done** (docs PR) |
| `cmake-pkg-docs` | Antora mapping + two generic patterns | **Done** (docs PR) |
| `cmake-pkg-stage-min` | Optional refresh-when-stale + broader `sources()` | **Done** (#292) |
| `toolchain-variant-accessors` | Zero-arg `Toolchain()` / `Variant()`; `HasToolchain` / `HasDependency`; deprecate `Using` + keyed `Toolchain`; strip docs; warn at runtime | **Done** (#293) |
| `cmake-pkg-args-helper` | Option B + unit tests | **Done** on branch / #294 (`minor`) |
| `cmake-pkg-methods` | Lean Option C: `CMakeConfigure` / `CMakeBuild` / `CMakeInstall` | **In progress** (`minor`) |
| `package-archive-progress` | Progress / heartbeat while creating large `.tar.gz` / `.zip` | Later (`patch`/`minor`) — project C pain |
| `package-variant-match` | Document dbg→rel default; opt-in strict/exact | Later (`minor`) |
| `cmake-pkg-dep-wire` | Antora: package dep + project-include / `extra_defines` pattern (Corosio-shaped) | Later (docs from smoke) |
| `cmake-pkg-stage-inplace` | Opt-in no-double-copy packaging (E) — large install-prefix | Side quest when disk/time friction appears |
| (later) Option C polish | MSVC multi-config escape hatch | After lean C |

## Acceptance

1. Design index lists this plan; links resolve.
2. Antora table is usable for CMake-novice authors; `--cov` honesty present.
3. Accessors: zero-arg `Toolchain()` / `Variant()`, `Has*`, deprecations, Antora strip of `Using` / keyed `Toolchain` as primary; unit + integration coverage (#293).
4. Option B: unit tests for configure argv mapping; Antora patterns use `cmake_configure_command` / methods.
5. Staging min: unit tests for refresh-when-newer and broader `sources()`; Antora NOTE matches behaviour (#292).
6. Option C: unit tests for `cmake_build_jobs` / methods; Antora patterns use `CMakeConfigure` / `CMakeBuild` / `CMakeInstall`; `--parallel` → `--parallel N`.
