# CMake package prefixes from BuildWith (publisher ergonomics)

- **Status:** in progress
- **Related:** [`ROADMAP.md`](../../ROADMAP.md) — 1.11.0; [`cmake-drive-and-package-staging.md`](cmake-drive-and-package-staging.md); [`archive/package-runtime-paths.md`](../archive/package-runtime-paths.md); [`archive/download-extract.md`](../archive/download-extract.md); transitive manifests [`gitlab-package-transitive.md`](gitlab-package-transitive.md); run object lists [`run-default-dependency-objects.md`](run-default-dependency-objects.md)
- **Updated:** 2026-09-13
- **Impact:** `minor`

## Problem

Publisher sconscripts still hand-wire BuildWith package dirs, tool paths, concrete
manifest versions, and local Ninja discovery.

## Settled decisions

| Topic | Decision |
|-------|----------|
| Lookup | Resolve via `env.BuildWith(name)` (cached). Accept name string or dependency object (`name()`). |
| Methods | `env.PackageDir` / `PackageBin` / `PackageLib` / `PackageVersion` / `CMakePrefixPathFor`. Free functions kept for tests. |
| Name ↔ slug | `name` only → `package = name.replace('_','-')`; `package` only → reverse; both → as-is; bare string = name. Escape hatch: pass both when convention does not hold. |
| Manifest | Omit `version` (fill from BuildWith); omit/`''` registry → `same`; bare strings / mixed lists. |
| Generator | `generator=None` → Ninja if `ninja` on PATH; `False` → omit `-G`; string → exact. |
| Refuse | Auto-injecting `CMAKE_PREFIX_PATH` into every `CMakeConfigure` without asking. |

## Target publisher shape

```python
publisher = GitlabPackagePublisher(
    env, …,
    dependencies = [
        'protobuf',
        'grpc',
        'opentelemetry_cpp',
    ],
)

cmake_out = env.CMakeConfigure(
    extracted_release,
    working_dir = extraction_folder,
    source_dir = '.',
    build_dir = build_output,
    install_prefix = str( install_location ),
    c_compiler = True,
    cxx_standard = False,
    extra_defines = {
        'CMAKE_PREFIX_PATH': env.CMakePrefixPathFor(
            'opentelemetry_cpp', 'grpc', 'protobuf',
        ),
        'Protobuf_PROTOC_EXECUTABLE': env.PackageBin( 'protobuf', 'protoc' ),
        'GOOGLE_CLOUD_CPP_GRPC_PLUGIN_EXECUTABLE': env.PackageBin(
            'grpc', 'grpc_cpp_plugin',
        ),
        # …
    },
)
```

## Progress snapshot

| Item | State |
|------|--------|
| Paths + version fill (free functions) | Done |
| Methods + name/object resolve | Done |
| Name ↔ slug + bare-string deps | Done |
| Default Ninja generator | Done |
| Unit tests / Antora / CHANGELOG | Done |
| Private adopt (gRPC + google-cloud-cpp) | Done |
