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

## Why

Under `--terse-output`, project sources already use `<working>` / `<final>` /
`<artefacts>`. Location libraries still print the storage folder:

```text
compile · ~/_cuppa/_download/git_https_github.com__fmtlib_fmt.git@master/src/format.cc
       → _build/git_https_github.com__fmtlib_fmt.git@master/gcc16/dbg/x86_64/cxx2c/working/src/format.o
```

Projects already have short registration names. Example from
`order_matcher/sconstruct`: `fmt`, `date`, `quince`, `quince-postgresql`,
`cpp_jwt`, … plus packages such as `boost_package`, and many `develop=` siblings
under `../../cplx_core/…`.

## Settled design

### Path shape: nested roots + shared `<variant>`

**Nested composition.** A flat Boost-style
`<fmt> = ~/_cuppa/_download/git_https_…@master` is only a prefix hint:
`_build/<fmt>/<variant>/working/…` is not a real path unless Cuppa also invents
`<fmt_working>` / `<fmt_final>` (or lies). That scales as **N deps × 2** tokens
and fights the existing `<working>` / `<final>` vocabulary.

Nested roots stay truthful and scale to packages:

```text
→ [location] <dependencies> = ~/_cuppa/_download
→ [location] <fmt> = git_https_github.com__fmtlib_fmt.git@master
→ [location] <date> = git_https_github.com__HowardHinnant_date.git@master
→ [location] <quince> = git_https_github.com__j0nnyw_quince.git@master
→ [location] <quince-postgresql> = git_https_github.com__j0nnyw_quince_postgresql.git@master
→ [location] test/matching_engine · gcc16_dbg_x86_64_cxx2c · <variant> = gcc16/dbg/x86_64/cxx2c
→ [location] test/matching_engine · gcc16_dbg_x86_64_cxx2c · <working> = _build/test/matching_engine/<variant>/working
→ [location] test/matching_engine · gcc16_dbg_x86_64_cxx2c · <final> = _build/test/matching_engine/<variant>/final
→ [location] test/matching_engine · gcc16_dbg_x86_64_cxx2c · <artefacts> = _artefacts

compile · <dependencies>/<fmt>/src/format.cc → _build/<fmt>/<variant>/working/src/format.o
compile · <dependencies>/<date>/src/tz.cpp → _build/<date>/<variant>/working/src/tz.o
compile · <dependencies>/<quince>/src/sql.cpp → _build/<quince>/<variant>/working/src/sql.o
```

Later (same grammar): `<packages>/<boost_package>/…`. Develop trees that are not
under `dependencies_root` keep a non-nested map
(`<baa> = ../../cplx_core/baa` or `~/…`) — only nest when the resolved `local()`
is contained in a registered parent root.

**Reject** `<fmt_working>` / `<fmt_final>` as the default design.

Migrate today's Boost author map from flat `<boost> = _download/boost_…` to the
same nested rule once the parent root for that extract is known
(`<dependencies>` for classic download Boost).

### Token name: always dependency registration `_name`

Use the name Cuppa already registers for `BuildWith` / `default_dependencies` /
removal selectors — not URL leaf guessing.

Real `order_matcher` tokens:

| Registration `_name` | Typical resolved source root (offline download) |
|----------------------|--------------------------------------------------|
| `fmt` | `~/_cuppa/_download/git_https_github.com__fmtlib_fmt.git@master` |
| `date` | `…/git_https_github.com__HowardHinnant_date.git@master` |
| `quince` | `…/git_https_github.com__j0nnyw_quince.git@master` |
| `quince-postgresql` | `…/git_https_github.com__j0nnyw_quince_postgresql.git@master` |
| `cpp_jwt` | `…/git_https_github.com__j0nnyw_cpp-jwt.git@master` |
| `boost_package` | package/develop tree (`../../packages/boost` or registry extract) |
| `baa` (etc.) | develop `../../cplx_core/baa` when develop is active; else download folder |

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
2. **Per-dep source map** — on location/package resolve,
   `label_terse_location(env, dep._name, local(), scope="sconstruct")`. Map RHS
   shown relative to parent when nested (`git_https_…@master`), else project/`~/`
   display as today.
3. **Build-tree rewrite** — extend `_locate` (not N new tokens): under
   `abs_build_root`, if the first segment equals a registered dep's
   `local_folder`, emit `_build/<name>/…`; then replace `env['tool_variant_dir']`
   with `<variant>`.
4. **Builtin `<variant>`** — from `tool_variant_dir`; print on variant begin;
   also allow `<working>` / `<final>` map RHS to contain `<variant>`.
5. **Transform sources** — route compile/markdown sources through the same
   locator (today `_compile_file_parts` in `cuppa/progress.py` uses
   `_display_source_path` only, so tokens never apply to the left of `→`).
6. **Hooks** — `cuppa/build_with_location.py` (`create` /
   `build_library_from_source`) and the existing Boost
   `label_terse_location` call site; package path in a follow-up slice if needed.
7. **Tests** — unit cases with `order_matcher`-shaped paths (`fmt` / `date` /
   `quince` folders under a fake dependencies root +
   `_build/<folder>/<tool_variant>/working/…`); update Boost location
   expectations to nested form.

## Work slices

| Slice | Deliverable | Notes |
|-------|-------------|-------|
| A | This plan + ROADMAP / design index + amend terse-delegated refusal | This commit |
| B | Nested `_locate` + `<variant>` + transform sources use locator | Core display |
| C | Register `<dependencies>` + per-dep `_name`; migrate Boost map | Structured hooks |
| D | Unit tests + `order_matcher` soak | |
| E | `<packages>` nesting when package roots are known | May follow B/C |

## Non-goals

- Path-sniffing unregistered trees under `dependencies_root`
- Per-dep `<fmt_working>` / `<fmt_final>`
- Guessing tokens from URL leaves
- Changing on-disk layout or `local_folder` naming
- Restyling console reports or non-terse transcripts

## Refusal rules

| Request | Response |
|---------|----------|
| Infer tokens from `_download` folder names alone | Refuse; register from dependency `_name` + resolved `local()` |
| Invent `<fmt_working>` / `<fmt_final>` per dependency | Refuse; use nested roots + shared `<variant>` |
| Guess `<date>` from a URL when `_name` is `quince_date_lib` | Refuse; token is registration `_name` |
| Change storage folder naming to short names | Refuse; display-only rewrite |
| Ship inside the native-output PR | Refuse; already landed as [#354](https://github.com/ja11sop/cuppa/pull/354) |

## Success criteria (soak on `order_matcher`)

1. Sconstruct/sconscript begin shows `<dependencies>` and per-dep maps for `fmt`,
   `date`, `quince`, … using registration names.
2. Compile lines use
   `<dependencies>/<fmt>/src/format.cc → _build/<fmt>/<variant>/working/src/format.o`
   (and the same for `date` / `quince`).
3. Project-local sources stay as today
   (`test/matching_engine/response_translator.cpp → <working>/…`).
4. Develop-active `baa` maps to the develop path without falsely nesting under
   `<dependencies>`.
5. Existing Boost terse location updated to the nested convention; unit tests
   green.

## Related

- Location map grammar: [`terse-delegated-output.md`](terse-delegated-output.md)
- Terse status lines: [`terse-build-output.md`](terse-build-output.md)
- Channel map: [`console-channels.md`](console-channels.md)
- Boost `-c` / extract `b2`: [`deep-clean.md`](deep-clean.md)
