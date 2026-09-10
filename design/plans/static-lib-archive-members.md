# Plan: Unique static-library archive members

- **Status:** in progress
- **Related:** [`ROADMAP.md`](../../ROADMAP.md) — follow-on to `compile-object-paths` (#213); [#287](https://github.com/ja11sop/cuppa/issues/287); [`sconscript-exports.md`](sconscript-exports.md) (Boost.Capy validation 2026-09-07); [`path-vocabulary-and-scons-nodes.md`](path-vocabulary-and-scons-nodes.md); methods Build / `BuildStaticLib`
- **Updated:** 2026-09-09
- **Impact:** patch — fix incorrect link / missing symbols when a static archive silently drops objects; may change `.a` member names (ABI of the archive file layout, not the C++ ABI)

## Problem

`Compile` / `CompileStatic` mirror nested sources under `working/` so two files named
`except.cpp` in different directories become distinct objects (shipped as
[#213](https://github.com/ja11sop/cuppa/issues/213) / [#214](https://github.com/ja11sop/cuppa/pull/214)):

```text
_build/…/working/src/detail/except.o
_build/…/working/src/buffers/detail/except.o
```

`BuildStaticLib` then feeds those nodes to SCons `StaticLibrary` → typically `ar rc
lib….a …`. Traditional `ar` stores members by **basename** only. A second `except.o`
replaces or shadows the first inside the archive. Linkers then see a subset of the
objects: undefined references that look like “missing source” or “wrong flags”, not
“archive ate my twin basename”.

Boost.Capy’s Cuppa sketch hit this on 2026-09-07 while validating `ExportShared`:
`src/detail/except.cpp` and `src/buffers/detail/except.cpp` both archive as `except.o`.
`ar t libcapy.a` listed duplicate basenames; extract kept one member. The failure mode
was easy to mis-attribute to Import/Export sharing (which was fine).

This is **orthogonal** to sconscript exports. #213 fixed the compile graph; the archive
step still flattens identity.

## Goals

1. Every object node passed to `BuildStaticLib` / `BuildLib` (static) must remain
   addressable inside the produced `.a` (no silent basename loss).
2. Fail loudly if the platform/toolchain cannot uniquify and a collision remains —
   never ship a “successful” archive that dropped members.
3. Document the rule next to Build methods and the #213 “same basename under
   `working/`” story so agents do not assume object-path mirroring implies archive safety.

## Non-goals

- Changing shared-library (`.so` / `.dll`) link behaviour (no `ar` member table).
- Renaming sources on disk or forbidding duplicate basenames in the project tree.
- Replacing SCons `StaticLibrary` with a custom archiver for every toolchain on day one
  if a smaller fix (unique member names / `ar` flags) works.

## Settled lean

| Topic | Decision |
|-------|----------|
| Where to fix | Cuppa’s static-lib path (`BuildStaticLib` / `BuildLib` static), not consumer workarounds |
| Preferred mechanism | On **basename collision only**, stage copies under `working/.archive_members/<lib>/` with names flattened from the `build_dir`-relative path (`src/detail/except.o` → `src_detail_except.o`); pass staged nodes to `StaticLibrary`. No-collision libraries unchanged (stable `ar` member names / signatures) |
| Collision policy if uniquify impossible | `StopError` listing the colliding flattened names and relative paths — never silent drop |
| Scope | Static archives only; same staging helps MSVC `.lib` when basenames collide |
| Relation to #213 | Treat as the archive half of “nested same-basename sources in one library” |
| Always stage / always flatten | **Deferred to 2.0** — one code path and uniform `ar t` names, but changes member names for *every* static lib (wider SCons signature churn and copy cost). Keep collide-only for the 1.x patch; revisit as a major when simplifying the staging branch is worth the rebuild blast radius |

## Design directions

### A — Unique member names at archive time (preferred) — shipping

Map each object node to a member name that encodes enough of the relative path under
`working/` to be unique, then stage a file whose **basename** is that name before
`StaticLibrary` / `$ARCOM`. **1.x:** only when basenames collide. **2.0 candidate:**
always flatten/stage (drop the detection branch).

### B — Detect-only (interim)

Not used as the sole fix; collision detection gates staging instead.

### C — Thin archives / `ar` path members

Deferred — portability across GCC/Clang/MSVC unclear.

## Work slices

| Slice | Deliverable |
|-------|-------------|
| `archive-member-repro` | Integration fixture: two `except.cpp` → one `BuildStaticLib` → link a TU that needs symbols from **both** |
| `archive-member-detect` | Basename collision → stage (not bare StopError) |
| `archive-member-uniquify` | Product fix in `build_library.py` + `static_archive_members.py` |
| `archive-member-doc` | Build methods note + changelog + plan/ROADMAP |
| `archive-member-always` | **2.0** — always stage/flatten; remove collide-only branch |

## Open questions

- Interaction with incremental `ar` / thin archives and `--parallel` archive updates (monitor after ship).
- Does `BuildSharedLib` need any analogous note for export libs that aggregate objects?
  (Likely no for ELF shared objects.)

## Progress snapshot

| Slice | Status |
|-------|--------|
| Problem seen on Boost.Capy Cuppa sketch | done (2026-09-07) |
| Plan + ROADMAP row | done |
| Repro integration test | done (PR) |
| Uniquify / detect fix | done (PR) |
| Docs | done (PR) |
| Always stage / flatten (2.0) | deferred |
