# Windows CI: run Conan 2 integration tests under MSVC

> Draft for a GitHub issue. Deferred on purpose after shipping Linux Conan consumer/publisher coverage (#29).

## Summary

Linux CI installs Conan 2 and runs `tests/integration/methods/test_conan.py` on the gcc/clang matrix.
Windows CI (`windows-latest`, `CUPPA_TEST_TOOLCHAIN=vc`) does **not** install Conan, so those scenarios **skip**.

This issue tracks enabling Conan integration on Windows with MSVC so consumer + publisher paths are exercised under `vc`, not only unit-tested settings mapping.

## Current state

| Area | Status |
|------|--------|
| Linux Conan integration | Done — `pip install 'conan>=2,<3'`, `conan profile detect --force`, full `test_conan` |
| MSVC → Conan settings | Done in unit tests (`compiler.runtime` / `runtime_type`, toolset → `compiler.version`) |
| Windows Conan CLI in CI | Not installed — tests skip via `_require_conan()` |
| Live remote upload | Still out of scope (all platforms) |

Relevant files:

- [`.github/workflows/test.yml`](.github/workflows/test.yml) — `integration-windows` job
- [`tests/integration/methods/test_conan.py`](tests/integration/methods/test_conan.py)
- [`cuppa/build_with_conan.py`](cuppa/build_with_conan.py) — settings + `tools.build:compiler_executables`
- Docs: [`docs/modules/ROOT/pages/integration/test-conan.adoc`](docs/modules/ROOT/pages/integration/test-conan.adoc) (Windows deferral note)

## Why it was deferred

1. **Profile / toolchain fidelity** — A cold Windows runner needs a maintainable Conan 2 + Visual Studio / MSVC profile so `--build=missing` (e.g. building `fmt`) works with Cuppa’s host `-s` overrides and compiler executables.
2. **Cost and flakes** — From-source Conan builds on `windows-latest` are slower and more brittle than Linux; shared-library runtime (`PATH`) adds another failure mode.
3. **Coverage already elsewhere** — Conan is optional; Linux already covers consumer install, generators_folder, publish export-pkg, shared publish, modules, and generated `requires=`.

## Goals

- Install Conan 2 on the Windows integration job (same idea as Linux: not a Cuppa runtime dependency).
- Ensure a default Conan profile exists (`conan profile detect` or an explicit MSVC profile).
- Run `test_conan` under `CUPPA_TEST_TOOLCHAIN=vc` without skips for “conan missing”.
- Fail clearly when MSVC/Conan settings mismatch (do not silent-skip once Conan is installed).

## Non-goals (for this issue)

- Making Conan mandatory for Cuppa on Windows.
- Live `--publish-package` upload to a real remote.
- macOS Conan matrix (separate decision if needed).
- Conan components / multi-lib (see [`CONAN_COMPONENTS_ISSUE.md`](CONAN_COMPONENTS_ISSUE.md)).

## Proposed work

### 1. CI wiring

In `integration-windows` (or a dedicated `integration-windows-conan` job):

```yaml
pip install 'conan>=2,<3'
conan version
conan profile detect --force   # or write an explicit MSVC profile
```

Decide whether Conan runs on the **existing** Windows job (longer wall clock) or a **separate** job so non-Conan Windows failures stay cheaper to triage.

### 2. Prove MSVC host settings + build of missing packages

Locally / in CI, with Cuppa’s mapped settings (and `tools.build:compiler_executables` if applicable for `cl`):

- Cold `conan install` of `fmt/12.1.0` (or current pin) with `--build=missing` under Debug + Cuppa’s `compiler=msvc` / runtime settings.
- Confirm CMake/Ninja (or whatever the fmt recipe uses) finds **MSVC**, not a stray MinGW/`g++` on `PATH`.

Document any required `tools.build:compiler_executables` / env (`VCINSTALLDIR`, developer command prompt) differences vs Linux clang/gcc.

### 3. Test suite behaviour on Windows

- Keep `_require_conan()` skip only when Conan is absent (local dev without Conan).
- Once CI installs Conan: publish / shared / modules scenarios should run or **fail** for real MSVC gaps — not skip.
- Modules publish tests may still skip without a modules-capable MSVC toolchain; that is fine if the skip reason stays accurate.
- Prefer per-test `--download-root=` + isolated `CONAN_HOME` (already used by newer publish tests) so cache paths do not leak across runs.

### 4. Docs / ROADMAP

- Update `test-conan.adoc` and `AGENTS.md` when Windows Conan CI is live.
- Mark a ROADMAP id (e.g. `conan-windows-ci`) Done.

## Acceptance criteria

- [ ] Windows CI installs a working Conan 2 CLI and creates a usable default/MSVC profile.
- [ ] `pytest -m integration` on Windows runs Conan scenarios (no skip for missing `conan`).
- [ ] At least: generators_folder or full install + build, offline miss, and one publish export-pkg → consumer round-trip are green under `vc`.
- [ ] Shared-library publish/consume either green on Windows (`PATH` / runtime) or explicitly documented/skipped with a clear reason.
- [ ] Docs note that Linux and Windows both exercise Conan integration.

## Open questions

1. Same job vs dedicated Windows Conan job (time vs isolation)?
2. Pin Conan version in CI (`conan>=2,<3` vs exact pin) for reproducibility?
3. Cache Conan package downloads between Windows runs (Actions cache of `CONAN_HOME` / download root) to cut cold-build time?
4. Is Apple Clang / macOS Conan in scope later, or Windows-only follow-up?

## References

- GitHub [#29](https://github.com/ja11sop/cuppa/issues/29) (Conan supply chain)
- [`CONAN_CONSUMER_PLAN.md`](CONAN_CONSUMER_PLAN.md), [`CONAN_PUBLISH_PLAN.md`](CONAN_PUBLISH_PLAN.md)
- Conan 2 profiles / MSVC settings: https://docs.conan.io/2/reference/config_files/profiles.html
