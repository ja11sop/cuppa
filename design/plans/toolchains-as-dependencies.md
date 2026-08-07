# Plan: Toolchains as dependencies

- **Status:** in progress
- **Related:** [`ROADMAP.md`](../../ROADMAP.md); Profiles [#127](https://github.com/ja11sop/cuppa/issues/127); type-selector note in [`boost-updates.md`](boost-updates.md)
- **Updated:** 2026-08-07

Fetched compilers should behave like other cuppa dependencies: download once, extract under
storage roots, list / remove / wipe later, and register a **stable toolchain name** for
`--toolchains=` and `_build` folders. The first slice is **Clang + public archive URLs**
(GitHub Releases). GCC/MSVC and authenticated Actions artifacts come later.

## Why

Alliance weekly Profiles builds (and other experimental Clangs) ship as Release tarballs.
Today the only way to use them is to unpack by hand and put `bin` on `PATH` before cuppa
runs — easy to collide with distro `clang24`, and invisible to list/remove.

## Goals (umbrella)

1. **Toolchain dependency type** — storage type `toolchain`, identity `clang` (then others),
   qualifier = release tag / stem.
2. **Session registration** — non-colliding name for `--toolchains=` and build layout.
3. **Public HTTPS / `file://` / local root** first; Actions artifact auth later.
4. **List / remove / wipe** under the same grammar as other deps (`[toolchain]clang/…`).
5. Enable [#127](https://github.com/ja11sop/cuppa/issues/127) `--profiles` on capable Clangs.

## Non-goals (this phase)

- URLs inside `--toolchains=`
- Auto “latest Profiles release”
- GCC / MSVC archive toolchains
- Actions artifact API downloads
- Full wipe UX polish (storage layout first; wire list/remove next)

## Naming

Registered toolchain:

`clang{major}_{sanitised_release_tag}`

Example: Release tag `profiles-2026-08-07-27` → **`clang24_profiles_2026_08_07_27`**.

Do not register as plain `clang24` (collides with PATH Clang). `--name()` / build folders use
this full id. Wildcards: `clang24_profiles*`.

`--clang-root=` without a tag: `clang{major}_local_{short_path_hash}`.

## CLI

```sh
cuppa -D --dbg \
  --toolchain-archive=https://github.com/cppalliance/clang/releases/download/profiles-2026-08-07-27/clang-profiles-linux-x86_64.tar.gz \
  --toolchains=clang24_profiles_2026_08_07_27
```

- `--toolchain-archive=` — public archive URL or `file://` / local path to `.tar.gz` / `.zip`
- `--clang-root=` — existing install prefix containing `bin/clang++`
- If archive/root is set and `--toolchains=` omitted → auto-select the registered name(s)

## Storage layout

| Role | Path |
|------|------|
| Download cache | `downloads_root/toolchains/clang/<qualifier>/<asset>` |
| Extract | `dependencies_root/toolchains/clang/<qualifier>/` (with `bin/clang++`) |

Offline: require cache / extract; clear error if missing.

## Phases

| Id | Work | Status |
|----|------|--------|
| `tc-dep-plan` | This plan + index | done |
| `tc-dep-clang-root` | `--clang-root=` + naming + register before/with `add_toolchains` | in progress |
| `tc-dep-archive` | `--toolchain-archive=` public HTTPS / file download + extract | in progress |
| `tc-dep-docs` | toolchains.adoc + CHANGELOG | in progress |
| `tc-dep-list` | `--list-dependencies` shows `toolchain` / `clang` | later |
| `tc-dep-remove` | remove / wipe `[toolchain]clang/…` | later |
| `tc-dep-profiles` | `#127` `--profiles` / `-fprofiles` | later |
| `tc-dep-actions` | Authenticated Actions artifact URLs | later |

## Related

- Type selectors for cross-type name clashes (`[gitlab]boost` vs `[archive]boost`) — see
  [`boost-updates.md`](boost-updates.md); not required for the first Clang archive PR.
