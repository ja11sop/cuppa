# Opt-in C++ Profiles (`--profiles` / attribute CLI)

- **Status:** in progress
- **Related:** [`ROADMAP.md`](../../ROADMAP.md) — `tc-dep-profiles`; [#127](https://github.com/ja11sop/cuppa/issues/127); toolchain supply [#160](https://github.com/ja11sop/cuppa/issues/160) (done); plan PR [#176](https://github.com/ja11sop/cuppa/pull/176)
- **Updated:** 2026-08-10

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

## 1. Naming review (BuildProfile vs C++ Profiles)

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

### Settled: keep `BuildProfile` names

Renaming Cuppa’s build profiles is **out of scope** for #127:

- Public method is already `BuildProfile` (not bare `Profile`).
- Docs already say “Dependencies and **profiles**” in the build-tweak sense.
- A rename would be a **major**-impact break for little clarity gain once CLI and docs
  always say **C++ Profiles** for the language feature.

### Settled: avoid the `env['profiles']` key clash

The only hard collision is the **environment key**, not the method name.

`--modules` stores a bool in `env['modules']`. A naïve `--profiles` with
`dest='profiles'` would overwrite or fight the BuildProfile factory map in
`env['profiles']`.

| User-facing | Implementation key |
|-------------|-------------------|
| `--profiles` | `env['cxx_profiles']` (bool) |
| `--profiles-enforce=a,b` | `env['cxx_profiles_enforce']` (list of strings) |
| Optional `env.Profiles()` / `env.ProfilesEnforce(…)` | Same keys; mirror `env.Modules()` |

CLI flag names stay short and parallel to `--modules`. Docs and help text always say
**C++ Profiles** when referring to this feature. Profile designators are opaque strings
passed through to attributes/flags (e.g. `std::init`); Cuppa does not rename them.

There is **no** `--profiles-require=` or `--profiles-suppress=` — see §2.4.

---

## 2. Settled CLI and behaviour

### 2.1 `--profiles`

Opt-in, like `--modules`:

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

### 2.2 `--profiles-enforce=<profile1>,<profile2>,…`

Comma-separated profile designators to enforce for every compiled C++ translation unit
in the activated session (unless a later per-env override exists).

Implies `--profiles` (enable the framework if enforce is set alone).

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
   - **Today:** skip `-include` when the unit already contains
     `[[profiles::enforce(…)]];` in the preamble (avoids two enforce
     empty-declarations).
   - **Next (composition):** when a first-line enforce already exists, rewrite
     that attribute in the compiler-facing view to **merge** CLI designators
     into its list (still without mutating the source tree). That enables
     CLI + source composition and, later, empty
     `[[profiles::enforce()]];` placeholders in every TU as an experimentation
     hook. Not implemented in the first B+C slice.
   - Module interface units: inject before any declaration, respecting the
     `module;` preamble pattern from P3589 (implementation must follow the
     framework’s “first empty-declaration” rule).

`--profiles` alone enables the framework without injecting enforce attributes;
projects can put `[[profiles::enforce(std::init)]];` (etc.) in source themselves.

Product docs: Antora [`cxx-profiles.adoc`](../../docs/modules/ROOT/pages/cxx-profiles.adoc).

### 2.3 Optional method surface

Mirror modules if useful in the same PR or a tiny follow-up:

- `env.Profiles(enabled=True)` — force on/off for that env.
- `env.ProfilesEnforce(['std::init', …])` — set enforce list for that env.

Not required for MVP if CLI covers CI and local use.

### 2.4 Out of scope: `require` and `suppress` (no Cuppa CLI)

P3589 also defines `profiles::require` and `profiles::suppress`. They are **source/module
attributes with different loci** from `enforce`. Cuppa does **not** expose
`--profiles-require=` or `--profiles-suppress=` — those flags would either mis-teach the
model (if implemented like enforce) or need machinery that is not a small opt-in flag.

| Attribute | Locus (P3589) | Why not a session CLI |
|-----------|---------------|------------------------|
| `enforce` | First empty-declaration of a TU | Session-wide policy **does** map → `--profiles-enforce=` |
| `require` | On a **module-import-declaration** only | Needs import-site / modules graph awareness; not a TU prefix |
| `suppress` | On a **statement or declaration** (local opt-out) | Authors write it in source; Cuppa will not rewrite bodies |

Authors keep using `[[profiles::suppress(…)]]` (and, when modules + Profiles mature,
`[[profiles::require(…)]]` on imports) in their own code. Cuppa’s job for 1.7.0 is
framework enablement (`-fprofiles`) plus optional **enforce** injection / flag mapping.

If a later need appears for “skip enforce injection on these paths”, that is a Cuppa
build carve-out (e.g. exclude globs), not `profiles::suppress`, and would be a separate
design note.

Smoke / docs: `--profiles --profiles-enforce=std::init` (or source
`[[profiles::enforce(std::init)]];` with `--profiles`). Extend designators only when the
toolchain actually supports them.

---

## 3. Refusal rules

| Request | Response |
|---------|----------|
| Rename `BuildProfile` / `cuppa.profiles` as part of #127 | Refuse; separate major if ever wanted |
| Use `env['profiles']` for the C++ Profiles bool | Refuse; keep BuildProfile map |
| Auto-enable Profiles on every Clang 24 | Refuse; only capable toolchains |
| Auto “latest Profiles” toolchain | Refuse; `tc-dep-latest` already out of scope |
| Invent non-existent `-fprofile-enforce` as required | Refuse; map when real, else inject |
| Make Profiles the default for all builds | Refuse; opt-in only for 1.7.0 |
| Close #127 without enforce path | Refuse; enforce is in the ticket goal |
| Add `--profiles-require=` / `--profiles-suppress=` | Refuse; wrong locus for a session CLI (§2.4) |
| Claim multi-profile support on Alliance Clang beyond `std::init` without evidence | Refuse; smoke and docs stay on verified names |

---

## 4. Implementation sketch

| Area | Likely touch |
|------|----------------|
| New method module | `cuppa/methods/cxx_profiles.py` (or `profiles_lang.py`) — `add_options` / `get_options` / activate |
| Toolchain API | `profiles_enable_flags`, `profiles_supported`, `profiles_enforce_flags` on Clang (and stubs returning `[]` / unsupported elsewhere) |
| Compile path | Wrapper / emitter / `-include` generator under `cuppa/cpp/` for **enforce** injection |
| CLI docs | `cli-reference.adoc`, Clang family page note, short hub blurb under toolchains; examples use `std::init` |
| Tests | Unit: option parsing, env key isolation from BuildProfile, enforce flag vs inject choice. Integration: Profiles Clang archive + `--profiles --profiles-enforce=std::init` smoke (skip when archive absent) |

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
| E | Integration smoke | Against a pinned Profiles Clang archive already used in docs |

Slice A is in [#176](https://github.com/ja11sop/cuppa/pull/176). B can merge without C if
enforce is the immediate next PR; prefer B+C together if the inject path stays small.

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
| CLI `--profiles` / `--profiles-enforce=` | Settled |
| No `--profiles-require=` / `--profiles-suppress=` | Settled (§2.4) |
| Alliance Clang smoke profile name `std::init` | Empirically verified (manual) |
| Toolchain flag + **enforce** inject paths | Implemented (probe `-fprofiles`; `-include` fallback) |
| Docs / tests | In progress (unit + skip-if-absent integration) |

**Next focus:** land B+C implementation PR; extend designators when Alliance Clang does.
