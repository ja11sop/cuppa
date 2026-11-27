# Note: stage shared package libs so consumer binaries run outside Cuppa ENV

- **Status:** proposal
- **Related:** [`archive/package-runtime-paths.md`](../archive/package-runtime-paths.md)
  (construction `ENV` + publisher `$ORIGIN/../lib`; absolute cache RPATH out of
  policy); [`pkgconfig-dependency-search-path.md`](pkgconfig-dependency-search-path.md)
  (link/Requires closure); `cuppa/package_managers/runtime_paths.py`;
  Antora Using GitLab packages; ROADMAP `package-runtime-deploy`
- **Updated:** 2026-11-27
- **Impact:** likely `minor` (new stage/collect methods + later default on
  `env.Build`); first slice can be additive methods only (`patch`-shaped) until
  the Build default lands

## Problem

Cuppa GitLab packages install shared libraries under a non-system prefix
(`<dependencies>/<variant>/<package>/<version>/lib`). On `BuildWith`,
`apply_package_runtime_paths` prepends those dirs to the **SCons construction
`ENV`** (`LD_LIBRARY_PATH` / `DYLD_LIBRARY_PATH` / `PATH`). That covers:

- host tools during the build (`protoc`, `grpc_cpp_plugin`, …), and
- binaries Cuppa itself spawns (`--test`, `--run`).

It does **not** cover a binary run **outside** that ENV: a shell, an IDE
launch, a container entrypoint, or systemd. Operators then point
`LD_LIBRARY_PATH` at package extract or publisher `final/` trees. That works
as a workaround and is host- and variant-specific; it is a poor Docker story
and not what we want as the product path.

Publisher packages already embed `$ORIGIN/../lib` for *their own* install
layout. Cross-package **absolute** RPATH into the dependency cache was
rejected in the runtime-paths slice (relocatable caches / version bumps).
Consumer tip binaries typically live under `_build/…/final/` with package
`.so` files elsewhere, so `$ORIGIN` alone does nothing unless the libs are
also placed relative to the binary.

```text
  BuildWith ──► link against package .so
            ──► ENV LD_LIBRARY_PATH=<deps>/…/lib   # Cuppa children only

  ./_build/…/final/widget_server                  # detached run
       └── loader: cannot find libwidget_core.so
```

## Goals

1. **Canonical approach** limited to **Cuppa package dynamic libraries** so a
   tip that linked them can run (and be copied into an image) without
   hand-maintained `LD_LIBRARY_PATH` to extract finals.
2. **Standalone methods first** aimed at tip programs from ``env.Build()``.
   Implementation should accept ordinary program nodes (not Build-only
   wrappers). A node from ``env.Program()`` may work the same way if Cuppa
   package link contributions are already on the env — that is incidental,
   not a documented product pattern and not a requirement to support
   ``StagePackageLibraries( env.Program( ... ) )`` as an API.
3. **Later default on ``env.Build()``** (with a disable flag) so ordinary tips
   “just work” with no sconscript change; Build calls the same helper as the
   standalone stage.
4. **Docker-friendly** collect into a chosen folder (always copy).
5. Keep **absolute dependency-cache RPATH** out of policy.
6. Keep existing construction-ENV injection for `--test` / `--run` / tools.

## Non-goals

- Replacing `apply_package_runtime_paths` for Cuppa-spawned processes.
- Vendoring system libs (`libssl`, `libstdc++`, …) into the stage set by
  default.
- A full product “deploy” (configs, images, systemd). Do **not** take the
  name ``Deploy`` for this slice — save it for a possible future broader
  verb.
- Changing how publishers install their own `bin/` → `lib/` RPATH.

## Settled direction

| Id | Approach | Role |
|----|----------|------|
| **A** | Link with `$ORIGIN` and/or `$ORIGIN/lib`; **`StagePackageLibraries`** **copies** the needed package shared libs beside the program (or under `./lib/`) | Canonical runnable tree |
| **B** | **`CollectPackageLibraries`** **copies** the same set into a chosen folder | Docker / assembly companion |
| **C** | Absolute `-Wl,-rpath,<deps>/…` | Out of policy |
| **D** | Generated wrapper / `.env` with `LD_LIBRARY_PATH` | Optional later; not the headline story |

### Naming

Use **`StagePackageLibraries`** / **`CollectPackageLibraries`**:

- Symmetric; clearly limited to package dynamic libraries.
- Avoids burning **`Deploy`** on a narrow staging step.

### Consumer API sketch

Standalone first; documented tip shape uses ``env.Build``:

