"""Keep `cuppa/VERSION` and `CHANGELOG.md` telling the same story."""

import pytest
from packaging.version import Version

from scripts import changelog
from scripts import check_version_bump
from scripts import github_api
from scripts.check_release import check as check_release
from scripts.check_version_bump import check as check_bump
from scripts.check_version_bump import impact_from_labels, labels_from_api


pytestmark = pytest.mark.unit


RELEASED = """# Changelog

## [1.4.0] - 2026-08-14

### Added

- Something worth mentioning.

## [1.3.2] - 2026-07-31

### Fixed

- Something else.

[1.4.0]: https://github.com/ja11sop/cuppa/compare/v1.3.2...v1.4.0
"""

IN_PROGRESS = """# Changelog

## [1.4.0] - unreleased

### Added

- Something worth mentioning.

## [1.3.2] - 2026-07-31

### Fixed

- Something else.

[1.4.0]: https://github.com/ja11sop/cuppa/compare/v1.3.2...HEAD
"""


def test_the_repository_is_consistent():
    found = changelog.problems()
    assert not found, "\n".join( found )


def test_a_released_changelog_matches_its_release_version():
    assert changelog.problems( '1.4.0', RELEASED ) == []


def test_an_in_progress_changelog_matches_its_development_version():
    assert changelog.problems( '1.4.0.dev', IN_PROGRESS ) == []


def test_a_development_version_needs_an_undated_section():
    found = changelog.problems( '1.4.0.dev', RELEASED )
    assert any( 'already dated' in problem for problem in found )


def test_a_release_version_needs_a_dated_section():
    found = changelog.problems( '1.4.0', IN_PROGRESS )
    assert any( 'still marked' in problem for problem in found )


def test_the_version_must_match_the_top_section():
    found = changelog.problems( '1.5.0.dev', IN_PROGRESS )
    assert any( 'top CHANGELOG.md section' in problem for problem in found )


def test_sections_must_descend():
    out_of_order = IN_PROGRESS.replace( '## [1.3.2] - 2026-07-31', '## [1.5.0] - 2026-07-31' )
    found = changelog.problems( '1.4.0.dev', out_of_order )
    assert any( 'out of order' in problem for problem in found )


def test_only_the_top_section_may_be_unreleased():
    two_unreleased = IN_PROGRESS.replace( '## [1.3.2] - 2026-07-31',
                                          '## [1.3.2] - unreleased' )
    found = changelog.problems( '1.4.0.dev', two_unreleased )
    assert any( 'unreleased sections' in problem for problem in found )


def test_recent_versions_need_a_compare_link():
    without_link = IN_PROGRESS.replace(
        '[1.4.0]: https://github.com/ja11sop/cuppa/compare/v1.3.2...HEAD\n', ''
    )
    found = changelog.problems( '1.4.0.dev', without_link )
    assert any( 'no compare link' in problem for problem in found )


@pytest.mark.parametrize( "impact,expected", [
    ( 'patch', '1.3.3' ),
    ( 'minor', '1.4.0' ),
    ( 'major', '2.0.0' ),
    ( 'none', '1.3.2' ),
] )
def test_expected_version_for_each_impact( impact, expected ):
    assert changelog.expected_version( Version( '1.3.2' ), impact ) == Version( expected )


def test_impact_comes_from_exactly_one_label():
    assert impact_from_labels( [ 'docs', 'impact:minor' ] ) == 'minor'

    with pytest.raises( ValueError, match='no impact:' ):
        impact_from_labels( [ 'docs' ] )
    with pytest.raises( ValueError, match='several impact labels' ):
        impact_from_labels( [ 'impact:minor', 'impact:patch' ] )
    with pytest.raises( ValueError, match='unknown impact' ):
        impact_from_labels( [ 'impact:huge' ] )


def _stub_github( response ):
    """Stand in for ``GitHub``, whether the caller authenticates or reads anonymously."""
    class _Client:
        seen = []

        def __init__( self, credential=None, anonymous=False ):
            self.credential = credential

        @classmethod
        def public( cls ):
            return cls( anonymous=True )

        def request( self, method, path, payload=None ):
            _Client.seen.append( ( method, path ) )
            return response

    return _Client


