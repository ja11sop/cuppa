# Plan: Tip consume forest stages without nesting

- **Status:** in progress
- **Related:** [`cascade-build-deps-tip-consume.md`](cascade-build-deps-tip-consume.md) (tip bind under `--build-cascade-dependencies`; deferred “second consume flag”); [`../archive/package-build-publish-deps.md`](../archive/package-build-publish-deps.md); [`../archive/stage-develop-locations.md`](../archive/stage-develop-locations.md); [`cascade-amend-package-manifest.md`](cascade-amend-package-manifest.md); ROADMAP **1.13.0** related
- **Updated:** 2026-10-27
- **Impact:** minor — new cascade companion; tip bind reuses build-deps tip-consume helpers

## Problem

After a successful `--cascade --build-cascade-dependencies` (and/or
`--amend-cascade-manifests`) soak, forest stages already exist under the
publisher trees. The operator often wants to **rebuild / retest only the tip**
while still linking those forest stages — downloads-root extracts may be stale
or intentionally not the soak medium.

Today the only way to tip-bind forest stages is to pass
`--build-cascade-dependencies`, which **always nests**. Dropping amend does
not mean “reuse stages”: without amend, build-deps nests are full publisher
**project** builds (cmake/ninja), not stage+amend.

Soak (**project F**, 2026-10-19): tip-only retest still required nine nested
amends (or a nest rebuild) to keep forest bind — wasteful when stages are
already current.

## Intent

1. Tip binds publisher-root `final/<package>/<version>/` stages the same way
   build-deps tip consume does (toolchain-strict; prefer nest-default `rel`;
   `--develop` still wins).
2. **No nest sessions** — zero nested `python -m cuppa`.
3. Missing / wrong-toolchain stage → **`StopError`** with a short hint to run
   `--build-cascade-dependencies` (or amend) first — **no** extract fall-back.
4. Compose with tip `--test` / `--force-test` / tip-local helpers without
   forcing nest rebuilds.

## Non-goals

- Silent “skip nest if stage fresh” inside `--build-cascade-dependencies`
  (useful later; different product — hides rebuilds).
- Tip extract overlay / mutating downloads-root.
- Combining with `--amend-cascade-manifests` (amend needs nests).
- Replacing `--cascade-plan` (review-only; still no bind).

## Naming steer

Existing cascade / companion vocabulary:

| Flag | Role |
|------|------|
| `--cascade` | Enable cascade orchestration |
| `--publish-cascade-dependencies` | Nest **publish** DAG; tip build |
| `--build-cascade-dependencies` | Nest **build**/stage DAG; tip forest bind |
| `--amend-cascade-manifests` | Tip signal → nest **amend** |
| `--collect-cascade` | Clone/collect publishers (no tip bind) |
| `--clone-publishers` | Fetch publisher trees |
| `--stage-develop` | Nest-stage location develop trees; tip consume develop stages |
| `--stage-package` / `--publish-package` | Tip packaging companions |

Pattern for DAG companions that act on package dependencies:
**`--<verb>-cascade-dependencies`**.

| Candidate | Verdict |
|-----------|---------|
| **`--consume-cascade-dependencies`** | **Lean** — matches tip-consume language; parallel to build/publish verbs; “consume” already means tip bind from a stage |
| `--use-cascade-dependencies` | Weaker — “use” is vague next to build/publish/consume; easy to confuse with “turn cascade on” |
| `--use-cascade` | Refuse — overlaps `--cascade`; too short |
| `--link-cascade-dependencies` | Accurate but novel verb vs Cuppa docs (“consume” / “bind”) |

**Settled lean:** `--consume-cascade-dependencies` (keep `--use-cascade-dependencies`
as a rejected alias in this plan so bikeshed does not reopen).

## Direction

| Piece | Lean |
|-------|------|
| Enable | `--cascade --consume-cascade-dependencies` |
| Mutex | Same family as build/publish cascade companions and tip `--publish-package` |
| Tip bind | Reuse `consume_build_cascade_package_stage` / resolve helpers from build-deps tip consume — factor a shared “forest tip consume” entry that does **not** call `run_build_cascade_stages` |
| Plan banner | e.g. “dependencies consume (no nest); tip build only” |
| `--cascade-plan` | Show the DAG and “would bind forest stages; no nests” |
| Amend | Refuse combine with `--amend-cascade-manifests` (or StopError) |

### Operator model (four postures)

| Intent | Flags |
|--------|-------|
| Review DAG | `--cascade --cascade-plan` |
| Nest build + tip forest bind | `--cascade --build-cascade-dependencies` |
| Nest publish + tip build | `--cascade --publish-cascade-dependencies` |
| Tip forest bind, **no nests** | `--cascade --consume-cascade-dependencies` |

## Progress

| Item | Status |
|------|--------|
| Soak gap captured | Done — this proposal (**project F**) |
| Naming | Lean `--consume-cascade-dependencies` |
| Implementation | Done — flag, mutex (including amend), tip bind via `consume_build_cascade_package_stage` with no nest-on-miss, `run_build_cascade_stages` stays build-deps only. Consume-only skips the graph. Under `--terse-output`: `<publishers>` root, `staged_package` / `develop_package` location kinds (label at bind; Boost `__call__` registers too), durable `[cascade] tip · mode · dependencies consume (no nest) · N staged packages` (not begin/end; no OFFLINE-style mode banner). Matching `cuppa: ... [info]` lines stay for non-terse only. `--cascade-plan` still reviews the DAG and does not nest. Blocked-plan closings name consume as a way to execute; the short “pass one of …” run phrase stays the nest companions so the clone-on-the-way line does not wrap |
| Antora cascade table + examples | Done — `dependencies/publishing/cascade.adoc`, `cli/dependencies-and-develop.adoc`, `cli/output-and-environment.adoc` |
| Unit tests (mutex, tip bind without nest, terse mode/kinds) | Done — `tests/unit/test_package_cascade.py`, `tests/unit/test_terse_transcript.py` |
