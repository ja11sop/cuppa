# Note: SCons `-j` can spuriously rebuild heavy C++ objects

- **Status:** documented opt-in workaround (SCons `--implicit-cache`); default-on still open
- **Related:** [`archive/parallel-job-count.md`](../archive/parallel-job-count.md); [#267](https://github.com/ja11sop/cuppa/issues/267) / [#269](https://github.com/ja11sop/cuppa/pull/269) Boost `STATICLIBS` order (related symptom, different root — see below); [`archive/gitlab-package-lib-groups.md`](../archive/gitlab-package-lib-groups.md) determinism note; ROADMAP `parallel-scons-large-graph`; Antora [`cli/building.adoc`](../../docs/modules/ROOT/pages/cli/building.adoc); SCons `--debug=explain`, `--implicit-cache`, `.sconsign.dblite`, default `MD5-timestamp` decider
- **Updated:** 2026-11-27
- **Impact:** `none` for docs / discoverability (SCons already owns `--implicit-cache`; Cuppa forwards it). Defaulting ImplicitCache on would be `patch` (or higher if it changes rebuild semantics broadly)

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
`--parallel=2` (or bare `--parallel`) spuriously rebuilds. So the trigger is
**multi-job SCons** (`num_jobs ≥ 2`), not Cuppa’s affinity mask by itself.

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

So the race is not only “next session disagrees”: under `-j≥2` the **same**
session already decides some heavy TUs are out of date. Serial then rewrites a
coherent `.sconsign` (one more rebuild), until the next multi-job run.

`--implicit-cache` reproducibly stopped the loop on this tip (including repeating
`--parallel` / serial while leaving the flag on). Removing the flag brings the
bug back. That is the leading Cuppa-side mitigation candidate.

**Caveat:** SCons ImplicitCache can miss newly added `#include` edges until
`--implicit-deps-changed` (or an equivalent cache bust). Any product default must
document that and/or pair with a safe invalidation story.

## Working theory

Under `-j`, SCons updates / compares a huge shared implicit-dependency picture and
`.sconsign` while several compile tasks run. Decide then disagrees with what was
stored (dep-set churn and “changed” CSIGs that do not match disk) and rebuilds the
heaviest scanners — **in that session and the next**. Serial (or `-j1`) writes a
coherent sconsign, which is why one single-job pass heals until the next multi-job
run.

Multi-sconscript sessions increase concurrent compile/scanner load and the size of
the shared dependency picture relative to a single-script `--scripts=` slice.
`--implicit-cache` avoids re-scanning / re-recording the full implicit set on every
decide, which would explain why it breaks the loop if the bug is scanner/sconsign
churn under concurrency (still consistent with upstream SCons, not Cuppa output).

Not a Cuppa terse / heartbeat issue. Cuppa’s `--parallel` only sets affinity +
`num_jobs` the same way operators already use `-j`.

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
| Trigger | Cross-process order flip (`set` / hash seed) | `num_jobs ≥ 2` + large multi-sconscript graph |
| Mitigated by | Deterministic `STATICLIBS` order (#269) | `--implicit-cache` on soak tip |
| Layer | Cuppa Boost expand | SCons implicit scan / `.sconsign` under `-j` |

So: same **symptom family** (sconsign/build-info disagrees while bytes on disk are
stable), not the same **error**. Parallel explain never cites a flipped link
action; it cites implicit-dep membership and false “changed” headers. A Boost-
style order bug would not explain `.o` rebuilds, and ImplicitCache stopping the
loop points at scanner/sconsign churn rather than an unstable `STATICLIBS`
construction. Still worth keeping #267 in mind when hunting any Cuppa path that
feeds sets into env lists without a fixed order — that class is real; this tip’s
evidence just does not match it.

## Non-goals (for now)

- Disabling `--parallel` or forcing `-j1` by default.
- Replacing SCons’ C scanner or decider without evidence (`--decider=MD5` did not help).
- Treating every incremental rebuild under `--develop` as this bug (real header edits
  still rebuild for good reasons).
- Blindly defaulting ImplicitCache without documenting include-graph staleness risk.

## Direction

The private soak tip is enough to ship Cuppa guidance. A shareable tree is **not**
a gate for docs — only for filing upstream against SCons (they need a runnable
case without our private tips). We can still **develop that case ourselves**: a
synthetic multi-sconscript + deep include graph that shows the spurious `-j`
rebuild loop (and that `--implicit-cache` stops it). Ideal shape:

1. **Cuppa integration fixture** (generated headers / several sconscripts) —
   CI-guarded repro without the private tip.
2. **Strip to pure SCons** (same layout, no Cuppa) when filing upstream — same
   evidence, SCons-maintainer-friendly.

| Probe | State |
|-------|--------|
| Multi-sconscript vs `--scripts=` control | Done (soak) |
| `--parallel=1` vs `≥2`; dirty during `-j` | Done (soak) |
| `--decider=MD5` | Done — no help |
| `--implicit-cache` | Done — **stops loop** on soak tip; caveat on new includes |
| Document opt-in (Antora + `--parallel` help) | **Done** this PR — SCons owns `--implicit-cache`; Cuppa forwards it (no duplicate Cuppa flag) |
| Synthetic multi-sconscript repro (Cuppa test) | Open — develop next; also feeds upstream |
| Default ImplicitCache on | Open — needs synthetic confidence + include-invalidation story |
| Upstream SCons | Open — after synthetic pure-SCons case exists |

**Operator workaround today (documented):** serial / `--parallel=1` heal pass; or
pass SCons `--implicit-cache` on the `cuppa` command line (and
`--implicit-deps-changed` after new `#include` edges).
