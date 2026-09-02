#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   C++ Profiles report — JSON schema, metadata, and model round-trip
#-------------------------------------------------------------------------------

import hashlib
import json
import os
from datetime import datetime, timezone

from cuppa.cpp.profiles_report.inventory import ProfilesInventory, location_dedupe_key
from cuppa.cpp.profiles_report.types import ProfilesDiagnostic, ProfilesScope

REPORT_JSON_SCHEMA_VERSION = 1
SUPPORTED_SCHEMA_VERSIONS = frozenset( ( REPORT_JSON_SCHEMA_VERSION, ) )


def _utc_timestamp():
    return datetime.now( timezone.utc ).replace( microsecond=0 ).isoformat()


def location_key_from_dedupe( scope, diagnostic ):
    """Return a stable hash key for diffing and deduping report locations."""
    key_parts = location_dedupe_key( scope, diagnostic )
    digest = hashlib.sha256(
        json.dumps( key_parts, separators=( ',', ':' ), ensure_ascii=True ).encode( 'utf-8' ),
    )
    return digest.hexdigest()


def location_key_from_location( location ):
    """Return the stable key for one inventoried location."""
    diagnostic = ProfilesDiagnostic(
        path=location.path,
        line=location.line,
        column=location.column,
        message=location.raw_message,
        profile=location.profile,
        normalised_message=location.normalised_message,
        rule_id=location.rule_id,
    )
    return location_key_from_dedupe( location.scope, diagnostic )


def attach_rule_doc_hrefs( model ):
    """Add published rule documentation URLs to nested rule entries."""
    from cuppa.cpp.profiles_report.report_html import rule_doc_href

    def enrich_rules( rules, profile_name ):
        for rule in rules:
            profile = rule.get( 'profile' ) or profile_name
            if not profile:
                continue
            rule[ 'doc_href' ] = rule_doc_href( profile, rule[ 'rule_id' ] )

    def enrich_files( files, profile_name ):
        for file_entry in files:
            profile = file_entry.get( 'profile' ) or profile_name
            enrich_rules( file_entry.get( 'rules', [] ), profile )

    for scope in model.get( 'scopes', [] ):
        for profile in scope.get( 'profiles', [] ):
            profile_name = profile.get( 'profile' )
            enrich_rules( profile.get( 'rules', [] ), profile_name )
            enrich_files( profile.get( 'files', [] ), profile_name )

    rollup = model.get( 'rollup', {} )
    for rule in rollup.get( 'rules', [] ):
        enrich_rules( [ rule ], rule.get( 'profile' ) )
    enrich_files( rollup.get( 'files', [] ), None )


def build_report_summary( model ):
    """Build a compact session summary for agents and CI gates."""
    rollup = model.get( 'rollup', {} )
    by_rule = {}
    for rule in rollup.get( 'rules', [] ):
        by_rule[ rule[ 'rule_id' ] ] = rule.get( 'total_references', 0 )
    return {
        'total_references': rollup.get( 'total_references', 0 ),
        'raw_total_references': rollup.get( 'raw_total_references', 0 ),
        'unique_violation_count': rollup.get( 'unique_violation_count', 0 ),
        'unique_rule_count': rollup.get( 'unique_rule_count', 0 ),
        'unique_locations': rollup.get( 'unique_locations', 0 ),
        'files_with_violations': len( rollup.get( 'files', [] ) ),
        'scope_count': len( model.get( 'scopes', [] ) ),
        'by_rule': by_rule,
    }


def build_flat_locations( inventory ):
    """Flatten inventoried locations for machine-readable analysis."""
    rows = []
    for location in inventory.locations():
        rows.append(
            {
                'location_key': location_key_from_location( location ),
                'sconscript': location.scope.sconscript,
                'variant_dir': location.scope.variant_dir,
                'variant_label': location.scope.variant_label,
                'toolchain': location.scope.toolchain,
                'profile': location.profile,
                'rule_id': location.rule_id,
                'path': location.path,
                'line': location.line,
                'column': location.column,
                'references': location.reference_count,
                'normalised_message': location.normalised_message,
                'message': location.raw_message,
            },
        )
    rows.sort(
        key=lambda row: (
            row[ 'sconscript' ],
            row[ 'variant_dir' ],
            row[ 'path' ],
            row[ 'line' ],
            row[ 'column' ],
            row[ 'profile' ],
            row[ 'rule_id' ],
        ),
    )
    return rows


