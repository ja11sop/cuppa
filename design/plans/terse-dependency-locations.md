# Plan: terse dependency location maps

- **Status:** proposal
- **Related:** [`ROADMAP.md`](../../ROADMAP.md) — Build console output (`console-terse-dep-locations`);
  companions [`terse-build-output.md`](terse-build-output.md) /
  [`terse-delegated-output.md`](terse-delegated-output.md) (done on master
  [#353](https://github.com/ja11sop/cuppa/pull/353)); channel map
  [`console-channels.md`](console-channels.md); native modifier
  [`native-toolchain-output.md`](native-toolchain-output.md) (done on master
  [#354](https://github.com/ja11sop/cuppa/pull/354))
- **Updated:** 2026-10-04
- **Impact:** minor — terse file cells and `[location]` maps only; default transcript
  unchanged; on-disk layout unchanged

## When the maps print (read vs build)

The first soak sketch hung sconstruct-scoped maps under
`sconstruct … [progress] · begin`. That line is a `NotifyProgress` node. It
runs **after** `scons: Building targets ...`. Git updates, clones, package
latest resolve, and `Location.local()` happen earlier, during
`scons: Reading SConscript files ...`, while `_pre_sconscript_phase_` is set
and `NotifyProgress.add` is a no-op.

That distinction is load-bearing:

- A `[location]` map is only useful for a line that prints **after** the token
  is registered.
- `cuppa: location: [info] Updating […]` already runs in the read phase. If
  those become terse one-liners that say `<fmt>`, the map must exist **before**
  the first `sconstruct [progress] · begin`.
- Read work has **no action fraction** (`4/36`). The **percent** column still
  applies: it is actions accounted this run, and it starts at zero
  ([`terse-build-output.md`](terse-build-output.md)). `[progress] · read` is the
  first checkpoint, so **`0%`**. `N/A` would break the column now that the line
  uses `[progress]` chrome. Do not invent `0/36` — the denominator does not
  exist yet. After sconscripts are evaluated, `[progress] · begin` may jump
  (up-to-date nodes count as done). That jump is the ledger appearing, not work
  done during `read`. Git update/clone does not move the percent.

Prefer **`[progress] · read`**, not a new `[read]` badge. Checkpoint chrome stays
`[progress]`; the action cell is `read`, same slot as `begin` / `end`. That
matches SCons "Reading SConscript files" without a third badge family next to
`[progress]` and `[location]`. The delegated-plan refusal is only "do not reuse
`begin`/`end` for CMake/`b2`" — a new action name on the same chrome is fine.
Not `[pre-read]` (it is during reading). Not `[configure]` (`~/.cuppaconfig`).
Not `[process]`.

### Settled read-phase line

```text
sconstruct   0% [progress] ~/src/app/sconstruct · read · 19 dependencies · 12 location · 7 package
              → [location] <dependencies> = ~/_cuppa/_download
              → [location] <fmt> = git_https_github.com__fmtlib_fmt.git@master
              → [location] <date> = git_https_github.com__HowardHinnant_date.git@master
              → [location] <quince> = git_https_github.com__j0nnyw_quince.git@master
scons: done reading SConscript files.
scons: Building targets ...
sconstruct  11% [progress] ~/src/app/sconstruct · begin · 6 sconscripts · 1 variant · 4/36 actions
```

| Piece | Choice | Why |
|-------|--------|-----|
| Badge | `[progress]` | Same checkpoint chrome as `begin` / `end`. Do not invent `[read]`. |
| Action | `read` | Same cell as `begin`. Summary after that: dependency counts, not action tallies. |
| Percent | `0%` | Same column as every `[progress]` line. Nothing in the action ledger is accounted yet. Not `N/A`. |
| Fraction | omit | No `0/36` / `0/0`. The denominator is not known until sconscripts have been added. |
| Maps | Hang here, **not** on `[progress] · begin` | Tokens must exist for later read-phase one-liners. Do not reprint the same maps on sconstruct begin. |
| Variant maps | Stay on variant `[progress] · begin` | `<working>` / `<final>` / `<artefacts>` / `<variant>` are build-layout, not resolve. |

Per-dep maps may print **lazily** as each dependency resolves (map line, then
any update for that name) instead of as one block. Lazy is better if update
one-liners land in the same PR. A single block at the start of `cuppa.run`
resolve is enough for compile-line rewriting alone.

### Update / clone one-liners (follow-on, same family)

Those `logger.info("Updating […]")` lines are **not** ordinary configure
commentary. They mutate trees, can take seconds, and `-Q` currently hides
them. They sit between log and transcript.

Under `--terse-output` they become **uncounted children of `[progress] · read`**,
using the same `→` indent as nested copies / `[location]`:

```text
sconstruct   0% [progress] ~/src/app/sconstruct · read · 10 dependencies · 8 location · 2 package
              → [location] <dependencies> = ~/_cuppa/_download
              → [location] <fmt> = git_https_github.com__fmtlib_fmt.git@master
              → [update] <fmt> · main · 9197f515
              → [location] <rapidjson> = git_https_github.com__miloyip_rapidjson.git@master
              → [update] <rapidjson> · master · 24b5e7a
              → [clone] <libfoo> · master · a1b2c3d
```

Stay under `-Q` (like `[progress]`, unlike `cuppa: configure: [info]`). Failure
keeps the existing warn/error (and enough URL/path to diagnose). Do not turn
cuppaconfig load, version, default-profile dumps, or the sconscript path list
into this channel — those stay logs ([`build-log-hygiene.md`](build-log-hygiene.md)).

Badges for the child line: `[update]`, `[clone]`, `[fetch]` (package download)
as needed. Not `[ok]` with a fake tally. Not `[progress]`.

This child-line slice can land after nested `_locate` (maps without updates
still pay off on compile lines). Do not block map rewriting on inventing the
whole read transcript.

## Why

Under `--terse-output`, project sources already use `<working>` / `<final>` /
`<artefacts>`. Location libraries still print the storage folder:

```text
compile · ~/_cuppa/_download/git_https_github.com__fmtlib_fmt.git@master/src/format.cc
       → _build/git_https_github.com__fmtlib_fmt.git@master/gcc16/dbg/x86_64/cxx2c/working/src/format.o
```

Projects already have short registration names on `location_dependency` /
`package_dependency` (`fmt`, `date`, `quince`, `boost_package`, …) and often
`develop=` trees beside the project.

## Settled design

### Path shape: nested roots + shared `<variant>`

**Nested composition.** A flat Boost-style
`<fmt> = ~/_cuppa/_download/git_https_…@master` is only a prefix hint:
`_build/<fmt>/<variant>/working/…` is not a real path unless Cuppa also invents
`<fmt_working>` / `<fmt_final>` (or lies). That scales as **N deps × 2** tokens
and fights the existing `<working>` / `<final>` vocabulary.

Nested roots stay truthful and scale to packages:

```text
sconstruct   0% [progress] ~/src/app/sconstruct · read · …
              → [location] <dependencies> = ~/_cuppa/_download
              → [location] <fmt> = git_https_github.com__fmtlib_fmt.git@master
              → [location] <date> = git_https_github.com__HowardHinnant_date.git@master
              → [location] <quince> = git_https_github.com__j0nnyw_quince.git@master
              → [location] <quince-postgresql> = git_https_github.com__j0nnyw_quince_postgresql.git@master
sconstruct  11% [progress] ~/src/app/sconstruct · begin · 6 sconscripts · 1 variant · 4/36 actions
              → [location] test/orders · gcc16_dbg_x86_64_cxx2c · <variant> = gcc16/dbg/x86_64/cxx2c
              → [location] test/orders · gcc16_dbg_x86_64_cxx2c · <working> = _build/test/orders/<variant>/working
              → [location] test/orders · gcc16_dbg_x86_64_cxx2c · <final> = _build/test/orders/<variant>/final
              → [location] test/orders · gcc16_dbg_x86_64_cxx2c · <artefacts> = _artefacts

compile · <dependencies>/<fmt>/src/format.cc → _build/<fmt>/<variant>/working/src/format.o
compile · <dependencies>/<date>/src/tz.cpp → _build/<date>/<variant>/working/src/tz.o
compile · <dependencies>/<quince>/src/sql.cpp → _build/<quince>/<variant>/working/src/sql.o
```

Later (same grammar): `<packages>/<boost_package>/…`. Develop trees that are not
under `dependencies_root` keep a non-nested map
(`<libfoo> = ../libfoo` or `~/…`) — only nest when the resolved `local()`
is contained in a registered parent root.

**Reject** `<fmt_working>` / `<fmt_final>` as the default design.

Migrate today's Boost author map from flat `<boost> = _download/boost_…` to the
same nested rule once the parent root for that extract is known
(`<dependencies>` for classic download Boost).

### Token name: always dependency registration `_name`

Use the name Cuppa already registers for `BuildWith` / `default_dependencies` /
removal selectors — not URL leaf guessing.

Example tokens (public location/package names):

| Registration `_name` | Typical resolved source root (offline download) |
|----------------------|--------------------------------------------------|
| `fmt` | `~/_cuppa/_download/git_https_github.com__fmtlib_fmt.git@master` |
| `date` | `…/git_https_github.com__HowardHinnant_date.git@master` |
| `quince` | `…/git_https_github.com__j0nnyw_quince.git@master` |
| `quince-postgresql` | `…/git_https_github.com__j0nnyw_quince_postgresql.git@master` |
| `boost_package` | package/develop tree (`../packages/boost` or registry extract) |
| `libfoo` (develop) | `../libfoo` when develop is active; else download folder |

Accept `<boost_package>` (do not invent `<boost>` from the package slug) so
tokens stay aligned with selectors; authors who want `<boost>` already control
`_name` in the sconstruct / package factory.

### Registration rule

Keep refusing **folder sniffing** of `_download` names. Allow **structured
registration**: when a dependency resolves `local()` / `local_folder()`, call
`label_terse_location` with `_name` and the resolved path(s).

This amends the older terse-delegated refusal that banned inferring `<boost>`
from `_download`: the ban was on path sniffing, not on registering a known
dependency's resolved tree.

## Implementation sketch

1. **Parent roots** — sconstruct-scoped `<dependencies>` from `dependencies_root`;
   add `<packages>` when a package install/develop root is known (same nesting
   grammar; may land in a second slice if package path discovery is thicker).
2. **Read-phase checkpoint** — emit one
   `sconstruct 0% [progress] … · read · …` line when resolve starts (not a
   `NotifyProgress` node). Print sconstruct-scoped maps under it. Do not reprint
   them on `sconstruct [progress] · begin`.
3. **Per-dep source map** — on location/package resolve,
   `label_terse_location(env, dep._name, local(), scope="sconstruct")`. Map RHS
   shown relative to parent when nested (`git_https_…@master`), else project/`~/`
   display as today. Print the map as soon as the path is known if update
   one-liners need the token on the next line.
4. **Build-tree rewrite** — extend `_locate` (not N new tokens): under
   `abs_build_root`, if the first segment equals a registered dep's
   `local_folder`, emit `_build/<name>/…`; then replace `env['tool_variant_dir']`
   with `<variant>`.
5. **Builtin `<variant>`** — from `tool_variant_dir`; print on variant begin;
   also allow `<working>` / `<final>` map RHS to contain `<variant>`.
6. **Transform sources** — route compile/markdown sources through the same
   locator (today `_compile_file_parts` in `cuppa/progress.py` uses
   `_display_source_path` only, so tokens never apply to the left of `→`).
7. **Hooks** — `cuppa/build_with_location.py` (`create` /
   `build_library_from_source`) and the existing Boost
   `label_terse_location` call site; package path in a follow-up slice if needed.
8. **Tests** — unit cases with location-library paths (`fmt` / `date` /
   `quince` folders under a fake dependencies root +
   `_build/<folder>/<tool_variant>/working/…`); update Boost location
   expectations to nested form.

## Work slices

| Slice | Deliverable | Notes |
|-------|-------------|-------|
| A | This plan + ROADMAP / design index + amend terse-delegated refusal | First commit |
| B | Nested `_locate` + `<variant>` + transform sources use locator | Done |
| C | `[progress] · read` checkpoint + register `<dependencies>` / per-dep `_name`; migrate Boost map | Done |
| D | Unit tests + soak on a multi-location project | Unit done; soak: skip maps on `-c`; unique nest; indent |
| G | Located product cells on `link` / `archive` / `index` | Follow-on; dest `_locate`, not a transform |
| E | `<packages>` nesting when package roots are known | Done; extract on variant begin; identity `name/version` on read |
| F | Terse `→ [update]` / `[clone]` / `[fetch]` children under `[progress] · read` | After C; stay under `-Q`; not configure logs |

## Non-goals

- Path-sniffing unregistered trees under `dependencies_root`
- Per-dep `<fmt_working>` / `<fmt_final>`
- Guessing tokens from URL leaves
- Changing on-disk layout or `local_folder` naming
- Restyling console reports or non-terse transcripts
- Turning cuppaconfig / version / default-profile / sconscript-list info logs into `[progress] · read` children
- Inventing a `[read]` badge instead of `[progress] · read`

## Refusal rules

| Request | Response |
|---------|----------|
| Infer tokens from `_download` folder names alone | Refuse; register from dependency `_name` + resolved `local()` |
| Invent `<fmt_working>` / `<fmt_final>` per dependency | Refuse; use nested roots + shared `<variant>` |
| Guess `<date>` from a URL when `_name` is `quince_date_lib` | Refuse; token is registration `_name` |
| Change storage folder naming to short names | Refuse; display-only rewrite |
| Hang sconstruct-scoped maps only on `[progress] · begin` | Refuse; too late for read-phase update lines |
| Invent a `[read]` badge | Refuse; action cell is `read` on existing `[progress]` chrome |
| Reuse `[progress] · begin` / `end` for CMake/`b2` | Refuse; that is the delegated-plan rule, unchanged |
| Print `N/A` in the percent column | Refuse; `[progress]` uses `0%` until the ledger accounts actions |
| Print `0/36` (or `0/0`) on `[progress] · read` | Refuse; no action denominator yet |
| Print `[progress] · read` maps on `-c` | Refuse; clean is not a build transcript |
| Prefix every product with `<final>/` | Refuse; only this variant's final dir is `<final>` |

## Success criteria (soak)

1. `[progress] · read` prints at `0%` before `scons: Building targets ...`, with
   `<dependencies>` and per-dep maps for `fmt`, `date`, `quince`, … using
   registration names. Those maps are **not** repeated on sconstruct
   `[progress] · begin`.
2. Compile lines use
   `<dependencies>/<fmt>/src/format.cc → _build/<fmt>/<variant>/working/src/format.o`
   (and the same for `date` / `quince`).
3. Project-local sources stay as today
   (`test/orders/widget.cpp → <working>/…`).
4. A develop-active location maps to the develop path without falsely nesting
   under `<dependencies>`.
5. Existing Boost terse location updated to the nested convention; unit tests
   green.
6. `-c` / `--clean` does **not** print `[progress] · read` or sconstruct
   location maps. Clean is resolve-then-remove; the map dump is noise next to
   `Removed …` lines.
7. Location maps under `[progress] · read` use the same `→` indent as variant
   maps (align `[location]` with `[progress]`).
8. Nested tokens are unique: one `<fmt>` even if sconstruct-scoped labels are
   registered from several sconscripts; project-root `#` locations do not wrap
   in-tree sources as `<app>/test/…`; two names on the same extract (e.g.
   `date` and `quince_date_lib`) emit one token.
9. `link` / `archive` / `index` (and other aggregates) show the located product
   (`<final>/management`, `_build/<fmt>/<variant>/final/libfmt.a`), not a bare
   leaf. `run` / `test` / `benchmark` use the same located program cell so a
   test lines up with the `link` that produced it. `test-case` uses that same
   muted `<final>/`, a plain binary name, then the coloured case
   (`<final>/management/case`).
10. Package identity maps print at read as `name/version · package`.
    Source tarballs print as `local_folder · archive`. SCM trees print as
    `local_folder · repository`. The read summary counts those kinds from
    each `default_dependencies` factory's class (`cls.create` is a
    classmethod; attributes live on the class). The read line is printed
    after default `BuildWith`, so traveling-manifest packages are in the
    totals. When they are, the line is
    `N dependencies (D declared, T transitive) · …`. Transitive maps
    append `· transitive` (info colour); declared maps stay unmarked. `<packages>` prints on variant begin as
    `<dependencies>/<package-tool-variant>` (often `rel` while the cell is
    `dbg`). Paths rewrite as `<packages>/<boost_package>/...`. Develop package
    trees stay un-nested. Root and package map values paint every path
    segment and the slashes between them info+bold; a nested parent token
    on the value (`<dependencies>/…`) stays subdued. Two names on one
    extract share the same folder identity on the map (not a home-prefixed
    path).

## Related

- Location map grammar: [`terse-delegated-output.md`](terse-delegated-output.md)
- Terse status lines: [`terse-build-output.md`](terse-build-output.md)
- Channel map: [`console-channels.md`](console-channels.md)
- Boost `-c` / extract `b2`: [`deep-clean.md`](deep-clean.md)
