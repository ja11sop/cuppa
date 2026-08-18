# Profiles inventory should imply unlimited compiler error limit

- **Status:** issue draft
- **Related:** [`ROADMAP.md`](../../ROADMAP.md) — C++ Profiles (`profiles-violation-report`); [`plans/cxx-profiles-report.md`](../plans/cxx-profiles-report.md) § [Implied diagnostic error limit](../plans/cxx-profiles-report.md#prof-report-error-limit); shipped implied `-i` [#199](https://github.com/ja11sop/cuppa/issues/199) / [#203](https://github.com/ja11sop/cuppa/pull/203); existing `--cxx-disable-error-limit` [`archive/cxx-profiles.md`](../archive/cxx-profiles.md) §2.3
- **Updated:** 2026-08-18
- **Impact:** minor — new CLI options; Profiles inventory runs change the effective per-TU diagnostic cap unless explicitly overridden

## Problem

Profiles inventory mode already implies SCons keep-going (`-i`) when the user did not pass it
([`profiles_inventory_cli.py`](../../cuppa/core/profiles_inventory_cli.py)). That lets the **build**
continue across translation units, but each compile can still hit the **compiler diagnostic cap**
(Clang default error limit, GCC `-fmax-errors` default, MSVC internal cap). The Profiles collector
only records diagnostics the compiler actually emitted.

Authors who pass `--cxx-profiles-report` (or declare `env.CollateCxxProfilesIndex()`) but forget
`--cxx-disable-error-limit` can therefore get an inventory that looks **better than the tree
really is** — worse than an honest truncated build because the HTML reads like a complete survey.

## Proposal

Mirror the implied `-i` pattern: **inventory mode implies unlimited errors per TU**, with explicit
opt-out.

### Precedence (highest wins)

| Priority | Input | Effective behaviour |
|----------|--------|---------------------|
| 1 | `--cxx-error-limit=N` | Append toolchain flag for **N** (`0` = unlimited) |
| 2 | `--cxx-default-error-limit` | No cuppa error-limit flag — compiler default cap |
| 3 | `--cxx-disable-error-limit` | Unlimited (`N=0`); keep as shorthand for non-inventory sweeps |
| 4 | Inventory active (`--cxx-profiles-report` or `CollateCxxProfilesIndex()`) | Unlimited unless overridden by 1–2 |
| 5 | Otherwise | Compiler default (no cuppa flag) |

Prefer **two flags** over a magic `default` token in `--cxx-error-limit=`:

- `--cxx-error-limit=N` — integer passthrough (`0` = unlimited)
- `--cxx-default-error-limit` — boolean override of the inventory implication

### Toolchain API

Generalise `disable_error_limit_flags(env)` → `error_limit_flags(env, limit)` on
`cuppa/toolchains/{clang,gcc,cl}.py`:

| `limit` | Clang | GCC | MSVC `cl` |
|---------|-------|-----|-----------|
| unset / default | *(no flag)* | *(no flag)* | *(no flag)* |
| `0` | `-ferror-limit=0` | `-fmax-errors=0` | *(none)* |
| `N>0` | `-ferror-limit=N` | `-fmax-errors=N` | *(none)* |

When a non-default limit was requested but the active toolchain returns no flags, emit a **one-line
warning** (same story as today for `--cxx-disable-error-limit` on MSVC).

### Activation paths

Same two paths as implied `-i`:

1. CLI `get_options` — when inventory is enabled, set effective unlimited unless the user passed
   `--cxx-default-error-limit` or `--cxx-error-limit=`
2. `activate_cxx_profiles_report()` / `init_env_for_variant` — same for method-only inventory

Optional: one **info** console line when inventory implied unlimited (skipped when the user
explicitly chose default or a numeric limit).

### `configure.conf` and `default_options`

**No new persistence machinery.** Any registered cuppa CLI option can already be stored under its
internal key (`dest`) in `configure.conf` or `cuppa.run(default_options=…)` — values are loaded
via the same path as flags (see `docs/modules/ROOT/pages/configuration.adoc`).

For this work the gap is **documentation**, not implementation of conf loading:

| Internal key | CLI |
|--------------|-----|
| `cxx_error_limit` | `--cxx-error-limit=N` *(new)* |
| `cxx_default_error_limit` | `--cxx-default-error-limit` *(new)* |
| `cxx_disable_error_limit` | `--cxx-disable-error-limit` *(existing)* |

Add a short **C++ Profiles** subsection to `configuration.adoc` (and cross-links from
`cxx-profiles.adoc` / CLI reference) with example keys — same pattern as
`reports_link_style` / `reports_*_hosts` documentation.

Example project default (explicit unlimited for all enforce builds, not only inventory):

[source,python]
----
# configure.conf
cxx_disable_error_limit = True
----

Example override when inventory is active but a capped compile is intentional:

[source,sh]
----
cuppa -D --cxx-profiles-report --cxx-default-error-limit …
----

### Docs / examples

Update “recommended pairing” examples that today list
`--cxx-disable-error-limit --cxx-profiles-report` to note that **report mode implies unlimited**
and the flag is only needed for non-report enforce sweeps or explicit `configure.conf` defaults.

## Acceptance criteria

- [ ] Inventory mode (`--cxx-profiles-report` or `CollateCxxProfilesIndex()`) appends unlimited
      error-limit flags on Clang/GCC when the user did not override
- [ ] `--cxx-default-error-limit` suppresses implied unlimited even in inventory mode
- [ ] `--cxx-error-limit=N` sets an explicit cap or `0` for unlimited; wins over inventory
      implication
- [ ] `--cxx-disable-error-limit` remains equivalent to `--cxx-error-limit=0` for ordinary builds
- [ ] MSVC: warn when a non-default limit was requested but cannot be applied
- [ ] Unit tests: precedence table, toolchain flag mapping, inventory activation without explicit
      disable flag
- [ ] Integration test: inventory run without `--cxx-disable-error-limit` still appends
      `-ferror-limit=0` / `-fmax-errors=0` on the active Linux toolchain
- [ ] Antora: CLI reference, C++ Profiles hub, and Configuration page document keys + behaviour
- [ ] [`cxx-profiles-report.md`](../plans/cxx-profiles-report.md) progress snapshot updated when
      shipped

## Out of scope

- MSVC support for lifting the internal `cl` cap (unchanged — document only)
- CI threshold / `--cxx-profiles-report-allow-errors` (deferred elsewhere)
