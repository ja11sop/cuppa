#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   C++ Profiles report — JSON schema, metadata, and model round-trip
#-------------------------------------------------------------------------------

import json
import os
from datetime import datetime, timezone

from cuppa.cpp.profiles_report.inventory import ProfilesInventory
from cuppa.cpp.profiles_report.types import ProfilesDiagnostic, ProfilesScope

REPORT_JSON_SCHEMA_VERSION = 1


def _utc_timestamp():
    return datetime.now( timezone.utc ).replace( microsecond=0 ).isoformat()


def build_report_metadata( env, header_context=None ):
    """Capture session fields needed to re-render HTML from JSON."""
    if header_context is None:
        from cuppa.cpp.profiles_report.report_html import report_header_context
        header_context = report_header_context( env )
    sconstruct_dir = env.get( 'sconstruct_dir' ) or os.getcwd()
    return {
        'sconstruct_dir': os.path.abspath( sconstruct_dir ),
        'report_project': header_context.get( 'report_project', '' ),
        'link_style': env.get( 'cxx_profiles_report_link_style' ) or 'local',
        'cxx_profiles_report_root': env.get( 'cxx_profiles_report_root' ) or sconstruct_dir,
        'report_uri': header_context.get( 'report_uri', '' ),
        'report_branch': header_context.get( 'report_branch', '' ),
        'report_revision': header_context.get( 'report_revision', '' ),
    }


def wrap_report_payload( model, env ):
    """Wrap a view model with schema version and session metadata."""
    return {
        'schema_version': REPORT_JSON_SCHEMA_VERSION,
        'generated_at': _utc_timestamp(),
        'metadata': build_report_metadata( env ),
        'report': model,
    }


def unwrap_report_payload( data ):
    """Return ``(model, metadata)`` from a loaded JSON document."""
    if not isinstance( data, dict ):
        raise ValueError( 'Profiles report JSON must be an object' )

    if 'report' in data and 'schema_version' in data:
        schema_version = data.get( 'schema_version' )
        if schema_version != REPORT_JSON_SCHEMA_VERSION:
            raise ValueError(
                'Unsupported Profiles report JSON schema version: {!r} (expected {})'.format(
                    schema_version,
                    REPORT_JSON_SCHEMA_VERSION,
                ),
            )
        model = data.get( 'report' )
        if not isinstance( model, dict ):
            raise ValueError( 'Profiles report JSON "report" must be an object' )
        metadata = data.get( 'metadata' ) or {}
        return model, metadata

    if 'scopes' in data and 'rollup' in data:
        return data, {}

    raise ValueError(
        'Unrecognised Profiles report JSON shape (expected schema_version/report or scopes/rollup)',
    )


def load_report_model( json_path ):
    """Load ``(model, metadata)`` from a report JSON file."""
    with open( json_path, encoding='utf-8' ) as handle:
        data = json.load( handle )
    return unwrap_report_payload( data )


def inventory_from_report_model( model ):
    """Rebuild a ``ProfilesInventory`` from a serialised view model."""
    inventory = ProfilesInventory()
    for scope_data in model.get( 'scopes', [] ):
        scope = ProfilesScope(
            sconscript=scope_data[ 'sconscript' ],
            variant_dir=scope_data[ 'variant_dir' ],
            toolchain=scope_data[ 'toolchain' ],
            variant_label=scope_data[ 'variant_label' ],
        )
        for profile_data in scope_data.get( 'profiles', [] ):
            profile_name = profile_data[ 'profile' ]
            for rule_data in profile_data.get( 'rules', [] ):
                rule_id = rule_data[ 'rule_id' ]
                for file_data in rule_data.get( 'files', [] ):
                    path = file_data[ 'path' ]
                    for location in file_data.get( 'locations', [] ):
                        diagnostic = ProfilesDiagnostic(
                            path=path,
                            line=location[ 'line' ],
                            column=location[ 'column' ],
                            message=location.get( 'message', '' ),
                            profile=profile_name,
                            normalised_message=location.get( 'normalised_message', '' ),
                            rule_id=rule_id,
                        )
                        references = location.get( 'references', 1 )
                        inventory.record( scope, diagnostic )
                        for _unused in range( references - 1 ):
                            inventory.record( scope, diagnostic )
    return inventory


def env_from_report_metadata( metadata, arguments ):
    """Merge CLI arguments with metadata saved in a report JSON file."""
    sconstruct_dir = arguments.sconstruct_dir
    if not sconstruct_dir and metadata.get( 'sconstruct_dir' ):
        sconstruct_dir = metadata[ 'sconstruct_dir' ]
    sconstruct_dir = os.path.abspath( sconstruct_dir or os.getcwd() )

    artifacts_root = arguments.artifacts_root
    abs_artifacts_root = (
        os.path.abspath( artifacts_root )
        if os.path.isabs( artifacts_root )
        else os.path.join( sconstruct_dir, artifacts_root )
    )

    link_style = arguments.link_style or metadata.get( 'link_style' ) or 'local'
    report_root = metadata.get( 'cxx_profiles_report_root' ) or sconstruct_dir

    env = {
        'sconstruct_dir': sconstruct_dir,
        'artifacts_root': artifacts_root,
        'abs_artifacts_root': abs_artifacts_root,
        'cxx_profiles_report': True,
        'cxx_profiles_report_link_style': link_style,
        'cxx_profiles_report_root': report_root,
    }
    if arguments.report_dir:
        env[ 'cxx_profiles_report' ] = os.path.abspath( arguments.report_dir )
    return env


def dump_report_json( handle, model, env ):
    """Write a versioned Profiles report JSON document."""
    payload = wrap_report_payload( model, env )
    json.dump( payload, handle, indent=2, sort_keys=True )
    handle.write( '\n' )
