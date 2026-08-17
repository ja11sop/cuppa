#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   Profiles violation inventory — scope, dedupe, replay, report model
#-------------------------------------------------------------------------------

import re

from cuppa.cpp.profiles_report.build_catalog import build_key_from_scope
from cuppa.cpp.profiles_report.parse import parse_profiles_diagnostic
from cuppa.cpp.profiles_report.types import (
    ProfilesLocation,
    ProfilesScope,
    unscoped_profiles_scope,
)
from cuppa.utility.preprocess import AnsiEscape

_PROGRESS_LINE_RE = re.compile( r'^Progress\(\s*(.+)\s*\)\s*$' )


def profiles_scope_from_construction_env( env ):
    """Build a ``ProfilesScope`` from a sconscript construction ``env``."""
    from cuppa.progress import NotifyProgress

    scope = NotifyProgress.scope_from_env( env )
    if scope is None:
        return unscoped_profiles_scope()

    sconscript, variant_dir = scope
    toolchain = NotifyProgress.toolchain_name( env )
    if not toolchain:
        return unscoped_profiles_scope()

    _toolchain_from_path, variant_label = parse_variant_scope_fields( variant_dir )
    return ProfilesScope(
        sconscript=sconscript,
        variant_dir=variant_dir,
        toolchain=toolchain,
        variant_label=variant_label,
    )


def parse_variant_scope_fields( variant_dir ):
    """Derive toolchain and variant label from a cuppa variant directory path.

    Variant dirs end with ``<toolchain>/<variant>/<arch>/<abi>`` under ``_build/…`` —
    see ``cuppa.core.build_layout.tool_variant_dir``. Root ``sconscript`` layouts omit a
    project path segment between ``_build/`` and the toolchain folder.
    """
    parts = variant_dir.strip( '/' ).split( '/' )
    # ``_build/<optional-sconscript-path>/<toolchain>/<variant>/<arch>/<abi>`` — root
    # sconscript has no middle segment (five parts); nested sconscripts have six or more.
    if len( parts ) < 5 or parts[ 0 ] != '_build':
        return '_unknown', '_unknown'
    return parts[ -4 ], parts[ -3 ]


def parse_progress_line( line ):
    """Parse one ``Progress( … )`` console line, or return ``None`` if it does not match."""
    match = _PROGRESS_LINE_RE.match( line.rstrip( '\r\n' ) )
    if not match:
        return None

    inner = match.group( 1 ).strip()
    if inner == 'SconstructBegin':
        return 'sconstruct_begin', None, None
    if inner == 'SconstructEnd':
        return 'sconstruct_end', None, None
    if inner.startswith( 'Begin sconscript: [' ) and inner.endswith( ']' ):
        return 'begin', inner[ len( 'Begin sconscript: [' ): -1 ], None
    if inner.startswith( 'End sconscript: [' ) and inner.endswith( ']' ):
        return 'end', inner[ len( 'End sconscript: [' ): -1 ], None
    if inner.startswith( 'Starting variant: [' ) and inner.endswith( ']' ):
        return 'started', None, inner[ len( 'Starting variant: [' ): -1 ]
    if inner.startswith( 'Finished variant: [' ) and inner.endswith( ']' ):
        return 'finished', None, inner[ len( 'Finished variant: [' ): -1 ]
    return None


class ProfilesScopeStack:
    """Track open Progress scopes while replaying a capture file.

    Supports interleaved ``--parallel`` output: nested sconscripts, multiple
    active variants, and resolution by most-recent ``Starting variant`` among
    those still open.
    """

    def __init__( self ):
        self._sconscript_stack = []
        self._active_variants = set()
        self._start_order = []

    def apply_progress( self, event, sconscript, variant_dir ):
        if event == 'begin':
            self._sconscript_stack.append( sconscript )
        elif event == 'started':
            current_sconscript = self._current_sconscript()
            if current_sconscript:
                scope_pair = ( current_sconscript, variant_dir )
                self._active_variants.add( scope_pair )
                self._start_order.append( scope_pair )
        elif event == 'finished':
            for scope_pair in list( self._active_variants ):
                if scope_pair[ 1 ] == variant_dir:
                    self._active_variants.discard( scope_pair )
        elif event == 'end':
            while self._sconscript_stack and self._sconscript_stack[ -1 ] == sconscript:
                self._sconscript_stack.pop()
            self._active_variants = {
                scope_pair
                for scope_pair in self._active_variants
                if scope_pair[ 0 ] != sconscript
            }
            self._prune_start_order()
        elif event == 'sconstruct_end':
            self._sconscript_stack = []
            self._active_variants = set()
            self._start_order = []

    def _current_sconscript( self ):
        return self._sconscript_stack[ -1 ] if self._sconscript_stack else None

    def _prune_start_order( self ):
        self._start_order = [
            scope_pair
            for scope_pair in self._start_order
            if scope_pair in self._active_variants
        ]

    def current_scope( self ):
        if not self._active_variants:
            return unscoped_profiles_scope()

        if len( self._active_variants ) == 1:
            sconscript, variant_dir = next( iter( self._active_variants ) )
        else:
            sconscript = None
            variant_dir = None
            for scope_pair in reversed( self._start_order ):
                if scope_pair in self._active_variants:
                    sconscript, variant_dir = scope_pair
                    break
            if sconscript is None:
                return unscoped_profiles_scope()

        toolchain, variant_label = parse_variant_scope_fields( variant_dir )
        return ProfilesScope(
            sconscript=sconscript,
            variant_dir=variant_dir,
            toolchain=toolchain,
            variant_label=variant_label,
        )


