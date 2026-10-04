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
- **Impact:** minor — terse file cells, resolve bookends, and `[location]` maps;
  default transcript unchanged; on-disk layout unchanged

## When the maps print (resolve vs build)

The first soak sketch hung sconstruct-scoped maps under
`sconstruct … [progress] · begin`. That line is a `NotifyProgress` node. It
runs **after** `scons: Building targets ...`. Git updates, clones, package
collect, and `Location.local()` happen earlier, during
`scons: Reading SConscript files ...`, while `_pre_sconscript_phase_` is set
and `NotifyProgress.add` is a no-op.

That distinction is load-bearing:

- A `[location]` map is only useful for a line that prints **after** the token
  is registered.
- `cuppa: location: [info] Updating […]` already runs in the read phase. If
  those become terse one-liners that say `<fmt>`, the map must exist **before**
  the update, and both must exist **before** `sconstruct [progress] · begin`.
- Resolve work has **no action fraction**. The **percent** column still
  applies and stays **`0%`** on the resolve bookends. `N/A` would break the
  column. Do not invent `0/36`. After sconscripts are evaluated,
  `[progress] · begin` may jump (up-to-date nodes count as done). Git
  update/clone does not move the percent.

Do **not** reuse `[progress]` for this span. `[progress]` is a scope
checkpoint on the action ledger (`begin` / `end`). Resolve can stall for
minutes and has no denominator yet. Do **not** reuse `[launch]` / `[done]`;
those mean a foreign graph (CMake/`b2`). Same *shape* as launch (open,
live children, close), different badges.

### Settled resolve bookend

```text
sconstruct   0% [prepare] ~/src/app/sconstruct · resolve · 35 declared dependencies
              → [location] <dependencies> = ~/_cuppa/_download · root
              → [location] <fmt> = git_https_github.com__fmtlib_fmt.git@master · repository
              → [update]   <fmt> · master · 9197f515
              → [location] <google_cloud_cpp> = google-cloud-cpp/3.9.0 · package
              → [location] <protobuf> = protobuf/36.1 · package · transitive
              → [collect]  <protobuf> · 36.1
sconstruct   0% [ready] ~/src/app/sconstruct · resolve · 42 dependencies (35 declared, 7 transitive) · 34 repositories · 8 packages
scons: done reading SConscript files.
scons: Building targets ...
sconstruct  11% [progress] ~/src/app/sconstruct · begin · 6 sconscripts · 1 variant · 4/36 actions
```

| Piece | Choice | Why |
|-------|--------|-----|
| Open badge | `[prepare]` | Cuppa is about to resolve trees; may stall. Info+bold, like `[launch]` / `[progress]`. Not `[initiate]` / `[process]`. |
| Close badge | `[ready]` | Maps and totals known; build can start. Not `[done]` (delegated close). |
| Action | `resolve` | Same word on both ends (as `cmake-build` on launch/done). Scope column already says `sconstruct`. |
| Open summary | `35 declared dependencies` | What is known: `default_dependencies`. Not bare `35 declared`. |
| Close summary | `42 dependencies (35 declared, 7 transitive) · 34 repositories · 8 packages` | Resolved graph. Parenthetical qualifies the total. Kind counts unqualified. |
| Percent | `0%` | No action ledger yet. Not `N/A`. Not `0/36`. |
| Children | Live `→` lines during `BuildWith` | Honest progress. Do not buffer until close. |
| Maps | Under `[prepare]`, not on `[progress] · begin` | Token then event. Do not reprint on sconstruct begin or `[ready]`. |
| Variant maps | Stay on variant `[progress] · begin` | Build-layout, not resolve. |

Offline with nothing to update is still honest: open, location maps, close.

### Update / clone / collect children (slice F)

Those `logger.info("Updating […]")` lines are **not** ordinary configure
commentary. They mutate trees, can take seconds, and `-Q` currently hides
them. Under `--terse-output` they are uncounted children of `[prepare]`,
same `→` indent as `[location]`. Stay under `-Q`. Failure keeps the
existing warn/error (and enough URL/path to diagnose). Do not turn
cuppaconfig load, version, default-profile dumps, or the sconscript path
list into this channel ([`build-log-hygiene.md`](build-log-hygiene.md)).

Print the `[location]` map **before** the retrieve, then the child **after**
the work so its colour can match `[ok]` / `[warn]` / `[error]`. A slow clone
still has the map as the in-flight cue; do not pre-colour a child as success.

| Work | Badge | Avoid |
|------|--------|--------|
| Existing SCM tree | `[update]` | |
| New working copy | `[clone]` | |
| Package archive from the registry | `[collect]` | `[fetch]` (sounds like `git fetch`) |
| Source tarball | `[download]` | |

Ten-column field so they line up with `[location]` (pad outside the colour).
Success uses the `[ok]` success colour; failure uses warn/error. Not an
action tally. Not `[progress]`. Git tag-force stays `[update]`.
`[location]` is bold muted grey (`as_emphasised` on `as_subdued`), not
notice yellow and not the bold plain action ink — amber reads as a status
beside green `[update]`.