```python
prog = env.Build( 'widget_server', sources )
env.StagePackageLibraries( prog )   # copy package .so next to prog / under lib/
# ensure RPATH includes $ORIGIN / $ORIGIN/lib (method or Build default later)

# Docker / explicit assembly (always copy)
env.CollectPackageLibraries(
        '_artifacts/runtime-libs',
        programs=[ prog ],
)
```

``StagePackageLibraries`` takes program node(s) (or a list). It keys off
Cuppa package link contributions on the env / executor, not on a Build-only
wrapper type — so a ``Program`` node *can* work if those contributions are
present, without designing the API around ``Program``.

### Default on ``env.Build()`` (second slice)

After the standalone methods soak:

- When ``env.Build`` produces a **program** whose link contribution includes
  **shared** Cuppa package libs, automatically stage those libs (same helper
  as ``StagePackageLibraries``) and ensure `$ORIGIN` / `$ORIGIN/lib` RPATH.
- Provide a **disable** flag (Build kwarg and/or cuppa option) for odd layouts
  and bisect.
- Do **not** auto-stage for static-only links, library targets, or every
  intermediate object compile — only the program node (typically under
  `final/`).

Implementation order: **standalone methods → default inside Build**.

### Computing the library set

Closure of **package shared** artefacts the program needs:

1. Cuppa package link contributions for this env / program (`use_libs` /
   defaults / transitive edge `use_libs`).
2. Resolve to shared files under each package `lib/` (soname + real file).
3. Optionally refine with ELF `NEEDED` (and Darwin/Windows equivalents).
4. Recurse traveling package dependencies (same shape as link / pkg-config
   search).

Do **not** stage the entire package `lib/` tree unless asked (`all=True`).
Do **not** include system libs by default.

### Copy, not symlink (default)

Package roots move between **develop**, **publisher-root** stages, and
**download/dependencies** extracts. Symlinks from `_build/…/final/` into
whichever tree was current go stale or point at the wrong tree after
`--develop`, cascade restage, or refresh, while RPATH still says `$ORIGIN`.

- **`StagePackageLibraries`:** **copy** by default (and for the Build
  default).
- **`CollectPackageLibraries`:** **copy** always.
- Symlink only as a possible later opt-in for tight local loops, with clear
  invalidation rules — not the product default.

### Platforms

Reuse the platform split in `runtime_paths.py`:

- Linux: `$ORIGIN`, `DT_NEEDED`, `.so*`
- Darwin: `@loader_path`, dylibs
- Windows: side-by-side DLLs beside the exe (no RPATH); stage copies DLLs

## Open questions

1. Exact RPATH API: always set inside ``StagePackageLibraries``, or split
   “add rpath” vs “copy libs”?
2. Should ``CollectPackageLibraries`` also accept package names
   (`['widget_core']`) as well as program nodes?
3. Layout default for Stage: libs **beside** the binary vs under ``lib/``
   next to it (`$ORIGIN` vs `$ORIGIN/lib`)?
4. Cleaning: staged copies under `final/` must be `Clean`ed / removal-options
   aware.
5. Disable flag spelling for Build default (`stage_package_libraries=False`
   vs cuppa option).

## Implementation sketch

1. Plan + ROADMAP (this document).
2. Helper: list package shared files for a program / env.
3. ``StagePackageLibraries`` + ``CollectPackageLibraries`` (copy; unit tests;
   like-example fixtures only).
4. Soak with an explicit ``StagePackageLibraries`` call on a tip that links a
   shared multi-lib stack; run from a clean env without `LD_LIBRARY_PATH`.
5. Wire the same helper as the default step inside ``env.Build`` + disable
   flag; Antora + CHANGELOG.
6. Optional: Collect into an image and run the entrypoint without host
   `LD_LIBRARY_PATH`.

## Risks

| Risk | Mitigation |
|------|------------|
| Staging too many libs | Closure from link contributions + optional NEEDED filter |
| Stale symlinks after develop / refresh | Copy by default for Stage and Collect |
| ``Deploy`` name collision / overreach | Use Stage/Collect PackageLibraries |
| Default Build surprises | Disable flag; narrow to programs with shared package links |
| Windows differs | Side-by-side DLL copy; document `--run` PATH inheritance |
| Duplicate RPATH noise | Dedupe; never add absolute cache paths |

## Progress snapshot

| Item | State |
|------|--------|
| Problem / Stage+Collect direction | Written (proposal) |
| Standalone methods | Not started |
| Default on ``env.Build`` | Not started (after standalone) |
| Antora / CHANGELOG | Not started |
