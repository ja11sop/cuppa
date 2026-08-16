#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   C++ Profiles report — anonymise saved JSON for shareable inventory artefacts
#-------------------------------------------------------------------------------

import copy
import hashlib
import json
import os
import re
from urllib.parse import urlparse

from cuppa.cpp.profiles_report.report_json import location_key_from_dedupe
from cuppa.cpp.profiles_report.types import ProfilesDiagnostic, ProfilesScope

ANONYMISATION_VERSION = 1
ANON_PLACEHOLDER_ROOT = '/anon/widget/root'

DEPS_ROOT = 'deps'
PROJECT_ROOT = 'project'

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
        'working',
    },
)

VARIANT_LABELS = frozenset( { 'dbg', 'rel', 'cov', 'opt', 'profile', 'san', 'asan', 'ubsan' } )

_HTML_ENRICHMENT_KEYS = frozenset(
    {
        'build_catalog',
        'build_inventory',
        'build_refs_display',
        'build_views',
        'display_path',
        'file_index',
        'href',
        'page_href',
        'path_tooltip',
        'peak_refs_display',
        'profiles_summary',
        'profiles_summary_items',
        'reference',
        'refs_display',
        'rules_display',
        'rules_summary',
        'rules_summary_items',
        'scope_path_suffix',
        'title_include_path',
        'title_include_prefix',
        'title_include_split',
        'title_prefix',
        'title_single',
        'title_split',
        'title_suffix',
        'title_suffix_only',
        'variant_display',
        'variant_display_tail',
        'violated_rules_display',
        'violating_files_display',
        'violation_message_html',
    },
)

_GIT_SSH_PREFIX = 'git_ssh_'
_DOWNLOAD_MARKERS = (
    '_cuppa/_download/',
    '/_cuppa/_download/',
    '/.cuppa/dependencies/',
    '/_cuppa/dependencies/',
    'dependencies/',
)
_MIN_FORBIDDEN_TOKEN_LEN = 3
_ENCODED_FOLDER_NOISE = frozenset( { 'git', 'ssh', 'http', 'https' } )
_ENCODED_FOLDER_RE = re.compile(
    r'(?:^|[/\\])(git_ssh_[^/\\]+(?:@[^/\\]+)?)(?:[/\\]|$)',
)

ENV_ANONYMISED_KEY = 'cxx_profiles_report_anonymised'
ENV_ANONYMISED_KEY_US = 'cxx_profiles_report_anonymized'


def metadata_is_anonymised( metadata ):
    """Return whether report JSON metadata marks the payload as anonymised."""
    if not metadata:
        return False
    return bool( metadata.get( 'anonymised' ) or metadata.get( 'anonymized' ) )


def env_is_anonymised( env ):
    """Return whether regen env suppresses identity-bearing source links."""
    if not env:
        return False
    return bool( env.get( ENV_ANONYMISED_KEY ) or env.get( ENV_ANONYMISED_KEY_US ) )


def set_env_anonymised( env ):
    env[ ENV_ANONYMISED_KEY ] = True
    env.pop( ENV_ANONYMISED_KEY_US, None )


def default_thematic_names_path():
    return os.path.join( os.path.dirname( __file__ ), 'thematic_names.json' )


def load_thematic_names( path=None ):
    """Load thematic name pools for dependency, project, and path rewriting."""
    names_path = path or default_thematic_names_path()
    with open( names_path, encoding='utf-8' ) as handle:
        data = json.load( handle )
    for key in ( 'dependency_slugs', 'project_slugs', 'path_names', 'path_compounds' ):
        if key not in data or not isinstance( data[ key ], list ) or not data[ key ]:
            raise ValueError( 'Thematic names JSON must include a non-empty {!r} list'.format( key ) )
    return data


def load_synonym_dictionary( path=None ):
    """Compatibility alias — returns ``path_names`` as a stem→name map is no longer used."""
    return load_thematic_names( path )


def _deterministic_pick( original, choices ):
    if not choices:
        raise ValueError( 'Thematic name pool is empty for {!r}'.format( original ) )
    digest = hashlib.sha256( original.encode( 'utf-8' ) ).hexdigest()
    index = int( digest, 16 ) % len( choices )
    return choices[ index ]


