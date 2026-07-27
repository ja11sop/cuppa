# test_test_reports

Canonical documentation for this integration test is on the Cuppa docs site:

**[test_test_reports](https://ja11sop.github.io/cuppa/cuppa/integration/test-test-reports.html)**

Source: [`docs/modules/ROOT/pages/integration/test-test-reports.adoc`](../../../../docs/modules/ROOT/pages/integration/test-test-reports.adoc)

Related test module: `test_test_reports.py`

Covers:

- `GenerateHtmlTestReport` (including with `--cov`; asserts report HTML + coverage JSON both exist)
- `CollateTestReportIndex` (single and shared-destination sibling sconscripts; master `test-report-index.html` / `.json`)
- `GenerateBittenReport`
