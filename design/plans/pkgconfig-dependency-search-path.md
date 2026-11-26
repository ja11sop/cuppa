# Note: compose pkg-config search paths from Cuppa package dependencies

- **Status:** in progress
- **Related:** [`archive/package-public-defines.md`](../archive/package-public-defines.md)
  (relocatable `.pc`, traveling `pkg_config_dir`);
  [`archive/cmake-package-prefix.md`](../archive/cmake-package-prefix.md)
  (`CMAKE_PREFIX_PATH` for *build*);
  [`archive/gitlab-package-transitive.md`](../archive/gitlab-package-transitive.md);
  `cuppa/package_managers/gitlab.py` (`parse_pkg_config`);
  `cuppa/buildsys/pkgconfig.py` (relocate only)
- **Updated:** 2026-11-26
- **Impact:** `patch` — correct consume for packages whose installed `.pc`
  files `Requires:` other Cuppa packages; no new public flags; Antora
  Using GitLab packages clarifies `pkg_config_dir` vs `use_libs`

## Problem

Cuppa consume runs pkg-config roughly as:

```text
pkg-config --with-path=<P>/lib/pkgconfig --libs --cflags <P_libs>
```

`--with-path` adds **only P's** directory. Installed `.pc` files for a fat
stack (example shape: a cloud client library) still say things like
`Requires: grpc++ grpc openssl protobuf …`. Those names are then resolved
from `PKG_CONFIG_PATH` or the **system** pkg-config paths.

On a machine with distro `grpc++.pc`, that "works" and silently links the
OS `libgrpc` against a Cuppa-built client — dual Abseil sonames, OpenSSL
symbol mismatches (seen on a rolling distro). After the distro package is
removed, pkg-config fails with `Package 'grpc++' not found` even though
Cuppa has already extracted its own `grpc` under `_dependencies`.

Build-time was never the gap: publishers already pass Cuppa prefixes via
`CMAKE_PREFIX_PATH` / `CMakePrefixPathFor`. Consume via pkg-config never
got the matching closed search path. `lib_groups` only expand same-package
stems; they do not replace upstream `Requires:` on the installed `.pc`
files.

Some dependency publishers install `lib/pkgconfig/*.pc` but omit
`pkg_config_dir` from the traveling manifest. Missing key correctly means
"do not run pkg-config for *this* package's `use_libs`", but those `.pc`
files are still needed as **search path** entries when a parent `Requires:`
them.

## Goals

1. When Cuppa runs pkg-config for package P, `Requires:` that name other
   **Cuppa packages already on P's traveling dependency closure** resolve
   to those extracts, not `/usr`.
2. Intentional system Requires (`openssl`, `zlib`, `libcurl`, …) still come
   from the OS.
3. Cuppa paths win over the OS when both provide the same module name.
4. Old extracts that install `*.pc` but omit `pkg_config_dir` still
   contribute a search directory via a narrow filesystem fallback.
5. Clearer failure when a Cuppa-shaped Require is missing (optional follow-on).

## Non-goals

- `--define-prefix` as the fix (already rejected; relocatable `${pcfiledir}`
  stays the publish-side story).
- Stripping or rewriting `Requires:` out of installed `.pc` files.
- Expanding `lib_groups` to fake foreign stems (`grpc++`, …).
- Requiring tip authors to export `PKG_CONFIG_PATH` by hand.
- Changing publisher CMake / `CMAKE_PREFIX_PATH` behaviour.

## Approach

### Compose `--with-path` from the traveling closure

In `GitlabPackageDependency.parse_pkg_config` (consume):

1. Keep P's resolved `pkg_config_dir` as the first `--with-path`.
2. Walk P's traveling manifest `dependencies` (BFS, cycle-safe), resolving
   each BuildWith name to its `package_dir` (already extracted / staged by
   `apply_transitive_build_with`).
3. For each dependency package dir, discover a pkg-config directory (below).
4. Pass **one `--with-path` per directory** (pkgconf accepts repeated flags;
   a colon inside a single `--with-path` does **not** work).
5. Leave host `PKG_CONFIG_PATH` / system paths alone so openssl/zlib still
   resolve.

Helper module (suggested): `cuppa/package_managers/pkgconfig_paths.py` —
pure collection / discovery, unit-tested without SCons.

### Discovering a dependency's pkg-config directory

Order for **search-path contribution only** (not for "does P use
pkg-config?"):

1. Traveling `pkg_config_dir` when present.
2. Else `<package_dir>/lib/pkgconfig` if that directory contains `*.pc`.
3. Else `<package_dir>/share/pkgconfig` if that directory contains `*.pc`.
4. Else skip (no search entry).

Primary package enablement stays unchanged: a missing manifest
`pkg_config_dir` still means do not run pkg-config for that package's own
`use_libs`. The fallback is only for finding modules **required by** a
parent that already opted into pkg-config.

### Publisher follow-up (private package trees)

Not required for the Cuppa core patch to help via fallback, but manifests
should be honest:

- Set `pkg_config_dir='lib/pkgconfig'` (or `share/pkgconfig`) on packages
  that install `.pc` files and are named in another package's `Requires:`.
- Republish; confirm relocate left `${pcfiledir}` prefixes on those files.

### Optional hardening (follow-on)

If pkg-config fails with "Package X not found" and X matches a traveling
edge name (or a well-known stem from that edge), raise a Cuppa `StopError`
naming the missing extract / missing search dir instead of a bare
`ParseConfig` `OSError`.

## Tests

- Discovery: manifest wins; `lib/pkgconfig` fallback when key omitted and
  `*.pc` present; no fallback when the directory is empty / absent.
- Command shape: multiple `--with-path` entries, primary first, deps
  deduped, order stable.
- Closure: parent Requires child module → child dir composed in; grandchild
  (child's dependency) composed when the child's traveling manifest lists it.
- `parse_pkg_config` clean-skip behaviour unchanged.
- Like-examples only in fixtures (`widget`, `widget_core`, …) — no private
  host / package paste.

## Soak

- Tip `use_libs` for a client library whose `.pc` `Requires:` Cuppa `grpc`
  (or like) with distro `grpc++` **uninstalled**: flags point at
  `_cuppa/_dependencies/...`, not `/usr/lib`.
- Same tip with distro grpc installed: Cuppa paths still win (first
  `--with-path` / search order).

## Risks

| Risk | Mitigation |
|------|------------|
| Fallback invents `lib/pkgconfig` for packages that never meant pkg-config | Only when `*.pc` files exist; primary enablement still requires the manifest key |
| System module name collides with a Cuppa `.pc` | Cuppa dirs first via `--with-path` |
| Dependency not yet BuildWith / extract missing | Skip that dir; pkg-config fails as today (optional clearer error later) |
| Old absolute-prefix `.pc` in dependency extracts | Separate relocate/republish issue; search path still finds the module |

## Implementation notes

- Touch `parse_pkg_config` on the consume dependency object; publisher-local
  `use_libs` that already has a single `_pkg_config_dir` can stay as-is or
  share the command formatter only.
- Do not put private consumer paths or registry hosts in the plan, tests,
  changelog, or PR body — use like-examples.