def build_report_metadata( env, header_context=None, model=None, incomplete_scopes=None ):
    """Capture session fields needed to re-render HTML from JSON."""
    if header_context is None:
        from cuppa.cpp.profiles_report.report_html import report_header_context
        header_context = report_header_context( env )
    sconstruct_dir = env.get( 'sconstruct_dir' ) or os.getcwd()
    scopes = ( model or {} ).get( 'scopes', [] )
    variant_labels = sorted(
        {
            scope.get( 'variant_label' )
            for scope in scopes
            if scope.get( 'variant_label' )
        },
    )
    incomplete = sorted( incomplete_scopes or [] )
    from cuppa.reports.link_style import resolve_report_link_style
    metadata = {
        'sconstruct_dir': os.path.abspath( sconstruct_dir ),
        'report_project': header_context.get( 'report_project', '' ),
        'link_style': resolve_report_link_style(
            env,
            per_report_env_key='cxx_profiles_report_link_style',
        ),
        'cxx_profiles_report_root': env.get( 'cxx_profiles_report_root' ) or sconstruct_dir,
        'report_uri': header_context.get( 'report_uri', '' ),
        'report_branch': header_context.get( 'report_branch', '' ),
        'report_revision': header_context.get( 'report_revision', '' ),
        'profiles_enforce': list( env.get( 'cxx_profiles_enforce' ) or [] ),
        'variant_labels': variant_labels,
        'incomplete_scopes': incomplete,
        'partial': bool( incomplete ),
    }
    scope_filter = env.get( '_cxx_profiles_scope_filter' )
    if scope_filter:
        metadata[ 'scope_filter' ] = dict( scope_filter )
    return metadata


def wrap_report_payload( model, env, inventory=None, incomplete_scopes=None, context=None ):
    """Wrap a view model with schema version, metadata, summary, and locations."""
    attach_rule_doc_hrefs( model )
    if context is None:
        from cuppa.cpp.profiles_report.context_summary import (
            build_report_context,
            resolve_context_mode,
        )
        context = build_report_context(
            model,
            env,
            parsed_files=getattr( env, '_cxx_profiles_parsed_files', None ),
            translation_units=getattr( env, '_cxx_profiles_translation_units', None ),
            context_mode=resolve_context_mode( env ),
        )
    payload = {
        'schema_version': REPORT_JSON_SCHEMA_VERSION,
        'generated_at': _utc_timestamp(),
        'metadata': build_report_metadata(
            env,
            model=model,
            incomplete_scopes=incomplete_scopes,
        ),
        'summary': build_report_summary( model ),
        'report': model,
    }
    if context is not None:
        payload[ 'context' ] = context
    if inventory is not None:
        payload[ 'locations' ] = build_flat_locations( inventory )
    return payload


def unwrap_report_payload( data ):
    """Return ``(model, metadata, extras)`` from a loaded JSON document."""
    if not isinstance( data, dict ):
        raise ValueError( 'Profiles report JSON must be an object' )

    extras = {
        'summary': data.get( 'summary' ) or {},
        'locations': data.get( 'locations' ) or [],
        'context': data.get( 'context' ) or None,
    }

    if 'report' in data and 'schema_version' in data:
        schema_version = data.get( 'schema_version' )
        if schema_version not in SUPPORTED_SCHEMA_VERSIONS:
            raise ValueError(
                'Unsupported Profiles report JSON schema version: {!r} (expected one of {})'.format(
                    schema_version,
                    sorted( SUPPORTED_SCHEMA_VERSIONS ),
                ),
            )
        model = data.get( 'report' )
        if not isinstance( model, dict ):
            raise ValueError( 'Profiles report JSON "report" must be an object' )
        metadata = data.get( 'metadata' ) or {}
        return model, metadata, extras

    if 'scopes' in data and 'rollup' in data:
        return data, {}, extras

    raise ValueError(
        'Unrecognised Profiles report JSON shape (expected schema_version/report or scopes/rollup)',
    )


def load_report_model( json_path ):
    """Load ``(model, metadata, extras)`` from a report JSON file."""
    with open( json_path, encoding='utf-8' ) as handle:
        data = json.load( handle )
    return unwrap_report_payload( data )


