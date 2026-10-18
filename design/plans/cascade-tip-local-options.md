# Plan: Cascade — do not forward tip-local options

- **Status:** done (soak 2026-10-19); follow-on escape hatch captured below — **not this PR**
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

## Open questions (core slice — settled)

1. **Allowlist maintenance** — **settled:** `cuppa.add_option` → tip-local;
   cuppa internals use `cuppa.core.options.add_option` (not tip-local).
2. **Value-taking tip options** — **settled:** kwargs recorded;
   `tip_local_option_takes_value()` drives `skip_next`.
3. **Visibility** — silent drop for v1; nest `command […]` already shows
   post-strip argv (enough for soak). Subdued “stripped: …” line still optional.
4. **`--cascade-plan` command reprint** — nest begin banners show argv **after**
   stripping; tip plan banner still shows the full tip command (correct).

## Initial investigation notes

* Failure is at **child** option parse (`scons` / cuppa launcher), not during
  tip resolve — plan tree prints successfully, then nest 1 dies.
* `tip_dependency_option_flags` cannot see `--test-postgres-container` (not a
  dependency factory option).
* Workaround today: omit tip-local flags on cascade command lines (no longer
  required after this PR — tip may keep helpers; nests drop them).
* Related soak leftover `opt-compat-early` remains about **known incompatible
  cuppa combinations**; keep that separate but cross-link.

## Remainder: opt-in forward of selected tip-local options

**Not this PR.** Default drop is correct and soaked. An escape hatch is only
useful when tip **and** nests deliberately share the same custom option (nest
must still `cuppa.add_option` it — Cuppa cannot invent child registrations).
Forwarding is “stop dropping these tip-local argv tokens,” not “teach nests
unknown flags.”

### Constraint

| Situation | Outcome |
|-----------|---------|
| Tip-local flag, nest never registered it | Nest still dies with `no such option` if forwarded |
| Tip-local flag, nest also registers it | Forward can work |
| Tip-only helper (`--test-postgres-container` soak) | Must stay **off** any allowlist |

### Approaches considered

| Id | Shape | Verdict |
|----|-------|---------|
| **A** | CLI allowlist `--cascade-local-options=opt1,opt2` (with/without leading `--`) | **Lean** — same family as `--cascade-variants`; safe default; discoverable on the command line |
| **B** | Boolean forward-all tip-local | **Refuse** as primary — recreates soak nest-1 failure whenever tip mixes tip-only and shared helpers |
| **C** | `cuppa.add_option(..., cascade=True)` / `cascade_forward=True` | Good later for **standing** monorepo conventions; still needs nest registration |
| **D** | Tip API `cuppa.cascade_forward_local_options([...])` | Cleaner than C when many flags share one policy; same constraints |
| **E** | Auto-intersect tip-local with “what child knows” | **Defer** — brittle (parse child sconstruct / side channel); too magical |
| **F** | Denylist (drop only listed tip-local) | Prefer allowlist — denylist ≈ forward-all for tips with many helpers |

### Settled lean for a follow-on (when demanded)

1. Keep **default = drop all tip-local** (shipped).
2. Add **A** — comma allowlist CLI; normalize names; **StopError** on names not
   in the tip-local set (typos must not silently no-op).
3. Allowlist removes flags only from the tip-local drop set — never un-drops
   `_NESTED_DROP_*` or dependency-scoped tip flags even if named in the list.
4. Empty / valueless flag → StopError.
5. Apply on the same `tip_forward_args` path used for package nests and location
   `--stage-develop` nests (same filter).
6. Optional later: **C** registration mark ∪ CLI allowlist (CLI wins for
   one-offs). Document that nests must still register forwarded options.
7. Naming: `--cascade-local-options` is fine; `--cascade-forward-local-options`
   is clearer about the verb — pick when implementing.

Soak (2026-10-19) did **not** need this escape hatch; tip helpers stayed tip-only
and nests succeeded.

## Progress

| Item | Status |
|------|--------|
| Soak captured | Done — this proposal |
| Track `cuppa.add_option` + nest drop | **Done** — `cuppa.add_option` → `add_tip_option`; cuppa internals keep `add_option` |
| Implementation | **Done** on this PR — `tip_forward_args` drops tip-local exact / `=` / takes-value |
| Antora cascade note | **Done** |
| Live soak with tip helpers on cascade line | **Succeeded** — nest command lines omit `--test-postgres-container`; tip still runs postgres docker helpers |
| Opt-in forward allowlist (`--cascade-local-options=…`) | **Captured** (remainder above) — not this PR |
