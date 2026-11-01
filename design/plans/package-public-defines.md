# Note: BuildWith should apply a package's public compile defines

- **Status:** done
- **Related:** [`gitlab-package-lib-groups.md`](../archive/gitlab-package-lib-groups.md) (Compile defines / flags — deferred `cppdefines` behind pkg-config); [`package-use-libs-defaults.md`](../archive/package-use-libs-defaults.md); [`package-runtime-paths.md`](../archive/package-runtime-paths.md); Antora [`dependencies/using/gitlab.adoc`](../../docs/modules/ROOT/pages/dependencies/using/gitlab.adoc) (Pkg-config); [#388](https://github.com/ja11sop/cuppa/pull/388)
- **Updated:** 2026-11-01
- **Impact:** `minor` — traveling manifest gains `public_defines`, `library_prefix`, and `pkg_config_dir`

Done in [#388](https://github.com/ja11sop/cuppa/pull/388). Ships with 1.14.0. The notes below are the record of the gap.

## What already travelled

`BuildWith` on a GitLab package already applies package knowledge:

- include paths
- libraries, from `use_libs`, `default_use_libs`, and `lib_groups`
- link paths and runtime search path

It did **not** apply the package's public compile defines. `cuppa-publish.json` had no such field. The only general path was opt-in: the consumer set `pkg_config_dir`, and `use_libs` then ran `pkg-config --libs --cflags`. Boost defines (`BOOST_PARAMETER_MAX_ARITY`, patched test, and the rest) are a special case inside `boost_package`, not the generic package.

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

The package carries its public compile defines. `BuildWith` applies them, as `CPPDEFINES`, when it applies the package (include path and the rest of the package interface). It does not wait for `use_libs`.

`use_libs` chooses what to link. `use_libs([])` clears that link contribution. It does not clear the package's public defines. A translation unit that includes the package headers without linking, and another that links, must still see the same defines. Otherwise they can be linked together later with two views of one public interface.

The defines are the package's preferred public behaviour, not only an ABI guard. A consumer can override, remove, or replace them afterwards, the same way they can amend any other flags `BuildWith` supplied.

How the defines get into the package is separate from when they are applied:

- The general case is the traveling manifest. A publisher written in SCons, or by hand, sets `public_defines` directly.
- A `.pc` file is already a consume path (`pkg_config_dir`). It stays. It is not the only way to carry a define.
- If the package was installed with CMake, the publisher passes `cmake_public_defines()` and does not retype the tokens. At publish, after install, Cuppa asks CMake for each imported target's `INTERFACE_COMPILE_DEFINITIONS` (the generator expression, so link-interface defines are included) and stores that answer. `extra_defines` remains how that package itself was built. It is not this field. Omitting the argument does not guess. `[]` publishes none.

A first cut on this branch applied defines only for the linked stem, and cleared them with `use_libs([])`, and treated the CMake scan as the feature. That is the wrong shape. Date's `USE_OS_TZDB=1` is the example that showed the hole. It is not a reason to withhold the define from a headers-only use of the same package.

Boost's handler-owned defines stay in `boost_package` until a manifest-selected handler exists. This note does not replace that handler.

## Examples

`public_defines` is a list of compile-define tokens for the package. It is not a map of link stems.

A publisher that does not use CMake sets the list. That is the general case:

```python
publisher = GitlabPackagePublisher(
    env,
    source_include_dir = '#/include',
    source_lib_dir     = env['abs_final_dir'],
    registry           = 'https://gitlab.example/api/v4/projects/1',
    package            = 'widget',
    version            = '1.0.0',
    default_use_libs   = [ 'widget' ],
    public_defines     = [ 'WIDGET_HAS_TLS=1' ],
)
```

The staged and published `cuppa-publish.json` carries the same list:

```json
{
  "package": "widget",
  "version": "1.0.0",
  "default_use_libs": ["widget"],
  "public_defines": ["WIDGET_HAS_TLS=1"]
}
```

Consume applies it where the headers go on, in `GitlabPackageDependency.initialise_build_variant`, beside `SYSINCPATH`. `use_libs` does not install or remove it:

```python
def initialise_build_variant(self, env, toolchain, variant, dependency_name=None):
    env.AppendUnique(SYSINCPATH = self._include_dir)
    install_cppdefines(env, read_public_defines(self._package_dir))
    # default_use_libs may still link. That is a separate step.
```

```python
def use_libs(self, env, libs):
    # link stems only. public_defines stay, including when libs is [].
```

A consumer that only wants the headers still sees the package's defines. Clearing the link line does not clear them. A later change to `CPPDEFINES` replaces the package default for that environment, the same as any other flag `BuildWith` wrote:

```python
env.BuildWith('widget')
# CPPDEFINES includes WIDGET_HAS_TLS=1
# nothing from widget is on the link line yet

env.BuildWith('widget').use_libs([])
# still WIDGET_HAS_TLS=1; widget is not linked

env.BuildWith('widget')
kept = [d for d in env['CPPDEFINES'] if d != 'WIDGET_HAS_TLS=1']
env.Replace(CPPDEFINES = kept + ['WIDGET_HAS_TLS=0'])
```

Date is the same shape. The package was built with `USE_OS_TZDB=1`. Every translation unit that can include `date/tz.h` should see that, whether or not this target links `date-tz`:

```json
"public_defines": ["USE_OS_TZDB=1"]
```

```python
env.BuildWith('date')
# SYSINCPATH has the date headers
# CPPDEFINES includes USE_OS_TZDB=1
# default_use_libs may also link date-tz; the define does not depend on that
```

The date publisher does not list the consumer defines. `USE_SYSTEM_TZ_DB` stays in `extra_defines`, which is how the library is built. The marker asks CMake after `CMakeInstall`:

```python
from cuppa.buildsys.cmake import cmake_public_defines

publisher = GitlabPackagePublisher(
    env,
    # ...
    default_use_libs = [ 'date-tz' ],
    public_defines   = cmake_public_defines(),
)
```

CMake's answer for this install is the package list `USE_OS_TZDB=1`, `ONLY_C_LOCALE=0`, `HAS_STRING_VIEW=1`. `date::date-tz` contributes `USE_OS_TZDB=1` and, through `INTERFACE_LINK_LIBRARIES`, the defines from `date::date`. Those are one list. A `$<...>` expression is evaluated by that probe; a token that is still a generator expression afterwards is dropped. If two targets export conflicting values (`FOO=0` and `FOO=1`), publish stops and the author sets `public_defines` to the list the package should carry. An explicit list does not also ask CMake.

A `.pc` file stays a consume path. It is not how `public_defines` is filled. Installed `.pc` files are rewritten so they follow the extract. `library_prefix` and `pkg_config_dir` travel with the package. All three are below.

## Relocatable pkg-config

Cuppa does not write these files. Upstream CMake does, during `cmake --install`, and it records the install prefix as an absolute path. A consumer who later points pkg-config at the extract still gets the publisher's build directory. Checked by copying installed files to `/tmp` and querying them: fmt, protobuf, and nlohmann-json stayed on the original prefix. OpenTelemetry and google-cloud-cpp already use `${pcfiledir}` and followed the copy.

pkgconf 2.5 can paper over that with `--define-prefix`. Cuppa does not pass that flag, and the flag is not part of every pkg-config. The file should be relocatable on its own.

`CMakeInstall` is the method that creates the files. After `cmake --install` it reads `CMAKE_INSTALL_PREFIX` from that build's `CMakeCache.txt` and rewrites `*.pc` under that prefix. Publishers that already call `CMakeInstall` do not grow a new line. google-cloud-cpp is the case that matters: its install target is a stamp, not the prefix directory, but the cache still has the prefix.

The rewrite itself is a helper, so a tree that was not installed by `CMakeInstall` can use it too:

```python
from cuppa.buildsys.pkgconfig import relocate_pkgconfig

changed = relocate_pkgconfig(install_prefix)
```

```python
installed = env.RelocatePkgConfig(cmake_install, prefix=install_location)
```

`CMakeInstall` calls the same helper. It does not run when the prefix is outside the package build (`/usr`, a system dest). It does not rewrite a file whose `prefix` is already `${pcfiledir}/...`.

The relative step is from the `.pc` file's directory up to the prefix, not a hard-coded `../..`. `lib/pkgconfig` and `share/pkgconfig` are both two levels. `lib/<triple>/pkgconfig` is three.

Three shapes in the current installs:

```text
# fmt: prefix is absolute, the other variables already use it
prefix=/home/.../final/fmt/12.2.0
libdir=${prefix}/lib

# protobuf: every path is absolute
prefix=/home/.../final/protobuf/36.1
exec_prefix=/home/.../final/protobuf/36.1
libdir=/home/.../final/protobuf/36.1/lib
includedir=/home/.../final/protobuf/36.1/include

# re2: no prefix variable at all
includedir=/home/.../final/re2/2025-11-05/include
libdir=/home/.../final/re2/2025-11-05/lib
```

become:

```text
prefix=${pcfiledir}/../..
exec_prefix=${prefix}
libdir=${prefix}/lib
includedir=${prefix}/include
```

Rules:

- An absolute path under the install prefix becomes `${prefix}/` plus the remainder. `exec_prefix` that equals the prefix becomes `${prefix}`.
- A file with no `prefix=` line gains `prefix=${pcfiledir}/<relative>`.
- `${prefix}`, `${exec_prefix}`, `${libdir}`, `${includedir}`, and `${pcfiledir}` stay as they are.
- A path that is not under the prefix is left alone.
- `Libs:` and `Cflags:` keep using those variables. A raw absolute path under the prefix on those lines is rewritten the same way.
- Running the helper again changes nothing.

`pkg_config_dir` travels with the package, the same way as `library_prefix`. The publisher sets the directory relative to the package root. It is written whenever the package uses pkg-config, including when that directory is `lib/pkgconfig`. A missing key means do not run pkg-config. It is not a stand-in for `lib/pkgconfig`: that would make an old extract look like a package that chose the common directory, and a later change of the assumed directory would reinterpret every manifest that left the key out. `share/pkgconfig` and `lib/<triple>/pkgconfig` are published as those paths.

```python
publisher = GitlabPackagePublisher(
    env,
    # ...
    pkg_config_dir = 'share/pkgconfig',
)
```

```json
"pkg_config_dir": "share/pkgconfig"
```

Consume uses the manifest value. A `pkg_config_dir` passed to `package_dependency` replaces it. `""` turns pkg-config off. Omit both and Cuppa links the libraries under `lib/` instead of running pkg-config.

## Traveling library_prefix

`library_prefix` is still only a consumer argument. It is how `use_libs('capy')` looks for `libboost_capy`, and how the `.pc` filename is chosen. Capy and corosio avoided it for the default link by publishing `default_use_libs` as `boost_capy`. A shorter token still needs the prefix. The package knows the prefix. The consumer should not have to.

```python
publisher = GitlabPackagePublisher(
    env,
    # ...
    library_prefix   = 'boost_',
    default_use_libs = [ 'boost_capy' ],
)
```

```json
"library_prefix": "boost_"
```

Consume uses the manifest value. A `library_prefix` passed to `package_dependency` replaces it. Omit both and the prefix stays empty, which is today's default.

This follows the `.pc` rewrite. It does not change how defines are applied.
