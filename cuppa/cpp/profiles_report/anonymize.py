#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   C++ Profiles report — anonymize saved JSON for shareable inventory artefacts
#-------------------------------------------------------------------------------

import copy
import hashlib
import json
import os
import re

from cuppa.cpp.profiles_report.report_json import location_key_from_dedupe
from cuppa.cpp.profiles_report.types import ProfilesDiagnostic, ProfilesScope

ANONYMIZATION_VERSION = 1
ANON_PLACEHOLDER_ROOT = '/home/user/project/widget'
ANON_PROJECT_SLUG = 'widget'

PASSTHROUGH_SEGMENTS = frozenset(
    {
        'include',
        'src',
        'source',
        'test',
        'tests',
        'lib',
        'libs',
        'util',
        'utils',
        'internal',
        'public',
        'private',
        'detail',
        'details',
        'generated',
        'build',
        'bin',
        'obj',
        'third_party',
        '3rdparty',
        'vendor',
        'extern',
        'external',
        'cpp',
        'hpp',
        'cxx',
        'cc',
        'c',
        'h',
        'hh',
        'inc',
    },
)

VARIANT_LABELS = frozenset( { 'dbg', 'rel', 'cov', 'opt', 'profile', 'san', 'asan', 'ubsan' } )

GENERIC_STEMS = ( 'module', 'component', 'item', 'element', 'entity' )

_CUPPA_DOWNLOAD_MARKER = '_cuppa/_download/'


def default_synonym_dictionary_path():
    return os.path.join( os.path.dirname( __file__ ), 'synonym_dictionary.json' )


def load_synonym_dictionary( path=None ):
    """Load the built-in offline synonym map."""
    dictionary_path = path or default_synonym_dictionary_path()
    with open( dictionary_path, encoding='utf-8' ) as handle:
        data = json.load( handle )
    if not isinstance( data, dict ):
        raise ValueError( 'Synonym dictionary must be a JSON object' )
    return data


def _deterministic_pick( original, choices ):
    if not choices:
        return original
    digest = hashlib.sha256( original.encode( 'utf-8' ) ).hexdigest()
    index = int( digest, 16 ) % len( choices )
    return choices[ index ]


def _split_extension( name ):
    base, ext = os.path.splitext( name )
    return base, ext


def anonymize_stem( stem, dictionary, passthrough=None ):
    """Rewrite one path component stem using dictionary rules."""
    if not stem:
        return stem
    passthrough = passthrough or PASSTHROUGH_SEGMENTS
    if stem in passthrough and '_' not in stem:
        return stem
    if stem in dictionary:
        return dictionary[ stem ]

    if '_' in stem:
        parts = stem.split( '_' )
        new_parts = []
        replaced = False
        for part in parts:
            if part in passthrough and not replaced:
                new_parts.append( part )
                continue
            if part in dictionary:
                new_parts.append( dictionary[ part ] )
                replaced = True
            elif not replaced:
                new_parts.append( _generic_stem( part, dictionary ) )
                replaced = True
            else:
                new_parts.append( dictionary.get( part, part ) )
        return '_'.join( new_parts )

    return _generic_stem( stem, dictionary )


def _generic_stem( original, dictionary ):
    choices = [
        dictionary[ key ]
        for key in GENERIC_STEMS
        if key in dictionary
    ]
    if not choices:
        choices = list( GENERIC_STEMS )
    return _deterministic_pick( original, choices )


def split_variant_dir( variant_dir ):
    """Split a variant directory into anonymizable prefix and preserved tail."""
    parts = [ part for part in variant_dir.strip( '/' ).split( '/' ) if part ]
    for index, part in enumerate( parts ):
        if part in VARIANT_LABELS and index >= 2:
            return parts[ : index - 1 ], parts[ index - 1 : ]
    return parts, []


