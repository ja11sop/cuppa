# Opt-in C++ Profiles (`--profiles` / attribute CLI)

- **Status:** proposal
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
| `--profiles-require=…` (see §2.4) | `env['cxx_profiles_require']` |
| `--profiles-suppress=…` (see §2.4) | `env['cxx_profiles_suppress']` |
| Optional `env.Profiles()` / `env.ProfilesEnforce(…)` (and siblings) | Same keys; mirror `env.Modules()` |

CLI flag names stay short and parallel to `--modules`. Docs and help text always say
**C++ Profiles** when referring to this feature. Profile designators are opaque strings
passed through to attributes/flags (e.g. `std::init`); Cuppa does not rename them.

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
   - Skip or no-op injection when the unit already opens with a matching
     `[[profiles::enforce(…)]];` (idempotent).
   - Module interface units: inject before any declaration, respecting the
     `module;` preamble pattern from P3589 (implementation must follow the
     framework’s “first empty-declaration” rule).

`--profiles` alone enables the framework without injecting enforce attributes;
projects can put `[[profiles::enforce(std::init)]];` (etc.) in source themselves.

### 2.3 Optional method surface

Mirror modules if useful in the same PR or a tiny follow-up:

- `env.Profiles(enabled=True)` — force on/off for that env.
- `env.ProfilesEnforce(['std::init', …])` — set enforce list for that env.
- Later: `env.ProfilesRequire(…)` / `env.ProfilesSuppress(…)` if those CLI flags ship.

Not required for MVP if CLI covers CI and local use.

### 2.4 Considering `--profiles-require=` and `--profiles-suppress=`

P3589 retains three attribute tokens that matter for Cuppa’s CLI family:
`profiles::enforce`, `profiles::require`, and `profiles::suppress`. Symmetry suggests
`--profiles-require=` and `--profiles-suppress=` beside `--profiles-enforce=`. The
**impact** of adding them is not “two more comma lists with the same inject path” —
the paper gives each attribute a different *locus*, so blind TU-prefix injection is
wrong for require and only maybe right for suppress.

#### Paper loci (why CLI is uneven)

| Attribute | Where it belongs (P3589) | Natural Cuppa CLI analogy |
|-----------|--------------------------|---------------------------|
| `enforce` | Empty-declaration at the start of a TU / module interface | Session-wide “build every TU under these profiles” → **`--profiles-enforce=`** |
| `require` | On a **module-import-declaration** only: the imported module (or header unit) must already `enforce` that profile | Not a TU-first empty-declaration. Means “this import must have been built under …” |
| `suppress` | On a **statement or declaration** (local opt-out; optional justification / rule args) | Local “trust me” — not the same as TU-wide policy |

So:

- **`--profiles-enforce=std::init`** maps cleanly to today’s Alliance Clang (verified) and to
  the inject-or-native-flag design in §2.2.
- **`--profiles-require=`** cannot mean “prepend `[[profiles::require(…)]];` to every `.cpp`”.
  That form is not how require works. A faithful CLI would need either:
  1. **Modules-aware wiring** — when Cuppa emits or wraps `import M`, attach
     `[[profiles::require(…)]]` to those imports (and fail if the BMI / interface was not
     built with matching enforce); or
  2. **A softer Cuppa meaning** — “fail the configure/build unless these profiles are in the
     enforce set” (policy / CI gate), which is *not* the P3589 attribute and should not
     reuse the `require` name without a clear docs warning; or
  3. **Defer** until modules + Profiles are exercised together on the Alliance build.
- **`--profiles-suppress=`** is ambiguous at session scope:
  1. **TU-wide suppress** — inject a file-scope suppress if the implementation accepts it as
     an empty-declaration or equivalent (needs proof on Alliance Clang; not verified).
  2. **Default local policy** — Cuppa cannot invent per-statement suppresses without parsing /
     rewriting bodies; out of scope.
  3. **Carve-out list** — “do not inject enforce into these sources” (path globs) is useful for
     third-party TUs but is a Cuppa build concern, not `profiles::suppress`. Prefer a
     separate knob later (e.g. `--profiles-enforce-exclude=`) rather than overloading
     suppress.
  4. **Header exemption** — P3589 also discusses `profiles::exempt` for headers; that is yet
     another attribute and should not be smuggled into `--profiles-suppress=`.

#### Interaction and ordering

If more than one of enforce / require / suppress are set:

- Any of them **implies `--profiles`** (framework on), same as enforce alone today.
- Enforce + suppress naming the **same** designator at session scope is contradictory unless
  suppress is defined as “local override only” (source) while enforce is the default — CLI
  should **StopError** on the same name appearing in both `--profiles-enforce=` and
  `--profiles-suppress=` until a layered model is specified.
