# Note: BuildWith should apply a package's public compile defines

- **Status:** proposal
- **Related:** [`gitlab-package-lib-groups.md`](../archive/gitlab-package-lib-groups.md) (Compile defines / flags — deferred `cppdefines` behind pkg-config); [`package-use-libs-defaults.md`](../archive/package-use-libs-defaults.md); [`package-runtime-paths.md`](../archive/package-runtime-paths.md); Antora [`dependencies/using/gitlab.adoc`](../../docs/modules/ROOT/pages/dependencies/using/gitlab.adoc) (Pkg-config)
- **Updated:** 2026-10-31
- **Impact:** `minor` if the traveling manifest gains a public-defines field

## What already travels

`BuildWith` on a GitLab package already applies package knowledge:

- include paths
- libraries, from `use_libs`, `default_use_libs`, and `lib_groups`
- link paths and runtime search path

It does **not** apply the package's public compile defines. `cuppa-publish.json` has no such field. The only general path is opt-in: the consumer sets `pkg_config_dir`, and `use_libs` then runs `pkg-config --libs --cflags`. Boost defines (`BOOST_PARAMETER_MAX_ARITY`, patched test, and the rest) are a special case inside `boost_package`, not the generic package.

The lib-groups plan recorded this and left traveling `cppdefines` as an optional follow-on, with `.pc` files as the supported escape hatch. That note is easy to miss, and the date package shows why `.pc` is not enough.

## What failed

Howard Hinnant's date 3.0.5, published as a GitLab package, exports:

```text
date::date-tz
  INTERFACE_COMPILE_DEFINITIONS "USE_OS_TZDB=1"
```

The extracted tree has CMake package files and `libdate-tz.so`. It has no `.pc`. Cuppa applied `default_use_libs` `['date-tz']` (link the shared library, add the headers) and did not import that define.

Every consumer translation unit then compiled `date/tz.h` with the header default `USE_OS_TZDB=0`, while the shared library was built with `USE_OS_TZDB=1`. Those two settings do not have the same timezone-database layout. `funding_rate_table` died in `date::utc_clock::from_sys` while searching `leap_seconds`, reported as a memory access at `0x1008`. Boost.Test's last checkpoint was the previous assertion, not the faulting line.

The old in-tree build compiled `tz.cpp` and the tests with the same defaults, so it could not show this. The define is part of the public C++ interface of `date-tz`, the same way the library stem is.

## What BuildWith should do

When a package target is applied — `default_use_libs` or an explicit `use_libs` — apply that target's public compile defines to the same environment, as `CPPDEFINES`. Clearing the link contribution (`use_libs([])`) clears those defines with it.

Grain is the linked target, not the whole package. `date::date` (headers only) does not carry `USE_OS_TZDB`. `date::date-tz` does. A define that changes a type or an inline function in a public header has to be present on every translation unit that includes that header.

Publish should record the defines the build system already exports (CMake `INTERFACE_COMPILE_DEFINITIONS` on the installed target) in the traveling manifest, beside the library the target applies. Consume should not require the tip to pass `pkg_config_dir` or a hand-written `-D` for a fact the package already stated.

Pkg-config stays valid when a package ships a usable `.pc`. It is not a substitute for a define that is already on the CMake target and was never opted into by the consumer. CMake `extra_defines` on the publisher stays build-time configuration of the package itself. It is not this field.

Boost's handler-owned defines stay in `boost_package` until a manifest-selected handler exists. This note does not replace that handler.
