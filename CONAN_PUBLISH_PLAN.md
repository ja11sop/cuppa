# Conan package publishing for Cuppa

Producer-side Conan 2 support: package Cuppa-built libraries and upload them to a Conan remote, without making Conan the build orchestrator.

Related: [`CONAN_CONSUMER_PLAN.md`](CONAN_CONSUMER_PLAN.md), [`ROADMAP.md`](ROADMAP.md), GitHub [#29](https://github.com/ja11sop/cuppa/issues/29).

## Goal

Teams with an internal Conan registry (GitLab Conan, Artifactory, …) can build with Cuppa and publish binaries that other Cuppa projects consume via existing `conan_deps` / `conan_dependency` — without CMake.

## Locked approach

**Cuppa builds first**, then a Conan recipe **packages prebuilt files** (`conan export-pkg`) and optionally **`conan upload`s**. Parallel to GitLab generic `PublishPackage`, not a replacement.

Rejected: `conan create` where `build()` runs Cuppa/SCons.

## API

```python
from cuppa.package_managers.conan import ConanPackagePublisher

publisher = ConanPackagePublisher(
    env,
    name='mylib',
    version='1.2.3',
    user='myorg',       # optional
    channel='stable',   # optional
    remote='gitlab',    # required for upload
    remote_url=None,    # optional: add remote if missing
    source_include_dir='include',
    source_lib_dir=env['abs_final_dir'],
    source_modules_dir=None,  # optional; default {source_lib_dir}/modules if present
    libs=None,          # optional; auto-detect from lib dir
    shared=False,       # optional; None = infer from staged libs
    requires=None,      # optional; generated recipe only
    # conanfile='conanfile.py',  # optional hand-written override
)

env.PublishPackage( built_lib, publisher )
# cuppa -D --rel --publish-package
```

Reuse `--publish-package`. Auth via `CONAN_LOGIN_USERNAME` / `CONAN_PASSWORD` (CI: `ci_user` + `CI_JOB_TOKEN`); Cuppa does not store tokens.

## Settings

Reuse `conan_settings_for()` / `settings_to_cli()` from `cuppa/build_with_conan.py` so package IDs match consumer installs.

## Offline

`--offline`: `export-pkg` may still update the local Conan cache; **upload is skipped** (or fails clearly if forced). Remotes are not contacted for upload. Recipes with `requires` need those packages already in the local cache.

## Phases

| Phase | Status |
|-------|--------|
| 0 Spike | Done — export-pkg + consumer round-trip via local cache |
| 1 MVP | Done — `ConanPackagePublisher`, unit/integration tests, packages docs |
| 2 Hardening | Done — `conanfile=` override, `shared=`, generated `requires=` |
| 2b Modules/BMI | Done — stage `modules/` + consumer `load_packaged_modules` (Cuppa-native; parity with GitLab) |
| Later | Components / multi-lib `cpp_info.components` (see `CONAN_COMPONENTS_ISSUE.md`) |

## Caveats

GitLab’s Conan 2 registry may still be marked under development; prefer documenting “any Conan 2 remote,” with GitLab as one target.
Components / multi-lib selection remain deferred.