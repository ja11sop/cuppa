# Note: `--show-global-conf` for `~/.cuppaconfig`

- **Status:** proposal
- **Related:** ROADMAP `cli-show-global-conf`; `cuppa/configure.py`; Antora
  [`configuration.adoc`](../../docs/modules/ROOT/pages/configuration.adoc) /
  [`cli/storage-and-configuration.adoc`](../../docs/modules/ROOT/pages/cli/storage-and-configuration.adoc);
  integration [`test_configure_conf.py`](../../tests/integration/test_configure_conf.py)
- **Updated:** 2026-11-13
- **Impact:** `patch` — new conf-only CLI flag; ships with 1.14.2

## Gap

Project and global configuration already pair for write / update / clear / remove:

| Project | Global |
|---------|--------|
| `--show-conf` | **(missing)** |
| `--save-conf` | `--save-global-conf` |
| `--update-conf` | `--update-global-conf` |
| `--remove-settings` | `--remove-global-settings` |
| `--clear-conf` | `--clear-global-conf` |

`--show-conf` is conf-only (no build): it loads global then project into
`configured_options`, logs each `loading` key, and prints an equivalent
`cuppa -D …` line from the **merged** map. Help text says “the configuration
file”; Antora says “global and project files”. There is no flag that inspects
`~/.cuppaconfig` alone — useful when diagnosing workstation defaults before
project overrides, or when no project `configure.conf` exists.

## Settled decisions

| Decision | Choice |
|----------|--------|
| Flag | `--show-global-conf` (`dest=show_global_conf`, `store_true`) |
| Scope | Read and report **`~/.cuppaconfig` only** (same path as `Configure.global_config_path()` / `global_config_path()`) |
| Conf-only | Yes — same exit path as `--show-conf` (`handle_conf_only` / `action() == "show_global"`); no build |
| Missing file | Same tone as other conf ops: info that the file does not exist; still exit without building |
| Equivalent CLI line | Built from **global settings only**, not the project merge |
| `--show-conf` behaviour | **Unchanged** this slice (keep merged load + equivalent line). Clarify Antora / `-h` wording so “merged effective” vs “global-only” is obvious once `--show-global-conf` exists |
| Both flags together | Allowed; report global first, then existing `--show-conf` merge (order matches load order). No Options Error |
| Saveable | Exclude `show_global_conf` from `_is_saveable` (with the other conf meta-flags) |
| `--use-conf` | Does **not** retarget global show (project alternate path only, as today) |

## Implementation sketch

1. `cuppa.core.options.add_option( '--show-global-conf', … )` next to the other global conf flags in `cuppa/configure.py`.
2. Wire `Configure.load` / `handle_conf_only` / `action` / `_is_saveable`.
3. On show-global: load settings from the global path only (reuse `load_settings_file` or the existing file loader), print `loading` lines (or a dedicated action verb), then print the equivalent `cuppa -D …` from that map — mirror the construct.py conf-only banner shape so operators recognise it.
4. Antora: add the row on `configuration.adoc` and `cli/storage-and-configuration.adoc`; mention in the “inspect with …” sentence.
5. Tests: unit for option wiring / conf-only / saveable exclusion; integration beside `test_save_and_show_conf` that writes a temp home `.cuppaconfig`, runs `--show-global-conf`, and asserts keys appear without requiring a project conf.

## Non-goals

- Changing merge precedence or the on-disk format.
- A `--show-project-conf` that dumps `configure.conf` without the global merge (can follow if operators still want file-scoped project show after this ships).
- Interactive editors or pretty-printers beyond today’s key = value / equivalent CLI presentation.

## Progress

| Slice | Status |
|-------|--------|
| Plan + ROADMAP / design index | **This PR** (cycle open) |
| Implement flag + docs + tests | Todo |
