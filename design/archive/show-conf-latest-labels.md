# Note: name remembered `gitlab_package_latest_*` pins on conf show

- **Status:** shipped
- **Related:** ROADMAP `cli-show-conf-latest-labels`;
  [`show-global-conf.md`](show-global-conf.md);
  [`gitlab-package-latest.md`](gitlab-package-latest.md);
  `cuppa/package_managers/gitlab_latest.py` (`registry_latest_conf_key`,
  `remember_registry_latest`); conf-only exit in `cuppa/construct.py`;
  Antora [`dependencies/using/gitlab.adoc`](../../docs/modules/ROOT/pages/dependencies/using/gitlab.adoc)
- **Updated:** 2026-11-14
- **Impact:** `patch` — shipped in 1.14.2 — [#407](https://github.com/ja11sop/cuppa/pull/407);
  display + remember-time sidecar; pin keys and resolve behaviour unchanged

## Observed

`--show-conf` / `--show-global-conf` print an equivalent `cuppa -D …` line whose
remembered registry-latest pins look like:

```text
--gitlab_package_latest_3e9aca8814a24728=1.92
--gitlab_package_latest_2c97352080a3c10c=1.34.8
```

The suffix is `sha256("{registry}|{package}")[:16]` — stable and unique, but
**one-way**. Operators cannot tell which package a pin belongs to without
re-deriving the hash from a known registry+package pair. That is especially
awkward on `--show-global-conf`, where pins accumulate across tip projects.

## Intent

Keep the conf keys and the equivalent CLI line as version pins only. After that
line (when any `gitlab_package_latest_*` keys are present), print a **display-only**
console-report mapping that names each pin.

Example shape (judgement-tree chrome: emphasised info count, muted stem,
plain hash ends so the digest stays scannable):

```text
2 registry latest mappings:
│
├── 2c97352080a3c10c · (unknown package) = 1.34.8
└── 3e9aca8814a24728 · boost = 1.92
```

Optional muted child or suffix for registry host when it helps disambiguate
same package name on two registries — settle in implementation if a soak tip
has collisions; default is package + version only.

## Settled decisions

| Decision | Choice |
|----------|--------|
| Conf key format | **Unchanged** — keep `gitlab_package_latest_<digest>` = version string |
| Equivalent `cuppa -D` line | **Unchanged** — still only the pin keys (no fake CLI flags for labels) |
| Where labels live | **Sidecar at remember time**, not inferred by reversing the hash |
| Sidecar form | Parallel conf keys `gitlab_package_latest_label_<digest> = "<package>"` (string), same conf file as the pin (project vs `~/.cuppaconfig` via existing `registry_latest_conf_path` scoping). Exclude `gitlab_package_latest_label_*` from `_is_saveable` and from the equivalent CLI builder |
| Why conf sidecar (not a separate JSON) | Same downloads-root scoping and clear/remove story as the pin; no second path to drift; `load_settings_file` already skips unknowns for builds |
| Registry URL in sidecar | **Optional later** — start with package name only; add `gitlab_package_latest_registry_<digest>` only if soak shows same-name collisions |
| When to write | `remember_registry_latest` upserts the label whenever it upserts the version (online success path) |
| Show surfaces | Both `--show-conf` (merged settings that include these keys) and `--show-global-conf` (global-only map). Emit the tree from whichever settings dict the equivalent line just used |
| Empty / no pins | Omit the tree entirely |
| Unknown label | Leaf shows `(unknown package) = <version>` until the next successful remember fills the sidecar. Do **not** fail show |
| Tip sconstruct scan | **Non-goal for v1** — incomplete for global conf; optional later as a best-effort fill for unknown labels in the current tip only |
| Remove / clear | Existing `--remove-settings` / `--clear-conf` (and global twins) already drop keys by name or wipe the file; document that operators removing a pin should also remove its `…_label_*` twin (or clear both). Optional nicety: removing a pin key also drops its label key — **follow-on**, not required to ship the tree |
| Console channel | Console report (`write_report_lines` / judgement-tree style), not `logger.info`, so `-Q` still shows it under the CONFIGURE banner |
| PR packaging | **Fold into [#407](https://github.com/ja11sop/cuppa/pull/407)** |

## Non-goals

- Changing how offline / unverified `latest` resolve uses the pin.
- Putting package names into the equivalent `cuppa -D` line.
- A human-editable “friendly key” as the pin itself (would break existing confs).
- Migrating historical pins offline (no registry round-trip on show).

## Implementation sketch

1. `remember_registry_latest`: after upserting the version key, upsert
   `gitlab_package_latest_label_<digest>` with the package string; exclude both
   label keys from saveable / equivalent-CLI filters (configure + construct).
2. Helper: given a settings dict, collect `gitlab_package_latest_<16 hex>` pins
   (not `…_label_*`), join labels, return ordered rows.
3. Conf-only exit in `construct.py`: after printing the equivalent line(s), if
   rows exist, emit the report tree (once per settings map shown — global then
   merge when both flags are set).
4. Unit tests: key helper; remember writes label; show builder; saveable
   exclusion; unknown label spelling.
5. Integration: seed home `.cuppaconfig` with pin + label (and pin without
   label); `--show-global-conf` asserts tree text.
6. Antora: one sentence under remembered version / conf-show docs pointing at
   the mapping tree.

## Progress

| Slice | Status |
|-------|--------|
| Plan + ROADMAP / design index | Done |
| Implement sidecar + show tree + tests/docs | **Done** — on [#407](https://github.com/ja11sop/cuppa/pull/407) |
| Choose #407 vs follow-up PR | Done — folded into #407 |