def _forbidden_blocks_name( name, forbidden ):
    if not name or not forbidden:
        return False
    if name in forbidden:
        return True
    lowered = name.lower()
    return any( token.lower() == lowered for token in forbidden if token )


def _thematic_name_is_safe( name, forbidden ):
    """Return whether ``name`` is safe to emit (exact and substring checks)."""
    if _forbidden_blocks_name( name, forbidden ):
        return False
    for token in forbidden:
        if not token:
            continue
        if _token_leaks( token, name ):
            return False
    return True


def _synthesised_thematic_name( original, used, forbidden ):
    """Return a stable synthetic name when the curated pool cannot supply one."""
    for salt in range( 1024 ):
        label = original if salt == 0 else '{}:{}'.format( original, salt )
        digest = hashlib.sha256( label.encode( 'utf-8' ) ).hexdigest()[ :10 ]
        candidate = 'slot-{}'.format( digest )
        if candidate in used:
            continue
        if not _thematic_name_is_safe( candidate, forbidden ):
            continue
        used.add( candidate )
        return candidate
    raise ValueError(
        'Could not allocate a thematic name for {!r}'.format( original ),
    )


def _pick_unique( original, pool, used, forbidden=None ):
    """Pick a stable thematic name from ``pool``, disambiguating collisions in-session."""
    forbidden = forbidden or set()
    available = [
        name
        for name in pool
        if name not in used and _thematic_name_is_safe( name, forbidden )
    ]
    if not available:
        return _synthesised_thematic_name( original, used, forbidden )
    candidate = _deterministic_pick( original, available )
    used.add( candidate )
    return candidate


def _split_extension( name ):
    base, ext = os.path.splitext( name )
    return base, ext


def split_variant_dir( variant_dir ):
    """Split a variant directory into anonymisable prefix and preserved tail."""
    parts = [ part for part in variant_dir.strip( '/' ).split( '/' ) if part ]
    for index, part in enumerate( parts ):
        if part in VARIANT_LABELS and index >= 2:
            return parts[ : index - 1 ], parts[ index - 1 : ]
    return parts, []


def _normalise_path( path ):
    return path.replace( '\\', '/' ) if path else path


def _is_encoded_dependency_folder( folder ):
    if not folder:
        return False
    if folder.startswith( _GIT_SSH_PREFIX ):
        return True
    return '@' in folder and '__' in folder


def _encoded_folder_tokens( folder ):
    """Extract identifying substrings from a cuppa download folder name."""
    tokens = set()
    if not folder:
        return tokens
    tokens.add( folder )
    if folder.startswith( _GIT_SSH_PREFIX ):
        tokens.add( folder[ len( _GIT_SSH_PREFIX ) : ] )
    for fragment in re.split( r'[@/_\\]+', folder ):
        if len( fragment ) >= _MIN_FORBIDDEN_TOKEN_LEN and fragment not in _ENCODED_FOLDER_NOISE:
            tokens.add( fragment )
    if '@' in folder:
        tokens.add( folder.split( '@', 1 )[ 0 ] )
        for branch in folder.split( '@' )[ 1 : ]:
            if len( branch ) >= _MIN_FORBIDDEN_TOKEN_LEN:
                tokens.add( branch )
    if '__' in folder:
        left, right = folder.split( '__', 1 )
        tokens.add( left )
        tokens.add( right )
    return tokens


def _split_download_relative( path ):
    """Return ``(encoded_folder, remainder)`` when ``path`` is under a download tree."""
    normalised = _normalise_path( path )
    for marker in _DOWNLOAD_MARKERS:
        index = normalised.find( marker )
        if index < 0:
            continue
        rel = normalised[ index + len( marker ) : ]
        if not rel:
            return None
        parts = [ part for part in rel.split( '/' ) if part ]
        if not parts:
            return None
        folder = parts[ 0 ]
        if not _is_encoded_dependency_folder( folder ):
            continue
        remainder = '/'.join( parts[ 1 : ] )
        return folder, remainder
    match = _ENCODED_FOLDER_RE.search( normalised )
    if match:
        folder = match.group( 1 )
        tail = normalised[ match.end() : ].lstrip( '/' )
        return folder, tail
    return None


