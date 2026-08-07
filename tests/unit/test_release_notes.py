#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

import pytest

from scripts.release_notes import notes_for


pytestmark = pytest.mark.unit


SAMPLE = """# Changelog

## [1.4.0] - 2026-08-07

### Added

- one feature (#1)

### Fixed

- one bug

## [1.3.2] - 2026-07-01

### Fixed

- older fix

[1.4.0]: https://github.com/ja11sop/cuppa/compare/v1.3.2...v1.4.0
[1.3.2]: https://github.com/ja11sop/cuppa/compare/v1.3.1...v1.3.2
"""


def test_notes_for_extracts_section_body():
    notes = notes_for( SAMPLE, '1.4.0' )
    assert '### Added' in notes
    assert 'one feature (#1)' in notes
    assert '### Fixed' in notes
    assert 'older fix' not in notes
    assert '[1.4.0]:' not in notes


def test_notes_for_missing_section():
    assert notes_for( SAMPLE, '9.9.9' ) is None
