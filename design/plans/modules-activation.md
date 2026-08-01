# C++ modules: how modules should be activated

- **Status:** proposal
- **Related:** [`ROADMAP.md`](../../ROADMAP.md) — `mod-activate-evidence`, `mod-scan-preamble`, `mod-scan-cache`
- **Updated:** 2026-07-31

The dialect fixes described in §2 are done; nothing from §4 onwards is built.

Today modules are opt-in through `--modules` / `env.Modules()`. This document works out whether
that should become opt-out — modules available whenever the toolchain supports them, in the way
`-fcoroutines` is — and, if so, what has to change first for that to be safe.

---

## 1. What `--modules` actually turns on today

Enabling modules is not one decision; it is four, and they have very different costs.

| # | Effect | Where | Cost when nothing in the project uses modules |
|---|--------|-------|-----------------------------------------------|
| 1 | Compiler flags that enable the feature | `toolchain.modules_enable_flags` | None for Clang and MSVC (both return `[]`). GCC returns `-fmodules -fmodule-mapper=<path>` on **every** translation unit and writes a mapper file |
| 2 | `Compile` switches to the modules path | `cuppa/methods/compile.py` → `cuppa/cpp/cxx_modules.py` | Every source is read and line-scanned at read time; object naming, `Depends` wiring, and per-source flags come from module code rather than the classic path |
| 3 | Module source suffixes registered | `register_module_source_suffixes` | Negligible; only teaches the Object builders about `.cppm` / `.cxxm` / `.ccm` / `.ixx` |
| 4 | A C++20 dialect floor | `ensure_modules_dialect_floor` | Was destructive (see §2); now inert unless the dialect in force is below C++20 |

Effect 2 is the one that matters. It also carries a failure mode: an `import` the scanner believes
it found but cannot resolve raises `StopError`, so a scanner false positive in a project with no
modules stops the build rather than being ignored. The scanner is line-oriented and does not
preprocess, which is a documented limit (macros and `#if` can invent imports).

## 2. Fixed on this branch, and why it matters here

Three defects made the current behaviour look worse than the design:

- The floor read `env['stdcpp']`, which is unset unless `--stdcpp` was passed, so it concluded the
  floor was unmet on every build and replaced the dialect with `c++20`. On a Clang 21 project that
  silently downgraded `c++2c` to `c++20` — post-C++20 library features stopped compiling — while
  the variant path still said `cxx2c`. It now consults `toolchain.abi` / `abi_flag`.
- The floor ran once per variant env at read time, so its message repeated per sconscript and it
  mutated envs that never compiled a module. It now runs from the compile that builds, declares, or
  imports a module, matching how the `import std` C++23 floor already worked.
- `c++98` / `c++03` outranked `c++26` in the rank table, so `--stdcpp=c++98 --modules` passed the
  floor check.

This removes cost 4 from the table above, which is the main reason the opt-out question is now
worth asking: with the floor honest, enabling the *flags* is close to free on all three toolchains.

## 3. The `-fcoroutines` comparison

`-fcoroutines` is added unconditionally to GCC's default dialect flags per version, with no opt-in
and no diagnostic. The comparison holds for effect 1 and breaks for effect 2:

- `-fcoroutines` enables a language feature inside the compiler. It cannot change which build graph
  cuppa constructs, cannot read source files, and cannot fail a build.
- Modules-on changes the code path that produces every object file in the project.

So "just set the flag when the toolchain supports it" is defensible on its own, and is *not* the
same change as "make every project build through the modules path".

## 4. Proposal: separate the flag from the orchestration

### 4.1 Capability flags follow the `-fcoroutines` precedent

Fold the enabling flags into what the toolchain already reports for its version, with no user
action. Clang and MSVC need nothing, so this is only a GCC question, and GCC's `-fmodules` is the
one flag in the set that is not free: it changes how `import` and `module` lines are treated and
requires a mapper file. GCC therefore keeps its flags tied to activation (§4.2) rather than being
added to the default dialect flags.

### 4.2 Orchestration activates on evidence, not on a flag

Activate the modules path for a `Compile` / `Build` call when there is positive evidence the call
involves modules:

| Signal | Detected by | Certainty |
|--------|-------------|-----------|
| A source with a module interface suffix (`.cppm`, `.cxxm`, `.ccm`, `.ixx`) | File extension, no scan | Certain |
| `env.Module(...)`, `env.HeaderUnit(...)`, `env.ImportModules(...)` in the sconscript | Explicit method call | Certain |
| A packaged dependency exposing `module-map.json` that the project imports | Package metadata | Certain |
| `export module` / `module X;` / `import …` in a `.cpp` | Line scanner | Good, but see §4.4 |

