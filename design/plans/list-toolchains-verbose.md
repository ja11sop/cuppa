# Plan: `--list-toolchains --list-format=verbose`

- **Status:** in progress
- **Related:** [`list-toolchains.md`](list-toolchains.md) (inventory tree on [#170](https://github.com/ja11sop/cuppa/pull/170));
  [`ROADMAP.md`](../../ROADMAP.md) — Toolchains; family pages
  (`toolchain-gcc.adoc` / `toolchain-clang.adoc` / `toolchain-msvc.adoc`);
  GCC link options / GNU ld `-Bstatic`/`-Bdynamic` (language-agnostic driver/linker flags)
- **Updated:** 2026-08-09
- **Next focus:** deferred `list-tc-flag-tables` (table-driven init); otherwise verbose + docs
  are on [#170](https://github.com/ja11sop/cuppa/pull/170)
- **Impact:** minor — verbose list surface + `describe()` API; dialect defaults owned by
  toolchain classes; no intentional change to build flag behaviour

## Why

`--list-toolchains` already answers *which* compilers Cuppa knows and *where* they live. Operators
also need *what Cuppa will pass* for dialects and default compile/link flags per variant — the
same facts that today live only in `toolchains.adoc` tables and in private
`_initialise_toolchain()` / `__default_dialect_flags()` logic.

`--list-format=verbose` is already a CLI choice for list actions, but for toolchains it is a
no-op (same as `text`). Verbose should hang a subdued info subtree under each **driver**, after
the usable Cuppa names.

## Goals

1. Under each driver (after name leaves), when `list_format == 'verbose'`, render subdued info
   nodes for dialects, stdlib (when supported), and default flags.
2. Each toolchain instance exposes `describe()` returning a stable dict; default dialect /
   stdlib / MSVC dialect lists come from the toolchain classes so they cannot drift from builds.
3. Longer term: refactor Gcc / Clang / Cl so default flag *composition* is data Cuppa can both
   apply in `_initialise_toolchain` and report via `describe()` (full table-driven init deferred).
4. Display each option line as a **single string** (space-joined), including **placeholders**
   where Cuppa injects libraries (and any other real injection points).
5. Nested JSON includes the same payload under each driver.
6. Keep non-verbose text output unchanged; keep build flag semantics unchanged.

## Non-goals

- Invoking the compiler to probe `-std=` support.
- Auto-generating family-page flag tables in this slice.
- Per-name info trees when several names share one driver.
- Inventing coverage for MSVC (`cov` omitted when unsupported).
- Inventing fake compile placeholders (`<sources>`, include paths) that Cuppa does not model
  in the toolchain flag tables.

## Clarification: session `--stdcpp`

A `--stdcpp=` on the **same** cuppa invocation as `--list-toolchains` is a session override for
builds. Verbose listing shows the toolchain’s **stored defaults** (what `_initialise_toolchain`
baked in). Session `--stdcpp` does **not** rewrite displayed `c++` lines. Dialects list what
Cuppa accepts for that toolchain; the default dialect also appears inside the `c++` flag string
as `-std=…` / `-std:…`, so readers see it twice by design (summary + concrete flags).

## Native toolchain note (C vs link)

GCC/Clang **link options** (`-rdynamic`, `-Wl,…`, `-Xlinker -Bstatic` / `-Bdynamic`) are
options on the **compiler driver / linker**, not C++-only language options. GNU ld’s
`-Bstatic`/`-Bdynamic` switch archive search behaviour for subsequent `-l` libs regardless of
whether the objects came from `gcc` or `g++`. Cuppa already applies these via `LINKFLAGS` /
`_LIBFLAGS` for both languages. Therefore verbose listing shows separate **`c++`** and **`c`**
compile lines (when the family has both) and one shared **`link`** line — not “CXX-only link”.

## Tree shape (verbose only)

```
… └── <driver path>
        ├── <name> [(default)]
        ├── available dialects: c++2c (default), c++26, c++2b, c++23, …
        ├── usable features: all c++2c, modules (experimental)
        ├── stdlib choices: libstdc++ (default), libc++                 # Clang only
        └── default invocations:
            ├── dbg
            │   ├── c++: -Wall … -std=c++2c <sources>
            │   ├── c: -Wall -g <sources>
            │   └── link: <objects> -rdynamic … <static_libs> … <dynamic_libs>
            ├── cov
            │   ├── c++: … <sources>
            │   ├── c: … <sources>
            │   └── link: <objects> …
            └── rel
                ├── c++: … <sources>
                ├── c: … <sources>
                └── link: <objects> …
```

- Info nodes are **siblings of names** under the driver.
- **Notice/yellow keys:** `available dialects:`, `usable features:`, `stdlib choices:`,
  `default invocations:`, `c++:` / `c:` / `link:`.
- **Normal text:** variant names (`dbg` / `cov` / `rel`) and flag / dialect / feature values.
- **Subdued:** commas in dialect/stdlib/feature lists, `(default)` / `(experimental)`,
  `<placeholder>` tokens, tree stems. Default `-l` libraries stay normal.
- Blank SIZE / LAST USED on info rows.
- Omit any key the toolchain does not have (`c` on MSVC, `cov` on MSVC, stdlib on GCC/MSVC).

## Settled decisions

| Topic | Decision |
|-------|----------|
| Attach point | Under **driver**, after all name leaves |
| Flag | Existing `--list-format=verbose` |
| Style | Info **keys** notice/yellow (`as_notice`); **variant names** normal; **values** normal;
  **commas**, ``(default)`` / ``(experimental)`` qualifiers, and ``<placeholder>`` tokens
  subdued; default ``-l…`` libraries normal; tree stems subdued |
| Variants | `dbg`, `cov` (if supported), `rel` — omit unsupported |
| Parent label | **`default invocations:`** (colon for consistency) |
| Leaf names | **`c++`**, **`c`**, **`link`** under `default invocations:`; omit absent sets |
| Display form | Each invocation is a **quoted string** in verbose text
  (`c++: "-Wall … <sources>"`; quotes subdued); JSON keeps the bare string |
| Placeholders | Compile: trailing `<sources>`. Link: leading `<objects>`; Linux GCC/Clang also
  `<static_libs>` / `<dynamic_libs>` around `-Xlinker -Bstatic` / `-Bdynamic`. Cuppa default
  libraries from `static_libraries` / `dynamic_libraries` (e.g. `-lpthread -lrt`, Clang
  `libc++` extras) are listed as normal `-l` tokens **before** the matching placeholder;
  the placeholder remains for further injected libs |
| Dialects | Label **`available dialects:`**. List every `-std=` name available for that compiler
  generation (working-draft + ISO aliases). Newest generation first; within a generation list
  the **working-draft** token first (e.g. `c++2c` before `c++26`) because Cuppa defaults to the
  draft name so builds can use post-freeze features — mark Cuppa’s default with ` (default)`.
  No `c++latest` on GNU drivers. No compiler spawn. **Default token** from
  `toolchain.default_dialect()` (Gcc/Clang/Cl) |
| Usable features | Label **`usable features:`**. Shorthand from `toolchain.usable_features()`:
  bare gated names when not dialect-inclusive (`concepts` on GCC 8–9);
  `all <default_dialect>[, gated…]` when the dialect carries the feature set
  (`all c++2a, coroutines` on GCC 10; `all c++2c` on GCC 11+); append
  `modules (experimental)` when `supports_modules` is true (still `--modules` opt-in) |
| Stdlib | **Clang only**: `stdlib choices: libstdc++ (default), libc++` from
  `Clang.stdlib_choices()` / instance `_stdlib`. Omit the whole line for GCC/MSVC |
| Session `--stdcpp` | Does not rewrite flag lines |
| Ownership | Version→default dialect tables live on toolchain classes; describe owns only the GNU
  alias catalog + joining `self.values` into templates |
| JSON | Same strings/placeholders under `driver.describe`; text only when `verbose` |

### Example link string (GCC/Clang Linux `dbg`)

Stored tokens (illustrative):

```python
['-rdynamic', '-Wl,-rpath=.', '-Xlinker', '-Bstatic', '<static_libs>',
 '-Xlinker', '-Bdynamic', '-lpthread', '-lrt', '<dynamic_libs>']
```

Displayed (verbose text; quotes subdued):

```text
link: "-rdynamic -Wl,-rpath=. -Xlinker -Bstatic <static_libs> -Xlinker -Bdynamic -lpthread -lrt <dynamic_libs>"
```

(`rel` may insert LTO tokens among the fixed flags; `cov` adds `--coverage`. Placeholders stay;
default libs stay visible ahead of `<dynamic_libs>`.)

This matches today’s `_linux_lib_flags` sandwich (`static_link` + STATICLIBS + `dynamic_link` + DYNAMICLIBS) without requiring a live SCons env to explain the shape.

### Naming rationale

| Label | Verdict |
|-------|---------|
| `CXX flags` / `CXXFLAGS` | SCons-centric |
| `c++ compiler` / `linker` | Accurate but long under `default flags` |
| **`c++` / `c` / `link`** | **Chosen** |
| `dialect:` / `stdlib:` | Too terse; prefer **`available dialects:`** / **`stdlib choices:`** |

## Refactor direction

Today `_initialise_toolchain` builds lists imperatively, and `_linux_lib_flags` only materialises
the static/dynamic sandwich when a DefaultEnvironment exists. Describe needs that sandwich as
**data** without depending on SCons string expansion of `_LIBFLAGS`.

**Done in this slice (anti-drift):**

- `Gcc.default_dialect()` / `Clang.default_dialect()` — single source for version→token;
  `__default_dialect_flags()` builds from that.
- `Clang.stdlib_choices()` — shared with `--clang-stdlib` option choices.
- `Cl.default_dialect()` / `Cl.available_dialects()` / derived `_default_dialect_flag`.
- `describe.py` calls those APIs; does **not** re-implement version tables.

**Still deferred:**

1. **Per-family flag tables** — version → default dialect extras; variant → tokens; LTO; Linux
   link template — feed both `_initialise_toolchain` and `describe()`.
2. **Non-Linux link template** polish.
3. Auto-generating family pages from the same tables.

Acceptance: describe unit tests for representative versions; existing LTO / stdlib tests keep
passing; no intentional flag drift.

## `describe()` payload (stable)

```python
{
    # Only dialects available for this compiler version (no c++latest / unsupported aliases).
    'dialects': ['c++11', 'c++14', /* … */, 'c++2c'],
    'default_dialect': 'c++2c',
    'stdlib_choices': ['libstdc++', 'libc++'],  # Clang only; omit key otherwise
    'default_stdlib': 'libstdc++',              # Clang only
    'variants': {
        'dbg': {
            'c++': '-Wall -fexceptions -g -std=c++2c …',
            'c': '-Wall -g',
            'link': (
                '-rdynamic -Wl,-rpath=. '
                '-Xlinker -Bstatic <static_libs> '
                '-Xlinker -Bdynamic <dynamic_libs>'
            ),
        },
        'cov': { 'c++': '…', 'c': '…', 'link': '…' },
        'rel': { 'c++': '…', 'c': '…', 'link': '…' },
    },
}
```

Internal storage may keep lists of tokens (including placeholder strings); `describe()` (or the
renderer) joins with a single space for display/JSON string fields. Omit variant keys and
language keys the toolchain does not define.

## Work slices

| ID | Slice | Notes |
|----|--------|-------|
| `list-tc-flag-tables` | Extract GCC/Clang/Cl composition + Linux link template with placeholders; helper feeds `_initialise_toolchain` / `_LIBFLAGS` | Behaviour-preserving |
| `list-tc-describe-api` | `describe()`; dialects + stdlib choices; joined strings | Unit tests |
| `list-tc-verbose-model` | Attach describe on driver nodes | JSON |
| `list-tc-verbose-render` | Notice keys / normal variants / muted commas; labels as settled | |
| `list-tc-verbose-docs` | CLI + toolchains note on placeholders / verbose / per-flag docs | |

## Refusal rules

- Do not call the compiler or network for describe.
- Do not print secrets from the environment.
- Do not change flag lists “to look nicer” — report what builds use (plus honest placeholders).
- Do not *replace* `<dynamic_libs>` with defaults; list default `-l` libs before the slot.
- Do not silently change default build flags while refactoring tables.
- Do not re-derive dialect version tables in `describe.py` once they live on the toolchain.

## Open decisions

1. **Non-Linux link template** — Windows/mingw and macOS: show whatever fixed link tokens Cuppa
   actually sets (may omit `<static_libs>` / `<dynamic_libs>` if that sandwich is Linux-only).

## Progress

| ID | Status |
|----|--------|
| `list-tc-flag-tables` | deferred — first slice reads `self.values`; full table-driven init later |
| `list-tc-describe-api` | done (`describe.py` + `default_dialect()` / stdlib / MSVC lists on classes) |
| `list-tc-verbose-model` | done |
| `list-tc-verbose-render` | done (labels + colour as settled; rules span widest content line) |
| `list-tc-verbose-docs` | done (CLI + hub/family pages; text/verbose/JSON samples via `generate_doc_samples`; quoted verbose invocations; `--stdcpp` table; AsciiDoc `++` escapes) |