class PathAnonymizer( object ):
    """Deterministic path rewriter for Profiles report JSON."""

    def __init__(
        self,
        metadata,
        dictionary=None,
        mapping=None,
        project_slug=None,
    ):
        self.metadata = metadata or {}
        self.dictionary = dictionary or load_synonym_dictionary()
        self.mapping = mapping if mapping is not None else None
        self.project_slug = project_slug or self._project_slug()
        self.sconstruct_dir = os.path.abspath(
            self.metadata.get( 'sconstruct_dir' ) or ANON_PLACEHOLDER_ROOT,
        )
        self.report_root = os.path.abspath(
            self.metadata.get( 'cxx_profiles_report_root' ) or self.sconstruct_dir,
        )
        self._cache = {}
        self._used_paths = set()

    def _project_slug( self ):
        project = self.metadata.get( 'report_project' ) or ''
        if project:
            slug = anonymize_stem( project, self.dictionary )
            if slug:
                return slug
        return ANON_PROJECT_SLUG

    def anonymize_sconscript( self, sconscript ):
        if not sconscript:
            return sconscript
        raw = sconscript.lstrip( './' )
        parts = [ part for part in raw.split( '/' ) if part ]
        if not parts:
            return './{}/sconscript'.format( self.project_slug )
        parts[ 0 ] = self.project_slug
        for index in range( 1, len( parts ) - 1 ):
            parts[ index ] = anonymize_stem( parts[ index ], self.dictionary )
        return './{}'.format( '/'.join( parts ) )

    def anonymize_variant_dir( self, variant_dir ):
        if not variant_dir:
            return variant_dir
        prefix, tail = split_variant_dir( variant_dir )
        if not prefix:
            return variant_dir
        new_prefix = []
        for index, part in enumerate( prefix ):
            if index == 0 and part == '_build':
                new_prefix.append( part )
                continue
            if index == 1:
                new_prefix.append( self.project_slug )
                continue
            new_prefix.append( anonymize_stem( part, self.dictionary ) )
        if tail:
            return '/'.join( new_prefix + tail )
        return '/'.join( new_prefix )

    def _download_relative( self, path ):
        normalised = path.replace( '\\', '/' )
        index = normalised.find( _CUPPA_DOWNLOAD_MARKER )
        if index < 0:
            return None
        return normalised[ index + len( _CUPPA_DOWNLOAD_MARKER ) : ]

    def _project_relative( self, path ):
        for root in ( self.report_root, self.sconstruct_dir ):
            try:
                rel = os.path.relpath( path, root )
            except ValueError:
                continue
            if not rel.startswith( '..' ):
                return rel.replace( '\\', '/' )
        return None

    def _anonymize_relative_parts( self, rel ):
        parts = [ part for part in rel.replace( '\\', '/' ).split( '/' ) if part ]
        rewritten = []
        for part in parts:
            base, ext = _split_extension( part )
            new_base = anonymize_stem( base, self.dictionary )
            rewritten.append( '{}{}'.format( new_base, ext ) )
        return rewritten

    def _join_relative( self, parts ):
        return '/'.join( parts )

    def _disambiguate( self, candidate ):
        if candidate not in self._used_paths:
            self._used_paths.add( candidate )
            return candidate
        directory, name = os.path.split( candidate.replace( '\\', '/' ) )
        base, ext = _split_extension( name )
        suffix = 2
        while True:
            if directory:
                disambiguated = '{}/{}_{}{}'.format( directory, base, suffix, ext )
            else:
                disambiguated = '{}_{}{}'.format( base, suffix, ext )
            if disambiguated not in self._used_paths:
                self._used_paths.add( disambiguated )
                return disambiguated
            suffix += 1

    def anonymize_path( self, path ):
        if not path:
            return path
        if path in self._cache:
            return self._cache[ path ]

        download_rel = self._download_relative( path )
        if download_rel is not None:
            parts = self._anonymize_relative_parts( download_rel )
            result = self._join_relative( [ '_cuppa', '_download', 'vendor' ] + parts )
        else:
            project_rel = self._project_relative( path ) if os.path.isabs( path ) else path.replace( '\\', '/' )
            if project_rel is None:
                project_rel = path.replace( '\\', '/' )
            if project_rel.startswith( '_build/' ) or project_rel == '_build':
                parts = project_rel.split( '/' )
                if len( parts ) >= 2:
                    parts[ 1 ] = self.project_slug
                for index in range( 2, len( parts ) ):
                    if parts[ index ] in VARIANT_LABELS:
                        break
                    if parts[ index ] in PASSTHROUGH_SEGMENTS:
                        continue
                    base, ext = _split_extension( parts[ index ] )
                    parts[ index ] = '{}{}'.format(
                        anonymize_stem( base, self.dictionary ),
                        ext,
                    )
                result = self._join_relative( parts )
            else:
                parts = self._anonymize_relative_parts( project_rel )
                result = self._join_relative( parts )

        result = self._disambiguate( result )
        self._cache[ path ] = result
        if self.mapping is not None:
            self.mapping[ path ] = result
        return result


