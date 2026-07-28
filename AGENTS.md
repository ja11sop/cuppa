---
name: Cuppa build system
description: Guidance for AI agents working on the cuppa repository or using cuppa in consumer projects
---

# Cuppa — agent notes

Cuppa is a SCons extension for C++ builds. This repository is the **cuppa package itself**. Consumer projects call `import cuppa` / `cuppa.run()` from their own `sconstruct`.

## Preferred invocation

```sh
cuppa -D --dbg
cuppa -D --dbg --test --show-test-output
cuppa -D --rel
cuppa -D --cov --test
cuppa -D --toolchains=gcc,clang
cuppa -D --scripts=path/to/sconscript
```

`cuppa` wraps `scons`, appends `--cuppa-mode`, masks `*TOKEN*` env values in output, and may restrict CPU affinity with `--parallel`.

Equivalent: `scons -D …` when the project's `sconstruct` already imports cuppa.

**Important:** standalone `cuppa --help` shows SCons help only. Cuppa options are SCons `AddOption` flags registered when `cuppa.run()` runs. Inspect options from a real project, or read `docs/modules/ROOT/pages/cli-reference.adoc` / [CLI reference](https://ja11sop.github.io/cuppa/cuppa/cli-reference.html).

## Defaults (do not invent older paths)

| Purpose | Default |
|---------|---------|
| Build root | `_build` |
| Download root | `_cuppa` |
| Cache root | `~/_cuppa/_cache` |
| Project conf | `configure.conf` |
| Global conf | `~/.cuppaconfig` |

## Flags agents should default to

- `--offline` — after the first fetch in a session; skips PyPI version check and remote location updates
- `--develop` — when using configured local develop paths for location/package deps
- `--parallel` — for compile-only speed; avoid when diagnosing failures or often when running tests/coverage
- `--verbosity=exception` or `--verbosity=debug` — when configure/sconscript load fails

**Coverage:** always pass both `--cov` and `--test`. `--cov` alone does not run tests.

## Where to change behaviour in this repo

| Area | Path |
|------|------|
| Public API | `cuppa/__init__.py` (`run`, `location_dependency`, `package_dependency`, `profile`) |
| Orchestration | `cuppa/construct.py` |
| CLI options | `cuppa/core/base_options.py`, `storage_options.py`, `location_options.py`, `cuppa/configure.py` |
| Methods | `cuppa/methods/` |
| Variants / actions | `cuppa/variants/` |
| Toolchains | `cuppa/toolchains/` (`gcc.py`, `clang.py`, `cl.py` — MSVC/`vc` on Windows; coverage is GCC/Clang only) |
| Dependencies | `cuppa/dependencies/`, `cuppa/build_with_location.py` |
| Packages | `cuppa/build_with_package.py`, `cuppa/package_managers/`, `cuppa/packages/` |
| Coverage | `cuppa/cpp/run_gcov_coverage.py`, `cuppa/methods/coverage.py` |
| C++ modules | `cuppa/cpp/module_scanner.py`, `cuppa/cpp/cxx_modules.py`, `cuppa/methods/modules.py`, `cuppa/methods/header_unit.py`, toolchain helpers in `gcc.py` / `clang.py` |
| Console entry | `cuppa/__main__.py` |

Module auto-registration: `cuppa/modules/registration.py` loads classes exposing `add_options` / `add_to_env` under methods, dependencies, profiles, variants, toolchains, project_generators.

Plugins (setuptools): `cuppa.method.plugins`, `cuppa.profile.plugins`, `cuppa.dependency.plugins`.

## Validating changes to cuppa

```sh
flake8 cuppa
pylint -E cuppa
pytest -m unit
pytest -m integration   # requires a C++ compiler (g++ preferred)
# Optionally force the toolchain used by integration helpers:
# CUPPA_TEST_TOOLCHAIN=clang pytest -m integration
# CUPPA_TEST_TOOLCHAIN=vc pytest -m integration   # Windows + MSVC
```

Unit tests under `tests/unit/` cover foundations (`location`, `build_with_*`, `configure`, `registration`, construct helpers, `CuppaEnvironment`) with mocked SCons/filesystem — no compiler or network. Prefer adding unit cases there for parsing, precedence, and edge cases before new integration scenarios.

Lint config: [`.flake8`](.flake8) and [`.pylintrc`](.pylintrc). Full settings and rationale for contributors/agents: [`docs/modules/ROOT/pages/linting.adoc`](docs/modules/ROOT/pages/linting.adoc). Keep the gate error-focused — do not broaden to style warnings without intent.

CI runs the integration suite once per Linux toolchain (`gcc`, `clang`) via `CUPPA_TEST_TOOLCHAIN`, and once on `windows-latest` with MSVC (`vc`).

Integration scenarios (with generated `sconstruct` / `sconscript` and expectations) are documented on the Antora site under **Integration tests** (`docs/modules/ROOT/pages/integration-tests.adoc` and `docs/modules/ROOT/pages/integration/`).

Smoke-test with the minimal example (from repo root, with cuppa importable — e.g. `pip install -e .` or `PYTHONPATH=.`):

```sh
cd examples/minimal
cuppa -D --dbg --test
```

Release checklist: see `release.txt` (`sdist` / `bdist_wheel` / `twine`).

## Documentation

- Human landing: `README.md`
- Canonical reference: Antora under `docs/` → https://ja11sop.github.io/cuppa/
- Further reading (talks / Clearpool posts): `docs/modules/ROOT/pages/index.adoc` (Further reading) and https://clearpool.io/tag/cuppa
- Lint settings / ignore rationale: `docs/modules/ROOT/pages/linting.adoc`
- Preview docs: `cd docs && npm ci && npm run build` → `_docs_build/site/` (Lunr search via `@antora/lunr-extension`)
- Integration test scenarios: Antora **Integration tests** section (`docs/modules/ROOT/pages/integration/`)

When docs and code disagree, **code is authoritative** (especially storage defaults, toolchain version lists, and whether `--cov` implies `--test`).

## Consumer-project tips

In a project that *uses* cuppa (not this repo):

```sh
cuppa -D --dbg --develop --offline --test
cuppa -D --cov --test --toolchains=gcc
```

Package registry dependencies need matching toolchain archives in the registry (or cache); `--develop` does not invent them.
GitLab auth: `GITLAB_REGISTRY_TOKEN` or `CI_JOB_TOKEN`.