def _metadata_forbidden_tokens( metadata ):
    tokens = set()
    for key in (
        'sconstruct_dir',
        'cxx_profiles_report_root',
        'report_uri',
        'report_project',
        'report_branch',
        'report_revision',
    ):
        value = metadata.get( key ) or ''
        if not value:
            continue
        tokens.add( value )
        if key in ( 'sconstruct_dir', 'cxx_profiles_report_root' ):
            tokens.add( os.path.basename( os.path.normpath( value ) ) )
        if key == 'report_uri' and '://' in value:
            parsed = urlparse( value )
            if parsed.hostname:
                tokens.add( parsed.hostname )
            if parsed.path:
                for fragment in parsed.path.split( '/' ):
                    if len( fragment ) >= _MIN_FORBIDDEN_TOKEN_LEN:
                        tokens.add( fragment )
    return tokens


def _path_forbidden_tokens( path, metadata ):
    tokens = set()
    if not path:
        return tokens
    normalised = _normalise_path( path )
    if normalised.startswith( '_build/' ):
        return tokens

    sconstruct = metadata.get( 'sconstruct_dir' ) or ''
    project_relative = None
    if sconstruct:
        try:
            rel = os.path.relpath( path, sconstruct )
            if not rel.startswith( '..' ):
                project_relative = _normalise_path( rel )
        except ValueError:
            pass

    if project_relative is not None:
        tokens.add( project_relative )
        segment_source = project_relative
    else:
        tokens.add( normalised )
        segment_source = normalised

    download = _split_download_relative( segment_source )
    if download is None and project_relative is None:
        download = _split_download_relative( normalised )
    if download:
        folder, _remainder = download
        tokens.update( _encoded_folder_tokens( folder ) )

    for part in segment_source.split( '/' ):
        if not part or part.startswith( '_' ):
            continue
        base, _ext = _split_extension( part )
        if base in PASSTHROUGH_SEGMENTS or base == 'sconscript':
            continue
        if len( base ) >= _MIN_FORBIDDEN_TOKEN_LEN:
            tokens.add( base )
        for fragment in base.split( '_' ):
            if fragment in PASSTHROUGH_SEGMENTS:
                continue
            if len( fragment ) >= _MIN_FORBIDDEN_TOKEN_LEN:
                tokens.add( fragment )
    return tokens


def _iter_path_strings( node ):
    if isinstance( node, dict ):
        for key, value in node.items():
            if key == 'path' and isinstance( value, str ):
                yield value
            else:
                yield from _iter_path_strings( value )
    elif isinstance( node, list ):
        for item in node:
            yield from _iter_path_strings( item )


def _iter_scope_strings( node ):
    if isinstance( node, dict ):
        value = node.get( 'sconscript' )
        if isinstance( value, str ):
            yield value
        for child in node.values():
            yield from _iter_scope_strings( child )
    elif isinstance( node, list ):
        for item in node:
            yield from _iter_scope_strings( item )


def collect_forbidden_tokens( payload ):
    """Build the set of identifying substrings that must not appear in shared output."""
    metadata = payload.get( 'metadata' ) or {}
    if metadata_is_anonymised( metadata ):
        return set()
    forbidden = _metadata_forbidden_tokens( metadata )
    for path in _iter_path_strings( payload ):
        forbidden.update( _path_forbidden_tokens( path, metadata ) )
    for scope_string in _iter_scope_strings( payload.get( 'report' ) or {} ):
        forbidden.update( _path_forbidden_tokens( scope_string, metadata ) )
    for row in payload.get( 'locations' ) or []:
        if isinstance( row, dict ):
            for key in ( 'sconscript', 'path' ):
                value = row.get( key )
                if isinstance( value, str ):
                    forbidden.update( _path_forbidden_tokens( value, metadata ) )
    return {
        token
        for token in forbidden
        if token
        and len( token ) >= _MIN_FORBIDDEN_TOKEN_LEN
        and token not in PASSTHROUGH_SEGMENTS
    }