def _strip_capture_line( line ):
    """Remove ANSI colour sequences from a saved capture line."""
    return AnsiEscape.strip( line )


def replay_profiles_capture( lines ):
    """Replay saved build output lines into a scoped ``ProfilesInventory``."""
    inventory = ProfilesInventory()
    stack = ProfilesScopeStack()
    unscoped_diagnostics = 0
    seen_scoped_lines = set()

    for line in lines:
        capture_line = _strip_capture_line( line )
        progress = parse_progress_line( capture_line )
        if progress is not None:
            stack.apply_progress( *progress )
            continue

        diagnostic = parse_profiles_diagnostic( capture_line, from_capture=True )
        if diagnostic is None:
            continue

        line_key = capture_line.rstrip( '\r\n' )
        scope = stack.current_scope()
        if scope.sconscript == '_unscoped':
            if line_key in seen_scoped_lines:
                continue
            unscoped_diagnostics += 1
        else:
            seen_scoped_lines.add( line_key )

        inventory.record( scope, diagnostic )

    return inventory, unscoped_diagnostics


def format_capture_summary( inventory, unscoped_diagnostics=0 ):
    """Return a human-readable summary of a replayed capture."""
    lines = [
        'total_references: {}'.format( inventory.total_references() ),
        'unique_locations: {}'.format( inventory.unique_locations() ),
    ]
    if unscoped_diagnostics:
        lines.append( 'unscoped_diagnostics: {}'.format( unscoped_diagnostics ) )

    model = inventory.as_report_model()
    for scope in model[ 'scopes' ]:
        lines.append( '' )
        lines.append(
            'scope: {}  {}'.format( scope[ 'sconscript' ], scope[ 'variant_dir' ] )
        )
        lines.append(
            '  toolchain: {}  variant: {}'.format(
                scope[ 'toolchain' ],
                scope[ 'variant_label' ],
            )
        )
        for profile in scope[ 'profiles' ]:
            lines.append( '  profile: {}'.format( profile[ 'profile' ] ) )
            for rule in sorted(
                profile[ 'rules' ],
                key=lambda entry: ( -entry[ 'total_references' ], entry[ 'rule_id' ] ),
            ):
                lines.append(
                    '    {}  {} refs  {} files'.format(
                        rule[ 'rule_id' ],
                        rule[ 'total_references' ],
                        rule[ 'unique_files' ],
                    )
                )

    return '\n'.join( lines )


def location_dedupe_key( scope, diagnostic ):
    """Return the scope-aware dedupe key for one parsed diagnostic."""
    return (
        scope.sconscript,
        scope.variant_dir,
        diagnostic.path,
        diagnostic.line,
        diagnostic.column,
        diagnostic.profile,
        diagnostic.normalised_message,
    )


def session_union_violation_key( location ):
    """Cross-variant identity for one rule violation (session union denominator)."""
    return (
        location.scope.sconscript,
        location.path,
        location.line,
        location.column,
        location.profile,
        location.rule_id,
    )


def _union_violation_count( locations ):
    return len( { session_union_violation_key( loc ) for loc in locations } )


def _union_reference_total( locations ):
    groups = {}
    for location in locations:
        key = session_union_violation_key( location )
        groups.setdefault( key, [] ).append( location.reference_count )
    return sum( max( counts ) for counts in groups.values() )


def _union_groups_for_rule( locations ):
    groups = {}
    for location in locations:
        rule_key = ( location.profile, location.rule_id )
        union_key = session_union_violation_key( location )
        rule_groups = groups.setdefault( rule_key, {} )
        rule_groups.setdefault( union_key, [] ).append( location.reference_count )
    return groups