def _scrub_metadata( metadata ):
    metadata[ 'sconstruct_dir' ] = ANON_PLACEHOLDER_ROOT
    metadata[ 'cxx_profiles_report_root' ] = ANON_PLACEHOLDER_ROOT
    metadata[ 'report_project' ] = 'example-project' if metadata.get( 'report_project' ) else ''
    metadata[ 'report_uri' ] = ''
    metadata[ 'report_branch' ] = ''
    metadata[ 'report_revision' ] = ''
    metadata[ 'link_style' ] = 'local'
    metadata[ 'anonymized' ] = True
    metadata[ 'anonymization_version' ] = ANONYMIZATION_VERSION
    return metadata


def _scrub_location_row( row, path_anonymizer ):
    row[ 'sconscript' ] = path_anonymizer.anonymize_sconscript( row.get( 'sconscript', '' ) )
    row[ 'variant_dir' ] = path_anonymizer.anonymize_variant_dir( row.get( 'variant_dir', '' ) )
    row[ 'path' ] = path_anonymizer.anonymize_path( row.get( 'path', '' ) )
    row.pop( 'message', None )
    scope = ProfilesScope(
        sconscript=row[ 'sconscript' ],
        variant_dir=row[ 'variant_dir' ],
        toolchain=row.get( 'toolchain', '' ),
        variant_label=row.get( 'variant_label', '' ),
    )
    diagnostic = ProfilesDiagnostic(
        path=row[ 'path' ],
        line=row.get( 'line', 0 ),
        column=row.get( 'column', 0 ),
        message='',
        profile=row.get( 'profile', '' ),
        normalised_message=row.get( 'normalised_message', '' ),
        rule_id=row.get( 'rule_id', '' ),
    )
    row[ 'location_key' ] = location_key_from_dedupe( scope, diagnostic )
    return row


def _scrub_violation_key( key, path_anonymizer ):
    if not isinstance( key, ( list, tuple ) ) or len( key ) < 2:
        return key
    scrubbed = list( key )
    scrubbed[ 0 ] = path_anonymizer.anonymize_sconscript( scrubbed[ 0 ] )
    scrubbed[ 1 ] = path_anonymizer.anonymize_path( scrubbed[ 1 ] )
    return scrubbed


def _scrub_violation_ref_entries( entries, path_anonymizer ):
    for entry in entries or []:
        if isinstance( entry, dict ) and 'key' in entry:
            entry[ 'key' ] = _scrub_violation_key( entry[ 'key' ], path_anonymizer )


def _scrub_identity_fields( node, path_anonymizer ):
    if not isinstance( node, dict ):
        return node
    if 'violation_identity_keys' in node:
        node[ 'violation_identity_keys' ] = [
            _scrub_violation_key( key, path_anonymizer )
            for key in node.get( 'violation_identity_keys', [] )
        ]
    _scrub_violation_ref_entries( node.get( 'violation_refs' ), path_anonymizer )
    return node


def _scrub_variant_counts( variants, path_anonymizer ):
    for variant in variants or []:
        _scrub_identity_fields( variant, path_anonymizer )
        for file_entry in variant.get( 'files', [] ):
            _scrub_file_entry( file_entry, path_anonymizer )


def _scrub_file_entry( file_entry, path_anonymizer ):
    file_entry[ 'path' ] = path_anonymizer.anonymize_path( file_entry.get( 'path', '' ) )
    for location in file_entry.get( 'locations', [] ):
        location.pop( 'message', None )
    _scrub_identity_fields( file_entry, path_anonymizer )
    _scrub_variant_counts( file_entry.get( 'variant_counts' ), path_anonymizer )
    for rule in file_entry.get( 'rules', [] ):
        _scrub_identity_fields( rule, path_anonymizer )
        _scrub_variant_counts( rule.get( 'variant_counts' ), path_anonymizer )
        for nested in rule.get( 'files', [] ):
            _scrub_file_entry( nested, path_anonymizer )
    return file_entry


