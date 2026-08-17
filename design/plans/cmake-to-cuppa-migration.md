# Plan: CMake → Cuppa migration guide (agents and humans)

- **Status:** proposal
- **Related:** [`ROADMAP.md`](../../ROADMAP.md) — `cmake-to-cuppa-migration`; [`sconscript-exports.md`](sconscript-exports.md); [#213](https://github.com/ja11sop/cuppa/issues/213)
- **Updated:** 2026-08-17

## Purpose

Provide a **decision-oriented** guide for moving a CMake-based C++ project (or a slice of it) onto Cuppa: what maps cleanly, what does not yet, and what to do while platform gaps are open.

Audience: maintainers, contributors, and **AI agents** asked to “add a Cuppa build alongside CMake” or “migrate tests to cuppa”.

Canonical product docs stay on the Antora site; this plan defines the **content outline** and the **honest capability matrix** before we publish a tutorial page (likely under Quickstart or a new “Migrating from CMake” page).

## Non-goals

- Replacing CMake inside Boost or other superprojects.
- Promising feature parity with `FetchContent`, `find_package`, generator expressions, or IDE export in one release.
- Auto-converting `CMakeLists.txt` — any “translator” is out of scope until manual patterns are stable.

## CMake concept → Cuppa mapping (draft matrix)

| CMake | Cuppa today | Notes / gap |
|-------|-------------|-------------|
| `add_library` static/shared | `env.BuildStaticLib` / `env.BuildSharedLib` | Object path collision on nested same-basename sources — [#213](https://github.com/ja11sop/cuppa/issues/213) |
| `add_executable` + `target_link_libraries` | `env.Build` / `env.BuildTest` | `BuildTest` adds `--test` run via process/boost runner |
| `target_include_directories` PUBLIC | `env.AppendUnique(CPPPATH=[...])` + package/location deps | |
| `target_compile_definitions` | `env.AppendUnique(CPPDEFINES=[...])` | Use `Clone()` for private defs (e.g. `*_SOURCE`) |
| `GLOB_RECURSE` sources | `env.RecursiveGlob` | Fine once compile paths fixed |
| `add_subdirectory` + target alias | **No export chain** between discovered sconscripts | [`sconscript-exports.md`](sconscript-exports.md) |
| `CTest` / `add_test` | `--test` + `env.BuildTest` | Custom harnesses (non–Boost.Test) use `default_runner='process'` |
| `find_package(Boost)` | `boost_package` / built-in Boost | Version/registry-specific |
| `FetchContent` | `location_dependency` / Conan / GitLab package | Different mental model — link to Dependencies hub |
| Toolchain / standard | `--toolchains=`, `--stdcpp` | Profiles: separate Profiles Clang archive |
| Coverage | `--cov --test` | gcov/llvm-cov via cuppa |
| Install / export | Package publish docs | Not consumer `cmake --install` |

## Recommended migration phases

### Phase 0 — Readiness checklist

- [ ] C++ dialect supported by cuppa toolchains (`--stdcpp` / default `c++2c` on GCC/Clang).
- [ ] Tests runnable as **process** (exit code) or **Boost.Test** — custom harnesses need one main per executable or a static lib with `main` (Capy `test_suite` pattern).
- [ ] No hard requirement for nested `add_subdirectory` **until** sconscript exports ship — or use **single root sconscript** interim.

### Phase 1 — Smoke build (library + one test)

1. Add minimal `sconstruct`: `cuppa.run(default_variants=['dbg'])`.
2. Add `sconscript`: `CPPPATH`, `BuildStaticLib`, one `BuildTest`.
3. Verify: `cuppa -D --dbg --test --offline`.

Matches [`examples/minimal/`](../../examples/minimal/).

### Phase 2 — Expand sources

1. Replace explicit file lists with `RecursiveGlob` where basenames are unique **or** split libs by subtree until [#213](https://github.com/ja11sop/cuppa/issues/213) lands.
2. Map `PRIVATE`/`PUBLIC` defs via `Clone()` envs per target class.

### Phase 3 — Tooling extras

- Coverage: `--cov --test`.
- Profiles inventory: `--cxx-profiles*` + `--cxx-profiles-report` (Profiles Clang only).
- CI: mirror [`AGENTS.md`](../../AGENTS.md) cuppa flags (`--offline`, `--develop` where applicable).

### Phase 4 — Decompose sconscripts (blocked)

- Split `test/sconscript`, shared libs — **after** export plan ships.

## Agent-oriented guidance (to publish)

Short rules for agents (expand in Antora later):

1. **Do not assume** `SConscript('child', exports=...)` works with Cuppa discovery — read [`sconscript-exports.md`](sconscript-exports.md).
2. **Do not assume** `RecursiveGlob` equals CMake `GLOB_RECURSE` until object paths are fixed — check for duplicate basenames (`find … -name '*.cpp' | xargs -n1 basename | sort | uniq -d`).
3. **Prefer** `location_dependency` / `package_dependency` over re-declaring third-party compile flags when a cuppa dep exists.
4. **Keep CMake** as canonical until the Cuppa graph runs the same test binaries — document “experimental Cuppa” in a sidecar note (see Boost.Capy `CUPPA-NOTES.md` pattern).
5. **Profiles report** requires Profiles-capable Clang; absence of violations means no HTML index — not a failed capture.

## Validation corpus

| Project shape | Role |
|---------------|------|
| [`examples/minimal/`](../../examples/minimal/) | Tiny green path |
| [`tests/fixtures/dummy_project/`](../../tests/fixtures/dummy_project/) | Glob + BuildTest |
| Boost.Capy (public) | Real C++20 coroutine library; nested sources + custom test harness; Profiles report — experimental `sconstruct` + `CUPPA-NOTES.md` |
| Private consumer **project A** (baa-shaped) | Packages + Boost runner — do not name in published docs |

## Deliverables

| ID | Output | Priority |
|----|--------|----------|
| `migrate-matrix` | Antora table (CMake ↔ Cuppa) with “gap” callouts | High |
| `migrate-tutorial` | Step-by-step “library + tests” from a stripped CMakeLists | High |
| `migrate-agents` | `AGENTS.md` pointer + short agent checklist (link only, no duplicate prose) | Medium |
| `migrate-profiles` | subsection: Profiles report on a migrated tree | Medium |
| `migrate-exports` | Update tutorial when sconscript exports land | After `sconscript-exports` |

## Progress snapshot

| Item | Status |
|------|--------|
| Boost.Capy experiment | done — surfaced compile + export gaps |
| Published Antora page | not started — blocked on [#213](https://github.com/ja11sop/cuppa/issues/213) for honest RecursiveGlob story |
| This plan | proposal |