Do not buffer the whole resolve to keep the close-line totals. A retrieve
child prints after the work so its colour can be `[ok]` / `[warn]` /
`[error]`. In-flight lag is accepted until
[`quiet-tty-heartbeat.md`](quiet-tty-heartbeat.md); the `[location]` map
is the live cue. Totals wait for `[ready]`.

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
sconstruct   0% [prepare] ~/src/app/sconstruct · resolve · 19 declared dependencies
              → [location] <dependencies> = ~/_cuppa/_download · root
              → [location] <fmt> = git_https_github.com__fmtlib_fmt.git@master · repository
              → [location] <date> = git_https_github.com__HowardHinnant_date.git@master · repository
              → [location] <quince> = git_https_github.com__j0nnyw_quince.git@master · repository
sconstruct   0% [ready] ~/src/app/sconstruct · resolve · 19 dependencies · 19 repositories
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
2. **Resolve bookend** — `[prepare]` before default `BuildWith`, live maps
   and retrieve children, `[ready]` after with resolved totals. Not a
   `NotifyProgress` node. Do not reprint maps on sconstruct
   `[progress] · begin` or on `[ready]`.
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
| C | `[prepare]` / `[ready]` · `resolve` bookend + register `<dependencies>` / per-dep `_name`; migrate Boost map | Done (was `[progress] · read`; bookend replaces it) |
| D | Unit tests + soak on a multi-location project | Done |
| G | Located product cells on `link` / `archive` / `index` | Done |
| E | `<packages>` nesting when package roots are known | Done |
| F | Live `→ [update]` / `[clone]` / `[collect]` / `[download]` under `[prepare]` | Done (unit); stay under `-Q`; not configure logs |

## Non-goals

- Path-sniffing unregistered trees under `dependencies_root`
- Per-dep `<fmt_working>` / `<fmt_final>`
- Guessing tokens from URL leaves
- Changing on-disk layout or `local_folder` naming
- Restyling console reports or non-terse transcripts
- Turning cuppaconfig / version / default-profile / sconscript-list info logs into `[prepare]` children
- Reusing `[launch]` / `[done]` for resolve (those are the foreign-graph pair)
- Buffering retrieve events until `[ready]` (hides slow work)

## Refusal rules

| Request | Response |
|---------|----------|
| Infer tokens from `_download` folder names alone | Refuse; register from dependency `_name` + resolved `local()` |
| Invent `<fmt_working>` / `<fmt_final>` per dependency | Refuse; use nested roots + shared `<variant>` |
| Guess `<date>` from a URL when `_name` is `quince_date_lib` | Refuse; token is registration `_name` |
| Change storage folder naming to short names | Refuse; display-only rewrite |
| Hang sconstruct-scoped maps only on `[progress] · begin` | Refuse; too late for resolve children |
| Reuse `[launch]` / `[done]` for resolve | Refuse; those close a foreign graph |
| Buffer `[update]` / `[clone]` / `[collect]` until `[ready]` | Refuse; the span exists so slow work is visible |
| Reuse `[progress] · begin` / `end` for CMake/`b2` | Refuse; that is the delegated-plan rule, unchanged |
| Print `N/A` in the percent column | Refuse; resolve bookends use `0%` |
| Print `0/36` (or `0/0`) on `[prepare]` / `[ready]` | Refuse; no action denominator yet |
| Print `[prepare]` / `[ready]` maps on `-c` | Refuse; clean is not a build transcript |
| Prefix every product with `<final>/` | Refuse; only this variant's final dir is `<final>` |

## Success criteria (soak)

1. `[prepare]` / `[ready]` print at `0%` before `scons: Building targets ...`,
   with live `<dependencies>` and per-dep maps for `fmt`, `date`, `quince`, …
   using registration names. Those maps are **not** repeated on sconstruct
   `[progress] · begin` or on `[ready]`. The open line says
   `N declared dependencies`. The close line has the resolved totals.
2. Compile lines use
   `<dependencies>/<fmt>/src/format.cc → _build/<fmt>/<variant>/working/src/format.o`
   (and the same for `date` / `quince`).
3. Project-local sources stay as today
   (`test/orders/widget.cpp → <working>/…`).
4. A develop-active location maps to the develop path without falsely nesting
   under `<dependencies>`.
5. Existing Boost terse location updated to the nested convention; unit tests
   green.
6. `-c` / `--clean` does **not** print `[prepare]` / `[ready]` or sconstruct
   location maps. Clean is resolve-then-remove; the map dump is noise next to
   `Removed …` lines.
7. Location maps under `[prepare]` use the same `→` indent as variant
   maps (align `[location]` with `[prepare]` / `[progress]`).
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
    classmethod; attributes live on the class). `[ready]` prints after default
    `BuildWith`, so traveling-manifest packages are in the totals. When they
    are, the close line is
    `N dependencies (D declared, T transitive) · …`. Transitive maps
    append `· transitive` (info colour); declared maps stay unmarked.
    Retrieve children (`[update]` / `[clone]` / `[collect]` / `[download]`)
    print live under `[prepare]`, after that dep's `[location]` map.
    `<packages>` prints on variant begin as
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
