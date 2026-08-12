#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   `.cuppa-reports` JSONL manifest — read, append, matched clean removal
#-------------------------------------------------------------------------------

import hashlib
import json
import os
import sys
from datetime import datetime, timezone

from cuppa.colourise import as_notice
from cuppa.log import logger

MANIFEST_BASENAME = '.cuppa-reports'
SCHEMA_VERSION = 1
KIND_CXX_PROFILES = 'cxx-profiles'


def manifest_path( project_root ):
    return os.path.join( project_root, MANIFEST_BASENAME )


def relpath_from_project( path, project_root ):
    if not path:
        return path
    try:
        rel = os.path.relpath( path, project_root )
    except ValueError:
        return path
    if rel.startswith( '..' ):
        return path
    return rel.replace( os.sep, '/' )


def cxx_profiles_report_options( env ):
    """Normalised report options used for ``invocation_key`` matching."""
    from cuppa.cpp.profiles_report.report_html import resolve_report_directory

    sconstruct_dir = env.get( 'sconstruct_dir' ) or os.getcwd()
    destination = resolve_report_directory( env )
    report_root = env.get( 'cxx_profiles_report_root' )
    if report_root:
        report_root = relpath_from_project( report_root, sconstruct_dir )
    return {
        'destination': relpath_from_project( destination, sconstruct_dir ),
        'link_style': env.get( 'cxx_profiles_report_link_style' ) or 'local',
        'report_root': report_root,
        'enforce': sorted( env.get( 'cxx_profiles_enforce' ) or [] ),
        'cxx_profiles': bool( env.get( 'cxx_profiles' ) ),
    }


def compute_invocation_key( cwd, argv, options ):
    payload = {
        'cwd': os.path.abspath( cwd ),
        'argv': list( argv ),
        'options': options,
    }
    digest = hashlib.sha256(
        json.dumps( payload, sort_keys=True, separators=( ',', ':' ) ).encode( 'utf-8' )
    ).hexdigest()
    return 'sha256:{}'.format( digest )


def paths_from_entry( entry ):
    paths = list( entry.get( 'session_paths', [] ) )
    for scope in entry.get( 'scopes', [] ):
        paths.extend( scope.get( 'paths', [] ) )
    all_paths = entry.get( 'all_paths' )
    if all_paths:
        return list( dict.fromkeys( all_paths ) )
    return list( dict.fromkeys( paths ) )


def read_entries( project_root ):
    path = manifest_path( project_root )
    if not os.path.isfile( path ):
        return []

    entries = []
    with open( path, encoding='utf-8' ) as handle:
        for line_number, line in enumerate( handle, start=1 ):
            text = line.strip()
            if not text:
                continue
            try:
                entries.append( json.loads( text ) )
            except json.JSONDecodeError as error:
                logger.warn(
                    "Ignoring invalid {} line {}: {}".format(
                        MANIFEST_BASENAME,
                        line_number,
                        error,
                    )
                )
    return entries


def append_entry( project_root, entry ):
    path = manifest_path( project_root )
    os.makedirs( os.path.dirname( path ) or '.', exist_ok=True )
    with open( path, 'a', encoding='utf-8' ) as handle:
        handle.write( json.dumps( entry, sort_keys=True ) )
        handle.write( '\n' )


def remove_matching_entries( project_root, invocation_key ):
    """Remove manifest rows for ``invocation_key`` and delete their artefact paths."""
    path = manifest_path( project_root )
    if not os.path.isfile( path ):
        return 0, []

    kept = []
    removed_paths = []
    removed_count = 0
    for entry in read_entries( project_root ):
        if entry.get( 'invocation_key' ) == invocation_key:
            removed_count += 1
            removed_paths.extend( paths_from_entry( entry ) )
        else:
            kept.append( entry )

    if removed_count == 0:
        return 0, []

    if kept:
        with open( path, 'w', encoding='utf-8' ) as handle:
            for entry in kept:
                handle.write( json.dumps( entry, sort_keys=True ) )
                handle.write( '\n' )
    else:
        os.remove( path )

    deleted = []
    for rel_path in dict.fromkeys( removed_paths ):
        abs_path = os.path.join( project_root, rel_path )
        if os.path.isfile( abs_path ):
            os.remove( abs_path )
            deleted.append( rel_path )
        elif os.path.isdir( abs_path ):
            import shutil
            shutil.rmtree( abs_path )
            deleted.append( rel_path )

    return removed_count, deleted


