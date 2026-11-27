# Note: SCons `-j` can spuriously rebuild heavy C++ objects

- **Status:** **fixed** — skip terse `is_up_to_date()` lookahead when `num_jobs > 1`
- **Related:** `cuppa/progress.py` `credit_terse_up_to_date_lookahead`; `CUPPA_TERSE_BISECT` soak switch; [#404](https://github.com/ja11sop/cuppa/pull/404); [#267](https://github.com/ja11sop/cuppa/issues/267) / [#269](https://github.com/ja11sop/cuppa/pull/269); ROADMAP `parallel-scons-large-graph`; Antora [`cli/building.adoc`](../../docs/modules/ROOT/pages/cli/building.adoc)
- **Updated:** 2026-11-27
- **Impact:** `patch`

## Observed

On a tip with deep Boost / Asio / package / develop include graphs, back-to-back
`--parallel` (SCons `num_jobs ≥ 2`) builds repeatedly recompile the same translation
units even though sources and headers are unchanged on disk. A following serial run
(or `--parallel=1`) does one cleanup rebuild, then stays fully up to date. The next
multi-job run starts the loop again.

`--debug=explain` shows, for those `.o` files:

- hundreds of paths **no longer a dependency** / **new dependency** (often including
  the `.cpp` itself in *both* lists), and
- thousands of headers **changed**,

while sampled header/source mtimes and sizes stay fixed across the rebuild. Only
`.sconsign.dblite` changes.

Control: after a stable serial up-to-date tree, `--parallel=1` stays up to date;
`--parallel=2` (or bare `--parallel`) spuriously rebuilds **when `--terse-output`
is on** (including via `~/.cuppaconfig`). Affinity alone is not the bug.

### Multi-sconscript vs single-sconscript (2026-11-27 soak)

On a mid-size tip with several test sconscripts under one sconstruct (deep Boost
include graph, `--develop`), the spurious loop correlates with **building more
than one sconscript in the same session**:

| Flow | Result |
|------|--------|
| `--parallel --scripts=<one test sconscript>` then serial `--test --scripts=…` | **Stable** — no recompile of the already-built `.o` |
| `--parallel` (all sconscripts) then serial `--test` | **Spurious rebuild** of heavy TUs before tests run |
| Second serial `--test` after that cleanup | **Stable** again |
| Another `--parallel` (all sconscripts) | **Spurious rebuild** returns (loop) |

So a single-sconscript parallel build is not enough to show the bug on this tip;
the multi-sconscript graph (four test scripts in the soak) is. That may mean more
concurrent scanner / `.sconsign` writers, a larger shared implicit-dep picture, or
both — still consistent with the working theory below, but it narrows the cheapest
repro: use ≥2 sconscripts, not only one heavy TU.

`--test` is not special: the decide phase rebuilds objects; tests then run. Serial
without `--test` after a dirtying parallel session shows the same decide behaviour.

### When the tree goes dirty (same soak)

After a clean serial baseline on the multi-sconscript tip:

| Probe | During that run | Next serial decide |
|-------|-----------------|--------------------|
| `--parallel=1` (affinity on, `num_jobs=1`) | Stable | Stable |
| `--parallel=2` | **Spurious compiles** | **Spurious compiles again** (heal pass) |
| Bare `--parallel` | Same loop | Same loop |
| `--parallel=2 --decider=MD5` | Still dirties | Still dirties |
| `--parallel=2 --implicit-cache` | **Stable** | **Stable** |
| Bare `--parallel --implicit-cache` (repeat) | **Stable** | **Stable** |
| Drop `--implicit-cache`, bare `--parallel` again | Loop returns immediately | — |

### Terse vs normal (2026-11-27 control — corrects earlier theory)

Earlier soaks all inherited **`terse_output = True`** from `~/.cuppaconfig`, so
they never separated Cuppa terse parallel chrome from bare SCons `-j`. On the
same multi-sconscript tip, after a clean serial heal:

| Flow | Result |
|------|--------|
| `--parallel=2 --normal-output` | **Stable** (0 compiles) |
| `--parallel=2 --terse-output` | **Spurious compiles** of the heavy TUs |
| Serial `--terse-output` after that | Same TUs compile again (heal) |
| After terse serial heal: `--parallel=2 --normal-output` | **Stable** |
| Then `--parallel=2 --terse-output` again | **Dirties again** |

So the loop is **`--terse-output` + `num_jobs ≥ 2`** on this tip, not
`num_jobs ≥ 2` alone. `--implicit-cache` still stops the loop *under terse*
(masks the decide/scan disagreement); `--normal-output` stops it without
ImplicitCache. That reopens Cuppa parallel progress / SPAWN / outstanding-timer
synchronisation as a prime suspect (recent terse `-j` work: heartbeat,
outstanding carousel, executor tally #404) — not ruled out as “SCons only”.

## Working theory (revised)

**Not** “Decider is broken on disk content.” Sampled sources/headers keep stable
mtimes/sizes. `MD5-timestamp` still decides from **stored** `.sconsign` build-info
vs current nodes. Something under **terse + `-j`** makes that comparison fail for
heavy TUs (false “changed” CSIGs and/or dep-set membership), in-session and on
the next decide.

**Explain caveats:** SCons `--debug=explain` runs *after* decide already chose to
rebuild. The familiar ``foo.cpp`` **is no longer a dependency** / **is a new
dependency** pair for the *same* path is a known explain/node-identity
confusion (VariantDir / stored vs live Node), not proof that the source was
removed from the graph. It should **not** by itself mean “rebuild.” The
accompanying thousands of headers **changed** is the more serious claim — and
with unchanged files on disk that points at bad/stale stored binfo or a
mismatched Node identity when looking up signatures, not at `MD5` of the bytes
on disk being wrong.

**Why ImplicitCache helped:** it avoids re-deriving / re-writing the huge
implicit set on every decide, so a fragile concurrent update under terse+`-j`
gets less chance to disagree. That is a **workaround**, not a root-cause fix.

**Resolved:** the terse up-to-date **lookahead** (`is_up_to_date()` on every
registered action before `Jobs.run`) was the Cuppa trigger under `-j`. See
Root cause and fix below.

### Related class: Boost `STATICLIBS` order (#267 / #269) — similar symptom, different bug

[#267](https://github.com/ja11sop/cuppa/issues/267) / [#269](https://github.com/ja11sop/cuppa/pull/269)
(and the determinism note in
[`archive/gitlab-package-lib-groups.md`](../archive/gitlab-package-lib-groups.md))
was another “files unchanged, SCons still rebuilds” loop. Root cause there was
**Cuppa-owned nondeterminism of an explicit dependency list**: remainder Boost
libs were appended by iterating a `set`, so `PYTHONHASHSEED` flipped
`STATICLIBS` / Program dependency order across processes. SCons treated that as
a changed build-info signature and **relinked every Program** (0 compiles). Fix:
stable master order in `boost_dependency_order()` + `Append` (not `AppendUnique`)
so repeats stay legal.

| | #267 Boost order | This parallel / multi-sconscript loop |
|--|------------------|--------------------------------------|
| Unchanged files on disk | Yes | Yes |
| What rebuilds | **Programs** (link only) | **`.o` files** (compile) |
| Explain shape | Link deps / action surface for archives + driver | Source “no longer” + “new” dependency; headers “changed” |
| Trigger | Cross-process order flip (`set` / hash seed) | **`--terse-output` + `num_jobs ≥ 2`** (+ large multi-sconscript graph) |
| Mitigated by | Deterministic `STATICLIBS` order (#269) | Skip terse `is_up_to_date` lookahead under `-j` |
| Layer | Cuppa Boost expand | Cuppa terse lookahead + parallel decide |

Same **symptom family**, not the same **error**. Keep #267 in mind for unordered
env lists; it does not explain these `.o` rebuilds.

## Non-goals (for now)

- Disabling `--parallel` or forcing `-j1` by default.
- Replacing SCons’ C scanner or decider without evidence (`--decider=MD5` did not help).
- Treating every incremental rebuild under `--develop` as this bug (real header edits
  still rebuild for good reasons).
- Blindly defaulting ImplicitCache without documenting include-graph staleness risk.

## Root cause and fix (2026-11-27)

`CUPPA_TERSE_BISECT` soak on the multi-sconscript tip:

| Disable | `--parallel=2 --terse-output` |
|---------|-------------------------------|
| (full terse) | Dirties |
| `hooks` / `outstanding` / `python_actions` / `flush` / `pending_dict` | Still dirties |
| `lookahead` | **Stable** |
| `print_cmd` / `stash` / `drop_at_take` | **Stable** (masks; not the preferred fix) |
| `drop_nodes_at_take` (keep argv, drop Node refs) | Still dirties |

So the failure mode is **`credit_terse_up_to_date_lookahead` → `Node.is_up_to_date()`
on the whole registered set before `Jobs.run`**, interacting with terse finish
formatting on worker threads under `-j` (large compile argv / transform field
path amplifies it). Holding Node refs across SPAWN alone is not sufficient;
dropping the stashed argv at finish also masks. Decider is not wrong on disk
bytes; explain removed+added remains node-identity noise.

**Fix:** `credit_terse_up_to_date_lookahead` returns immediately when
`GetOption('num_jobs') > 1`. Serial `-j1` keeps the lookahead so the first
`[progress]` percent still includes already-current work. `make_ready` credits
still cover up-to-date actions under `-j`. Tip soak: five× `--parallel=2` and
bare `--parallel` with terse — 0 spurious compiles.

`CUPPA_TERSE_BISECT` remains a soak-only switch (like `CUPPA_TERSE_TALLY_DUMP`).

## Direction

| Probe | State |
|-------|--------|
| Multi-sconscript / `-j` / terse vs normal | Done |
| Bisect terse subsystems | Done — **lookahead** |
| Skip lookahead under `num_jobs > 1` | **Done** — tip verified |
| Unit tests for skip / bisect helper | Done |
| Synthetic CI repro | Optional follow-up (fixed without it) |
| Default ImplicitCache on | Not needed for this bug |
| Upstream SCons | Not indicated |
