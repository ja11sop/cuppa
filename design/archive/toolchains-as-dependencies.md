# Plan: Toolchains as dependencies

- **Status:** shipped
- **Related:** [`ROADMAP.md`](../../ROADMAP.md); umbrella [#160](https://github.com/ja11sop/cuppa/issues/160) (Clang [#159](https://github.com/ja11sop/cuppa/pull/159) / GCC [#164](https://github.com/ja11sop/cuppa/pull/164)); Profiles follow-on [#127](https://github.com/ja11sop/cuppa/issues/127); type-selector note in [`boost-updates.md`](../plans/boost-updates.md); report polish [#161](https://github.com/ja11sop/cuppa/issues/161); download progress [#165](https://github.com/ja11sop/cuppa/pull/165)
- **Updated:** 2026-08-09

Fetched compilers behave like other cuppa dependencies: download once, extract under
storage roots, list / remove / wipe later, and register a **stable toolchain name** for
`--toolchains=` and `_build` folders. **Clang** (public archive URLs) and **GCC**
(`gcc-snapshot` `.deb` + `--gcc-root=`) are the shipped families. MSVC and authenticated
Actions artifacts remain follow-ons (see ROADMAP).

**Product goal — multiple concurrent copies:** users must be able to keep several Clang and
several GCC installs registered at once and **select more than one in a single cuppa run**
(`--toolchains=a,b` or wildcards) so builds and behaviours can be compared across versions and
snapshots. Non-colliding names (`gcc{major}_local_{hash}`, `clang{major}_{tag}`, …) exist for
that reason. Discovery under `toolchains/{clang,gcc}/` plus the ordinary multi-toolchain grid
are the durable mechanism; `--*-root=` / `--toolchain-archive=` only **supply** installs.

## Why

Alliance weekly Profiles builds (and other experimental Clangs) ship as Release tarballs.
Today the only way to use them is to unpack by hand and put `bin` on `PATH` before cuppa
runs — easy to collide with distro `clang24`, and invisible to list/remove.

The same collision problem exists for bleeding-edge **GCC**: Debian’s `gcc-snapshot` package
ships a full toolchain tree. Cuppa accepts a `.deb` URL via `--toolchain-archive=` or an
already-unpacked prefix via `--gcc-root=`.

## Goals (umbrella)

1. **Toolchain dependency type** — storage type `toolchain`, identity `clang` / `gcc`
   (then others), qualifier = release tag / stem / local hash.
2. **Session registration** — non-colliding name for `--toolchains=` and build layout.
3. **Public HTTPS / `file://` / local root** first; Actions artifact auth later.
4. **List / remove / wipe** under the same grammar as other deps (`[toolchain]clang/…`,
   `[toolchain]gcc/…`).
5. **Many installs at once** — discover all cached/external registrations; compare via
   `--toolchains=` multi-select.
6. Enable [#127](https://github.com/ja11sop/cuppa/issues/127) `--profiles` on capable Clangs
   (separate issue).

## Non-goals (remaining)

- Auto “latest Profiles release” or auto “latest gcc-snapshot” pin chasing
- Installing `.deb` packages system-wide (`dpkg -i` from cuppa)
- MSVC archive toolchains
- Actions artifact API downloads
- URL token inside `--toolchains=` (`tc-dep-url-sugar`)

## Naming

### Clang

`clang{major}_{sanitised_release_tag}` or `clang{major}_local_{short_path_hash}` for
`--clang-root=`.

### GCC

`gcc{major}_{sanitised_deb_stem}` for `.deb` archives, or `gcc{major}_local_{hash}` for
`--gcc-root=`.

Force-wipe accepts storage identity and session name for both families.

## CLI

```sh
# Managed Clang
cuppa -D --dbg \
  --toolchain-archive=https://github.com/cppalliance/clang/releases/download/profiles-2026-08-07-27/clang-profiles-linux-x86_64.tar.gz

# Managed Debian gcc-snapshot
cuppa -D --dbg \
  --toolchain-archive=https://deb.debian.org/debian/pool/main/g/gcc-snapshot/gcc-snapshot_20260725-1_amd64.deb

# External prefixes (persist registration under dependencies_root/toolchains/…)
cuppa -D --dbg --clang-root=/path/to/clang/prefix
cuppa -D --dbg --gcc-root=/path/to/gcc/prefix

# Compare several registered installs
cuppa -D --dbg --toolchains=gcc15,gcc16_gcc_snapshot_20260725_1_amd64,clang24_profiles_2026_08_07_27
```

- `--toolchain-archive=` — basename tokens `gcc` / `clang` choose the family; if
  ambiguous, download/stage and probe archive members for `bin/g++` / `bin/clang++`;
  extension is last resort (`.deb` → GCC). GCC `.deb` uses `ar` + `data.tar.*`
- `--clang-root=` / `--gcc-root=` — external prefix; writes `cuppa-toolchain.json` (`kind: external`)
- Auto-select when supply flags are set and `--toolchains=` omitted (prepared this session only)
- External force-wipe removes the registration stub, not the external tree

## Storage layout

| Role | Path |
|------|------|
| Download cache | `downloads_root/toolchains/{clang,gcc}/<qualifier>/<asset>` |
| Owned extract | `dependencies_root/toolchains/{clang,gcc}/<qualifier>/` |
| External registration | same path + `cuppa-toolchain.json` pointing at the prefix |

## Phases

| Id | Work | Status |
|----|------|--------|
| `tc-dep-plan` | This plan + index | done |
| `tc-dep-clang-root` | `--clang-root=` + naming + register | done |
| `tc-dep-archive` | `--toolchain-archive=` Clang HTTPS / file | done |
| `tc-dep-discover` | Start-up scan of cached extracts | done |
| `tc-dep-docs` | toolchains.adoc + CHANGELOG | done |
| `tc-dep-list` | list/downloads type `toolchain` | done |
| `tc-dep-remove` | force-wipe `[toolchain]…` | done |
| `tc-dep-pr` | First Clang slice land | done |
| `tc-dep-gcc-root` | `--gcc-root=` + persist external + discover gcc | done (#164) |
| `tc-dep-gcc-deb` | `.deb` as `--toolchain-archive=` for gcc-snapshot | done (#164) |
| `tc-dep-external-persist` | Persist `--clang-root=` / `--gcc-root=` registrations | done (#164) |
| `tc-dep-url-sugar` | Optional URL token in `--toolchains=` | later (ROADMAP) |
| `tc-dep-profiles` | [#127](https://github.com/ja11sop/cuppa/issues/127) `--profiles` | later (separate issue) |
| `tc-dep-actions` | Authenticated Actions artifact URLs | later (ROADMAP) |
| `dl-prog` | Shared HTTP download progress for large archives | done (#165) — [`download-progress.md`](download-progress.md) |

## Related

- Type selectors for cross-type name clashes — see [`boost-updates.md`](../plans/boost-updates.md).
- Report / judgement-tree polish:
  [`console-report-patterns.md`](console-report-patterns.md) / [#161](https://github.com/ja11sop/cuppa/issues/161).