def _union_rule_metrics( rule_groups ):
    if not rule_groups:
        return 0, 0
    return (
        len( rule_groups ),
        sum( max( counts ) for counts in rule_groups.values() ),
    )


def _sort_rules( rules ):
    return sorted(
        rules,
        key=lambda entry: ( -entry[ 'total_references' ], entry[ 'rule_id' ] ),
    )


def _sort_files( files ):
    return sorted(
        files,
        key=lambda entry: ( -entry[ 'total_references' ], entry[ 'path' ] ),
    )


def _sort_rule_files( files ):
    return sorted(
        files,
        key=lambda entry: (
            -entry.get( 'unique_line_count', 0 ),
            entry.get( 'path', '' ),
        ),
    )


def _sort_file_rules( rules ):
    return sorted(
        rules,
        key=lambda entry: ( -entry[ 'total_references' ], entry[ 'rule_id' ] ),
    )


def _violation_key_to_json( key ):
    return list( key )


def _record_violation_ref( violation_refs, violation_ref_peaks, union_key, reference_count ):
    """Accumulate build-sum and per-row-peak refs for one violation identity."""
    violation_refs[ union_key ] = (
        violation_refs.get( union_key, 0 ) + reference_count
    )
    violation_ref_peaks[ union_key ] = max(
        violation_ref_peaks.get( union_key, 0 ),
        reference_count,
    )


def _empty_variant_bucket():
    return {
        'violation_lines': set(),
        'violation_refs': {},
        'violation_ref_peaks': {},
        'references': 0,
        'files': {},
        'rules': {},
    }


def _variant_reference_metrics( variant_data ):
    """Return union refs, peak refs, and raw compile refs for one build bucket."""
    lines = variant_data.get( 'violation_lines', set() )
    ref_sums = variant_data.get( 'violation_refs', {} )
    ref_peaks = variant_data.get( 'violation_ref_peaks', {} )
    union_refs = sum(
        ref_peaks.get( key, ref_sums.get( key, 0 ) )
        for key in lines
    )
    peak_refs = sum( ref_sums.get( key, 0 ) for key in lines )
    raw_refs = variant_data.get( 'references', 0 )
    return union_refs, peak_refs, raw_refs


def _accumulate_location_variants(
    location,
    rule_entry,
    session_file_entry=None,
    profile_file_entry=None,
):
    """Track per-build violation keys and reference metrics for roll-up tables."""
    union_key = session_union_violation_key( location )
    build_key = build_key_from_scope( location.scope )
    variant_entry = rule_entry.setdefault( 'variants', {} ).setdefault(
        build_key,
        _empty_variant_bucket(),
    )
    variant_entry[ 'violation_lines' ].add( union_key )
    _record_violation_ref(
        variant_entry[ 'violation_refs' ],
        variant_entry[ 'violation_ref_peaks' ],
        union_key,
        location.reference_count,
    )
    variant_entry[ 'references' ] += location.reference_count
    rule_file = variant_entry[ 'files' ].setdefault(
        location.path,
        { 'lines': set(), 'references': 0, 'violation_keys': set() },
    )
    rule_file[ 'lines' ].add( location.line )
    rule_file[ 'references' ] += location.reference_count
    rule_file[ 'violation_keys' ].add( union_key )

    if session_file_entry is not None:
        file_variant = session_file_entry.setdefault( 'variants', {} ).setdefault(
            build_key,
            _empty_variant_bucket(),
        )
        file_variant[ 'violation_lines' ].add( union_key )
        _record_violation_ref(
            file_variant[ 'violation_refs' ],
            file_variant[ 'violation_ref_peaks' ],
            union_key,
            location.reference_count,
        )
        file_variant[ 'references' ] += location.reference_count
        file_variant[ 'rules' ][ location.rule_id ] = (
            file_variant[ 'rules' ].get( location.rule_id, 0 )
            + location.reference_count
        )

    if profile_file_entry is not None:
        profile_variant = profile_file_entry.setdefault( 'variants', {} ).setdefault(
            build_key,
            _empty_variant_bucket(),
        )
        profile_variant[ 'violation_lines' ].add( union_key )
        _record_violation_ref(
            profile_variant[ 'violation_refs' ],
            profile_variant[ 'violation_ref_peaks' ],
            union_key,
            location.reference_count,
        )
        profile_variant[ 'references' ] += location.reference_count
        profile_variant[ 'rules' ][ location.rule_id ] = (
            profile_variant[ 'rules' ].get( location.rule_id, 0 )
            + location.reference_count
        )


