#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   C++ Profiles violation report — parse, classify, scope-aware aggregation
#-------------------------------------------------------------------------------

import re
from collections import namedtuple


ProfilesScope = namedtuple(
    'ProfilesScope',
    [ 'sconscript', 'variant_dir', 'toolchain', 'variant_label' ],
)

ProfilesDiagnostic = namedtuple(
    'ProfilesDiagnostic',
    [
        'path',
        'line',
        'column',
        'message',
        'profile',
        'normalised_message',
        'rule_id',
    ],
)

ProfilesLocation = namedtuple(
    'ProfilesLocation',
    [
        'scope',
        'path',
        'line',
        'column',
        'profile',
        'normalised_message',
        'rule_id',
        'reference_count',
        'raw_message',
    ],
)

_UNSCOPED = ProfilesScope(
    sconscript='_unscoped',
    variant_dir='_unscoped',
    toolchain='_unscoped',
    variant_label='_unscoped',
)

_PROFILE_SUFFIX = " under profile '"
_QUOTED_FRAGMENT_RE = re.compile( r"'[^']*'" )
_PROGRESS_LINE_RE = re.compile( r'^Progress\(\s*(.+)\s*\)\s*$' )

_RULE_CLASSIFIERS = (
    (
        re.compile(
            r"^variable '…' must be initialized or marked '…'$"
        ),
        'uninit_decl',
    ),
    (
        re.compile(
            r"^non-local variable '…' requires constant initialization$"
        ),
        'static_runtime_init',
    ),
    (
        re.compile(
            r"^constructor does not initialize member '…'$"
        ),
        'ctor_uninit_member',
    ),
    (
        re.compile(
            r"^constructor does not initialize base class '…'$"
        ),
        'ctor_uninit_member',
    ),
    (
        re.compile(
            r"^pointer to uninitialized memory must be marked '…'$"
        ),
        'ref_to_uninit',
    ),
)

UNCLASSIFIED_RULE_ID = '_unclassified'


def unscoped_profiles_scope():
    """Return the fallback scope when spawn or Progress attribution is unknown."""
    return _UNSCOPED


def normalise_message( message ):
    """Collapse quoted identifiers so template and member names share one pattern key."""
    return _QUOTED_FRAGMENT_RE.sub( "'…'", message )


def classify_rule( normalised_message ):
    """Map a normalised diagnostic message to a Profiles rule id."""
    for pattern, rule_id in _RULE_CLASSIFIERS:
        if pattern.match( normalised_message ):
            return rule_id
    return UNCLASSIFIED_RULE_ID


def parse_profiles_diagnostic( line ):
    """Parse one Clang Profiles diagnostic line, or return ``None`` if it does not match."""
    text = line.rstrip( '\r\n' )
    suffix_index = text.rfind( _PROFILE_SUFFIX )
    if suffix_index == -1:
        return None

    profile_end = text.rfind( "'", len( text ) - 1 )
    if profile_end <= suffix_index:
        return None

    profile = text[ suffix_index + len( _PROFILE_SUFFIX ):profile_end ]
    before_profile = text[ :suffix_index ]

    error_marker = ': error: '
    error_index = before_profile.find( error_marker )
    if error_index == -1:
        return None

    message = before_profile[ error_index + len( error_marker ):]
    location_part = before_profile[ :error_index ]

    column_index = location_part.rfind( ':' )
    if column_index == -1:
        return None
    try:
        column = int( location_part[ column_index + 1: ] )
    except ValueError:
        return None

    rest = location_part[ :column_index ]
    line_index = rest.rfind( ':' )
    if line_index == -1:
        return None
    try:
        line_number = int( rest[ line_index + 1: ] )
    except ValueError:
        return None

    path = rest[ :line_index ]
    if not path:
        return None

    normalised = normalise_message( message )
    return ProfilesDiagnostic(
        path=path,
        line=line_number,
        column=column,
        message=message,
        profile=profile,
        normalised_message=normalised,
        rule_id=classify_rule( normalised ),
    )


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
                },
            )
            profile_entry = scope_entry[ 'profiles' ].setdefault(
                location.profile,
                { 'rules': {}, 'files': {} },
            )
            rule_entry = profile_entry[ 'rules' ].setdefault(
                location.rule_id,
                { 'total_references': 0, 'unique_files': set(), 'files': {} },
            )
            rule_entry[ 'total_references' ] += location.reference_count
            rule_entry[ 'unique_files' ].add( location.path )
            file_entry = rule_entry[ 'files' ].setdefault(
                location.path,
                { 'total_references': 0, 'locations': [] },
            )
            file_entry[ 'total_references' ] += location.reference_count
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
                { 'total_references': 0, 'rules': {} },
            )
            file_roll[ 'total_references' ] += location.reference_count
            file_rule = file_roll[ 'rules' ].setdefault(
                location.rule_id,
                { 'total_references': 0 },
            )
            file_rule[ 'total_references' ] += location.reference_count

        serialised_scopes = []
        for scope_entry in scopes.values():
            profiles = []
            for profile_name, profile_data in sorted( scope_entry[ 'profiles' ].items() ):
                rules = []
                for rule_id, rule_data in sorted( profile_data[ 'rules' ].items() ):
                    files = []
                    for path, file_data in sorted( rule_data[ 'files' ].items() ):
                        files.append(
                            {
                                'path': path,
                                'total_references': file_data[ 'total_references' ],
                                'locations': file_data[ 'locations' ],
                            },
                        )
                    rules.append(
                        {
                            'rule_id': rule_id,
                            'total_references': rule_data[ 'total_references' ],
                            'unique_files': len( rule_data[ 'unique_files' ] ),
                            'files': files,
                        },
                    )
                files_view = []
                for path, file_data in sorted( profile_data[ 'files' ].items() ):
                    rules_on_file = [
                        {
                            'rule_id': rule_id,
                            'total_references': rule_entry[ 'total_references' ],
                        }
                        for rule_id, rule_entry in sorted( file_data[ 'rules' ].items() )
                    ]
                    files_view.append(
                        {
                            'path': path,
                            'total_references': file_data[ 'total_references' ],
                            'rules': rules_on_file,
                        },
                    )
                profiles.append(
                    {
                        'profile': profile_name,
                        'rules': rules,
                        'files': files_view,
                    },
                )
            serialised_scopes.append(
                {
                    'sconscript': scope_entry[ 'sconscript' ],
                    'variant_dir': scope_entry[ 'variant_dir' ],
                    'toolchain': scope_entry[ 'toolchain' ],
                    'variant_label': scope_entry[ 'variant_label' ],
                    'profiles': profiles,
                },
            )

        return {
            'scopes': serialised_scopes,
            'rollup': {
                'total_references': self.total_references(),
                'unique_locations': self.unique_locations(),
            },
        }
