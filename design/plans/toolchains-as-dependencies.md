# Plan: Toolchains as dependencies

- **Status:** in progress
- **Related:** [`ROADMAP.md`](../../ROADMAP.md); umbrella [#160](https://github.com/ja11sop/cuppa/issues/160); Profiles follow-on [#127](https://github.com/ja11sop/cuppa/issues/127); type-selector note in [`boost-updates.md`](boost-updates.md); report polish [#161](https://github.com/ja11sop/cuppa/issues/161)
- **Updated:** 2026-08-07

Fetched compilers should behave like other cuppa dependencies: download once, extract under
storage roots, list / remove / wipe later, and register a **stable toolchain name** for
`--toolchains=` and `_build` folders. The first slice is **Clang + public archive URLs**
(GitHub Releases). **GCC snapshot via a local prefix** (same shape as `--clang-root=`) is the
next driver; MSVC and authenticated Actions artifacts come later.

## Why

Alliance weekly Profiles builds (and other experimental Clangs) ship as Release tarballs.
Today the only way to use them is to unpack by hand and put `bin` on `PATH` before cuppa
runs — easy to collide with distro `clang24`, and invisible to list/remove.

The same collision problem exists for bleeding-edge **GCC**: Debian’s `gcc-snapshot` package
ships a full toolchain tree that you can unpack beside the project without installing it as
the system compiler. Cuppa should accept that prefix the way it accepts `--clang-root=`.

## Goals (umbrella)

1. **Toolchain dependency type** — storage type `toolchain`, identity `clang` then `gcc`
   (then others), qualifier = release tag / stem / local hash.
2. **Session registration** — non-colliding name for `--toolchains=` and build layout.
3. **Public HTTPS / `file://` / local root** first; Actions artifact auth later.
4. **List / remove / wipe** under the same grammar as other deps (`[toolchain]clang/…`,
   `[toolchain]gcc/…`).
5. Enable [#127](https://github.com/ja11sop/cuppa/issues/127) `--profiles` on capable Clangs
   (separate issue; not part of the first PR).

## Non-goals (this phase)

- Auto “latest Profiles release” or auto “latest gcc-snapshot” pin chasing
- Installing `.deb` packages system-wide (always extract to a user-owned prefix)
- Full cuppa-driven download/unpack of Debian `.deb` in the first GCC slice (document the
  manual extract; optional `--toolchain-archive=` for `.deb` later)
- MSVC archive toolchains
- Actions artifact API downloads
- Full wipe UX polish beyond force-wipe + list (done for classify / `[D]` / session-name wipe)
- Judgement-tree / list-scope polish — tracked in [#161](https://github.com/ja11sop/cuppa/issues/161)

## Naming

### Clang (shipped in the first PR)

Registered toolchain:

`clang{major}_{sanitised_release_tag}`

Example: Release tag `profiles-2026-08-07-27` → **`clang24_profiles_2026_08_07_27`**.

Do not register as plain `clang24` (collides with PATH Clang). `--name()` / build folders use
this full id. Wildcards: `clang24_profiles*`.

`--clang-root=` without a tag: `clang{major}_local_{short_path_hash}`.

Force-wipe accepts both storage identity and session name:

- `[toolchain]clang/profiles_2026_08_07_27`
- `[toolchain]clang24_profiles_2026_08_07_27`

### GCC snapshot / local root (planned)

Same pattern as `--clang-root=`:

`--gcc-root=` → register **`gcc{major}_local_{short_path_hash}`** (or
`gcc{major}_snapshot_{sanitised_qualifier}` when the user passes an explicit tag / date stem).

Do not register as plain `gcc` / `gcc15` when the binary is a snapshot tree — that collides with
the distro driver cuppa already knows. Wildcards: `gcc*_snapshot*`, `gcc*_local_*`.

Force-wipe:

- `[toolchain]gcc/<qualifier>`
- `[toolchain]gcc{major}_local_{hash}` (session name)

## CLI

```sh
cuppa -D --dbg \
  --toolchain-archive=https://github.com/cppalliance/clang/releases/download/profiles-2026-08-07-27/clang-profiles-linux-x86_64.tar.gz \
  --toolchains=clang24_profiles_2026_08_07_27
```

- `--toolchain-archive=` — public archive URL or `file://` / local path to `.tar.gz` / `.zip`
  (Clang first; GCC `.tar.*` if useful later)
- `--clang-root=` — existing install prefix containing `bin/clang++`
- `--gcc-root=` — **planned** — existing prefix containing `bin/g++` (see [GCC snapshot](#gcc-snapshot-local-prefix) below)
- If archive/root is set and `--toolchains=` omitted → auto-select the registered name(s)
- Later sessions: scan extracts under `dependencies_root/toolchains/{clang,gcc}/`, register each
  as available, skip if the derived name is already in the pre-registered toolchain map, and
  select with `--toolchains=clang24_profiles_…` / `--toolchains=gcc*_local_*` (no auto-select for
  cached-only discovery)
- Listing: type `toolchain`; selected `--toolchains=` extract is **referenced**; drop stale
  inventory for the `toolchains/` parent folder (no duplicate under source archives);
  verbose LOCATION uses `[D]` when the download archive is present

### Why not `--toolchains=https://…` (kept separate for now)

`ParseToolchainsOption` is names + wildcards. Keep **supply** (`--toolchain-archive=` /
`--*-root=`) and **selection** (`--toolchains=`) as separate flags.

That still matches the common “only URL” case via auto-select: omitting `--toolchains=` after
`--toolchain-archive=` selects the registered name for this session. Putting the URL *inside*
`--toolchains=` would feel natural for that one case, but it muddies:

- comma-lists and wildcards (`gcc,clang24_profiles*`)
- error attribution (fetch failed vs unknown name)
- parallel supply via `--clang-root=` / `--gcc-root=` (not a URL)
- future multi-archive / “fetch but do not select”

**Open follow-up (`tc-dep-url-sugar`):** optionally accept a URL token in `--toolchains=` as
sugar for “prepare this archive and select it”, while keeping `--toolchain-archive=` as the
explicit supply flag. Not required for the first PR.

## Storage layout

| Role | Path |
|------|------|
| Download cache (Clang) | `downloads_root/toolchains/clang/<qualifier>/<asset>` |
| Extract (Clang) | `dependencies_root/toolchains/clang/<qualifier>/` (with `bin/clang++`) |
| Local / snapshot (GCC) | `dependencies_root/toolchains/gcc/<qualifier>/` (with `bin/g++`), **or** point `--gcc-root=` at an extract outside storage and still register the session name |

Offline: require cache / extract / root; clear error if missing.

## GCC snapshot (local prefix)

Debian publishes a rolling **gcc-snapshot** package (Sid): toolchain files under a versioned
prefix inside the `.deb`, not as a drop-in replacement for `/usr/bin/g++`. That makes it a good
fit for the same “point cuppa at a prefix” model as `--clang-root=`.

### Where to get the package

- Package details: [Debian Sid `gcc-snapshot`](https://packages.debian.org/sid/gcc-snapshot)
- Pool (`.deb` files): [debian pool `gcc-snapshot`](https://deb.debian.org/debian/pool/main/g/gcc-snapshot/)
  (any official Debian mirror’s `pool/main/g/gcc-snapshot/` works)

Cuppa does **not** need to `apt install` the package. Prefer downloading the `.deb` and
extracting it into a user-owned directory (or into `dependencies_root/toolchains/gcc/…` once
`--gcc-root=` / discover lands).

### Manual extract (document for consumers; first GCC slice)

A `.deb` is an `ar` archive whose payload is usually `data.tar.xz` (or `.zst`). Example recipe
after downloading `gcc-snapshot_*_amd64.deb`:

```sh
# Extract the contents of the .deb archive
ar x gcc-snapshot_*_amd64.deb

# Extract the actual file payload into a local directory
mkdir -p gcc-snapshot-root
tar -xf data.tar.* -C gcc-snapshot-root/

# Optional: clean up the temporary archive members and the .deb
rm -f control.tar.* data.tar.* debian-binary gcc-snapshot_*_amd64.deb
```

The usable compiler prefix is somewhere under that tree (typically a path containing `bin/g++`
— confirm with `find gcc-snapshot-root -type f -name g++`). Point cuppa at **that** prefix:

```sh
cuppa -D --dbg --gcc-root=/path/to/prefix/with/bin/g++
# or, once registered / discovered:
cuppa -D --dbg --toolchains=gcc16_local_a1b2c3d4
```

### Design notes for the GCC slice

| Topic | Direction |
|-------|-----------|
| Flag | `--gcc-root=` mirrors `--clang-root=` (symmetric; avoid a premature generic `--toolchain-root=` until a third family needs it) |
| Probe | Require `bin/g++` (and resolve `gcc`, `g++` version the way Clang resolves `clang++`) |
| Register | `gcc{major}_local_{hash}` from the prefix path, unless the user supplies a qualifier |
| Discover | Scan `dependencies_root/toolchains/gcc/*` on start, same as Clang |
| `.deb` as `--toolchain-archive=` | Optional later (`tc-dep-gcc-deb`): download + `ar`/`tar` into storage; not required to unlock `--gcc-root=` |
| System package | Out of scope — never `dpkg -i` from cuppa |

## Phases

| Id | Work | Status |
|----|------|--------|
| `tc-dep-plan` | This plan + index | done |
| `tc-dep-clang-root` | `--clang-root=` + naming + register before/with `add_toolchains` | done |
| `tc-dep-archive` | `--toolchain-archive=` public HTTPS / file download + extract | done |
| `tc-dep-discover` | Start-up scan of cached extracts; `--toolchains=` without archive URL | done |
| `tc-dep-docs` | toolchains.adoc + CHANGELOG | done |
| `tc-dep-list` | `--list-dependencies` / downloads show `toolchain` / `clang` | done (classify + walk) |
| `tc-dep-remove` | `--force-wipe-*` with `[toolchain]…`; project remove/purge/wipe N/A | done (force-wipe path) |
| `tc-dep-pr` | Land first slice via PR (cites [#160](https://github.com/ja11sop/cuppa/issues/160)) | in progress |
| `tc-dep-gcc-root` | `--gcc-root=` + naming + discover under `toolchains/gcc/`; docs for `.deb` extract | later |
| `tc-dep-gcc-deb` | Optional: treat a `.deb` URL/path as `--toolchain-archive=` for gcc-snapshot | later |
| `tc-dep-url-sugar` | Optional URL token in `--toolchains=` (see note above) | later |
| `tc-dep-profiles` | [#127](https://github.com/ja11sop/cuppa/issues/127) `--profiles` / `-fprofiles` | later |
| `tc-dep-actions` | Authenticated Actions artifact URLs | later |

## Related

- Type selectors for cross-type name clashes (`[gitlab]boost` vs `[archive]boost`) — see
  [`boost-updates.md`](boost-updates.md); not required for the first Clang archive PR.
- Report / judgement-tree polish that landed beside this work:
  [`console-report-patterns.md`](console-report-patterns.md) / [#161](https://github.com/ja11sop/cuppa/issues/161).