def _serialise_violation_refs( violation_refs, violation_ref_peaks=None ):
    serialised = []
    for key, refs in sorted( violation_refs.items() ):
        entry = {
            'key': _violation_key_to_json( key ),
            'refs': refs,
        }
        if violation_ref_peaks is not None:
            entry[ 'row_peak' ] = violation_ref_peaks.get( key, refs )
        serialised.append( entry )
    return serialised


def _build_key_fields( build_key ):
    variant_label, variant_display_tail, toolchain = build_key
    return {
        'build_key': list( build_key ),
        'variant_label': variant_label,
        'variant_display_tail': variant_display_tail,
        'toolchain': toolchain,
    }


def _serialise_file_variant_counts( variants ):
    """Per-build inventory rule-type and reference counts for by-file roll-up rows."""
    result = []
    for build_key, data in sorted(
        variants.items(),
        key=lambda item: item[ 0 ],
    ):
        entry = _build_key_fields( build_key )
        union_refs, peak_refs, raw_refs = _variant_reference_metrics( data )
        entry.update(
            {
                'rule_ids': sorted( data.get( 'rules', {} ).keys() ),
                'unique_rule_count': len( data.get( 'rules', {} ) ),
                'unique_line_count': len( data.get( 'violation_lines', set() ) ),
                'total_references': raw_refs,
                'union_references': union_refs,
                'peak_references': peak_refs,
                'violation_identity_keys': [
                    _violation_key_to_json( key )
                    for key in sorted( data.get( 'violation_lines', set() ) )
                ],
                'violation_refs': _serialise_violation_refs(
                    data.get( 'violation_refs', {} ),
                    data.get( 'violation_ref_peaks' ),
                ),
            },
        )
        result.append( entry )
    return result


def _serialise_file_rule_variant_counts( variants, rule_id ):
    """Per-build violation and reference counts for one rule on one file roll-up row."""
    counts = []
    for build_key, data in sorted(
        variants.items(),
        key=lambda item: item[ 0 ],
    ):
        matching_keys = {
            key
            for key in data.get( 'violation_lines', set() )
            if key[ -1 ] == rule_id
        }
        if not matching_keys:
            continue
        rule_refs = {
            key: data.get( 'violation_refs', {} ).get( key, 0 )
            for key in matching_keys
        }
        rule_ref_peaks = {
            key: data.get( 'violation_ref_peaks', {} ).get(
                key,
                rule_refs.get( key, 0 ),
            )
            for key in matching_keys
        }
        union_refs = sum( rule_ref_peaks.get( key, rule_refs.get( key, 0 ) ) for key in matching_keys )
        peak_refs = sum( rule_refs.values() )
        entry = _build_key_fields( build_key )
        entry.update(
            {
                'unique_line_count': len( matching_keys ),
                'total_references': peak_refs,
                'union_references': union_refs,
                'peak_references': peak_refs,
                'violation_identity_keys': [
                    _violation_key_to_json( key )
                    for key in sorted( matching_keys )
                ],
                'violation_refs': _serialise_violation_refs(
                    rule_refs,
                    rule_ref_peaks,
                ),
            },
        )
        counts.append( entry )
    return counts


def _serialise_file_rules( rules, variants ):
    """Return sorted per-rule violation detail for one file roll-up row."""
    serialised = []
    for rule_id, rule_data in rules.items():
        variant_counts = _serialise_file_rule_variant_counts(
            variants,
            rule_id,
        )
        if variant_counts:
            metrics = variant_counts[ 0 ]
            union_refs = metrics.get(
                'union_references',
                metrics[ 'total_references' ],
            )
            peak_refs = metrics.get(
                'peak_references',
                metrics[ 'total_references' ],
            )
            build_refs = metrics[ 'total_references' ]
        else:
            union_refs = peak_refs = build_refs = rule_data[ 'total_references' ]
        serialised.append(
            {
                'rule_id': rule_id,
                'total_references': union_refs,
                'peak_references': peak_refs,
                'build_references': build_refs,
                'unique_line_count': len( rule_data[ 'lines' ] ),
                'sample_normalised_message': rule_data.get( 'sample_normalised_message' ),
                'variant_counts': variant_counts,
            },
        )
    serialised = _sort_file_rules( serialised )
    variant_rule_refs = []
    for build_key, data in sorted(
        variants.items(),
        key=lambda item: item[ 0 ],
    ):
        entry = _build_key_fields( build_key )
        entry[ 'rules' ] = dict( data.get( 'rules', {} ) )
        variant_rule_refs.append( entry )
    return serialised, variant_rule_refs


