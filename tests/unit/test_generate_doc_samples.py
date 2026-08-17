#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

"""Doc listing samples must come from the real formatters (no hand-indented trees)."""

import pytest

from scripts import generate_doc_samples as samples


pytestmark = pytest.mark.unit


def test_remove_gitlab_sample_nests_version_under_identity():
    path = samples.sample_remove_gitlab_dry_run()
    text = path.read_text( encoding='utf-8' )
    lines = text.splitlines()
    identity = next(
            line for line in lines
            if 'boost_package' in line and '-✔-' in line and 'related' not in line
    )
    version = next(
            line for line in lines
            if line.rstrip().endswith( '1.91' ) and '-✔-' in line
    )
    leaf = next( line for line in lines if 'would rm' in line and 'gcc153' in line )
    # Glyph column moves right with each nesting level.
    assert identity.index( '-✔-' ) < version.index( '-✔-' )
    assert version.index( '└──' ) < leaf.index( '└──' )


def test_list_downloads_sample_has_type_spacer_and_gitlab_first():
    path = samples.sample_list_downloads()
    text = path.read_text( encoding='utf-8' )
    gitlab_idx = text.index( 'gitlab packages' )
    source_idx = text.index( 'source archives' )
    assert gitlab_idx < source_idx
    assert '│   │' in text
    assert 'today' in text
    assert ' days ago' not in text


def test_list_dependencies_verbose_sample_has_location_and_download_mark():
    path = samples.sample_list_dependencies_verbose()
    text = path.read_text( encoding='utf-8' )
    assert 'LOCATION' in text
    assert '[D]' in text
    assert 'archive present under downloads' in text
    assert 'today' in text
    assert ' days ago' not in text


def test_list_develop_sample_has_status_table_and_judgement_tree():
    path = samples.sample_list_develop()
    text = path.read_text( encoding='utf-8' )
    assert text.startswith( 'Building on branch [feature_orders]' )
    assert 'STATUS  DEPENDENCY' in text
    assert '1 error' in text
    assert '~/coding/gizmo' in text
    assert '--update-develop would fast-forward' in text


def test_list_toolchains_sample_has_discovered_and_registered():
    path = samples.sample_list_toolchains()
    text = path.read_text( encoding='utf-8' )
    assert 'discovered' in text
    assert 'registered' in text
    assert '~/_cuppa/_download/toolchains/' in text
    assert 'Force-wipe removal of toolchains' in text


def test_list_toolchains_verbose_sample_has_dialects_and_invocations():
    path = samples.sample_list_toolchains_verbose()
    text = path.read_text( encoding='utf-8' )
    assert 'available dialects:' in text
    assert 'default invocations:' in text
    assert 'c++: "-Wall' in text
    assert 'registered' in text


def test_list_builds_sample_uses_relative_build_root():
    path = samples.sample_list_builds()
    text = path.read_text( encoding='utf-8' )
    assert 'BUILD FOLDER' in text
    assert '_build' in text
    assert '/tmp/' not in text
    assert 'selected (2 of 3 entries)' in text
    assert 'Append --remove-builds' in text


def test_remove_builds_dry_run_sample_announces_dry_run():
    path = samples.sample_remove_builds_dry_run()
    text = path.read_text( encoding='utf-8' )
    assert text.startswith( 'Would remove' )
    assert 'dry run (-n); nothing removed' in text
    assert 'REMOVED' in text


def test_remove_builds_error_sample_has_permission_judgement():
    path = samples.sample_remove_builds_error()
    text = path.read_text( encoding='utf-8' )
    assert 'Permission denied' in text
    assert '1 error' in text
    assert '✘✘✘' in text or '✗✗✗' in text


def test_remove_all_builds_dry_run_sample_targets_build_root():
    path = samples.sample_remove_all_builds_dry_run()
    text = path.read_text( encoding='utf-8' )
    assert 'Would remove build root _build' in text
    assert 'removed all 3 entries' in text


def test_json_list_samples_use_render_json_payload_shape():
    import json

    path = samples.sample_list_toolchains_json()
    text = path.read_text( encoding='utf-8' )
    assert '"sections":\n    [' in text
    payload = json.loads( text )
    assert payload['wipe_applies_to'] == 'registered'
    describe = payload['sections'][0]['families'][0]['versions'][0]['drivers'][0]['describe']
    assert describe['variants']['dbg']['c++'].startswith( '-Wall' )
    assert 'cov' not in describe['variants']

    deps = json.loads(
            samples.sample_list_dependencies_json().read_text(
                    encoding='utf-8'
            )
    )
    assert deps['scope'] == 'all'
    assert len( deps['entries'] ) == 2
    assert 'tree' in deps

    develop = json.loads(
            samples.sample_list_develop_json().read_text( encoding='utf-8' )
    )
    assert develop['would_update'] == [ 'flange' ]
    assert { entry['name'] for entry in develop['entries'] } == { 'flange', 'gizmo' }
    assert develop['entries'][0]['path'].startswith( '/home/user/' )

    builds = json.loads(
            samples.sample_list_builds_json().read_text(
                    encoding='utf-8'
            )
    )
    assert builds['build_root'] == '_build'
    assert builds['summary']['selected_entries'] == 1
    assert builds['summary']['entries'] == 2
