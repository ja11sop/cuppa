#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   Profiles violation inventory — scope, dedupe, replay, report model
#-------------------------------------------------------------------------------

import re

from cuppa.cpp.profiles_report.parse import parse_profiles_diagnostic
from cuppa.cpp.profiles_report.types import (
    ProfilesLocation,
    ProfilesScope,
    unscoped_profiles_scope,
)

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
    see ``cuppa.core.build_layout.tool_variant_dir``.
    """
    parts = variant_dir.strip( '/' ).split( '/' )
    if len( parts ) < 6 or parts[ 0 ] != '_build':
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
    """Track the open Progress scope while replaying a serial capture file."""

    def __init__( self ):
        self._sconscript = None
        self._variant_dir = None

    def apply_progress( self, event, sconscript, variant_dir ):
        if event == 'begin':
            self._sconscript = sconscript
        elif event == 'started':
            self._variant_dir = variant_dir
        elif event == 'finished':
            if self._variant_dir == variant_dir:
                self._variant_dir = None
        elif event == 'end':
            if self._sconscript == sconscript:
                self._sconscript = None
                self._variant_dir = None
        elif event == 'sconstruct_end':
            self._sconscript = None
            self._variant_dir = None

    def current_scope( self ):
        if self._sconscript and self._variant_dir:
            toolchain, variant_label = parse_variant_scope_fields( self._variant_dir )
            return ProfilesScope(
                sconscript=self._sconscript,
                variant_dir=self._variant_dir,
                toolchain=toolchain,
                variant_label=variant_label,
            )
        return unscoped_profiles_scope()


def replay_profiles_capture( lines ):
    """Replay saved build output lines into a scoped ``ProfilesInventory``."""
    inventory = ProfilesInventory()
    stack = ProfilesScopeStack()
    unscoped_diagnostics = 0

    for line in lines:
        progress = parse_progress_line( line )
        if progress is not None:
            stack.apply_progress( *progress )
            continue

        diagnostic = parse_profiles_diagnostic( line )
        if diagnostic is None:
            continue

        scope = stack.current_scope()
        if scope.sconscript == '_unscoped':
            unscoped_diagnostics += 1
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


def _serialise_file_variant_counts( variants ):
    """Per-build-type rule-type and reference counts for by-file roll-up rows."""
    result = []
    for label, data in sorted(
        variants.items(),
        key=lambda item: item[ 0 ],
    ):
        result.append(
            {
                'variant_label': label,
                'unique_rule_count': len( data.get( 'rules', {} ) ),
                'unique_line_count': len( data.get( 'violation_lines', set() ) ),
                'total_references': data[ 'references' ],
            },
        )
    return result


def _serialise_file_rules( rules, variants ):
    """Return sorted per-rule violation detail for one file roll-up row."""
    serialised = []
    for rule_id, rule_data in rules.items():
        serialised.append(
            {
                'rule_id': rule_id,
                'total_references': rule_data[ 'total_references' ],
                'unique_line_count': len( rule_data[ 'lines' ] ),
                'sample_normalised_message': rule_data.get( 'sample_normalised_message' ),
            },
        )
    serialised = _sort_file_rules( serialised )
    variant_rule_refs = {}
    for label, data in variants.items():
        variant_rule_refs[ label ] = dict( data.get( 'rules', {} ) )
    return serialised, variant_rule_refs


def _file_variant_counts_for_rule( variants, path ):
    """Per-build-type violation and reference counts for one file under a rule."""
    counts = []
    for label, data in sorted(
        variants.items(),
        key=lambda item: item[ 0 ],
    ):
        file_data = data.get( 'files', {} ).get( path )
        if file_data is None:
            continue
        counts.append(
            {
                'variant_label': label,
                'unique_line_count': len( file_data[ 'lines' ] ),
                'total_references': file_data[ 'references' ],
            },
        )
    return counts


def _serialise_variant_counts( variants, include_files=False ):
    """Return sorted per-build-type violation and reference counts for roll-up tables."""
    result = []
    for label, data in sorted(
        variants.items(),
        key=lambda item: item[ 0 ],
    ):
        entry = {
            'variant_label': label,
            'unique_line_count': len( data[ 'violation_lines' ] ),
            'total_references': data[ 'references' ],
        }
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
    """Cross-scope roll-up keyed without scope (reference counts add across variants)."""
    rules = {}
    files = {}
    for location in locations:
        rule_key = ( location.profile, location.rule_id )
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
        rule_entry[ 'total_references' ] += location.reference_count
        if rule_entry[ 'sample_normalised_message' ] is None:
            rule_entry[ 'sample_normalised_message' ] = location.normalised_message
        rule_entry[ 'violation_lines' ].add( ( location.path, location.line ) )
        rule_entry[ 'unique_files' ].add( location.path )
        variant_entry = rule_entry[ 'variants' ].setdefault(
            location.scope.variant_label,
            { 'violation_lines': set(), 'references': 0, 'files': {} },
        )
        variant_entry[ 'violation_lines' ].add( ( location.path, location.line ) )
        variant_entry[ 'references' ] += location.reference_count
        variant_file = variant_entry[ 'files' ].setdefault(
            location.path,
            { 'lines': set(), 'references': 0 },
        )
        variant_file[ 'lines' ].add( location.line )
        variant_file[ 'references' ] += location.reference_count
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

        file_key = ( location.profile, location.path )
        file_entry = files.setdefault(
            file_key,
            {
                'profile': location.profile,
                'path': location.path,
                'total_references': 0,
                'lines': set(),
                'variants': {},
                'rules': {},
                'scopes': {},
            },
        )
        file_entry[ 'total_references' ] += location.reference_count
        file_entry[ 'lines' ].add( location.line )
        file_variant = file_entry[ 'variants' ].setdefault(
            location.scope.variant_label,
            { 'violation_lines': set(), 'references': 0, 'rules': {} },
        )
        file_variant[ 'violation_lines' ].add( ( location.path, location.line ) )
        file_variant[ 'references' ] += location.reference_count
        file_variant[ 'rules' ][ location.rule_id ] = (
            file_variant[ 'rules' ].get( location.rule_id, 0 )
            + location.reference_count
        )
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
    for entry in rules.values():
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
                'total_references': entry[ 'total_references' ],
                'unique_line_count': len( entry[ 'violation_lines' ] ),
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
        rollup_files.append(
            {
                'profile': entry[ 'profile' ],
                'path': entry[ 'path' ],
                'total_references': entry[ 'total_references' ],
                'unique_line_count': len( entry[ 'lines' ] ),
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

    def unique_locations( self ):
        return len( self._locations )

    def unique_violation_count( self ):
        """Count distinct source lines with violations (path + line), across all scopes."""
        return len(
            {
                ( location.path, location.line )
                for location in self._locations.values()
            },
        )

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
                    'violation_lines': set(),
                },
            )
            scope_entry[ 'violation_lines' ].add( ( location.path, location.line ) )
            profile_entry = scope_entry[ 'profiles' ].setdefault(
                location.profile,
                { 'rules': {}, 'files': {}, 'violation_lines': set() },
            )
            profile_entry[ 'violation_lines' ].add( ( location.path, location.line ) )
            rule_entry = profile_entry[ 'rules' ].setdefault(
                location.rule_id,
                {
                    'total_references': 0,
                    'unique_files': set(),
                    'files': {},
                    'violation_lines': set(),
                    'sample_normalised_message': None,
                },
            )
            rule_entry[ 'total_references' ] += location.reference_count
            if rule_entry[ 'sample_normalised_message' ] is None:
                rule_entry[ 'sample_normalised_message' ] = location.normalised_message
            rule_entry[ 'unique_files' ].add( location.path )
            rule_entry[ 'violation_lines' ].add( ( location.path, location.line ) )
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

            file_roll = profile_entry[ 'files' ].setdefault(
                location.path,
                { 'total_references': 0, 'rules': {}, 'lines': set() },
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
                    files = []
                    for path, file_data in rule_data[ 'files' ].items():
                        files.append(
                            {
                                'path': path,
                                'total_references': file_data[ 'total_references' ],
                                'unique_line_count': len( file_data[ 'lines' ] ),
                                'variant_counts': [
                                    {
                                        'variant_label': scope_entry[ 'variant_label' ],
                                        'unique_line_count': len(
                                            file_data[ 'lines' ],
                                        ),
                                        'total_references': file_data[
                                            'total_references'
                                        ],
                                    },
                                ],
                                'locations': file_data[ 'locations' ],
                            },
                        )
                    files = _sort_rule_files( files )
                    rules.append(
                        {
                            'rule_id': rule_id,
                            'total_references': rule_data[ 'total_references' ],
                            'unique_line_count': len( rule_data[ 'violation_lines' ] ),
                            'unique_files': len( rule_data[ 'unique_files' ] ),
                            'unique_locations': sum(
                                len( file_data[ 'locations' ] )
                                for file_data in rule_data[ 'files' ].values()
                            ),
                            'variant_counts': [
                                {
                                    'variant_label': scope_entry[ 'variant_label' ],
                                    'unique_line_count': len(
                                        rule_data[ 'violation_lines' ],
                                    ),
                                    'total_references': rule_data[ 'total_references' ],
                                    'file_count': len( files ),
                                    'files': files,
                                },
                            ],
                            'sample_normalised_message': rule_data[
                                'sample_normalised_message'
                            ],
                            'files': files,
                        },
                    )
                rules = _sort_rules( rules )
                files_view = []
                for path, file_data in sorted( profile_data[ 'files' ].items() ):
                    rules_on_file, variant_rule_refs = _serialise_file_rules(
                        file_data[ 'rules' ],
                        {
                            scope_entry[ 'variant_label' ]: {
                                'rules': {
                                    rule_id: rule_entry[ 'total_references' ]
                                    for rule_id, rule_entry in file_data[
                                        'rules'
                                    ].items()
                                },
                            },
                        },
                    )
                    files_view.append(
                        {
                            'profile': profile_name,
                            'path': path,
                            'total_references': file_data[ 'total_references' ],
                            'unique_line_count': len( file_data[ 'lines' ] ),
                            'unique_rule_count': len( file_data[ 'rules' ] ),
                            'variant_counts': [
                                {
                                    'variant_label': scope_entry[ 'variant_label' ],
                                    'unique_rule_count': len( file_data[ 'rules' ] ),
                                    'unique_line_count': len( file_data[ 'lines' ] ),
                                    'total_references': file_data[ 'total_references' ],
                                },
                            ],
                            'variant_rule_refs': variant_rule_refs,
                            'rules': rules_on_file,
                        },
                    )
                files_view = _sort_files( files_view )
                profiles.append(
                    {
                        'profile': profile_name,
                        'unique_line_count': len( profile_data[ 'violation_lines' ] ),
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
            serialised_scopes.append(
                {
                    'sconscript': scope_entry[ 'sconscript' ],
                    'variant_dir': scope_entry[ 'variant_dir' ],
                    'toolchain': scope_entry[ 'toolchain' ],
                    'variant_label': scope_entry[ 'variant_label' ],
                    'report_stem': _scope_report_stem( scope_entry ),
                    'total_references': scope_total,
                    'unique_line_count': len( scope_entry[ 'violation_lines' ] ),
                    'unique_rule_count': scope_rule_count,
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
                'total_references': self.total_references(),
                'unique_locations': self.unique_locations(),
                'unique_violation_count': self.unique_violation_count(),
                'variant_count': len( serialised_scopes ),
                'rules': session_rollup[ 'rules' ],
                'files': session_rollup[ 'files' ],
            },
        }