def _scrub_rule( rule, path_anonymizer ):
    _scrub_identity_fields( rule, path_anonymizer )
    _scrub_variant_counts( rule.get( 'variant_counts' ), path_anonymizer )
    for file_entry in rule.get( 'files', [] ):
        _scrub_file_entry( file_entry, path_anonymizer )
    return rule


def _scrub_profile( profile, path_anonymizer ):
    for rule in profile.get( 'rules', [] ):
        _scrub_rule( rule, path_anonymizer )
    for file_entry in profile.get( 'files', [] ):
        _scrub_file_entry( file_entry, path_anonymizer )
    return profile


def _scrub_scope( scope, path_anonymizer ):
    scope[ 'sconscript' ] = path_anonymizer.anonymize_sconscript( scope.get( 'sconscript', '' ) )
    scope[ 'variant_dir' ] = path_anonymizer.anonymize_variant_dir( scope.get( 'variant_dir', '' ) )
    for profile in scope.get( 'profiles', [] ):
        _scrub_profile( profile, path_anonymizer )
    return scope


def _scrub_model( model, path_anonymizer ):
    for scope in model.get( 'scopes', [] ):
        _scrub_scope( scope, path_anonymizer )
    rollup = model.get( 'rollup', {} )
    for rule in rollup.get( 'rules', [] ):
        _scrub_rule( rule, path_anonymizer )
    for file_entry in rollup.get( 'files', [] ):
        _scrub_file_entry( file_entry, path_anonymizer )
    return model


def anonymize_report_payload( payload, *, dictionary=None, mapping=None, force=False ):
    """Return a deep-copied anonymized report payload."""
    if not isinstance( payload, dict ):
        raise ValueError( 'Profiles report payload must be an object' )
    if payload.get( 'metadata', {} ).get( 'anonymized' ) and not force:
        raise ValueError(
            'Input already has metadata.anonymized; pass force=True to re-anonymize',
        )

    result = copy.deepcopy( payload )
    metadata = result.setdefault( 'metadata', {} )
    path_anonymizer = PathAnonymizer( metadata, dictionary=dictionary, mapping=mapping )

    model = result.get( 'report' )
    if isinstance( model, dict ):
        _scrub_model( model, path_anonymizer )

    locations = result.get( 'locations' ) or []
    if locations:
        result[ 'locations' ] = [
            _scrub_location_row( row, path_anonymizer )
            for row in locations
        ]

    incomplete = metadata.get( 'incomplete_scopes' ) or []
    if incomplete:
        metadata[ 'incomplete_scopes' ] = [
            path_anonymizer.anonymize_sconscript( item )
            for item in incomplete
        ]

    _scrub_metadata( metadata )
    return result


def anonymize_report_document( data, *, dictionary=None, mapping=None, force=False ):
    """Anonymize a loaded JSON document (schema envelope or legacy model)."""
    from cuppa.cpp.profiles_report.report_json import unwrap_report_payload

    model, metadata, extras = unwrap_report_payload( data )
    if 'report' in data and 'schema_version' in data:
        return anonymize_report_payload( data, dictionary=dictionary, mapping=mapping, force=force )

    payload = {
        'schema_version': data.get( 'schema_version', 1 ),
        'generated_at': data.get( 'generated_at', '' ),
        'metadata': metadata,
        'summary': extras.get( 'summary' ) or {},
        'locations': extras.get( 'locations' ) or [],
        'report': model,
    }
    if extras.get( 'context' ) is not None:
        payload[ 'context' ] = extras[ 'context' ]
    return anonymize_report_payload( payload, dictionary=dictionary, mapping=mapping, force=force )


def forbidden_identity_patterns( metadata ):
    """Return regex fragments that must not appear in shared JSON."""
    patterns = []
    for key in ( 'sconstruct_dir', 'cxx_profiles_report_root', 'report_uri', 'report_project' ):
        value = metadata.get( key ) or ''
        if value and value not in ( ANON_PLACEHOLDER_ROOT, 'example-project', '' ):
            patterns.append( re.escape( value ) )
    return patterns
