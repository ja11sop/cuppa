# Plan: Parallel local integration tests

- **Status:** proposal
- **Related:** [`ROADMAP.md`](../../ROADMAP.md) — `integration-parallel-local`; [`AGENTS.md`](../../AGENTS.md) local gate; [`tests/helpers/cuppa_runner.py`](../../tests/helpers/cuppa_runner.py); [`parallel-job-count.md`](parallel-job-count.md) (Cuppa build `--parallel=N` — different concern)
- **Updated:** 2026-09-14
- **Impact:** `none` (contributor / local gate tooling; no product CLI)

## Problem

The local pre-push gate runs `pytest -m integration` **serially**. On a typical
developer machine that is about **7–10 minutes** (recent sample: ~6m44s for
186 passed / 13 skipped). Waiting on that before every push burns wall clock
even though most cases are independent: each drives Cuppa in a **subprocess**
with its own `tmp_path` project tree.

Goal is **not** maximum throughput. Target: turn an **8–10 minute** serial run
into roughly **2–3 minutes** by running a **small number** of integration tests
at once (order of **3–4 workers**), without thrashing the machine or flaking.

## Why this is feasible

| Property | Implication |
|----------|-------------|
| `run_cuppa` uses `subprocess` | Pytest workers do not share an in-process SCons graph |
| Cases use `tmp_path` project copies | Per-test build trees already isolate `_build/` |
| Inventory / storage / Conan often set `HOME` / `--storage-root` / `CONAN_HOME` | Pattern for isolation already exists |
| CI already parallelises **across** matrix jobs | This plan is **within** one local (or optional CI) pytest process |

## Settled shape (preferred)

1. **Isolation first** — default every `run_cuppa` (or an autouse fixture) to a
   per-test `HOME` / `USERPROFILE` under `tmp_path` (and keep Conan’s existing
   `CONAN_HOME` pattern). Tests that need a planted storage tree keep passing
   `--storage-root=` as today. Motivation: many compile smokes still inherit the
   real home and share `~/.cuppa`; concurrent writers are the main flake risk
   (`test_storage_roots` already documents why a shared home is unsafe).

2. **Modest pytest-xdist** — optional local invocation, e.g.
   ```sh
   pytest -m integration -n 4 --dist=loadfile
   ```
   Prefer **`--dist=loadfile`** so a heavy file (modules, Conan, coverage) stays
   on one worker. Cap workers around **4** (or `min(4, cpu_count//2)`), not
   `-n auto` on a 16-core box.

3. **Do not nest Cuppa `--parallel` at full width** — while xdist workers are
   active, keep each `run_cuppa` compile **serial** (or a tiny job count) unless
   a case explicitly needs Cuppa parallel. Worker parallelism × Cuppa parallel
   oversubscribes CPU and hurts wall time.

4. **Serial escape hatch** — mark rare outliers `@pytest.mark.serial` (or
   equivalent xdist pattern) if anything still races after HOME isolation.

5. **Docs / AGENTS** — document the parallel spelling as the **preferred local
   gate** once green; keep plain `pytest -m integration` valid. CI matrix can
   stay serial per job at first (jobs already fan out by toolchain).

## Settled refusals

| Refuse | Why |
|--------|-----|
| Flipping `-n auto` on today’s suite without HOME isolation | Shared `~/.cuppa` races |
| Treating this as a substitute for Cuppa `--parallel=N` | Different layer; see [`parallel-job-count.md`](parallel-job-count.md) |
| Requiring xdist in CI before local proof | Optional dependency; measure flake rate first |
| Maximising worker count for “raw speed” | Goal is ~2–3 minutes, not saturating the box |

## Couples with / not

- **Not** [`coverage-parallel.md`](coverage-parallel.md) / `GCOV_PREFIX` — that is
  parallel **collection inside one Cuppa cov run**, not pytest workers.
- **Not** [`parallel-job-count.md`](parallel-job-count.md) — product CLI for
  one build’s job count.
- **Related process:** [`AGENTS.md`](../../AGENTS.md) “Before pushing” gate once
  the parallel spelling is trusted.

## Acceptance

1. With HOME isolation + `-n 4 --dist=loadfile`, a full local integration run
   finishes in about **2–3 minutes** on a mid-range laptop (document the
   measured before/after once).
2. No new flakes attributed to shared storage/home under that spelling (or
   outliers marked serial with a one-line reason).
3. `pytest -m integration` without xdist still passes.
4. AGENTS / Contributing mention the parallel local gate; `pytest-xdist` is an
   optional test extra (not a runtime dependency of Cuppa).

## Progress snapshot

| Item | State |
|------|-------|
| Problem / target wall time | Captured |
| Settled shape (isolation → modest xdist → no nested parallel) | Captured |
| Implementation | Not started |
| Issue filed | Not yet |
