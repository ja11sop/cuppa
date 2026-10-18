# Plan: Cascade — do not forward tip-local options

- **Status:** done (soak 2026-10-19)
- **Related:** [`../archive/cascade-consume-ux-soak.md`](../archive/cascade-consume-ux-soak.md) (`opt-compat-early`); [`../archive/package-develop-local.md`](../archive/package-develop-local.md) (nested argv drops tip dependency-scoped flags); `tip_forward_args` / `tip_dependency_option_flags` in [`package_cascade.py`](../../cuppa/package_managers/package_cascade.py); [`console-stop-error-reporting.md`](console-stop-error-reporting.md); [`cascade-amend-package-manifest.md`](cascade-amend-package-manifest.md) (`--amend-cascade-manifests`); [`cascade-build-deps-tip-consume.md`](cascade-build-deps-tip-consume.md) (separate: tip consume forest stages); ROADMAP **1.13.0** related
- **Updated:** 2026-10-19
- **Impact:** patch — nested cascade argv filter; tip UX when custom `cuppa.add_option` flags are present

> Tip-local AddOption drops are the opposite of cascade-amend: here we **must
> not** forward unknown tip flags; there we may **choose** to forward / specialize
> a known cuppa flag so nests metadata-amend instead of full-building.

## Problem

`tip_forward_args` already drops:

* cascade / publisher / amend meta-flags (`_NESTED_DROP_*`);
* tip **dependency-scoped** flags discovered via
  `tip_dependency_option_flags(env)` (`--<dep>-gitlab-develop`, location
  overrides, …).

It does **not** drop **tip-local** options registered with `cuppa.add_option`
in the tip `sconstruct` (project-only helpers). Those travel into nested
publisher sessions verbatim. The child never registered them → SCons fails
before the nest build:

```text
nested build 1 of 9: abseil_cpp …
  command [… -m cuppa … --test-postgres-container …]
SCons Error: no such option: --test-postgres-container
```

Soak (2026-10-18): tip
`--cascade --build-cascade-dependencies --amend-package-manifest` with
`--test-postgres-container` (and similarly `--start-dev-env`,
`--pipeline-debugging` on the same tip) breaks the first nest.

Global settings that belong on every project still travel via
`~/.cuppaconfig` (child loads itself). Tip-local AddOption flags are **not**
that channel.

## Intent

1. Identify CLI flags the **tip** registered that nested publishers will not
   know.
2. Drop those from `tip_forward_args` (exact and `=` / separate-value forms as
   needed).
3. Keep forwarding real cuppa / SCons globals (variants, toolchains, offline,
   terse, verbosity, …) and continue dropping dependency-scoped tip flags.
4. Optionally note in cascade plan / nest command preview when tip-local flags
   were stripped (debug or subdued one-liner — settle later).

## Non-goals

- Auto-forwarding tip-local flags into nests that happen to define the same
  dest (too magical; nests opt in via their own sconstruct / cuppaconfig).
- Replacing `opt-compat-early` (incompatible cuppa flag *sets*); this is
  **unknown-on-child** tip custom options.
- Changing how `cuppa.add_option` works for non-cascade tips.

## Direction

### Discovery

`cuppa.add_option` → `cuppa.core.options.add_option` → `SCons.Script.AddOption`
today with **no registry**. Lean:

1. **Track tip AddOption ids** in `cuppa.core.options` (set of `--flag` strings
   passed as the first arg / option strings). Call sites already use
   `cuppa.add_option('--test-postgres-container', …)`.
2. Distinguish **cuppa-module** registrations (variants, toolchains, package
   managers, …) from **tip** registrations:
   * either only record when `add_option` is invoked from outside `cuppa.*`
     (stack inspect — brittle), or
   * record all AddOption through `cuppa.add_option`, and maintain an
     **allowlist** of cuppa-owned option string prefixes / names registered
     during cuppa bootstrap; tip flags = recorded − allowlist, or
   * record tip flags only for calls after `cuppa.run` starts reading the
     sconstruct body (hook: tip `add_option` wrapper remains the public API —
     mark “project phase” once construct begins loading the tip script).

Simplest robust lean: **`cuppa.add_option` always records**; cuppa’s own
`AddOption` paths that go through the same wrapper populate an allowlist at
module-registration time; anything recorded that is not allowlisted is
tip-local for nest drop. Paths that call `SCons.Script.AddOption` directly
stay nest-safe only if they are cuppa internals (audit).

### Forward filter

Extend `tip_forward_args` (when `env` is available, or always via the recorded
set):

```text
drop_exact |= tip_local_option_flags()
```

Same prefix / takes-value handling as dependency-scoped drops where options
take a separate argv token.

### Operator model

| Flag class | Nest behaviour |
|------------|----------------|
| Cuppa / SCons global (`--rel`, `--toolchains`, `--offline`, `--terse-output`, …) | Forward (subject to existing nest-rel / drop tables) |
| Tip dependency-scoped (`--foo-gitlab-develop`, …) | Drop today |
| Tip-local `cuppa.add_option` (`--test-postgres-container`, …) | **Drop** (this plan) |
| `~/.cuppaconfig` keys | Child loads; not tip argv |

## Open questions

1. **Allowlist maintenance** — derive from registration modules vs static
   frozenset of known cuppa flags (static set drifts; registration-derived is
   better).
2. **Value-taking tip options** — detect `nargs` / `action` from the recorded
   kwargs so `skip_next` works; store metadata beside the flag string.
3. **Visibility** — silent drop vs subdued nest log line listing stripped flags.
4. **`--cascade-plan` command reprint** — should the printed nest command show
   argv **after** tip-local stripping so operators are not surprised?

## Initial investigation notes

* Failure is at **child** option parse (`scons` / cuppa launcher), not during
  tip resolve — plan tree prints successfully, then nest 1 dies.
* `tip_dependency_option_flags` cannot see `--test-postgres-container` (not a
  dependency factory option).
* Workaround today: omit tip-local flags on cascade command lines.
* Related soak leftover `opt-compat-early` remains about **known incompatible
  cuppa combinations**; keep that separate but cross-link.

## Progress

| Item | Status |
|------|--------|
| Soak captured | Done — this proposal |
| Track `cuppa.add_option` + nest drop | **Done** — `cuppa.add_option` → `add_tip_option`; cuppa internals keep `add_option` |
| Implementation | **Done** on this PR — `tip_forward_args` drops tip-local exact / `=` / takes-value |
| Antora cascade note | **Done** |
| Live soak with tip helpers on cascade line | **Succeeded** — nest command lines omit `--test-postgres-container`; tip still runs postgres docker helpers |
