# test_available_reports

Canonical documentation for this integration test is on the Cuppa docs site:

**[test_available_reports](https://ja11sop.github.io/cuppa/cuppa/integration/test-available-reports.html)**

Source: [`docs/modules/ROOT/pages/integration/test-available-reports.adoc`](../../../../docs/modules/ROOT/pages/integration/test-available-reports.adoc)

Related test module: `test_available_reports.py`

Covers:

- `--list-available-reports` judgement tree and JSON on a real `sconstruct` (no build)
- Canonical `_artefacts/` wiring via **two** cuppa invocations: `--cov --test` for three-test collation, then `--cxx-profiles` with `env.CollateCxxProfilesIndex()` in the sconscript (Alliance archive when needed; no `--cxx-profiles-report`; keep-going implied by inventory mode)