def inventory_from_flat_locations( locations ):
    """Rebuild inventory from a flat ``locations[]`` array."""
    inventory = ProfilesInventory()
    for row in locations:
        scope = ProfilesScope(
            sconscript=row[ 'sconscript' ],
            variant_dir=row[ 'variant_dir' ],
            toolchain=row[ 'toolchain' ],
            variant_label=row[ 'variant_label' ],
        )
        diagnostic = ProfilesDiagnostic(
            path=row[ 'path' ],
            line=row[ 'line' ],
            column=row[ 'column' ],
            message=row.get( 'message', '' ),
            profile=row[ 'profile' ],
            normalised_message=row.get( 'normalised_message', '' ),
            rule_id=row[ 'rule_id' ],
        )
        references = row.get( 'references', 1 )
        inventory.record( scope, diagnostic )
        for _unused in range( references - 1 ):
            inventory.record( scope, diagnostic )
    return inventory


def inventory_from_report_model( model, flat_locations=None ):
    """Rebuild a ``ProfilesInventory`` from JSON (flat or nested)."""
    if flat_locations:
        return inventory_from_flat_locations( flat_locations )

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
    from cuppa.cpp.profiles_report.anonymise import (
        ANON_PLACEHOLDER_ROOT,
        metadata_is_anonymised,
        set_env_anonymised,
    )

    anonymised = metadata_is_anonymised( metadata )
    if getattr( arguments, 'sconstruct_dir', None ):
        sconstruct_dir = os.path.abspath( arguments.sconstruct_dir )
    elif anonymised:
        sconstruct_dir = os.path.abspath(
            metadata.get( 'sconstruct_dir' ) or ANON_PLACEHOLDER_ROOT,
        )
    elif metadata.get( 'sconstruct_dir' ):
        sconstruct_dir = metadata[ 'sconstruct_dir' ]
    else:
        sconstruct_dir = os.path.abspath( os.getcwd() )

    artefacts_root = (
        getattr( arguments, 'artefacts_root', None )
        or getattr( arguments, 'artifacts_root', None )
        or '_artefacts'
    )
    abs_artefacts_root = (
        os.path.abspath( artefacts_root )
        if os.path.isabs( artefacts_root )
        else os.path.join( sconstruct_dir, artefacts_root )
    )

    def _normalise_style( value ):
        return value if value else None

    profiles_style = _normalise_style(
        getattr( arguments, 'cxx_profiles_report_link_style', None ),
    )
    session_style = _normalise_style(
        getattr( arguments, 'reports_link_style', None ),
    ) or _normalise_style( getattr( arguments, 'link_style', None ) )

    if anonymised and not getattr( arguments, 'sconstruct_dir', None ):
        report_root = os.path.abspath(
            metadata.get( 'cxx_profiles_report_root' ) or sconstruct_dir,
        )
    else:
        report_root = metadata.get( 'cxx_profiles_report_root' ) or sconstruct_dir

    env = {
        'sconstruct_dir': sconstruct_dir,
        'artefacts_root': artefacts_root,
        'abs_artefacts_root': abs_artefacts_root,
        'artifacts_root': artefacts_root,
        'abs_artifacts_root': abs_artefacts_root,
        'cxx_profiles_report': True,
        'cxx_profiles_report_root': report_root,
    }
    if profiles_style:
        env[ 'cxx_profiles_report_link_style' ] = profiles_style
    elif session_style:
        env[ 'reports_link_style' ] = session_style
    elif metadata.get( 'link_style' ):
        env[ 'reports_link_style' ] = metadata[ 'link_style' ]
    if metadata.get( 'profiles_enforce' ):
        env[ 'cxx_profiles_enforce' ] = list( metadata[ 'profiles_enforce' ] )
    if metadata_is_anonymised( metadata ):
        set_env_anonymised( env )
    if arguments.report_dir:
        env[ 'cxx_profiles_report' ] = os.path.abspath( arguments.report_dir )
    return env


def dump_report_json(
    handle,
    model,
    env,
    inventory=None,
    incomplete_scopes=None,
    context=None,
    parsed_files=None,
    translation_units=None,
):
    """Write a versioned Profiles report JSON document."""
    if inventory is None:
        inventory = inventory_from_report_model( model )
    merged_env = dict( env )
    if parsed_files is not None:
        merged_env[ '_cxx_profiles_parsed_files' ] = parsed_files
    if translation_units is not None:
        merged_env[ '_cxx_profiles_translation_units' ] = translation_units
    payload = wrap_report_payload(
        model,
        merged_env,
        inventory=inventory,
        incomplete_scopes=incomplete_scopes,
        context=context,
    )
    json.dump( payload, handle, indent=2, sort_keys=True )
    handle.write( '\n' )
