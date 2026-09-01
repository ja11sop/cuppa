# Cuppa

[![Latest Version](https://img.shields.io/pypi/v/cuppa.svg)](https://pypi.org/project/cuppa/) [![Documentation](https://github.com/ja11sop/cuppa/actions/workflows/docs.yml/badge.svg)](https://ja11sop.github.io/cuppa/) [![Boost License](https://img.shields.io/badge/license-Boost-blue.svg)](https://www.boost.org/LICENSE_1_0.txt)

**Cuppa** is an extensible C++ build system on top of [SCons](https://www.scons.org/). It keeps `sconscript` files declarative while handling toolchains, variants, dependencies, tests, and coverage. From a project tree you typically run:

```sh
cuppa -D
```

and cuppa builds the relevant `sconscript` files (the `-D` SCons flag finds the `sconstruct` and runs scripts relative to your starting directory).

Full reference documentation: **[https://ja11sop.github.io/cuppa/](https://ja11sop.github.io/cuppa/)** (Antora site in [`docs/`](docs/)). Contributing to cuppa itself (versioning, releases): [Contributing](https://ja11sop.github.io/cuppa/cuppa/contributing.html). Agent-oriented guidance: [`AGENTS.md`](AGENTS.md). Feature roadmap: [`ROADMAP.md`](ROADMAP.md). Release notes: [`CHANGELOG.md`](CHANGELOG.md). Design notes and plans: [`design/`](design/).

## Features

- Make-like CLI via `cuppa` or `scons` with cuppa loaded in the `sconstruct`
- Multi-variant builds: debug (`--dbg`), release (`--rel`), coverage (`--cov`, GCC/Clang)
- Multi-toolchain: GCC, Clang, and MSVC (`vc` on Windows), with wildcards (`--toolchains=gcc*,clang21`)
- Out-of-tree builds under `_build/`, with dependencies and downloads shared under `~/.cuppa/`
- Dependencies: Boost, Qt4/Qt5, Quince, location-based libraries, GitLab package registry
- Test runners and HTML coverage (gcovr), plus optional HTML test reports
- Optional C++20 modules (`--modules`): named modules, partitions, header units, `import std` where supported
- Persistent config: `configure.conf` and `~/.cuppaconfig`

## Installation

```sh
pip install cuppa
```

The `cuppa` console script wraps `scons`: it appends `--cuppa-mode`, intercepts stdout/stderr to mask environment values whose names contain `TOKEN`, and may adjust CPU affinity when `--parallel` is used. Prefer `cuppa` over bare `scons` in CI.

Other install options (local `pip install cuppa -t .`, `site_scons`, bootstrap from `sconstruct`) are covered in the [install guide](https://ja11sop.github.io/cuppa/cuppa/install.html).

## Quickstart

**`sconstruct`:**

```python
import cuppa

cuppa.run()
```

**`sconscript`:**

```python
Import('env')

for source in env.GlobFiles('*.cpp'):
    env.Build(str(source)[:-4], source)
```

Build:

```sh
cuppa -D
cuppa -D --dbg
cuppa -D --rel
```

Treat sources as tests and run them:

```python
Import('env')

for source in env.GlobFiles('*.cpp'):
    env.BuildTest(str(source)[:-4], source)
```

```sh
cuppa -D --dbg --test --show-test-output
```

A self-contained smoke project lives in [`examples/minimal/`](examples/minimal/).

### Default dependencies

```python
import cuppa

cuppa.run(
    default_options = {
        'boost-location': '/path/to/boost',
    },
    default_dependencies = [
        'boost',
    ],
)
```

```python
Import('env')

env.AppendUnique(STATICLIBS=env.BoostStaticLibs(['system', 'filesystem']))
env.BuildTest('my_test', 'my_test.cpp')
```

## Everyday CLI

| Flag | Purpose |
|------|---------|
| `-D` | SCons: find `sconstruct` upward; run scripts from cwd |
| `--dbg` / `--rel` / `--cov` | Build variants |
| `--test` / `--force-test` | Run `BuildTest` / `Test` targets |
| `--toolchains=LIST` | Toolchains (comma-separated; wildcards allowed) |
| `--scripts=LIST` | Limit which sconscripts run |
| `--parallel` | Parallel compile (`-j` sized to the machine) |
| `--offline` | Skip PyPI version check and remote repo updates |
| `--develop` | Prefer configured develop locations / package develop paths |
| `--show-test-output` | Print test process output |
| `--verbosity=exception` | Full stack traces on failure |
| `--save-conf` / `--show-conf` | Persist or inspect project `configure.conf` |

**Coverage needs both flags:** `--cov` does not imply `--test`. Typical coverage run:

```sh
cuppa -D --cov --test
```

Benchmarks and generic runners: `--benchmark`, `--run` (and `--force-*` variants).

See the [CLI reference](https://ja11sop.github.io/cuppa/cuppa/cli-reference.html) for the full option list (storage, location matching, Boost, GitLab packages, Code::Blocks export, and more).

## Build layout

| Purpose | Default | Override |
|---------|---------|----------|
| Build output | `_build` | `--build-root` |
| Dependency trees | `~/.cuppa/dependencies` | `--dependencies-root` |
| Downloaded archives | `~/.cuppa/downloads` | `--downloads-root` |

The last two are shared between projects. `--storage-root` moves both together, so
`--storage-root=_cuppa` keeps all storage inside the project.

Layout under the build root:

```text
<build_root>/<sconscript_path>/<toolchain>/<variant>/<target_arch>/<abi>/working/
<build_root>/<sconscript_path>/<toolchain>/<variant>/<target_arch>/<abi>/final/
```

If the script file is named `sconscript`, that filename segment is omitted.

## Concepts

| Term | Meaning |
|------|---------|
| **Methods** | Env helpers such as `Build`, `BuildTest`, `BuildWith`, `Coverage` — variant- and toolchain-aware |
| **Dependencies** | Named compile/link (and optional fetch) packages: Boost, Qt, locations, registry packages |
| **Profiles** | Small reusable env tweaks (example: `quad_float`) |
| **Variants / actions** | How to compile (`dbg`/`rel`/`cov`) vs extra work (`test`/`benchmark`/`run`) |
| **Toolchains** | Concrete compilers discovered at configure time (`gcc`, `gcc15`, `clang`, `clang21`, …) |

Toolchains are discovered from the machine; supported aliases currently extend through **gcc16** (including `gcc162`) and **clang22**, plus MSVC `vc` / `vc*` on Windows (coverage is GCC/Clang only). Details: [toolchains](https://ja11sop.github.io/cuppa/cuppa/toolchains.html).

## Configuration

Save local defaults:

```sh
cuppa -D --develop --offline --save-conf
```

- Project file: `configure.conf` (or `--use-conf=PATH`)
- Global file: `~/.cuppaconfig` (see `--save-global-conf` and related flags)

GitLab package auth typically uses `GITLAB_REGISTRY_TOKEN` or `CI_JOB_TOKEN`.

## Packages and locations

- **Location dependencies** — `cuppa.location_dependency(...)` for header-only or VCS/archive libraries
- **Registry packages** — `cuppa.package_dependency(...)` and `cuppa.packages.boost_package.define(...)` for prebuilt GitLab generic packages

`--develop` does not replace a missing registry archive; the package must exist remotely or already be cached.

## Documentation site

Canonical deep reference is the Antora site under [`docs/`](docs/), including the full
**[Integration tests](https://ja11sop.github.io/cuppa/cuppa/latest/integration-tests.html)**
section (generated `sconstruct` / `sconscript` for each pytest scenario). The public default
is the **latest release** (`/cuppa/latest/…`); unreleased tip docs are under `next`.
Agent-oriented Markdown index: [llms.txt](https://ja11sop.github.io/cuppa/llms.txt).

Preview the current checkout locally (includes Lunr full-text search):

```sh
cd docs
npm ci
npm run build
```

Build the multi-version public site (needs git tags; adds `llms.txt` with `build:site:all`,
which also requires `pandoc` and Python `lxml`):

```sh
cd docs
npm run build:site:all
```

Output is written to `_docs_build/site/`. Open `_docs_build/site/index.html`.

## Design principles

- Keep `sconscript` files declarative
- Encapsulate dependency and toolchain knowledge once, reuse everywhere
- Codify SCons best practices behind intent-oriented methods (`Build`, `BuildTest`, `BuildWith`)

## Further reading

Historical talks and write-ups (prefer this README / the [docs site](https://ja11sop.github.io/cuppa/) / the code when details disagree):

- [clearpool.io — posts tagged cuppa](https://clearpool.io/tag/cuppa)
- [Managing C++ Build Complexity using Cuppa](https://clearpool.io/pulse/posts/2016/May/06/managing-c-build-complexity-using-cuppa/) (ACCU 2016, *A Quick Cuppa*)
- [Modern C++ Builds and ACCU Autumn Preview](https://clearpool.io/pulse/posts/2019/Jul/25/modern-c-builds-and-accu-autumn-preview/) (*Another Quick Cuppa*)
- [C++20, Cuppa and the ¡Three Asios!](https://clearpool.io/pulse/posts/2019/Jul/30/c20-cuppa-and-the-three-asios/) (includes *Building Codes*; `SContext`-style bootstrapping described there is **not** upstream cuppa)

## License

[Boost Software License 1.0](LICENSE_1_0.txt)
