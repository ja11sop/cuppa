# Plan: Toolchains as dependencies

- **Status:** in progress
- **Related:** [`ROADMAP.md`](../../ROADMAP.md); umbrella [#160](https://github.com/ja11sop/cuppa/issues/160); Profiles follow-on [#127](https://github.com/ja11sop/cuppa/issues/127); type-selector note in [`boost-updates.md`](boost-updates.md); report polish [#161](https://github.com/ja11sop/cuppa/issues/161)
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
5. Enable [#127](https://github.com/ja11sop/cuppa/issues/127) `--profiles` on capable Clangs
   (separate issue; not part of the first PR).

## Non-goals (this phase)

- Auto “latest Profiles release”
- GCC / MSVC archive toolchains
- Actions artifact API downloads
- Full wipe UX polish beyond force-wipe + list (done for classify / `[D]` / session-name wipe)
- Judgement-tree / list-scope polish — tracked in [#161](https://github.com/ja11sop/cuppa/issues/161)

## Naming

Registered toolchain:

`clang{major}_{sanitised_release_tag}`

Example: Release tag `profiles-2026-08-07-27` → **`clang24_profiles_2026_08_07_27`**.

Do not register as plain `clang24` (collides with PATH Clang). `--name()` / build folders use
this full id. Wildcards: `clang24_profiles*`.

`--clang-root=` without a tag: `clang{major}_local_{short_path_hash}`.

Force-wipe accepts both storage identity and session name:

- `[toolchain]clang/profiles_2026_08_07_27`
- `[toolchain]clang24_profiles_2026_08_07_27`

## CLI

```sh
cuppa -D --dbg \
  --toolchain-archive=https://github.com/cppalliance/clang/releases/download/profiles-2026-08-07-27/clang-profiles-linux-x86_64.tar.gz \
  --toolchains=clang24_profiles_2026_08_07_27
```

- `--toolchain-archive=` — public archive URL or `file://` / local path to `.tar.gz` / `.zip`
- `--clang-root=` — existing install prefix containing `bin/clang++`
- If archive/root is set and `--toolchains=` omitted → auto-select the registered name(s)
- Later sessions: scan extracts under `dependencies_root/toolchains/clang/`, register each as
  available, skip if the derived name is already in the pre-registered toolchain map, and
  select with `--toolchains=clang24_profiles_…` (no auto-select for cached-only discovery)
- Listing: type `toolchain`; selected `--toolchains=` extract is **referenced**; drop stale
  inventory for the `toolchains/` parent folder (no duplicate under source archives);
  verbose LOCATION uses `[D]` when the download archive is present

### Why not `--toolchains=https://…` (kept separate for now)

`ParseToolchainsOption` is names + wildcards. Keep **supply** (`--toolchain-archive=`) and
**selection** (`--toolchains=`) as separate flags.

That still matches the common “only URL” case via auto-select: omitting `--toolchains=` after
`--toolchain-archive=` selects the registered name for this session. Putting the URL *inside*
`--toolchains=` would feel natural for that one case, but it muddies:

- comma-lists and wildcards (`gcc,clang24_profiles*`)
- error attribution (fetch failed vs unknown name)
- parallel supply via `--clang-root=` (not a URL)
- future multi-archive / “fetch but do not select”

**Open follow-up (`tc-dep-url-sugar`):** optionally accept a URL token in `--toolchains=` as
sugar for “prepare this archive and select it”, while keeping `--toolchain-archive=` as the
explicit supply flag. Not required for the first PR.

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
| `tc-dep-clang-root` | `--clang-root=` + naming + register before/with `add_toolchains` | done |
| `tc-dep-archive` | `--toolchain-archive=` public HTTPS / file download + extract | done |
| `tc-dep-discover` | Start-up scan of cached extracts; `--toolchains=` without archive URL | done |
| `tc-dep-docs` | toolchains.adoc + CHANGELOG | done |
| `tc-dep-list` | `--list-dependencies` / downloads show `toolchain` / `clang` | done (classify + walk) |
| `tc-dep-remove` | `--force-wipe-*` with `[toolchain]…`; project remove/purge/wipe N/A | done (force-wipe path) |
| `tc-dep-pr` | Land first slice via PR (cites [#160](https://github.com/ja11sop/cuppa/issues/160)) | in progress |
| `tc-dep-url-sugar` | Optional URL token in `--toolchains=` (see note above) | later |
| `tc-dep-profiles` | [#127](https://github.com/ja11sop/cuppa/issues/127) `--profiles` / `-fprofiles` | later |
| `tc-dep-actions` | Authenticated Actions artifact URLs | later |

## Related

- Type selectors for cross-type name clashes (`[gitlab]boost` vs `[archive]boost`) — see
  [`boost-updates.md`](boost-updates.md); not required for the first Clang archive PR.
- Report / judgement-tree polish that landed beside this work:
  [`console-report-patterns.md`](console-report-patterns.md) / [#161](https://github.com/ja11sop/cuppa/issues/161).