def _iter_string_values( node ):
    if isinstance( node, dict ):
        for value in node.values():
            yield from _iter_string_values( value )
    elif isinstance( node, list ):
        for item in node:
            yield from _iter_string_values( item )
    elif isinstance( node, str ):
        yield node


def verify_anonymised_output( payload, forbidden_tokens ):
    """Raise ``ValueError`` when any input-derived forbidden token survives anonymisation."""
    check_payload = copy.deepcopy( payload )
    check_payload.pop( 'context', None )
    metadata = check_payload.get( 'metadata' ) or {}
    for key in (
        'sconstruct_dir',
        'cxx_profiles_report_root',
        'report_uri',
        'report_branch',
        'report_revision',
    ):
        metadata.pop( key, None )
    serialized = '\n'.join( _iter_string_values( check_payload ) )
    leaks = [
        token
        for token in sorted( forbidden_tokens, key=len, reverse=True )
        if _token_leaks( token, serialized )
    ]
    if leaks:
        sample = ', '.join( repr( token ) for token in leaks[ :8 ] )
        extra = '' if len( leaks ) <= 8 else ' (and {} more)'.format( len( leaks ) - 8 )
        raise ValueError(
            'Anonymised output still contains input-derived token(s): {}{}'.format(
                sample,
                extra,
            ),
        )


def _strip_structural_substrings( text ):
    return text.replace( 'cxx-profiles--', '' )


def _token_leaks( token, serialized ):
    """Return whether ``token`` appears as an identity leak in serialized JSON values."""
    if not token or token in PASSTHROUGH_SEGMENTS:
        return False
    if token.startswith( './' ) or '/' in token:
        return token in serialized
    checked = _strip_structural_substrings( serialized )
    if re.search(
        r'(?<![\w]){}(?![\w])'.format( re.escape( token ) ),
        checked,
    ):
        return True
    for separator in ( '/', '_', '-', '.', '@', ':' ):
        if '{}{}{}'.format( separator, token, separator ) in checked:
            return True
        if checked.endswith( '{}{}'.format( separator, token ) ):
            return True
        if checked.startswith( '{}{}'.format( token, separator ) ):
            if token == PROJECT_ROOT and separator == '/':
                return False
            return True
    return False


def forbidden_identity_patterns( metadata ):
    """Return regex fragments that must not appear in shared JSON (metadata only)."""
    return [
        re.escape( token )
        for token in sorted(
            _metadata_forbidden_tokens( metadata ),
            key=len,
            reverse=True,
        )
        if len( token ) >= _MIN_FORBIDDEN_TOKEN_LEN
    ]