def build_cxx_profiles_entry(
    env,
    model,
    session_paths,
    scope_paths,
    incomplete_scopes=None,
    partial=False,
):
    sconstruct_dir = env.get( 'sconstruct_dir' ) or os.getcwd()
    options = cxx_profiles_report_options( env )
    incomplete = set( incomplete_scopes or [] )
    scopes = []
    for scope in model.get( 'scopes', [] ):
        profiles = sorted(
            profile[ 'profile' ] for profile in scope.get( 'profiles', [] )
        )
        scopes.append(
            {
                'sconscript': scope[ 'sconscript' ],
                'variant_dir': scope[ 'variant_dir' ],
                'variant_label': scope[ 'variant_label' ],
                'toolchain': scope[ 'toolchain' ],
                'complete': scope[ 'variant_dir' ] not in incomplete,
                'profiles': profiles,
                'paths': scope_paths.get( scope[ 'report_stem' ], [] ),
            },
        )

    rel_session_paths = [
        relpath_from_project( path, sconstruct_dir ) for path in session_paths
    ]
    all_paths = list( dict.fromkeys( rel_session_paths ) )
    for scope in scopes:
        all_paths.extend( scope[ 'paths' ] )
    all_paths = list( dict.fromkeys( all_paths ) )

    return {
        'kind': KIND_CXX_PROFILES,
        'schema': SCHEMA_VERSION,
        'created': datetime.now( timezone.utc ).replace( microsecond=0 ).isoformat(),
        'partial': bool( partial or incomplete ),
        'invocation_key': compute_invocation_key(
            sconstruct_dir,
            sys.argv,
            options,
        ),
        'argv': list( sys.argv ),
        'cwd': os.path.abspath( sconstruct_dir ),
        'options': options,
        'session_paths': rel_session_paths,
        'scopes': scopes,
        'all_paths': all_paths,
    }


def maybe_remove_cxx_profiles_on_clean( env ):
    """When ``--clean`` or ``--remove-builds`` runs with report flags, delete matching artefacts."""
    if not env.get( 'cxx_profiles_report' ):
        return 0, []
    if not env.get( 'clean' ) and not env.get( 'remove_builds' ):
        return 0, []

    sconstruct_dir = env.get( 'sconstruct_dir' ) or os.getcwd()
    options = cxx_profiles_report_options( env )
    invocation_key = compute_invocation_key( sconstruct_dir, sys.argv, options )
    removed_count, deleted = remove_matching_entries( sconstruct_dir, invocation_key )
    if removed_count:
        logger.info(
            "C++ Profiles report clean: removed {} manifest entr{} ({} file(s))".format(
                removed_count,
                'y' if removed_count == 1 else 'ies',
                len( deleted ),
            )
        )
        for rel_path in deleted:
            logger.info( "  {}".format( as_notice( rel_path ) ) )
    return removed_count, deleted


def append_cxx_profiles_entry(
    env,
    model,
    session_paths,
    scope_paths,
    incomplete_scopes=None,
    partial=False,
):
    sconstruct_dir = env.get( 'sconstruct_dir' ) or os.getcwd()
    entry = build_cxx_profiles_entry(
        env,
        model,
        session_paths,
        scope_paths,
        incomplete_scopes=incomplete_scopes,
        partial=partial,
    )
    append_entry( sconstruct_dir, entry )
    logger.debug(
        "Appended {} manifest entry for {}".format(
            MANIFEST_BASENAME,
            entry[ 'invocation_key' ],
        )
    )
    return entry