def test_labels_are_read_live_so_a_frozen_payload_cannot_decide( monkeypatch ):
    """The opened event is sealed before create-pr labels the pull request."""
    client = _stub_github(
        ( 200, { 'labels': [ { 'name': 'impact:minor' }, { 'name': 'docs' } ] } )
    )
    monkeypatch.setattr( github_api, 'GitHub', client )
    monkeypatch.setenv( 'GITHUB_REPOSITORY', 'ja11sop/cuppa' )
    monkeypatch.setenv( 'GITHUB_TOKEN', 'job-token' )

    assert labels_from_api( 303 ) == [ 'impact:minor', 'docs' ]
    assert client.seen == [ ( 'GET', '/repos/ja11sop/cuppa/pulls/303' ) ]


def test_a_failed_label_read_is_reported_rather_than_guessed( monkeypatch ):
    monkeypatch.setattr(
        github_api, 'GitHub', _stub_github( ( 404, { 'message': 'Not Found' } ) )
    )
    monkeypatch.setenv( 'GITHUB_REPOSITORY', 'ja11sop/cuppa' )

    with pytest.raises( ValueError, match='HTTP 404' ):
        labels_from_api( 303 )

    monkeypatch.delenv( 'GITHUB_REPOSITORY' )
    with pytest.raises( ValueError, match='which repository' ):
        labels_from_api( 303 )


def test_the_gate_falls_back_to_payload_labels_when_the_api_is_unreachable( monkeypatch, capsys ):
    """A flaky API must not turn the gate into a coin toss."""
    def _unreachable( number, repository=None ):
        raise OSError( 'connection refused' )

    monkeypatch.setattr( check_version_bump, 'labels_from_api', _unreachable )
    monkeypatch.setattr( check_version_bump, 'version_at', lambda ref: '1.11.0.dev' )

    exit_status = check_version_bump.main( [
        '--base-ref', 'origin/master',
        '--pull-request', '303',
        '--labels', 'impact:minor',
    ] )
    output = capsys.readouterr().out
    assert 'using the event payload' in output
    assert exit_status == 0


def test_a_minor_change_is_accepted_at_the_next_minor():
    assert check_bump( '1.4.0.dev', IN_PROGRESS, '1.3.2', 'minor' ) == []


def test_a_major_change_is_rejected_at_a_minor_bump():
    found = check_bump( '1.4.0.dev', IN_PROGRESS, '1.3.2', 'major' )
    assert any( 'needs at least [2.0.0]' in problem for problem in found )


def test_a_patch_change_is_accepted_inside_an_open_minor_cycle():
    assert check_bump( '1.4.0.dev', IN_PROGRESS, '1.4.0.dev', 'patch' ) == []


def test_a_feature_without_a_bump_is_rejected():
    unchanged = RELEASED.replace( '## [1.4.0] - 2026-08-14', '## [1.3.2] - 2026-07-31', 1 )
    unchanged = unchanged.replace( '## [1.3.2] - 2026-07-31\n\n### Fixed\n\n- Something else.\n\n',
                                   '', 1 )
    found = check_bump( '1.3.2', unchanged, '1.3.2', 'minor' )
    assert found


def test_a_release_version_on_a_branch_is_rejected():
    released_top = IN_PROGRESS.replace( '## [1.4.0] - unreleased', '## [1.4.0] - 2026-08-14' )
    found = check_bump( '1.4.0', released_top, '1.3.2', 'minor' )
    assert any( 'not a development version' in problem for problem in found )


def test_an_entry_free_section_is_rejected():
    empty = IN_PROGRESS.replace( '- Something worth mentioning.\n', '' )
    found = check_bump( '1.4.0.dev', empty, '1.3.2', 'minor' )
    assert any( 'no entries' in problem for problem in found )


def test_a_release_needs_a_dated_section_and_a_matching_tag():
    assert check_release( 'v1.4.0', '1.4.0', RELEASED ) == []

    found = check_release( 'v1.4.0', '1.4.0.dev', IN_PROGRESS )
    assert any( 'development version' in problem for problem in found )

    found = check_release( 'v1.5.0', '1.4.0', RELEASED )
    assert any( 'does not match' in problem for problem in found )