class PathAnonymiser( object ):
    """Deterministic path rewriter for Profiles report JSON."""

    def __init__(
        self,
        metadata,
        thematic_names=None,
        mapping=None,
        project_slug=None,
        forbidden=None,
    ):
        self.metadata = metadata or {}
        self.names = thematic_names or load_thematic_names()
        self.mapping = mapping if mapping is not None else None
        self.sconstruct_dir = os.path.abspath(
            self.metadata.get( 'sconstruct_dir' ) or ANON_PLACEHOLDER_ROOT,
        )
        self.report_root = os.path.abspath(
            self.metadata.get( 'cxx_profiles_report_root' ) or self.sconstruct_dir,
        )
        self._forbidden = set( forbidden or () )
        self._dep_slugs = {}
        self._used_dep_slugs = set()
        self._used_stems = set()
        self._stem_cache = {}
        self._cache = {}
        self._used_paths = set()
        self.project_slug = project_slug or self._project_slug()

    def _project_slug( self ):
        project = self.metadata.get( 'report_project' ) or os.path.basename(
            self.sconstruct_dir.rstrip( os.sep ),
        )
        if not project or project == os.path.basename( ANON_PLACEHOLDER_ROOT ):
            return _pick_unique(
                'project',
                self.names[ 'project_slugs' ],
                set(),
                self._forbidden,
            )
        return _pick_unique(
            project,
            self.names[ 'project_slugs' ],
            set(),
            self._forbidden,
        )

    def _dep_slug( self, folder_key ):
        if folder_key not in self._dep_slugs:
            self._dep_slugs[ folder_key ] = _pick_unique(
                folder_key,
                self.names[ 'dependency_slugs' ],
                self._used_dep_slugs,
                self._forbidden,
            )
        return self._dep_slugs[ folder_key ]

    def _thematic_stem( self, stem ):
        if stem in self._stem_cache:
            return self._stem_cache[ stem ]
        if not stem or stem in PASSTHROUGH_SEGMENTS:
            result = stem
        elif stem.isdigit():
            result = stem
        elif '_' in stem:
            compounds = self.names.get( 'path_compounds' ) or []
            if compounds:
                available = [
                    name
                    for name in compounds
                    if name not in self._used_stems
                    and _thematic_name_is_safe( name, self._forbidden )
                ]
                if available:
                    result = _pick_unique(
                        stem,
                        compounds,
                        self._used_stems,
                        self._forbidden,
                    )
                else:
                    result = '_'.join(
                        self._thematic_stem( part ) for part in stem.split( '_' )
                    )
            else:
                result = '_'.join(
                    self._thematic_stem( part ) for part in stem.split( '_' )
                )
        else:
            result = _pick_unique(
                stem,
                self.names[ 'path_names' ],
                self._used_stems,
                self._forbidden,
            )
        self._stem_cache[ stem ] = result
        return result

    def _anonymise_tail( self, rel ):
        parts = [ part for part in _normalise_path( rel ).split( '/' ) if part ]
        rewritten = []
        for part in parts:
            base, ext = _split_extension( part )
            new_base = self._thematic_stem( base )
            rewritten.append( '{}{}'.format( new_base, ext ) )
        return '/'.join( rewritten )

    def anonymise_sconscript( self, sconscript ):
        if not sconscript:
            return sconscript
        raw = sconscript.lstrip( './' )
        parts = [ part for part in raw.split( '/' ) if part ]
        if not parts:
            return './{}/sconscript'.format( self.project_slug )
        parts[ 0 ] = self.project_slug
        for index in range( 1, len( parts ) - 1 ):
            parts[ index ] = self._thematic_stem( parts[ index ] )
        return './{}'.format( '/'.join( parts ) )

    def anonymise_variant_dir( self, variant_dir ):
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
            if part in PASSTHROUGH_SEGMENTS:
                new_prefix.append( part )
            else:
                new_prefix.append( self._thematic_stem( part ) )
        if tail:
            return '/'.join( new_prefix + tail )
        return '/'.join( new_prefix )

    def _project_relative( self, path ):
        for root in ( self.report_root, self.sconstruct_dir ):
            try:
                rel = os.path.relpath( path, root )
            except ValueError:
                continue
            if not rel.startswith( '..' ):
                return _normalise_path( rel )
        return None

    def _disambiguate( self, candidate ):
        if candidate not in self._used_paths:
            self._used_paths.add( candidate )
            return candidate
        directory, name = os.path.split( candidate )
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

    def anonymise_path( self, path ):
        if not path:
            return path
        if path in self._cache:
            return self._cache[ path ]

        download = _split_download_relative( path )
        if download is not None:
            folder_key, remainder = download
            dep_slug = self._dep_slug( folder_key )
            tail = self._anonymise_tail( remainder ) if remainder else ''
            if tail:
                result = '{}/{}/{}'.format( DEPS_ROOT, dep_slug, tail )
            else:
                result = '{}/{}'.format( DEPS_ROOT, dep_slug )
        else:
            project_rel = self._project_relative( path ) if os.path.isabs( path ) else _normalise_path( path )
            if project_rel is None:
                project_rel = _normalise_path( path )
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
                    parts[ index ] = '{}{}'.format( self._thematic_stem( base ), ext )
                result = '/'.join( parts )
            else:
                tail = self._anonymise_tail( project_rel )
                result = '{}/{}'.format( PROJECT_ROOT, tail ) if tail else PROJECT_ROOT

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
    metadata[ 'anonymised' ] = True
    metadata[ 'anonymisation_version' ] = ANONYMISATION_VERSION
    metadata.pop( 'anonymized', None )
    metadata.pop( 'anonymization_version', None )
    return metadata


