# Note: SCons `-j` can spuriously rebuild heavy C++ objects

- **Status:** proposal
- **Related:** [`archive/parallel-job-count.md`](../archive/parallel-job-count.md); ROADMAP `parallel-scons-large-graph`; Antora [`cli/building.adoc`](../../docs/modules/ROOT/pages/cli/building.adoc); SCons `--debug=explain`, `.sconsign.dblite`, default `MD5-timestamp` decider
- **Updated:** 2026-11-13
- **Impact:** `none` while documenting; any Cuppa mitigation later is likely `patch` (or upstream SCons)

## Observed

On a large tip with deep Boost / Asio / package / develop include graphs, back-to-back
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
**multi-job SCons**, not Cuppa’s affinity mask by itself.

## Working theory

Under `-j`, SCons updates / compares a huge shared implicit-dependency picture and
`.sconsign` while several compile tasks run. The next decide phase then disagrees
with what was stored (dep-set churn and “changed” CSIGs that do not match disk) and
rebuilds the heaviest scanners first. Serial (or `-j1`) writes a coherent sconsign,
which is why one single-job pass heals until the next multi-job run.

Not a Cuppa terse / heartbeat issue. Cuppa’s `--parallel` only sets affinity +
`num_jobs` the same way operators already use `-j`.

## Non-goals (for now)

- Disabling `--parallel` or forcing `-j1` by default.
- Replacing SCons’ C scanner or decider without evidence.
- Treating every incremental rebuild under `--develop` as this bug (real header edits
  still rebuild for good reasons).

## Direction (when we have time)

| Probe | Why |
|-------|-----|
| `ImplicitCache` / decider experiments | See whether Cuppa can narrow the race without papering over real deps |
| Minimal public repro | Isolate Boost.Test + Asio-sized graphs under stock SCons `-j` |
| Upstream SCons | File or track if this is a known `.sconsign` / scanner concurrency issue |
| Docs | Operators already warned via Antora NOTE on `cli/building.adoc` |

Until then: document the quirk; if a tree keeps recompiling the same units under
`--parallel`, a serial pass (or `--parallel=1`) restores a clean up-to-date state.
