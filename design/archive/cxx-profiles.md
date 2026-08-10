# Opt-in C++ Profiles (`--cxx-profiles*` / attribute CLI)

- **Status:** shipped
- **Related:** [`ROADMAP.md`](../../ROADMAP.md) — C++ Profiles; [#127](https://github.com/ja11sop/cuppa/issues/127); toolchain supply [#160](https://github.com/ja11sop/cuppa/issues/160); [#176](https://github.com/ja11sop/cuppa/pull/176), [#177](https://github.com/ja11sop/cuppa/pull/177), [#180](https://github.com/ja11sop/cuppa/pull/180)
- **Updated:** 2026-08-10
- **Impact:** minor — `--cxx-profiles*`, enforce composition, `--cxx-disable-error-limit`, `--cxx-modules` vocabulary

Ship opt-in WG21 / experimental-Clang **C++ Profiles** support in the **1.7.0** cycle.
Profiles-capable Clang archives are already fetchable via `--toolchain-archive=` /
`--clang-root=`; this plan is the Cuppa flag surface and compile-path wiring.

**Empirically verified on C++ Alliance Clang 24 (Profiles archive):** placing

```cpp
[[profiles::enforce(std::init)]];
```

at the top of a translation unit (with `-fprofiles`) is accepted and exercises the
initialization profile. Treat **`std::init` as the only known-working profile name** for
smoke tests and docs until the fork advertises more. Do not invent `type_safety` /
`bounds_safety` CLI examples against that build until they compile there.

---

## 1. Naming review (BuildProfile vs C++ Profiles vs C++ vocabulary)

Cuppa already uses the word *profile* for a different, long-standing concept:

| Surface | Meaning today |
|---------|----------------|
| `env.BuildProfile(…)` | Apply named **build** profiles (lightweight env / flag tweaks) |
| `cuppa.run(profiles=…, default_profiles=…)` | Register / default those factories |
| `env['profiles']` | Dict of BuildProfile factory callables |
| `cuppa/profiles/` / `cuppa.profile.plugins` | Built-in and plugin BuildProfiles |
| Docs “Dependencies and profiles” | Same build-profile concept |

**C++ Profiles** are language-level attributes and compiler rules
(`[[profiles::enforce(…)]];`, experimental `-fprofiles`). They are unrelated to
`BuildProfile`.

Most cuppa methods are **language- and toolchain-agnostic** (`Build`, `Test`,
`Coverage`, …). C++ modules and C++ Profiles are not — they should use an explicit
**`cxx-` public vocabulary** (CLI flags and env methods), parallel to each other.

### Settled: keep `BuildProfile` names

Renaming Cuppa’s build profiles is **out of scope** for #127:

- Public method is already `BuildProfile` (not bare `Profile`).
- Docs already say “Dependencies and **profiles**” in the build-tweak sense.
- A rename would be a **major**-impact break for little clarity gain once CLI and docs
  always say **C++ Profiles** for the language feature.

### Settled: avoid the `env['profiles']` key clash

The only hard collision is the **environment key**, not the method name.

A naïve `--profiles` with `dest='profiles'` would overwrite or fight the BuildProfile
factory map in `env['profiles']`. Implementation keys stay `cxx_*` (see §1.1).

### Settled: `--cxx-profiles*` and `--cxx-modules*` public vocabulary

C++-specific features use an explicit **`cxx-` prefix** on CLI flags and env methods.
Most cuppa methods stay language-agnostic (`Build`, `Test`, `Coverage`, …).

| Canonical (docs + code) | Deprecated alias (modules only → remove v2) | Implementation key |
|-------------------------|---------------------------------------------|--------------------|
| `--cxx-modules` | `--modules` | `env['modules']` (unchanged internal key) |
| `env.CxxModules()` | `env.Modules()` | same |
| `--cxx-profiles` | *(none — never released under short name)* | `env['cxx_profiles']` |
| `--cxx-profiles-enforce=a,b` | *(none)* | `env['cxx_profiles_enforce']` |
| `env.CxxProfiles()` | *(none)* | same |
| `env.CxxProfilesEnforce(…)` | *(none)* | same |
| `--cxx-disable-error-limit` | *(new)* | `env['cxx_disable_error_limit']` |

Rules:

- **Product docs** use only the `cxx-` forms (plus a short “deprecated aliases” note
  for `--modules` / `env.Modules()` only).
- **Deprecation:** when `--modules` or `env.Modules()` is used, emit one clear
  `logger.warn` naming `--cxx-modules` / `env.CxxModules()` and “removed in cuppa 2.0”.
- **Profiles:** no `--profiles` / `env.Profiles()` compatibility — #177 landed on
  master but 1.7.0 is not released; rename in place before release.

Profile designators passed to `--cxx-profiles-enforce=` remain opaque compiler strings
(e.g. `std::init`); cuppa does not rename them.

There is **no** `--cxx-profiles-require=` / `--cxx-profiles-suppress=` — see §2.4.

---

## 2. Settled CLI and behaviour

### 2.1 `--cxx-profiles`

Opt-in, like `--cxx-modules`:

- When set, activate C++ Profiles for the session (per variant env).
- Ask the toolchain for enable flags (expected: `-fprofiles` on Profiles-capable Clang).
- Append those flags to `CXXFLAGS` (same pattern as `modules_enable_flags`).
- If the selected toolchain reports **no** Profiles support, **StopError** with a clear
  reason and a hint to use a Profiles Clang archive (do not silently no-op).

Capability detection (first cut):

- Prefer an explicit toolchain API, e.g. `toolchain.profiles_enable_flags(env)` →
  `['-fprofiles']` or `[]`.
- Do **not** assume “any Clang 24”; distro `clang24` is not Profiles-capable.
  Session names / qualifiers such as `clang24_profiles_…` are a useful heuristic but
  the flag API is the source of truth.

### 2.2 `--cxx-profiles-enforce=<profile1>,<profile2>,…`

Comma-separated profile designators to enforce for every compiled C++ translation unit
in the activated session (unless a later per-env override exists).

Implies `--cxx-profiles` (enable the framework if enforce is set alone).

Resolution order per toolchain:

1. **Native flag map** — if the toolchain implements
   `profiles_enforce_flags(env, names) → […]` (e.g. hypothetical
   `-fprofile-enforce=…` / `-fprofiles-enforce=…`), use that. None known on today’s
   C++ Alliance Clang; keep the hook so vendors can wire in without another Cuppa
   design pass.
2. **Source injection** — otherwise, a Cuppa C++ compile preprocessor / wrapper that
   ensures the first non-empty declaration position receives:

   ```cpp
   [[profiles::enforce(std::init)]];
   // or, when several designators are requested:
   [[profiles::enforce(profile1, profile2)]];
   ```

   Injected as the first line of the unit presented to the compiler (empty-declaration
   form required by the framework papers). Prefer a generated side-file or
   compiler `-include` / forced-include strategy if that preserves `#line` / diagnostics
   better than rewriting the user’s path in place; exact mechanism is an
   implementation detail settled in the PR, with these constraints:

   - Do not mutate the user’s source tree.
   - Diagnostics should still point at the user’s file when practical.
   - **Shipped (1.7.0):** skip `-include` when the unit already contains
     `[[profiles::enforce(…)]];` in the preamble (avoids two enforce
     empty-declarations).
   - **Shipped (1.7.0, slice H):** when a first-line enforce already exists, rewrite
     that attribute in the compiler-facing view to **merge** CLI designators into
     its list (still without mutating the source tree).
   - Module interface units: inject before any declaration, respecting the
     `module;` preamble pattern from P3589 (implementation must follow the
     framework’s “first empty-declaration” rule).

`--cxx-profiles` alone enables the framework without injecting enforce attributes;
projects can put `[[profiles::enforce(std::init)]];` (etc.) in source themselves.

Product docs: Antora [`cxx-profiles.adoc`](../../docs/modules/ROOT/pages/cxx-profiles.adoc).

### 2.3 `--cxx-disable-error-limit`

When **Profiles enforce** (or other strict checking) is active, compilers often emit
only the first *N* diagnostics then stop (`clang` default error limit, `gcc`
`-fmax-errors` default, MSVC has its own cap). For Profiles work you frequently want
**the full violation list** (dedupe, report, fix in batch).

| Toolchain | Expected flag(s) |
|-----------|------------------|
| Clang | `-ferror-limit=0` |
| GCC | `-fmax-errors=0` |
| MSVC | No supported `cl.exe` flag (fatal C1003 cap is fixed; `/ERRORLIMIT` is lld-link, not `cl`) |

Behaviour:

- Opt-in CLI `--cxx-disable-error-limit` (no legacy alias).
- Toolchain API, e.g. `disable_error_limit_flags(env) → […]`, appended to `CXXFLAGS`
  when the option is set (same activation pattern as Profiles/modules enable flags).
- Docs: recommend pairing with `--cxx-profiles-enforce=` when building a Profiles
  violation inventory; flag is not Profiles-specific (usable for any large error sweep).

Optional method mirror: `env.CxxDisableErrorLimit(True)`.

### 2.4 Method surface

| Canonical | Deprecated alias (v2 removal) |
|-----------|-------------------------------|
| `env.CxxProfiles(enabled=True)` | `env.Profiles()` |
| `env.CxxProfilesEnforce(['std::init', …])` | `env.ProfilesEnforce(…)` |
| `env.CxxModules(enabled=True)` | `env.Modules()` |

### 2.5 Compose with existing `[[profiles::enforce(…)]];` (shipped)

**Goal:** support **composition** without a second enforce empty-declaration
at the top of a translation unit.

| Scenario | Desired compiler-facing behaviour |
|----------|-----------------------------------|
| TU has no enforce attribute | Today: `-include` generated header with `[[profiles::enforce(…)]);` |
| TU opens with `[[profiles::enforce(foo)]];` and CLI passes `--cxx-profiles-enforce=std::init` | Rewrite (view-only) to `[[profiles::enforce(foo, std::init)]];` before compile |
| Project standardises on `[[profiles::enforce()]];` in every TU | Merge CLI designators into the empty list as experimentation hook |

Constraints carry forward: **do not mutate the user’s source tree**; preserve `#line` /
diagnostics where practical; respect `module;` preamble on module interface units.

Implementation sketch for the follow-on:

- Preamble scan (reuse / extend `source_has_profiles_enforce` in `cuppa/cpp/cxx_profiles.py`).
- When enforce is present, emit a **per-TU compiler-facing wrapper** or patched view
  (same family as `-include`, or a thin compile wrapper) that replaces only the first
  matching enforce attribute line — not a second `-include` enforce block.
- Unit tests: merge lists, no double-enforce, skip inject when merge succeeds.
- Integration: Alliance Clang + `std::init` with source + CLI both set.

**Not in 1.7.0 MVP** ([#177](https://github.com/ja11sop/cuppa/pull/177) skips inject when
enforce already exists). This section is the explicit design anchor for the next slice.

### 2.6 Out of scope: `require` and `suppress` (no Cuppa CLI)

P3589 also defines `profiles::require` and `profiles::suppress`. They are **source/module
attributes with different loci** from `enforce`. Cuppa does **not** expose
`--cxx-profiles-require=` or `--cxx-profiles-suppress=` — those flags would either
mis-teach the model (if implemented like enforce) or need machinery that is not a small
opt-in flag.

| Attribute | Locus (P3589) | Why not a session CLI |
|-----------|---------------|------------------------|
| `enforce` | First empty-declaration of a TU | Session-wide policy **does** map → `--cxx-profiles-enforce=` |
| `require` | On a **module-import-declaration** only | Needs import-site / modules graph awareness; not a TU prefix |
| `suppress` | On a **statement or declaration** (local opt-out) | Authors write it in source; Cuppa will not rewrite bodies |

Authors keep using `[[profiles::suppress(…)]]` (and, when modules + Profiles mature,
`[[profiles::require(…)]]` on imports) in their own code. Cuppa’s job for 1.7.0 is
framework enablement (`-fprofiles`) plus optional **enforce** injection / flag mapping.

If a later need appears for “skip enforce injection on these paths”, that is a Cuppa
build carve-out (e.g. exclude globs), not `profiles::suppress`, and would be a separate
design note.

Smoke / docs: `--cxx-profiles --cxx-profiles-enforce=std::init` (or source
`[[profiles::enforce(std::init)]];` with `--cxx-profiles`). Extend designators only when the
toolchain actually supports them.

---

## 3. Refusal rules

| Request | Response |
|---------|----------|
| Rename `BuildProfile` / `cuppa.profiles` as part of #127 | Refuse; separate major if ever wanted |
| Use `env['profiles']` for the C++ Profiles bool | Refuse; keep BuildProfile map |
| Keep `--modules` / `--profiles` as the only documented names after cxx rename lands | Refuse; docs canonical = `cxx-*`; aliases deprecated only |
| Remove `--modules` / `--profiles` before cuppa 2.0 without deprecation period | Refuse; warn first, remove in v2 |
| Auto-enable Profiles on every Clang 24 | Refuse; only capable toolchains |
| Auto “latest Profiles” toolchain | Refuse; `tc-dep-latest` already out of scope |
| Invent non-existent `-fprofile-enforce` as required | Refuse; map when real, else inject |
| Make Profiles the default for all builds | Refuse; opt-in only |
| Close #127 without enforce path | Refuse; enforce is in the ticket goal |
| Add `--cxx-profiles-require=` / `--cxx-profiles-suppress=` | Refuse; wrong locus for a session CLI (§2.6) |
| Claim multi-profile support on Alliance Clang beyond `std::init` without evidence | Refuse; smoke and docs stay on verified names |
| Hard-code `-ferror-limit=0` only in Profiles code with no `--cxx-disable-error-limit` | Refuse; use shared flag + toolchain map |

---

## 4. Implementation sketch

| Area | Likely touch |
|------|----------------|
| Profiles method | `cuppa/methods/cxx_profiles.py` — options, aliases, activate |
| Modules method | `cuppa/methods/modules.py` — add `--cxx-modules` / deprecate `--modules` |
| Toolchain API | `profiles_enable_flags`, `profiles_enforce_flags`, `disable_error_limit_flags` |
| Compile path | `cuppa/cpp/cxx_profiles.py` — enforce inject; §2.5 composition follow-on |
| CLI docs | `cli-reference.adoc`, `cxx-profiles.adoc`, `cxx-modules.adoc`; **no** primary use of deprecated names |
| Tests | Unit: alias deprecation, env keys, error-limit flags per toolchain. Integration: Profiles smoke + optional full-error-limit build |

Registration follows the modules pattern (`add_options` / `add_to_env` /
`init_env_for_variant`).

---

## 5. Work slices

| Slice | Deliverable | Notes |
|-------|-------------|-------|
| A | Design + issue refresh | This document; #127 papers + goal text |
| B | `--profiles` → `-fprofiles` | Toolchain API + StopError when unsupported |
| C | `--profiles-enforce=` | Native map hook + inject fallback; smoke with `std::init` |
| D | Docs + samples | CLI reference; toolchain page; `std::init` example |
| E | Integration smoke | Against a pinned Profiles Clang archive |
| **F** | **`--cxx-*` vocabulary** | Shipped ([#180](https://github.com/ja11sop/cuppa/pull/180)): `--cxx-profiles*` (no legacy); `--cxx-modules` + deprecate `--modules` / `env.Modules()` |
| **G** | **`--cxx-disable-error-limit`** | Shipped ([#180](https://github.com/ja11sop/cuppa/pull/180)): toolchain `disable_error_limit_flags` |
| **H** | **Enforce composition (§2.5)** | Shipped ([#180](https://github.com/ja11sop/cuppa/pull/180)): merge into existing `[[profiles::enforce(…)]];` in compiler view |

Slices A–E shipped ([#176](https://github.com/ja11sop/cuppa/pull/176), [#177](https://github.com/ja11sop/cuppa/pull/177)).
Slices F–H shipped in **1.7.0** ([#180](https://github.com/ja11sop/cuppa/pull/180)).

---

## 6. Papers and references (issue table)

Canonical paper list lives on [#127](https://github.com/ja11sop/cuppa/issues/127).
Keep that table updated when new revisions land; do not duplicate the full table in
product docs. Framework and syntax anchors for implementers:

- P3589R2 — framework (`enforce` / `require` / `suppress`; only **enforce** is a Cuppa CLI)
- P3081R2 — core safety profiles direction
- P4222R1 — initialization profile (Alliance designator today: `std::init`)
- P3984R0 — type-safety profile (`std::type` in framework examples)
- Experimental Clang: [cppalliance/clang `profiles-framework`](https://github.com/cppalliance/clang/tree/profiles-framework),
  docs `clang/docs/ProfilesFramework.rst`, release archives under
  `cppalliance/clang` tags such as `profiles-2026-08-07-27`

---

## 7. Progress snapshot

| Item | State |
|------|-------|
| Profiles Clang supply (`--toolchain-archive=` / session names) | Done (#160) |
| Naming: keep BuildProfile; `env['cxx_profiles']` for language feature | Settled |
| MVP CLI `--cxx-profiles` / `--cxx-profiles-enforce=` | Shipped (#177); renamed before 1.7.0 release (no `--profiles` alias) |
| Canonical `--cxx-modules` + deprecate `--modules` / `env.Modules()` | Shipped (slice **F**) |
| `--cxx-disable-error-limit` | Shipped (slice **G**) |
| Enforce composition with existing source attribute (§2.5) | Shipped (slice **H**) |
| No `--cxx-profiles-require=` / `--cxx-profiles-suppress=` | Settled (§2.6) |
| Alliance Clang smoke profile name `std::init` | Empirically verified |
| Toolchain flag + enforce `-include` inject | Shipped (#177) |
| Docs / tests | Shipped ([#177](https://github.com/ja11sop/cuppa/pull/177), [#180](https://github.com/ja11sop/cuppa/pull/180)) |

**Follow-ons (post-1.7.0):** more designators as compilers add them; native enforce flags when
available; path carve-outs; modules + `profiles::require` import-site wiring. See
[`ROADMAP.md`](../../ROADMAP.md) — C++ Profiles.
