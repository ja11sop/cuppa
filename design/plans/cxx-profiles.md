# Opt-in C++ Profiles (`--profiles` / `--profiles-enforce`)

- **Status:** proposal
- **Related:** [`ROADMAP.md`](../../ROADMAP.md) — `tc-dep-profiles`; [#127](https://github.com/ja11sop/cuppa/issues/127); toolchain supply [#160](https://github.com/ja11sop/cuppa/issues/160) (done)
- **Updated:** 2026-08-10

Ship opt-in WG21 / experimental-Clang **C++ Profiles** support in the **1.7.0** cycle.
Profiles-capable Clang archives are already fetchable via `--toolchain-archive=` /
`--clang-root=`; this plan is the Cuppa flag surface and compile-path wiring.

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
**C++ Profiles** when referring to this feature.

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
   [[profiles::enforce(profile1, profile2)]];
   ```

   Injected as the first line of the unit presented to the compiler (empty-declaration
   form required by the framework papers). Prefer a generated side-file or
   compiler `-include` / forced-include strategy if that preserves `#line` / diagnostics
   better than rewriting the user’s path in place; exact mechanism is an
   implementation detail settled in the PR, with these constraints:

   - Do not mutate the user’s source tree.
   - Diagnostics should still point at the user’s file when practical.
   - Skip or no-op injection when the unit already opens with a matching
     `[[profiles::enforce(…)]];` (idempotent).
   - Module interface units: inject before any declaration, respecting the
     `module;` preamble pattern from P3589 (implementation must follow the
     framework’s “first empty-declaration” rule).

`--profiles` alone enables the framework without injecting enforce attributes;
projects can put `[[profiles::enforce(…)]]` in source themselves.

### 2.3 Optional method surface

Mirror modules if useful in the same PR or a tiny follow-up:

- `env.Profiles(enabled=True)` — force on/off for that env.
- `env.ProfilesEnforce(['type_safety', …])` — set enforce list for that env.

Not required for MVP if CLI covers CI and local use.

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

---

## 4. Implementation sketch

| Area | Likely touch |
|------|----------------|
| New method module | `cuppa/methods/cxx_profiles.py` (or `profiles_lang.py`) — `add_options` / `get_options` / activate |
| Toolchain API | `profiles_enable_flags`, `profiles_supported`, `profiles_enforce_flags` on Clang (and stubs returning `[]` / unsupported elsewhere) |
| Compile path | Wrapper / emitter / `-include` generator under `cuppa/cpp/` for enforce injection |
| CLI docs | `cli-reference.adoc`, Clang family page note, short hub blurb under toolchains |
| Tests | Unit: option parsing, env key isolation from BuildProfile, enforce flag vs inject choice. Integration: Profiles Clang archive + `--profiles` / `--profiles-enforce=` smoke (skip when archive absent) |

Registration follows the modules pattern (`add_options` / `add_to_env` /
`init_env_for_variant`).

---

## 5. Work slices

| Slice | Deliverable | Notes |
|-------|-------------|-------|
| A | Design + issue refresh | This document; #127 papers + goal text |
| B | `--profiles` → `-fprofiles` | Toolchain API + StopError when unsupported |
| C | `--profiles-enforce=` | Native map hook + inject fallback |
| D | Docs + samples | CLI reference; toolchain page; maybe one Antora sample |
| E | Integration smoke | Against a pinned Profiles Clang archive already used in docs |

Slice A lands first (no product behaviour). B can merge without C if enforce is the
immediate next PR; prefer B+C together if the inject path stays small.

---

## 6. Papers and references (issue table)

Canonical paper list lives on [#127](https://github.com/ja11sop/cuppa/issues/127).
Keep that table updated when new revisions land; do not duplicate the full table in
product docs. Framework and syntax anchors for implementers:

- P3589R2 — framework (`[[profiles::enforce]]` / require / suppress)
- P3081R2 — core safety profiles direction
- P4222R1 — initialization profile (successor focus vs older P3402 line)
- P3984R0 — type-safety profile
- Experimental Clang: [cppalliance/clang `profiles-framework`](https://github.com/cppalliance/clang/tree/profiles-framework),
  docs `clang/docs/ProfilesFramework.rst`, release archives under
  `cppalliance/clang` tags such as `profiles-2026-08-07-27`

---

## 7. Progress snapshot

| Item | State |
|------|-------|
| Profiles Clang supply (`--toolchain-archive=` / session names) | Done (#160) |
| Naming: keep BuildProfile; `env['cxx_profiles']` for language feature | Settled |
| CLI `--profiles` / `--profiles-enforce=` | Settled (not implemented) |
| Toolchain flag + inject paths | Proposed |
| Docs / tests | Not started |

**Next focus:** implement slice B on a Profiles-capable Clang after #175 (1.7.0.dev)
merges.