def _scrub_location_row( row, path_anonymiser ):
    row[ 'sconscript' ] = path_anonymiser.anonymise_sconscript( row.get( 'sconscript', '' ) )
    row[ 'variant_dir' ] = path_anonymiser.anonymise_variant_dir( row.get( 'variant_dir', '' ) )
    row[ 'path' ] = path_anonymiser.anonymise_path( row.get( 'path', '' ) )
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


def _anonymise_scope_summary( text, path_anonymiser ):
    if not text:
        return text
    if ' / ' in text:
        sconscript, suffix = text.split( ' / ', 1 )
        return '{} / {}'.format(
            path_anonymiser.anonymise_sconscript( sconscript.strip() ),
            suffix,
        )
    return path_anonymiser.anonymise_sconscript( text )


def _scrub_scope_summaries( entries, path_anonymiser ):
    for entry in entries or []:
        if isinstance( entry, dict ) and 'scope' in entry:
            entry[ 'scope' ] = _anonymise_scope_summary(
                entry.get( 'scope', '' ),
                path_anonymiser,
            )


def _scrub_violation_key( key, path_anonymiser ):
    if not isinstance( key, ( list, tuple ) ) or len( key ) < 2:
        return key
    scrubbed = list( key )
    scrubbed[ 0 ] = path_anonymiser.anonymise_sconscript( scrubbed[ 0 ] )
    if len( scrubbed ) > 1 and isinstance( scrubbed[ 1 ], str ):
        if not _is_anonymised_path( scrubbed[ 1 ] ):
            scrubbed[ 1 ] = path_anonymiser.anonymise_path( scrubbed[ 1 ] )
    return scrubbed


def _scrub_violation_ref_entries( entries, path_anonymiser ):
    for entry in entries or []:
        if isinstance( entry, dict ) and 'key' in entry:
            entry[ 'key' ] = _scrub_violation_key( entry[ 'key' ], path_anonymiser )


def _scrub_identity_fields( node, path_anonymiser ):
    if not isinstance( node, dict ):
        return node
    if 'violation_identity_keys' in node:
        node[ 'violation_identity_keys' ] = [
            _scrub_violation_key( key, path_anonymiser )
            for key in node.get( 'violation_identity_keys', [] )
        ]
    _scrub_violation_ref_entries( node.get( 'violation_refs' ), path_anonymiser )
    return node


def _scrub_variant_counts( variants, path_anonymiser ):
    for variant in variants or []:
        _scrub_identity_fields( variant, path_anonymiser )
        for file_entry in variant.get( 'files', [] ):
            _scrub_file_entry( file_entry, path_anonymiser )


def _scrub_file_entry( file_entry, path_anonymiser ):
    file_entry[ 'path' ] = path_anonymiser.anonymise_path( file_entry.get( 'path', '' ) )
    for location in file_entry.get( 'locations', [] ):
        location.pop( 'message', None )
    _scrub_identity_fields( file_entry, path_anonymiser )
    _scrub_scope_summaries( file_entry.get( 'scopes' ), path_anonymiser )
    _scrub_variant_counts( file_entry.get( 'variant_counts' ), path_anonymiser )
    for rule in file_entry.get( 'rules', [] ):
        _scrub_identity_fields( rule, path_anonymiser )
        _scrub_variant_counts( rule.get( 'variant_counts' ), path_anonymiser )
        for nested in rule.get( 'files', [] ):
            _scrub_file_entry( nested, path_anonymiser )
    return file_entry


def _scrub_rule( rule, path_anonymiser ):
    _scrub_identity_fields( rule, path_anonymiser )
    _scrub_scope_summaries( rule.get( 'scopes' ), path_anonymiser )
    _scrub_variant_counts( rule.get( 'variant_counts' ), path_anonymiser )
    for file_entry in rule.get( 'files', [] ):
        _scrub_file_entry( file_entry, path_anonymiser )
    return rule


