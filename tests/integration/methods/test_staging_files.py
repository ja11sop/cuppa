"""Staging files: CopyFiles / CopyFilesAs / Install / InstallAs parity across variants."""

import os
from pathlib import Path

import pytest

from tests.helpers.cuppa_runner import assert_success, find_under_build, run_cuppa
from tests.helpers.project import copy_dummy_project, write_sconstruct, write_sconscript


pytestmark = pytest.mark.integration


def _final_copies( project, name ):
    """Return staged files named ``name`` under each variant ``final/`` tree."""
    hits = []
    for path in find_under_build( project, name ):
        parts = path.parts
        if "final" in parts:
            hits.append( path )
    return sorted( hits )


def _variant_labels( paths ):
    """Extract dbg/rel (or similar) variant directory names from final/ paths."""
    labels = set()
    for path in paths:
        parts = list( path.parts )
        try:
            final_idx = parts.index( "final" )
        except ValueError:
            continue
        # .../<toolchain>/<variant>/.../final/...
        for part in parts[:final_idx]:
            if part in ( "dbg", "rel", "cov" ):
                labels.add( part )
    return labels


def test_copy_files_stages_under_final_for_dbg_and_rel( tmp_path ):
    project = copy_dummy_project( tmp_path )
    write_sconstruct( project, default_variants=["dbg"] )
    write_sconscript(
        project,
        "Import('env')\n"
        "env.CopyFiles('staged', 'data/copy_me.txt')\n",
    )
    result = run_cuppa( project, "--dbg", "--rel" )
    assert_success( result )
    copies = _final_copies( project, "copy_me.txt" )
    assert len( copies ) == 2, copies
    assert _variant_labels( copies ) == { "dbg", "rel" }
    for path in copies:
        assert path.parent.name == "staged" or "staged" in path.parts


def test_install_with_abs_final_dir_matches_copy_files_layout( tmp_path ):
    """Parity: Install(abs_final_dir/…) and CopyFiles(relative) land the same."""
    project = copy_dummy_project( tmp_path )
    write_sconstruct( project )
    write_sconscript(
        project,
        "Import('env')\n"
        "import os\n"
        "env.CopyFiles('via_copy', 'data/copy_me.txt')\n"
        "env.Install(os.path.join(env['abs_final_dir'], 'via_install'), 'data/copy_me.txt')\n",
    )
    result = run_cuppa( project, "--dbg", "--rel" )
    assert_success( result )

    for variant in ( "dbg", "rel" ):
        copy_hits = [
            p for p in _final_copies( project, "copy_me.txt" )
            if variant in p.parts and "via_copy" in p.parts
        ]
        install_hits = [
            p for p in _final_copies( project, "copy_me.txt" )
            if variant in p.parts and "via_install" in p.parts
        ]
        assert len( copy_hits ) == 1, copy_hits
        assert len( install_hits ) == 1, install_hits
        assert copy_hits[0].read_text() == install_hits[0].read_text()


def test_copy_files_as_and_install_as_rename_parity_dbg_rel( tmp_path ):
    project = copy_dummy_project( tmp_path )
    write_sconstruct( project )
    write_sconscript(
        project,
        "Import('env')\n"
        "import os\n"
        "env.CopyFilesAs('renamed_copy.txt', 'data/copy_me.txt')\n"
        "env.InstallAs(\n"
        "    os.path.join(env['abs_final_dir'], 'renamed_install.txt'),\n"
        "    'data/copy_me.txt',\n"
        ")\n",
    )
    result = run_cuppa( project, "--dbg", "--rel" )
    assert_success( result )

    copy_hits = _final_copies( project, "renamed_copy.txt" )
    install_hits = _final_copies( project, "renamed_install.txt" )
    assert len( copy_hits ) == 2, copy_hits
    assert len( install_hits ) == 2, install_hits
    assert _variant_labels( copy_hits ) == { "dbg", "rel" }
    assert _variant_labels( install_hits ) == { "dbg", "rel" }


def test_staging_progress_chain_covers_dbg_and_rel( tmp_path ):
    """NotifyProgress started/finished fire once per variant for Install and CopyFiles."""
    project = copy_dummy_project( tmp_path )
    write_sconstruct( project )
    events_path = project / "progress_events.txt"
    write_sconscript(
        project,
        "Import('env')\n"
        "from cuppa.progress import NotifyProgress\n"
        "\n"
        "events_file = r'{events}'\n"
        "\n"
        "def _on_progress(event, sconscript, variant, callback_env, target, source):\n"
        "    if event in ('started', 'finished'):\n"
        "        with open(events_file, 'a') as handle:\n"
        "            handle.write(event + '|' + str(variant) + '\\n')\n"
        "\n"
        "NotifyProgress.register_callback(None, _on_progress)\n"
        "env.CopyFiles('prog_copy', 'data/copy_me.txt')\n"
        "import os\n"
        "env.Install(os.path.join(env['abs_final_dir'], 'prog_install'), 'data/copy_me.txt')\n"
        .format( events=str( events_path ) ),
    )
    if events_path.exists():
        events_path.unlink()
    result = run_cuppa( project, "--dbg", "--rel" )
    assert_success( result )
    assert events_path.exists(), result.stdout
    lines = [ line.strip() for line in events_path.read_text().splitlines() if line.strip() ]
    started = [ line for line in lines if line.startswith( "started|" ) ]
    finished = [ line for line in lines if line.startswith( "finished|" ) ]
    assert len( started ) >= 2, lines
    assert len( finished ) >= 2, lines
    started_variants = { line.split( "|", 1 )[1] for line in started }
    finished_variants = { line.split( "|", 1 )[1] for line in finished }
    assert any( "dbg" in v for v in started_variants ), started_variants
    assert any( "rel" in v for v in started_variants ), started_variants
    assert started_variants == finished_variants