def _file_variant_counts_for_rule( variants, path ):
    """Per-build violation and reference counts for one file under a rule."""
    counts = []
    for build_key, data in sorted(
        variants.items(),
        key=lambda item: item[ 0 ],
    ):
        file_data = data.get( 'files', {} ).get( path )
        if file_data is None:
            continue
        entry = _build_key_fields( build_key )
        file_refs = {
            key: data.get( 'violation_refs', {} ).get( key, 0 )
            for key in file_data.get( 'violation_keys', set() )
        }
        file_ref_peaks = {
            key: data.get( 'violation_ref_peaks', {} ).get(
                key,
                file_refs.get( key, 0 ),
            )
            for key in file_data.get( 'violation_keys', set() )
        }
        union_refs = sum(
            file_ref_peaks.get( key, file_refs.get( key, 0 ) )
            for key in file_data.get( 'violation_keys', set() )
        )
        peak_refs = sum( file_refs.values() )
        entry.update(
            {
                'unique_line_count': len( file_data[ 'lines' ] ),
                'total_references': file_data[ 'references' ],
                'union_references': union_refs,
                'peak_references': peak_refs,
                'violation_identity_keys': [
                    _violation_key_to_json( key )
                    for key in sorted( file_data.get( 'violation_keys', set() ) )
                ],
                'violation_refs': _serialise_violation_refs(
                    file_refs,
                    file_ref_peaks,
                ),
            },
        )
        counts.append( entry )
    return counts


def _serialise_variant_counts( variants, include_files=False ):
    """Return sorted per-build inventory violation and reference counts for roll-up tables."""
    result = []
    for build_key, data in sorted(
        variants.items(),
        key=lambda item: item[ 0 ],
    ):
        union_refs, peak_refs, raw_refs = _variant_reference_metrics( data )
        entry = _build_key_fields( build_key )
        entry.update(
            {
                'unique_line_count': len( data[ 'violation_lines' ] ),
                'total_references': raw_refs,
                'union_references': union_refs,
                'peak_references': peak_refs,
                'violation_identity_keys': [
                    _violation_key_to_json( key )
                    for key in sorted( data[ 'violation_lines' ] )
                ],
                'violation_refs': _serialise_violation_refs(
                    data.get( 'violation_refs', {} ),
                    data.get( 'violation_ref_peaks' ),
                ),
            },
        )
        if include_files:
            files = []
            for path, file_data in data.get( 'files', {} ).items():
                files.append(
                    {
                        'path': path,
                        'unique_line_count': len( file_data[ 'lines' ] ),
                        'total_references': file_data[ 'references' ],
                    },
                )
            files = _sort_rule_files( files )
            entry[ 'file_count' ] = len( files )
            entry[ 'files' ] = files
        result.append( entry )
    return result


def _scope_report_stem( scope_entry ):
    """Filename stem for a per-scope HTML detail page."""
    raw = '--'.join(
        (
            scope_entry[ 'sconscript' ].strip( './' ).replace( '/', '--' ),
            scope_entry[ 'variant_label' ],
            scope_entry[ 'toolchain' ],
        ),
    )
    safe = ''.join(
        ch if ch.isalnum() or ch in '-_.' else '-'
        for ch in raw
    )
    while '--' in safe:
        safe = safe.replace( '--', '-' )
    return 'cxx-profiles--{}'.format( safe.strip( '-' ) )


