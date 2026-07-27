#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

import pytest

from cuppa.test_report.html_report import GenerateHtmlReportBuilder


pytestmark = pytest.mark.unit


def test_html_report_emitter_ignores_coverage_json():
    builder = GenerateHtmlReportBuilder(final_dir=None)
    sources = [
        "/build/final/all.report.json",
        "/build/final/coverage--all.json",
        "/build/final/coverage--all.log",
        "/build/final/message.report.json",
    ]
    targets, filtered = builder.emitter([], sources, env=None)
    assert [str(s) for s in filtered] == [
        "/build/final/all.report.json",
        "/build/final/message.report.json",
    ]
    assert "/build/final/all.report.html" in targets
    assert "/build/final/message.report.html" in targets
    assert not any("coverage--" in str(t) for t in targets)