- Require does not replace enforce: a program still `enforce`s in its own TUs; require
  constrains **dependencies**. Document that clearly so users do not pass
  `--profiles-require=std::init` expecting initialization checking in their `.cpp` files.

#### Implementation cost if we reserve the flags now

| Choice | Pros | Cons |
|--------|------|------|
| **A. Document + reserve CLI in 1.7.0, implement enforce only** | Stable flag names; no false require/suppress behaviour | Help text must say “reserved / not yet wired” or omit until ready |
| **B. Ship all three with inject-as-first-line** | Symmetric code path | **Incorrect** for require; likely wrong for suppress; teaches bad models |
| **C. Ship require/suppress only when native compiler flags exist** | Honest | May never land; still need attribute story for Alliance Clang |
| **D. Full modules-aware require + local suppress tooling** | Faithful to P3589 | Large; depends on modules path maturity (`--modules`) |

**Proposal (not yet settled as product behaviour):** prefer **A** for the first
implementation PR — implement `--profiles` + `--profiles-enforce=` against `std::init`,
and add a plan subsection + issue note that `--profiles-require=` /
`--profiles-suppress=` are **design-reserved** pending §2.4 resolution. Do not merge
choice B. If we want the options visible early for discussion, register them with
help text that points at this section and StopError with “not implemented” rather than
injecting wrong attributes.

#### Smoke / docs consequences

- First integration example: `--profiles --profiles-enforce=std::init` on a Profiles
  Clang session (or source-only `[[profiles::enforce(std::init)]];` with `--profiles`).
- Do not document `--profiles-require=std::init` as enabling init checking.
- When Alliance Clang adds more profiles, extend examples; Cuppa still passes designators
  through unchanged.

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
| Inject `[[profiles::require(…)]];` as a TU-first empty-declaration | Refuse; wrong locus (import-only in P3589) |
| Treat `--profiles-require=` as a synonym for enforce | Refuse; different attribute / meaning |
| Claim multi-profile support on Alliance Clang beyond `std::init` without evidence | Refuse; smoke and docs stay on verified names |

---

## 4. Implementation sketch

| Area | Likely touch |
|------|----------------|
| New method module | `cuppa/methods/cxx_profiles.py` (or `profiles_lang.py`) — `add_options` / `get_options` / activate |
| Toolchain API | `profiles_enable_flags`, `profiles_supported`, `profiles_enforce_flags` on Clang (and stubs returning `[]` / unsupported elsewhere) |
| Compile path | Wrapper / emitter / `-include` generator under `cuppa/cpp/` for **enforce** injection (require/suppress only after §2.4) |
| CLI docs | `cli-reference.adoc`, Clang family page note, short hub blurb under toolchains; examples use `std::init` |
| Tests | Unit: option parsing, env key isolation from BuildProfile, enforce flag vs inject choice. Integration: Profiles Clang archive + `--profiles --profiles-enforce=std::init` smoke (skip when archive absent) |

Registration follows the modules pattern (`add_options` / `add_to_env` /
`init_env_for_variant`).

---

## 5. Work slices

| Slice | Deliverable | Notes |
|-------|-------------|-------|
| A | Design + issue refresh | This document; #127 papers + goal text; §2.4 require/suppress |
| B | `--profiles` → `-fprofiles` | Toolchain API + StopError when unsupported |
| C | `--profiles-enforce=` | Native map hook + inject fallback; smoke with `std::init` |
| D | Docs + samples | CLI reference; toolchain page; `std::init` example |
| E | Integration smoke | Against a pinned Profiles Clang archive already used in docs |
| F | `--profiles-require=` / `--profiles-suppress=` | Only after §2.4 settled; not the same inject path as enforce |

Slice A is in [#176](https://github.com/ja11sop/cuppa/pull/176). B can merge without C if
enforce is the immediate next PR; prefer B+C together if the inject path stays small.
Slice F is explicitly later.

---

## 6. Papers and references (issue table)

Canonical paper list lives on [#127](https://github.com/ja11sop/cuppa/issues/127).
Keep that table updated when new revisions land; do not duplicate the full table in
product docs. Framework and syntax anchors for implementers:

- P3589R2 — framework (`[[profiles::enforce]]` / require / suppress); **loci differ**
- P3081R2 — core safety profiles direction
- P4222R1 — initialization profile (successor focus vs older P3402 line; Alliance name `std::init`)
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
| Alliance Clang smoke profile name `std::init` | Empirically verified (manual) |
| CLI `--profiles-require=` / `--profiles-suppress=` | Discussed (§2.4); prefer reserve, implement later |
| Toolchain flag + **enforce** inject paths | Proposed |
| Docs / tests | Not started |

**Next focus:** implement slices B+C (`--profiles` + `--profiles-enforce=std::init`) on a
Profiles-capable Clang under **1.7.0.dev**; keep require/suppress out of that PR unless
§2.4 is settled toward a faithful (non-inject) design.