A project of module interfaces and consumers then builds with no flag at all, which is the
opt-out ergonomics we want, while a project with none of these signals never enters the modules
path and cannot be affected by scanner behaviour.

### 4.3 `--modules` and `--no-modules` become overrides

| Invocation | Behaviour |
|------------|-----------|
| (nothing) | Activate per §4.2. An unsupported toolchain is reported once at info level and the build continues on the classic path |
| `--modules` | Force activation. An unsupported toolchain stops the build with today's clear error — this is what CI wants |
| `--no-modules` | Never activate, even with module sources present. Escape hatch for bisecting a suspected modules problem |

`env.Modules()` keeps working as the per-env force-on.

### 4.4 Scanner work this depends on

Auto-activation only reaches a `.cpp` after that file has been scanned, so scanning becomes part of
the default path and has to be both cheap and forgiving:

- **Preamble-only scanning.** `scan_file` reads whole files today (`handle.read()`). Module and
  import declarations may only appear in the preamble, so scanning can stop at the first
  declaration that ends it. Big win on large sources.
- **Result cache** keyed on path plus mtime and size, so repeat builds and multiple `Compile` calls
  over the same source scan once.
- **Warn rather than stop** for an unresolved import when activation was automatic. `StopError`
  stays the behaviour under explicit `--modules` / `env.Modules()`, where the user has asserted the
  project uses modules.

### 4.5 Measurement gate

Before any default changes, measure read-time cost on a header-heavy project (**project A** in
`INTERNAL_PROJECTS.local.md`: 362 single-source test binaries, 545 headers):

1. `--modules` today versus no flag, timing the SConscript read phase only.
2. The same pair with preamble-only scanning and the scan cache in place.

If preamble scanning plus caching does not make the read phase indistinguishable from the classic
path, auto-activation should stay off by default and `--modules` remains the opt-in.

## 5. Phases

| ID | Work | Depends on | Notes |
|----|------|------------|-------|
| `mod-scan-preamble` | Stop scanning at the end of the preamble | — | Pure win regardless of the activation decision |
| `mod-scan-cache` | Cache scan results per path / mtime / size | — | Same |
| `mod-scan-timing` | Time the read phase with and without modules on project A | above two | The §4.5 gate |
| `mod-activate-evidence` | Activate the modules path per §4.2 | `mod-scan-timing` | Includes the unresolved-import severity split |
| `mod-no-modules-flag` | `--no-modules` override | `mod-activate-evidence` | Also useful on its own for bisecting |
| `mod-gcc-flag-scope` | Give GCC its `-fmodules` / mapper flags per compile that needs them instead of per env | `mod-activate-evidence` | Removes the last always-on effect; the duplicate-flag fix on this branch is the interim step |
| `mod-docs-activation` | Rewrite `cxx-modules.adoc` "Enable modules" and `cli-reference.adoc` for the new model | all above | Docs currently teach opt-in as the only path |

## 6. Non-goals

- Emulating a real preprocessor in the scanner. If accuracy beyond the preamble is needed, that is
  the existing `scan-deps` roadmap item (`clang-scan-deps` / P1689), not a bigger regex.
- Removing `--modules`. It stays as the force-on with a hard error, which is what CI and bug
  reproduction need.
- Changing BMI layout, packaging, or the toolchain capability floors.

## 7. Open questions

- Should a `.cpp` containing `export module` be enough to activate, or should interface units be
  required to use a module suffix once activation is automatic? The stricter rule removes the
  scanner from the activation decision entirely, at the cost of rejecting a pattern that works
  today.
- With activation per `Compile` call, should a project that activates in one sconscript and not
  another get one info message per build (current dedupe) or per sconscript?
- When modules are auto-activated and the toolchain cannot support them, is one info line enough,
  or should that be a warning? Warning risks noise on every build for macOS Apple Clang users.
- Does `--no-modules` also need to suppress `env.Modules()` in a sconscript, or only the automatic
  path? Suppressing an explicit project-level call is surprising, but it makes the flag a reliable
  bisecting tool.

## 8. Reference

- `cuppa/methods/modules.py` — activation, dialect floor, source suffixes
- `cuppa/cpp/cxx_modules.py` — modules compile path, registry, header units, `import std`
- `cuppa/cpp/module_scanner.py` — line scanner
- `cuppa/toolchains/{gcc,clang,cl}.py` — `supports_modules`, `modules_enable_flags`,
  `consume_module_flags`, `interface_module_flags`
- `docs/modules/ROOT/pages/cxx-modules.adoc` — user guide and Limits
