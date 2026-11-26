# Note: stage shared package libs so consumer binaries run outside Cuppa ENV

- **Status:** proposal
- **Related:** [`archive/package-runtime-paths.md`](../archive/package-runtime-paths.md)
  (construction `ENV` + publisher `$ORIGIN/../lib`; absolute cache RPATH out of
  policy); [`pkgconfig-dependency-search-path.md`](pkgconfig-dependency-search-path.md)
  (link/Requires closure); `cuppa/package_managers/runtime_paths.py`;
  Antora Using GitLab packages; ROADMAP `package-runtime-deploy`
- **Updated:** 2026-11-26
- **Impact:** likely `minor` (new `Deploy` / collect API and optional default
  RPATH behaviour); could be `patch` if everything is opt-in methods only

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
       └── loader: cannot find libgrpc.so.56
```

## Goals

1. **Canonical approach** so a tip that links shared Cuppa package libs can
   run (and be copied into an image) with one or two small sconscript changes —
   not hand-maintained `LD_LIBRARY_PATH` to extract finals.
2. **Default “build so it can run”** path for ordinary programs when that is
   safe, without forcing every Install/copy in the graph to duplicate libs.
3. **Docker-friendly** layout: a directory tree (or flat lib folder) that can
   be `COPY`’d and either uses `$ORIGIN` or a single, intentional loader path.
4. Keep **absolute dependency-cache RPATH** out of policy.
5. Keep existing construction-ENV injection for `--test` / `--run` / tools.

## Non-goals

- Replacing `apply_package_runtime_paths` for Cuppa-spawned processes.
- Vendoring system libs (`libssl`, `libstdc++`, …) into the stage set by
  default.
- A full distro packaging / FHS product (deb/rpm); staging is enough.
- Changing how publishers install their own `bin/` → `lib/` RPATH.

## Settled direction (proposal)

Treat **A + B** as the product pair; **C/D** stay workarounds or non-goals.

| Id | Approach | Role |
|----|----------|------|
| **A** | Link with `$ORIGIN` and/or `$ORIGIN/lib`; **Deploy** copies or symlinks the needed package `.so` set beside the program (or under `./lib/`) | Canonical local + image-relocatable run |
| **B** | **CollectRuntimeLibraries** (name TBD) gathers the same set into a chosen folder for Docker layers / `ldconfig` | Assembly companion when the image layout is not “bin + sibling lib” |
| **C** | Absolute `-Wl,-rpath,<deps>/…` | Out of policy |
| **D** | Generated wrapper / `.env` with `LD_LIBRARY_PATH` | Optional later; not the headline story |

### Consumer API sketch

```python
prog = env.Program( 'widget_server', sources )
# Opt-in stage (first slice — safest):
env.Deploy( prog )   # or env.DeployRuntime( prog, layout='beside'|'lib' )

# Docker / explicit assembly:
env.CollectRuntimeLibraries(
        '_artifacts/runtime-libs',
        programs=[ prog ],   # or infer from package link contributions
)
```

Exact method names TBD (`Deploy` may collide with mental model of “install to
prefix”; prefer a Cuppa-specific name if SCons/docs noise is high).

### Default behaviour (second slice or flag)

When a consumer program’s link contribution includes **shared** Cuppa package
libs:

- add `$ORIGIN` / `$ORIGIN/lib` to RPATH if not already present, and/or
- auto-Deploy into the program’s final directory.

Make the default **narrow** (programs in `final/`, not every intermediate
`.o` link) so build trees do not explode. First implementation may be
**opt-in only**; document the one-liner as the supported fix.

### Computing the library set

Prefer a **closure of shared artefacts the program actually needs**:

1. Start from Cuppa package link contributions recorded for this env /
   program (stems from `use_libs` / defaults / transitive edge `use_libs`).
2. Resolve to shared files under each package `lib/` (soname + real file).
3. Optionally refine with ELF `NEEDED` (and Darwin/Windows equivalents) so
   unused stems are not copied.
4. Recurse package dependencies the same way link and pkg-config search
   already walk the traveling manifest (grpc → abseil / protobuf / …).

Do **not** stage the entire package `lib/` tree unless the author asks
(`all=True` or similar).

### Copy vs symlink

- **Local Deploy:** symlink by default on POSIX (fast, updates with
  `--refresh-downloads`); copy when `copy=True` or when the filesystem
  cannot symlink.
- **Collect for Docker:** copy by default (portable layers).

### Platforms

Reuse the platform split in `runtime_paths.py`:

- Linux: `$ORIGIN`, `DT_NEEDED`, `.so*`
- Darwin: `@loader_path`, dylibs
- Windows: side-by-side DLLs / `PATH` beside the exe (no RPATH); Deploy
  copies DLLs next to the binary

## Open questions

1. Method naming: `Deploy` vs `DeployRuntime` vs `StagePackageLibraries`.
2. Default-on for `final/` programs in the first PR, or opt-in only until
   soaked?
3. Should Collect accept package names (`['grpc', 'protobuf']`) as well as
   program nodes?
4. Interaction with tips that already pass `-Wl,-rpath,.` — Deploy should
   make that sufficient; avoid stacking absolute paths.
5. Cleaning: staged libs under `final/` must be `Clean`ed / removal-options
   aware.

## Implementation sketch

1. Plan + ROADMAP row; Antora note under Using GitLab packages (runtime
   outside Cuppa).
2. Helper: given env + program (or package names), list shared files to stage.
3. `CollectRuntimeLibraries` → directory of files (unit-tested).
4. `DeployRuntime` → beside program / `lib/` + ensure RPATH `$ORIGIN` /
   `$ORIGIN/lib` on that program’s link.
5. Optional default for final programs once soak is green.
6. Tests with like-example fixtures (`widget`, fake `.so` names); no private
   host or package paste.
7. Soak: tip binary that links a shared multi-lib stack; run from a clean
   env without `LD_LIBRARY_PATH`; copy `final/` into a minimal container and
   run the entrypoint.

## Risks

| Risk | Mitigation |
|------|------------|
| Staging too many libs | Closure from link contributions + optional NEEDED filter |
| Symlinks break in images | Collect copies; Deploy `copy=True` for release layouts |
| Duplicate RPATH noise | Dedupe; don’t add absolute cache paths |
| Windows differs | Side-by-side DLL Deploy; document PATH inheritance for `--run` |
| Name clash with “deploy” | Prefer Cuppa-specific method name if confusing |

## Progress snapshot

| Item | State |
|------|--------|
| Problem / A+B direction | Written (proposal) |
| Implementation | Not started |
| Antora / CHANGELOG | Not started |