def _scrub_profile( profile, path_anonymiser ):
    for rule in profile.get( 'rules', [] ):
        _scrub_rule( rule, path_anonymiser )
    for file_entry in profile.get( 'files', [] ):
        _scrub_file_entry( file_entry, path_anonymiser )
    return profile


def _scrub_scope( scope, path_anonymiser ):
    scope[ 'sconscript' ] = path_anonymiser.anonymise_sconscript( scope.get( 'sconscript', '' ) )
    scope[ 'variant_dir' ] = path_anonymiser.anonymise_variant_dir( scope.get( 'variant_dir', '' ) )
    for profile in scope.get( 'profiles', [] ):
        _scrub_profile( profile, path_anonymiser )
    from cuppa.cpp.profiles_report.inventory import _scope_report_stem

    scope[ 'report_stem' ] = _scope_report_stem( scope )
    return scope


def _is_anonymised_path( path ):
    normalised = _normalise_path( path )
    if not normalised:
        return False
    return (
        normalised.startswith( '{}/'.format( DEPS_ROOT ) )
        or normalised == DEPS_ROOT
        or normalised.startswith( '{}/'.format( PROJECT_ROOT ) )
        or normalised == PROJECT_ROOT
        or normalised.startswith( '_build/' )
        or normalised == '_build'
    )


def _looks_like_violation_key( value ):
    return (
        isinstance( value, ( list, tuple ) )
        and len( value ) >= 2
        and isinstance( value[ 0 ], str )
        and isinstance( value[ 1 ], str )
        and (
            value[ 0 ].startswith( './' )
            or value[ 1 ].startswith( '/' )
            or '/_cuppa/_download/' in value[ 1 ]
            or value[ 1 ].startswith( '_cuppa/_download/' )
        )
    )


def _strip_html_enrichment( node ):
    """Remove HTML-only roll-up fields that may embed stale absolute paths."""
    if isinstance( node, dict ):
        for key in list( node.keys() ):
            if key in _HTML_ENRICHMENT_KEYS:
                del node[ key ]
            else:
                _strip_html_enrichment( node[ key ] )
    elif isinstance( node, list ):
        for item in node:
            _strip_html_enrichment( item )


def _looks_like_sconscript_path( text ):
    normalised = ( text or '' ).strip()
    if not normalised.endswith( 'sconscript' ) or normalised == 'sconscript':
        return False
    return normalised.startswith( './' ) or '/' in normalised


def _scrub_text_field( key, value, path_anonymiser ):
    if not isinstance( value, str ) or not value:
        return value
    if key in _HTML_ENRICHMENT_KEYS:
        return None
    if key == 'sconscript':
        return path_anonymiser.anonymise_sconscript( value )
    if key == 'scope':
        return _anonymise_scope_summary( value, path_anonymiser )
    if key == 'variant_dir':
        return path_anonymiser.anonymise_variant_dir( value )
    if _looks_like_sconscript_path( value ):
        prefixed = value if value.startswith( './' ) else './{}'.format( value )
        return path_anonymiser.anonymise_sconscript( prefixed )
    return value


def _scrub_path_strings_recursive( node, path_anonymiser ):
    """Catch-all pass for path, scope, and sconscript-bearing string fields."""
    if isinstance( node, dict ):
        if 'path' in node and isinstance( node[ 'path' ], str ):
            if not _is_anonymised_path( node[ 'path' ] ):
                node[ 'path' ] = path_anonymiser.anonymise_path( node[ 'path' ] )
        if 'violation_identity_keys' in node:
            node[ 'violation_identity_keys' ] = [
                _scrub_violation_key( key, path_anonymiser )
                for key in node.get( 'violation_identity_keys', [] )
            ]
        _scrub_violation_ref_entries( node.get( 'violation_refs' ), path_anonymiser )
        for key, value in list( node.items() ):
            if key in ( 'violation_identity_keys', 'violation_refs' ):
                continue
            if isinstance( value, str ):
                scrubbed = _scrub_text_field( key, value, path_anonymiser )
                if scrubbed is None:
                    del node[ key ]
                elif scrubbed != value:
                    node[ key ] = scrubbed
            else:
                _scrub_path_strings_recursive( value, path_anonymiser )
    elif isinstance( node, list ):
        for index, item in enumerate( node ):
            if _looks_like_violation_key( item ):
                node[ index ] = _scrub_violation_key( item, path_anonymiser )
            elif isinstance( item, str ):
                scrubbed = _scrub_text_field( '', item, path_anonymiser )
                if scrubbed is not None and scrubbed != item:
                    node[ index ] = scrubbed
            else:
                _scrub_path_strings_recursive( item, path_anonymiser )


