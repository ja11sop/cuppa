# Note: stage shared package libs so consumer binaries run outside Cuppa ENV

- **Status:** done
- **Related:** [`archive/package-runtime-paths.md`](../archive/package-runtime-paths.md)
  (construction `ENV` + publisher `$ORIGIN/../lib`; absolute cache RPATH out of
  policy); [`pkgconfig-dependency-search-path.md`](pkgconfig-dependency-search-path.md)
  (link/Requires closure); `cuppa/package_managers/runtime_paths.py`;
  Antora Using GitLab packages; ROADMAP `package-runtime-deploy`;
  [#413](https://github.com/ja11sop/cuppa/pull/413)
- **Updated:** 2026-11-27
- **Impact:** `minor` (`StagePackageLibraries` / `CollectPackageLibraries` +
  default-on inside `env.Build` with disable flag) — shipped on master in #413

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
2. **Standalone methods** aimed at tip programs from ``env.Build()``.
   Implementation accepts ordinary program nodes (not Build-only wrappers). A
   node from ``env.Program()`` may work the same way if Cuppa package link
   contributions are already on the env — that is incidental, not a documented
   product pattern.
3. **Default on ``env.Build()``** (with a disable flag) in the **same** PR so
   ordinary tips “just work” with no sconscript change; Build calls the same
   helper as the standalone stage.
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
- Auto-stage for ``BuildTest`` / ``BuildBenchmark`` (Cuppa ENV covers
  ``--test``); revisit if detached test binaries become a product need.
- Staging shared libs linked only via pkg-config ``ParseConfig`` (no stem
  contribution recorded) — follow-on if soak shows a gap.

## Settled direction

| Id | Approach | Role |
|----|----------|------|
| **A** | Link with `$ORIGIN` / `$ORIGIN/lib` (Darwin `@loader_path`); **`StagePackageLibraries`** **copies** package shared libs under sibling ``lib/`` (Windows: beside the exe) | Canonical runnable tree |
| **B** | **`CollectPackageLibraries`** **copies** the same set into a chosen folder | Docker / assembly companion |
| **C** | Absolute `-Wl,-rpath,<deps>/…` | Out of policy |
| **D** | Generated wrapper / `.env` with `LD_LIBRARY_PATH` | Optional later; not the headline story |

### Naming

Use **`StagePackageLibraries`** / **`CollectPackageLibraries`**:

- Symmetric; clearly limited to package dynamic libraries.
- Avoids burning **`Deploy`** on a narrow staging step.

### Consumer API sketch

```python
prog = env.Build( 'widget_server', sources )
# default: stages package .so under final/…/lib/ + ORIGIN rpath
# disable: env.Build( ..., stage_package_libraries=False )

# Explicit (same helper Build uses):
env.StagePackageLibraries( prog )

# Docker / explicit assembly (always copy)
env.CollectPackageLibraries(
        '#/_artifacts/runtime-libs',
        programs=[ prog ],
)
```

### Default on ``env.Build()``

- When ``env.Build`` produces a program and the env has **shared** Cuppa
  package link contributions, automatically stage those libs and ensure
  `$ORIGIN` / `$ORIGIN/lib` (or Darwin `@loader_path`) RPATH.
- Disable: ``stage_package_libraries=False`` on ``Build``, or set
  ``env['stage_package_libraries'] = False``.
- No-op when there are no shared package contributions (static-only /
  headers-only).

### First-slice defaults (locked)

| Topic | Choice |
|-------|--------|
| Stage layout | Sibling ``lib/`` next to the program (`$ORIGIN/lib`); Windows DLLs beside the exe |
| RPATH | Always ensure `$ORIGIN` + `$ORIGIN/lib` (Darwin `@loader_path`) inside Stage and Build default; dedupe; never absolute cache paths |
| Library set | Package link contributions (`shared` + `libpath` + `library_prefix`); all soname/realpath files matching each stem; no `NEEDED` walk yet; no `all=True` yet |
| Copy vs symlink | **Copy** always |
| Clean | Staged Install nodes are ``Clean``ed against the program |
| Collect inputs | Destination dir + optional ``programs`` (for Depends); library set from env contributions (same as Stage) |

### Computing the library set

1. Cuppa package link contributions for this env (`use_libs` / defaults /
   transitive edge `use_libs`).
2. Resolve to shared files under each package `lib/` (unversioned + versioned
   soname files for each stem).
3. Optional later: ELF `NEEDED` refine; `all=True` whole `lib/` tree.

Do **not** include system libs by default.

## Platforms

Reuse the platform split in `runtime_paths.py`:

- Linux: `$ORIGIN`, `.so*`
- Darwin: `@loader_path`, dylibs
- Windows: side-by-side DLLs beside the exe (no RPATH)

## Implementation sketch

1. Plan + ROADMAP (this document).
2. Helper: list package shared files for an env; ORIGIN rpath flags; stage/collect Install.
3. ``StagePackageLibraries`` + ``CollectPackageLibraries`` (copy; unit tests).
4. Wire the same helper as the default step inside ``env.Build`` + disable flag.
5. Antora + CHANGELOG.
6. Soak: tip binary from clean env without `LD_LIBRARY_PATH`; optional Collect into an image.

## Risks

| Risk | Mitigation |
|------|------------|
| Staging too many libs | Closure from link contributions only |
| Stale symlinks after develop / refresh | Copy by default |
| ``Deploy`` name collision / overreach | Use Stage/Collect PackageLibraries |
| Default Build surprises | Disable flag; no-op when no shared package libs |
| Windows differs | Side-by-side DLL copy; document `--run` PATH inheritance |
| Duplicate RPATH noise | Dedupe; never add absolute cache paths |
| pkg-config-only shared link | Documented non-goal; follow-on if needed |

## Progress snapshot

| Item | State |
|------|--------|
| Problem / Stage+Collect direction | Written |
| First-slice defaults locked | Written |
| Helper + standalone methods | Done (#413) |
| Default on ``env.Build`` | Done (#413) |
| Antora / CHANGELOG | Done (#413) |
| Tip soak without ``LD_LIBRARY_PATH`` | Done (local + integration ``test_build_stage_package_libraries``) |
| Build RPATH scoped to program node | Done (no shared-env ``AppendUnique`` bleed) |