def _build_session_rollup( locations ):
    """Cross-scope roll-up keyed without scope (union across variants where noted)."""
    locations = tuple( locations )
    rule_union_groups = _union_groups_for_rule( locations )
    rules = {}
    files = {}
    for location in locations:
        rule_key = ( location.profile, location.rule_id )
        union_key = session_union_violation_key( location )
        rule_entry = rules.setdefault(
            rule_key,
            {
                'profile': location.profile,
                'rule_id': location.rule_id,
                'total_references': 0,
                'violation_lines': set(),
                'unique_files': set(),
                'files': {},
                'variants': {},
                'scopes': {},
                'sample_normalised_message': None,
            },
        )
        if rule_entry[ 'sample_normalised_message' ] is None:
            rule_entry[ 'sample_normalised_message' ] = location.normalised_message
        rule_entry[ 'violation_lines' ].add( union_key )
        rule_entry[ 'unique_files' ].add( location.path )

        file_key = ( location.profile, location.path )
        file_entry = files.setdefault(
            file_key,
            {
                'profile': location.profile,
                'path': location.path,
                'total_references': 0,
                'lines': set(),
                'violation_identities': set(),
                'variants': {},
                'rules': {},
                'scopes': {},
            },
        )
        _accumulate_location_variants(
            location,
            rule_entry,
            session_file_entry=file_entry,
        )
        rule_file = rule_entry[ 'files' ].setdefault(
            location.path,
            { 'total_references': 0, 'lines': set() },
        )
        rule_file[ 'total_references' ] += location.reference_count
        rule_file[ 'lines' ].add( location.line )
        scope_key = '{} / {}'.format(
            location.scope.sconscript,
            location.scope.variant_label,
        )
        rule_entry[ 'scopes' ][ scope_key ] = (
            rule_entry[ 'scopes' ].get( scope_key, 0 ) + location.reference_count
        )

        file_entry[ 'violation_identities' ].add( union_key )
        file_entry[ 'lines' ].add( location.line )
        file_rule = file_entry[ 'rules' ].setdefault(
            location.rule_id,
            {
                'total_references': 0,
                'lines': set(),
                'sample_normalised_message': None,
            },
        )
        file_rule[ 'total_references' ] += location.reference_count
        file_rule[ 'lines' ].add( location.line )
        if file_rule[ 'sample_normalised_message' ] is None:
            file_rule[ 'sample_normalised_message' ] = location.normalised_message
        file_entry[ 'scopes' ][ scope_key ] = (
            file_entry[ 'scopes' ].get( scope_key, 0 ) + location.reference_count
        )

    rollup_rules = []
    for rule_key, entry in rules.items():
        union_groups = rule_union_groups.get( rule_key, {} )
        union_violations, union_references = _union_rule_metrics( union_groups )
        rule_files = []
        for path, file_data in entry[ 'files' ].items():
            rule_files.append(
                {
                    'path': path,
                    'total_references': file_data[ 'total_references' ],
                    'unique_line_count': len( file_data[ 'lines' ] ),
                    'variant_counts': _file_variant_counts_for_rule(
                        entry[ 'variants' ],
                        path,
                    ),
                },
            )
        rule_files = _sort_rule_files( rule_files )
        rollup_rules.append(
            {
                'profile': entry[ 'profile' ],
                'rule_id': entry[ 'rule_id' ],
                'total_references': union_references,
                'unique_line_count': union_violations,
                'unique_files': len( entry[ 'unique_files' ] ),
                'variant_counts': _serialise_variant_counts(
                    entry[ 'variants' ],
                    include_files=True,
                ),
                'sample_normalised_message': entry[ 'sample_normalised_message' ],
                'files': rule_files,
                'scopes': [
                    { 'scope': scope, 'references': count }
                    for scope, count in sorted( entry[ 'scopes' ].items() )
                ],
            },
        )

    rollup_files = []
    for entry in files.values():
        rules, variant_rule_refs = _serialise_file_rules(
            entry[ 'rules' ],
            entry[ 'variants' ],
        )
        file_union_groups = {}
        for location in locations:
            if location.profile != entry[ 'profile' ] or location.path != entry[ 'path' ]:
                continue
            union_key = session_union_violation_key( location )
            file_union_groups.setdefault( union_key, [] ).append(
                location.reference_count,
            )
        _, file_union_references = _union_rule_metrics( file_union_groups )
        rollup_files.append(
            {
                'profile': entry[ 'profile' ],
                'path': entry[ 'path' ],
                'total_references': file_union_references,
                'unique_line_count': len( entry[ 'violation_identities' ] ),
                'unique_rule_count': len( entry[ 'rules' ] ),
                'variant_counts': _serialise_file_variant_counts( entry[ 'variants' ] ),
                'variant_rule_refs': variant_rule_refs,
                'rules': rules,
                'scopes': [
                    { 'scope': scope, 'references': count }
                    for scope, count in sorted( entry[ 'scopes' ].items() )
                ],
            },
        )

    return {
        'rules': _sort_rules( rollup_rules ),
        'files': _sort_files( rollup_files ),
    }