def _scrub_model( model, path_anonymiser ):
    for scope in model.get( 'scopes', [] ):
        _scrub_scope( scope, path_anonymiser )
    rollup = model.get( 'rollup', {} )
    for rule in rollup.get( 'rules', [] ):
        _scrub_rule( rule, path_anonymiser )
    for file_entry in rollup.get( 'files', [] ):
        _scrub_file_entry( file_entry, path_anonymiser )
    return model


def anonymise_report_payload( payload, *, thematic_names=None, mapping=None, force=False ):
    """Return a deep-copied anonymised report payload."""
    if not isinstance( payload, dict ):
        raise ValueError( 'Profiles report payload must be an object' )
    if metadata_is_anonymised( payload.get( 'metadata', {} ) ) and not force:
        raise ValueError(
            'Input already has metadata.anonymised; pass force=True to re-anonymise',
        )

    forbidden_tokens = collect_forbidden_tokens( payload )
    result = copy.deepcopy( payload )
    metadata = result.setdefault( 'metadata', {} )
    path_anonymiser = PathAnonymiser(
        metadata,
        thematic_names=thematic_names,
        mapping=mapping,
        forbidden=forbidden_tokens,
    )

    model = result.get( 'report' )
    if isinstance( model, dict ):
        _scrub_model( model, path_anonymiser )
        _scrub_path_strings_recursive( model, path_anonymiser )
        _strip_html_enrichment( model )

    locations = result.get( 'locations' ) or []
    if locations:
        result[ 'locations' ] = [
            _scrub_location_row( row, path_anonymiser )
            for row in locations
        ]
        _scrub_path_strings_recursive( result[ 'locations' ], path_anonymiser )

    incomplete = metadata.get( 'incomplete_scopes' ) or []
    if incomplete:
        metadata[ 'incomplete_scopes' ] = [
            path_anonymiser.anonymise_sconscript( item )
            for item in incomplete
        ]

    _scrub_metadata( metadata )
    verify_anonymised_output( result, forbidden_tokens )
    return result


def anonymise_report_document( data, *, thematic_names=None, mapping=None, force=False ):
    """Anonymize a loaded JSON document (schema envelope or legacy model)."""
    from cuppa.cpp.profiles_report.report_json import unwrap_report_payload

    model, metadata, extras = unwrap_report_payload( data )
    if 'report' in data and 'schema_version' in data:
        return anonymise_report_payload(
            data,
            thematic_names=thematic_names,
            mapping=mapping,
            force=force,
        )

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
    return anonymise_report_payload(
        payload,
        thematic_names=thematic_names,
        mapping=mapping,
        force=force,
    )


def anonymise_stem( stem, dictionary, passthrough=None ):
    """Rewrite one path stem using the thematic ``path_names`` pool (stable pick)."""
    names = dictionary if isinstance( dictionary.get( 'path_names' ), list ) else load_thematic_names()
    used = set()
    anonymiser = PathAnonymiser( {}, thematic_names=names )
    anonymiser._used_stems = used
    return anonymiser._thematic_stem( stem )


# US spelling compatibility (accepted on read; not advertised in CLI or docs).
ANONYMIZATION_VERSION = ANONYMISATION_VERSION
PathAnonymizer = PathAnonymiser
anonymize_report_payload = anonymise_report_payload
anonymize_report_document = anonymise_report_document
anonymize_stem = anonymise_stem
verify_anonymized_output = verify_anonymised_output
