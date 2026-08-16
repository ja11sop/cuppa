#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   Built-in HTML report kinds and toolchain availability for --list-available-reports
#-------------------------------------------------------------------------------

import os
from collections import namedtuple

from cuppa.reports.manifest import MANIFEST_BASENAME

ReportKind = namedtuple(
    'ReportKind',
    [
        'kind',
        'label',
        'default_subdir',
        'under_artefacts_root',
        'cli_flags',
        'env_method',
        'manifest_kind',
        'clean_via',
        'notes',
    ],
)

REPORT_KINDS = (
    ReportKind(
        kind='cxx-profiles',
        label='C++ Profiles violation report',
        default_subdir='cxx-profiles',
        under_artefacts_root=True,
        cli_flags=( '--cxx-profiles-report', ),
        env_method='CxxProfilesReport',
        manifest_kind='cxx-profiles',
        clean_via='{} manifest (matched on --clean / --remove-builds)'.format(
            MANIFEST_BASENAME,
        ),
        notes='Also requires --cxx-profiles or --cxx-profiles-enforce= with a Profiles-capable Clang',
    ),
    ReportKind(
        kind='coverage',
        label='Coverage HTML',
        default_subdir='coverage',
        under_artefacts_root=True,
        cli_flags=( '--cov', '--test' ),
        env_method='CollateCoverageIndex',
        manifest_kind=None,
        clean_via='not removed by --remove-builds alone',
        notes='Destination is usually set in the sconscript; conventional tree is '
              '<artefacts-root>/coverage/',
    ),
    ReportKind(
        kind='test',
        label='Test HTML report',
        default_subdir=None,
        under_artefacts_root=False,
        cli_flags=( '--test', ),
        env_method='GenerateHtmlTestReport',
        manifest_kind=None,
        clean_via='SCons Clean() where the sconscript declares it',
        notes='Per-program *.report.html paths under _build/ (not on artefacts_root by default)',
    ),
)


def abs_artefacts_root_from_env( env ):
    """Return the absolute artefacts root, preferring British env keys."""
    abs_root = env.get( 'abs_artefacts_root' ) or env.get( 'abs_artifacts_root' )
    if abs_root:
        return os.path.abspath( abs_root )
    rel_root = env.get( 'artefacts_root' ) or env.get( 'artifacts_root' ) or '_artefacts'
    sconstruct_dir = env.get( 'sconstruct_dir' ) or os.getcwd()
    if os.path.isabs( rel_root ):
        return os.path.abspath( rel_root )
    return os.path.abspath( os.path.join( sconstruct_dir, rel_root ) )


def rel_artefacts_root_from_env( env ):
    """Return the project-relative artefacts root path."""
    return env.get( 'artefacts_root' ) or env.get( 'artifacts_root' ) or '_artefacts'


def default_report_dir_for_kind( env, kind ):
    """Return the default output directory for a registered report kind, if any."""
    if not kind.under_artefacts_root or not kind.default_subdir:
        return None
    return os.path.join( abs_artefacts_root_from_env( env ), kind.default_subdir )


def report_kind_by_id( kind_id ):
    for kind in REPORT_KINDS:
        if kind.kind == kind_id:
            return kind
    return None


def toolchain_supports_report_kind( toolchain, kind_id, env=None ):
    """Return whether ``toolchain`` can produce HTML for the given report kind."""
    if kind_id == 'test':
        runners = getattr( toolchain, 'test_runners', None )
        if callable( runners ):
            try:
                return bool( runners() )
            except Exception:
                return False
        return callable( getattr( toolchain, 'test_runner', None ) )
    if kind_id == 'coverage':
        supports = getattr( toolchain, 'supports_coverage', None )
        if callable( supports ):
            try:
                return bool( supports() )
            except Exception:
                return False
        return False
    if kind_id == 'cxx-profiles':
        profiles = getattr( toolchain, 'profiles_supported', None )
        if callable( profiles ):
            try:
                return bool( profiles( env ) )
            except Exception:
                return False
        return False
    return False


def supporting_toolchain_rows_for_kind( cuppa_env, kind_id ):
    """Return sorted toolchain rows that support ``kind_id`` on this system."""
    from cuppa.core.toolchain_actions import row_from_toolchain

    toolchains = cuppa_env.get( 'toolchains' ) or {}
    rows = []
    for name in sorted( toolchains.keys() ):
        toolchain = toolchains[ name ]
        if not toolchain_supports_report_kind( toolchain, kind_id, cuppa_env ):
            continue
        row = row_from_toolchain( name, toolchain )
        rows.append(
            {
                'name': row[ 'name' ],
                'family': row[ 'family' ],
                'version': row[ 'version' ],
                'section': row[ 'section' ],
                'driver_path': row[ 'driver_path' ],
            },
        )
    return rows


def serialise_report_kinds( env, include_toolchains=True ):
    """Build JSON-serialisable rows for ``--list-available-reports --list-format=json``."""
    abs_root = abs_artefacts_root_from_env( env )
    rel_root = rel_artefacts_root_from_env( env )
    rows = []
    for kind in REPORT_KINDS:
        default_dir = default_report_dir_for_kind( env, kind )
        row = {
            'kind': kind.kind,
            'label': kind.label,
            'default_subdir': kind.default_subdir,
            'under_artefacts_root': kind.under_artefacts_root,
            'default_directory': default_dir,
            'default_directory_relative': (
                '{}/{}'.format( rel_root, kind.default_subdir )
                if kind.default_subdir and kind.under_artefacts_root
                else None
            ),
            'cli_flags': list( kind.cli_flags ),
            'env_method': kind.env_method,
            'manifest_kind': kind.manifest_kind,
            'clean_via': kind.clean_via,
            'notes': kind.notes or None,
        }
        if include_toolchains:
            row[ 'supporting_toolchains' ] = supporting_toolchain_rows_for_kind( env, kind.kind )
        rows.append( row )
    return {
        'artefacts_root': rel_root,
        'abs_artefacts_root': abs_root,
        'artifacts_root': rel_root,
        'abs_artifacts_root': abs_root,
        'report_kinds': rows,
    }


def serialise_available_reports( env ):
    """Alias for :func:`serialise_report_kinds` with toolchain rows included."""
    return serialise_report_kinds( env, include_toolchains=True )
