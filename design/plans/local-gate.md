# Plan: Local gate orchestrator

- **Status:** proposal
- **Related:** [`AGENTS.md`](../../AGENTS.md) (Before pushing); [`docs/modules/ROOT/pages/contributing/overview.adoc`](../../docs/modules/ROOT/pages/contributing/overview.adoc); [`integration-parallel-local.md`](integration-parallel-local.md); [`tests/helpers/cuppa_runner.py`](../../tests/helpers/cuppa_runner.py)
- **Updated:** 2026-09-23
- **Impact:** `none` (contributor / agent tooling; no product CLI)

## Problem

The pre-push ritual in `AGENTS.md` is a multi-step checklist (`venv`, `flake8`,
`pylint -E`, `pytest -m unit`, `pytest -m integration`). Agents and humans
re-derive it every session and often:

1. Use a host `pytest` / broken user-site wrappers instead of `venv/bin/…`
2. Burn 7–10 minutes on integration only to discover a **subprocess** env break
   (soak: nested `python -m cuppa` → `ModuleNotFoundError: No module named 'six'`
   while in-process `import six` in the venv succeeds)
3. Misread “54 failed” as a product regression when the failure is preflight

Goal: one command that **fails fast on env**, then runs the same gate CI expects,
with clear exit meanings for agents.

## Settled shape (preferred)

```sh
# From repo root, after venv exists (create once per AGENTS.md):
python -m scripts.local_gate
# or explicitly:
venv/bin/python -m scripts.local_gate
```

| Mode | Behaviour |
|------|-----------|
| Default | Preflight → flake8 → pylint `-E` → `pytest -m unit` → `pytest -m integration` |
| `--unit` | Preflight → lint → unit only |
| `--integration` | Preflight (incl. C++ + subprocess smoke) → integration only |
| `--preflight-only` | Env checks only |
| `--skip-integration` | Alias of “lint + unit” when wall clock matters mid-iteration |

Implementation: `scripts/local_gate.py` (+ `__main__` via `python -m scripts.local_gate`).
Prefer discovering `venv/bin/python` next to the repo root and **re-exec** with that
interpreter if the current one is not the venv (refuse silent host-Python runs).

### Preflight checks (fail before the suite)

1. **Interpreter** — running under checkout `venv/` (or `VIRTUAL_ENV` pointing at it)
2. **Imports in-process** — `six`, `SCons`, `cuppa`, `pytest`, `flake8`, `pylint`
3. **Subprocess smoke** — write a tiny tmp `sconstruct` (`import cuppa`), run
   `sys.executable -m cuppa -D --offline --dump --toolchains=…` (or the helper’s
   default toolchain). Must exit 0 (or a known non-env StopError). This is the
   check that catches “venv import works, nested cuppa does not”
4. **C++** — when integration will run: same `require_cxx` / toolchain probe the
   integration helpers use
5. **Optional** — warn if `CUPPA_TEST_TOOLCHAIN` / `CUPPA_TEST_ARGS` look set for CI
   cells the operator did not intend

Print a short “preflight ok” line; on failure print **env broken** and exit **2**
(distinct from pytest failure **1**).

### Gate steps

Reuse existing tools; do not reimplement lint/pytest. Stream output. Stop on first
failing step (default); optional `--keep-going` later if useful.

Document in `AGENTS.md` and Contributing as the **preferred** local gate; keep the
expanded commands as the explainer underneath.

## Settled refusals

| Refuse | Why |
|--------|-----|
| Making `local_gate` a product `cuppa` CLI flag | Contributor tooling, not a project build option |
| Auto-`pip install`ing missing deps without asking | Surprising network / env mutation |
| Replacing CI | Local gate only; matrix stays authoritative |
| Bundling xdist into v1 | Parallel local is [`integration-parallel-local.md`](integration-parallel-local.md); optional later `--parallel` once that lands |
| Treating Q11 / product work as part of this PR | Orthogonal |

## Couples with

- **After:** [`integration-parallel-local.md`](integration-parallel-local.md) can add
  `local_gate --integration --parallel` once HOME isolation + xdist are trusted
- **Process:** append a bullet to [`agent-workflow-journey.md`](../process/agent-workflow-journey.md)
  when agents are told to prefer `scripts.local_gate` over hand-rolled checklists

## Acceptance

1. `python -m scripts.local_gate --preflight-only` fails clearly when not in venv or
   when subprocess smoke cannot `import six`
2. Default gate matches today’s AGENTS sequence on a healthy machine
3. `AGENTS.md` + Contributing point at the orchestrator; unit test that the module
   imports and preflight refuses a fake broken `PYTHONPATH` smoke if cheap
4. Design index + ROADMAP row (`local-gate`); `impact:none`

## Progress snapshot

| Item | State |
|------|-------|
| Problem / soak (subprocess `six`) | Captured |
| Settled shape / refusals | Settled (2026-09-23) |
| Implementation | Not started |
