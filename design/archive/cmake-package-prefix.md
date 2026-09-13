# CMake package prefixes and publisher API ergonomics

- **Status:** shipped
- **Related:** [`ROADMAP.md`](../../ROADMAP.md) — 1.11.0; [`cmake-drive-and-package-staging.md`](../plans/cmake-drive-and-package-staging.md); [`package-runtime-paths.md`](package-runtime-paths.md); [`download-extract.md`](download-extract.md); transitive manifests [`../plans/gitlab-package-transitive.md`](../plans/gitlab-package-transitive.md); run object lists [`../plans/run-default-dependency-objects.md`](../plans/run-default-dependency-objects.md)
- **Updated:** 2026-09-14
- **Impact:** `minor`

## Problem

Publisher sconscripts still hand-wired BuildWith package dirs, tool paths, concrete
manifest versions, and local Ninja discovery:

```python
protobuf = env.BuildWith( 'protobuf' )
protobuf_dep = protobuf.package()
protobuf_package_dir = protobuf_dep.package_dir()
protobuf_version = protobuf_dep.version()
cmake_prefix = cmake_prefix_path( otel_dir, grpc_dir, protobuf_dir )
protoc = os.path.join( protobuf_package_dir, 'bin', 'protoc' )
cmake_generator = 'Ninja' if shutil.which( 'ninja' ) else None
```

Runtime ENV and includes already came from `BuildWith` / auto-enable. The remaining
ceremony was **CMake prefix / tool paths**, **manifest pins**, and **generator discovery**.

## Settled decisions

| Topic | Decision |
|-------|----------|
| Lookup | Resolve via `env.BuildWith(name)` (cached). Accept name string or dependency object (`name()`). |
| Methods | `env.PackageDir` / `PackageBin` / `PackageLib` / `PackageVersion` / `CMakePrefixPathFor`. Free functions kept under `cuppa.package_managers.package_paths` / `cmake_prefix_path_for` for unit tests. |
| Name ↔ slug | Prefer convention **(b)**: `name` only → `package = name.replace('_','-')`; `package` only → reverse; both → as-is; bare string = Cuppa **name**. Escape hatch: pass both when the slug is not that transform (e.g. Boost). Do not force name == slug **(a)** — fights GitLab hyphens and snake_case Python ids. |
| Manifest | Omit `version` (fill from BuildWith at publish); omit/`''` registry → `same`; bare strings / mixed lists. Manifest still stores concrete `name` + `package` after normalisation. |
| Indent | 4-space semantic indents for dicts/lists; deeper only for line continuations. |
| Generator | `generator=None` → Ninja if `ninja` on PATH; `False` → omit `-G`; string → exact. Shared by Option B argv helpers and `env.CMakeConfigure`. |
| `cuppa.run` objects | Already shipped (`run_list_names` / preferred `import_dependencies` / `auto_enable_dependencies`). Not re-implemented here. |
| Refuse | Auto-injecting `CMAKE_PREFIX_PATH` into every `CMakeConfigure` without asking (order-sensitive / too magical). |

### Name ↔ slug rationale

Clearpool groups/repos/variables use snake_case; GitLab package slugs often use hyphens
(`opentelemetry_cpp` / `opentelemetry-cpp`). Deriving the missing field keeps publisher
`dependencies=['opentelemetry_cpp']` honest without inventing a second vocabulary where
`package=` means BuildWith name.

### Generator flow

```mermaid
flowchart TD
  call["env.CMakeConfigure(...)"]
  gen{"generator arg"}
  call --> gen
  gen -->|"string"| exact["-G that string"]
  gen -->|"False"| omit["no -G"]
  gen -->|"None / omitted"| auto{"ninja on PATH?"}
  auto -->|yes| ninja["-G Ninja"]
  auto -->|no| omit
```

## Shipped shape

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

Private adopt: protobuf, gRPC, OpenTelemetry C++, and google-cloud-cpp
publishers (4-space indent; no local `which('ninja')`; bare dep names / objects
where applicable).

## Progress snapshot

| Item | State |
|------|--------|
| Paths + version fill (free functions) | Done |
| Methods + name/object resolve | Done |
| Name ↔ slug + bare-string deps | Done |
| Default Ninja generator | Done |
| Unit tests / Antora / CHANGELOG | Done |
| Private adopt (protobuf, gRPC, OTel, google-cloud-cpp) | Done |

## Out of scope / follow-ons (not blocking this plan)

- Pushing / updating Cuppa PR [#294](https://github.com/ja11sop/cuppa/pull/294) with the post-Option-C soak commits.
- Packaging remaining google-cloud-cpp / gRPC **system** deps as Cuppa packages for a full controlled soak (Abseil, c-ares, RE2, …) — see soak notes below / cmake-drive plan.
- Further cmake-drive items (archive progress, #209 in-place packaging, publish-side CLI pins) remain on [`cmake-drive-and-package-staging.md`](../plans/cmake-drive-and-package-staging.md).

## Full soak — remaining cloud-cpp host deps (candidate packages)

Today still taken from the host (see google-cloud-cpp publisher README). Candidates to promote to Cuppa packages when doing a full soak (version-matched, `CMAKE_PREFIX_PATH` instead of apt):

| Likely Cuppa package | Why package | Often leave as system |
|----------------------|-------------|------------------------|
| `abseil_cpp` / abseil-cpp | Shared by protobuf, gRPC, cloud-cpp; Sid vs pin drift | — |
| `c_ares` / c-ares | gRPC / cloud-cpp `*_PROVIDER=package` | — |
| `re2` | gRPC / cloud-cpp | — |
| `crc32c` | cloud-cpp common | — |
| `nlohmann_json` | cloud-cpp | — |
| — | — | OpenSSL, zlib, curl, nghttp2, systemd |

Order matters: Abseil before protobuf; c-ares / RE2 before gRPC; then OTel; then cloud-cpp.