class ProfilesInventory:
    """In-memory Profiles violation inventory with scope-aware dedupe."""

    def __init__( self ):
        self._locations = {}

    def record( self, scope, diagnostic ):
        """Record one parsed diagnostic, incrementing reference counts for duplicates."""
        key = location_dedupe_key( scope, diagnostic )
        existing = self._locations.get( key )
        if existing is not None:
            self._locations[ key ] = existing._replace(
                reference_count=existing.reference_count + 1,
            )
            return existing

        location = ProfilesLocation(
            scope=scope,
            path=diagnostic.path,
            line=diagnostic.line,
            column=diagnostic.column,
            profile=diagnostic.profile,
            normalised_message=diagnostic.normalised_message,
            rule_id=diagnostic.rule_id,
            reference_count=1,
            raw_message=diagnostic.message,
        )
        self._locations[ key ] = location
        return location

    def locations( self ):
        return tuple( self._locations.values() )

    def total_references( self ):
        return sum( location.reference_count for location in self._locations.values() )

    def session_union_references( self ):
        return _union_reference_total( self._locations.values() )

    def unique_locations( self ):
        return len( self._locations )

    def unique_violation_count( self ):
        """Count distinct rule violations unioned across variants and toolchains."""
        return _union_violation_count( self._locations.values() )

    def as_report_model( self ):
        """Return a minimal JSON-serialisable view model for tests and later HTML."""
        scopes = {}
        for location in self._locations.values():
            scope_key = (
                location.scope.sconscript,
                location.scope.variant_dir,
                location.scope.toolchain,
            )
            scope_entry = scopes.setdefault(
                scope_key,
                {
                    'sconscript': location.scope.sconscript,
                    'variant_dir': location.scope.variant_dir,
                    'toolchain': location.scope.toolchain,
                    'variant_label': location.scope.variant_label,
                    'profiles': {},
                    'violation_identities': set(),
                },
            )
            scope_entry[ 'violation_identities' ].add(
                session_union_violation_key( location ),
            )
            profile_entry = scope_entry[ 'profiles' ].setdefault(
                location.profile,
                { 'rules': {}, 'files': {}, 'violation_identities': set() },
            )
            profile_entry[ 'violation_identities' ].add(
                session_union_violation_key( location ),
            )
            rule_entry = profile_entry[ 'rules' ].setdefault(
                location.rule_id,
                {
                    'total_references': 0,
                    'unique_files': set(),
                    'files': {},
                    'variants': {},
                    'violation_identities': set(),
                    'sample_normalised_message': None,
                },
            )
            if rule_entry[ 'sample_normalised_message' ] is None:
                rule_entry[ 'sample_normalised_message' ] = location.normalised_message
            rule_entry[ 'total_references' ] += location.reference_count
            rule_entry[ 'unique_files' ].add( location.path )
            rule_entry[ 'violation_identities' ].add(
                session_union_violation_key( location ),
            )

            file_roll = profile_entry[ 'files' ].setdefault(
                location.path,
                {
                    'total_references': 0,
                    'rules': {},
                    'lines': set(),
                    'variants': {},
                },
            )
            _accumulate_location_variants(
                location,
                rule_entry,
                profile_file_entry=file_roll,
            )
            file_entry = rule_entry[ 'files' ].setdefault(
                location.path,
                { 'total_references': 0, 'lines': set(), 'locations': [] },
            )
            file_entry[ 'total_references' ] += location.reference_count
            file_entry[ 'lines' ].add( location.line )
            file_entry[ 'locations' ].append(
                {
                    'line': location.line,
                    'column': location.column,
                    'references': location.reference_count,
                    'message': location.raw_message,
                    'normalised_message': location.normalised_message,
                },
            )

            file_roll[ 'total_references' ] += location.reference_count
            file_roll[ 'lines' ].add( location.line )
            file_rule = file_roll[ 'rules' ].setdefault(
                location.rule_id,
                {
                    'total_references': 0,
                    'lines': set(),
                    'sample_normalised_message': None,
                    'sample_message': location.raw_message,
                },
            )
            file_rule[ 'total_references' ] += location.reference_count
            file_rule[ 'lines' ].add( location.line )
            if file_rule[ 'sample_normalised_message' ] is None:
                file_rule[ 'sample_normalised_message' ] = location.normalised_message

        serialised_scopes = []
        for scope_entry in scopes.values():
            profiles = []
            for profile_name, profile_data in sorted( scope_entry[ 'profiles' ].items() ):
                rules = []
                for rule_id, rule_data in sorted( profile_data[ 'rules' ].items() ):
                    variants = rule_data.get( 'variants', {} )
                    if variants:
                        variant_data = next( iter( variants.values() ) )
                        union_refs, peak_refs, _raw_refs = _variant_reference_metrics(
                            variant_data,
                        )
                    else:
                        union_refs = peak_refs = rule_data[ 'total_references' ]
                    files = []
                    for path, file_data in rule_data[ 'files' ].items():
                        file_variant_counts = _file_variant_counts_for_rule(
                            variants,
                            path,
                        )
                        if file_variant_counts:
                            file_metrics = file_variant_counts[ 0 ]
                            file_union = file_metrics.get(
                                'union_references',
                                file_metrics[ 'total_references' ],
                            )
                            file_peak = file_metrics.get(
                                'peak_references',
                                file_metrics[ 'total_references' ],
                            )
                            file_build = file_metrics[ 'total_references' ]
                        else:
                            file_union = file_peak = file_build = file_data[
                                'total_references'
                            ]
                        files.append(
                            {
                                'path': path,
                                'total_references': file_union,
                                'peak_references': file_peak,
                                'build_references': file_build,
                                'unique_line_count': len( file_data[ 'lines' ] ),
                                'variant_counts': file_variant_counts,
                                'locations': file_data[ 'locations' ],
                            },
                        )
                    files = _sort_rule_files( files )
                    rules.append(
                        {
                            'rule_id': rule_id,
                            'total_references': union_refs,
                            'peak_references': peak_refs,
                            'unique_line_count': len(
                                rule_data[ 'violation_identities' ],
                            ),
                            'unique_files': len( rule_data[ 'unique_files' ] ),
                            'unique_locations': sum(
                                len( file_data[ 'locations' ] )
                                for file_data in rule_data[ 'files' ].values()
                            ),
                            'variant_counts': _serialise_variant_counts(
                                variants,
                                include_files=True,
                            ),
                            'sample_normalised_message': rule_data[
                                'sample_normalised_message'
                            ],
                            'files': files,
                        },
                    )
                rules = _sort_rules( rules )
                files_view = []
                for path, file_data in sorted( profile_data[ 'files' ].items() ):
                    file_variants = file_data.get( 'variants', {} )
                    rules_on_file, variant_rule_refs = _serialise_file_rules(
                        file_data[ 'rules' ],
                        file_variants,
                    )
                    if file_variants:
                        file_variant_data = next( iter( file_variants.values() ) )
                        file_union, file_peak, _file_raw = _variant_reference_metrics(
                            file_variant_data,
                        )
                    else:
                        file_union = file_peak = file_data[ 'total_references' ]
                    files_view.append(
                        {
                            'profile': profile_name,
                            'path': path,
                            'total_references': file_union,
                            'peak_references': file_peak,
                            'unique_line_count': len( file_data[ 'lines' ] ),
                            'unique_rule_count': len( file_data[ 'rules' ] ),
                            'variant_counts': _serialise_file_variant_counts(
                                file_variants,
                            ),
                            'variant_rule_refs': variant_rule_refs,
                            'rules': rules_on_file,
                        },
                    )
                files_view = _sort_files( files_view )
                profiles.append(
                    {
                        'profile': profile_name,
                        'unique_line_count': len( profile_data[ 'violation_identities' ] ),
                        'rules': rules,
                        'files': files_view,
                    },
                )
            scope_total = sum(
                rule[ 'total_references' ]
                for profile in profiles
                for rule in profile[ 'rules' ]
            )
            scope_rule_count = sum(
                len( profile[ 'rules' ] )
                for profile in profiles
            )
            scope_file_paths = set()
            for profile_data in scope_entry[ 'profiles' ].values():
                scope_file_paths.update( profile_data[ 'files' ].keys() )
            scope_key = (
                scope_entry[ 'sconscript' ],
                scope_entry[ 'variant_dir' ],
                scope_entry[ 'toolchain' ],
            )
            scope_build_refs = sum(
                location.reference_count
                for location in self._locations.values()
                if (
                    location.scope.sconscript,
                    location.scope.variant_dir,
                    location.scope.toolchain,
                ) == scope_key
            )
            serialised_scopes.append(
                {
                    'sconscript': scope_entry[ 'sconscript' ],
                    'variant_dir': scope_entry[ 'variant_dir' ],
                    'toolchain': scope_entry[ 'toolchain' ],
                    'variant_label': scope_entry[ 'variant_label' ],
                    'report_stem': _scope_report_stem( scope_entry ),
                    'total_references': scope_total,
                    'build_references': scope_build_refs,
                    'unique_line_count': len( scope_entry[ 'violation_identities' ] ),
                    'unique_rule_count': scope_rule_count,
                    'unique_file_count': len( scope_file_paths ),
                    'profiles': profiles,
                },
            )

        serialised_scopes.sort(
            key=lambda entry: ( -entry[ 'total_references' ], entry[ 'sconscript' ] ),
        )
        session_rollup = _build_session_rollup( self._locations.values() )

        return {
            'scopes': serialised_scopes,
            'rollup': {
                'total_references': self.session_union_references(),
                'raw_total_references': self.total_references(),
                'unique_locations': self.unique_locations(),
                'unique_violation_count': self.unique_violation_count(),
                'unique_rule_count': len( session_rollup[ 'rules' ] ),
                'variant_count': len( serialised_scopes ),
                'rules': session_rollup[ 'rules' ],
                'files': session_rollup[ 'files' ],
            },
        }
