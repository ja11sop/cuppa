#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   C++ Profiles report — dependency display paths and marked-up source pages
#-------------------------------------------------------------------------------

import html
import hashlib
import os
import re
from collections import defaultdict

from cuppa.core.dependency_identity import enrich_described
from cuppa.core.dependency_storage import describe_tree_path, split_location_folder_name
from cuppa.cpp.profiles_report.breadcrumbs import source_breadcrumbs
from cuppa.cpp.profiles_report.profiles import std_init
from cuppa.cpp.coverage_by_source import language_for_source
from cuppa.log import logger

BY_SOURCE_DIR = 'by-source'
_GIT_SSH_PREFIX = 'git_ssh_'
# First path segment names commonly used as ``location_dependency(..., include=...)`` roots.
_COMMON_INCLUDE_DIR_NAMES = frozenset(
    {
        'include',
        'inc',
        'src',
        'public',
        'headers',
        'interface',
    },
)
# Visible display placeholder for normalised ``'…'`` name fragments in summary messages.
VIOLATION_MESSAGE_PLACEHOLDER = '<name>'
VIOLATION_TYPE_PLACEHOLDER = '<type>'
_NORMALISED_PLACEHOLDER_RE = re.compile( r"'…'" )
_ATTR_LITERAL_RE = re.compile( r'\[\[[^\]]+\]\]' )


_MAX_SOURCE_FILENAME_LEN = 240


def sanitized_source_filename( source_path ):
    stem = source_path.replace( '\\', '/' ).replace( '/', '--' )
    candidate = stem + '.html'
    if len( candidate ) <= _MAX_SOURCE_FILENAME_LEN:
        return candidate

    digest = hashlib.sha256( source_path.encode( 'utf-8' ) ).hexdigest()[:16]
    base = os.path.basename( source_path ).replace( os.sep, '--' )
    base = re.sub( r'[^A-Za-z0-9._-]+', '_', base )[:80].strip( '_.' ) or 'source'
    return '{}--{}.html'.format( base, digest )


def source_page_relpath( source_path ):
    return os.path.join( BY_SOURCE_DIR, sanitized_source_filename( source_path ) )


def _try_relpath( path, root ):
    if not path or not root:
        return None
    try:
        rel = os.path.relpath( path, os.path.realpath( root ) )
    except ValueError:
        return None
    if rel.startswith( '..' ):
        return None
    return rel.replace( os.sep, '/' )


def _decode_git_ssh_folder( folder ):
    """Turn ``git_ssh_git@host__org_repo`` + ``@branch`` into ``host/org/repo@branch``."""
    stem, qualifier = split_location_folder_name( folder )
    if not stem.startswith( _GIT_SSH_PREFIX ):
        return None

    encoded = stem[ len( _GIT_SSH_PREFIX ): ]
    if encoded.startswith( 'git_git@' ):
        encoded = 'git@' + encoded[ len( 'git_git@' ): ]
    elif encoded.startswith( 'git_' ):
        encoded = encoded[ len( 'git_' ): ]

    if '__' not in encoded:
        return None

    user_host, repo_encoded = encoded.split( '__', 1 )
    host = user_host.split( '@', 1 )[ -1 ] if '@' in user_host else user_host
    repo_path = repo_encoded.strip( '_' ).replace( '_', '/' )
    prefix = '{}/{}'.format( host, repo_path )
    if qualifier:
        prefix += qualifier
    return prefix


def _storage_root_for_path( path, env ):
    for key in ( 'dependencies_root', 'downloads_root' ):
        root = env.get( key )
        if not root:
            continue
        try:
            real_root = os.path.realpath( root )
        except OSError:
            real_root = root
        if os.path.commonpath( [ os.path.realpath( path ), real_root ] ) == real_root:
            return real_root

    normalized = os.path.normpath( path )
    parts = normalized.split( os.sep )
    for index, part in enumerate( parts ):
        if part in ( 'dependencies', '_download' ):
            return os.sep.join( parts[ : index + 1 ] )
    return None


def display_path_for_report( path, env ):
    """Rebase project paths or shorten dependency download paths for display."""
    if not path:
        return path

    storage_root = _storage_root_for_path( path, env )
    if storage_root:
        rel = _try_relpath( path, storage_root )
        if rel:
            parts = rel.split( '/', 1 )
            folder = parts[ 0 ]
            remainder = parts[ 1 ] if len( parts ) > 1 else ''
            dependency_root = os.path.join( storage_root, folder )

            described = describe_tree_path( dependency_root, storage_root )
            enrich_described( dependency_root, described )
            short_name = described.get( 'short_name' )
            if short_name:
                qualifier = described.get( 'qualifier' ) or ''
                prefix = '{}{}'.format( short_name, qualifier )
                if remainder:
                    return '{}/{}'.format( prefix, remainder )
                return prefix

            decoded = _decode_git_ssh_folder( folder )
            if decoded:
                if remainder:
                    return '{}/{}'.format( decoded, remainder )
                return decoded
            return rel

    report_root = env.get( 'cxx_profiles_report_root' )
    sconstruct_dir = env.get( 'sconstruct_dir' )
    for root in ( report_root, sconstruct_dir ):
        rel = _try_relpath( path, root )
        if rel:
            return rel

    return path


def _split_location_include_remainder( dependency_root, remainder ):
    """Split a dependency-relative path into ``(-I prefix, #include path)``."""
    if not remainder or '/' not in remainder:
        return None

    rel = remainder.replace( '\\', '/' )
    parts = rel.split( '/' )
    include_dir = parts[ 0 ]
    if include_dir not in _COMMON_INCLUDE_DIR_NAMES:
        return None

    include_root = os.path.join( dependency_root, include_dir )
    if not os.path.isdir( include_root ):
        return None

    include_path = '/'.join( parts[ 1: ] )
    if not include_path:
        return None

    return '{}/'.format( include_dir ), include_path


def _dependency_title_parts( source_path, env ):
    """Return ``(repo_prefix, local_remainder, dependency_root)`` or ``None``."""
    storage_root = _storage_root_for_path( source_path, env )
    if not storage_root:
        return None

    rel = _try_relpath( source_path, storage_root )
    if not rel:
        return None

    parts = rel.split( '/', 1 )
    folder = parts[ 0 ]
    remainder = parts[ 1 ] if len( parts ) > 1 else ''
    if not remainder:
        return None

    dependency_root = os.path.join( storage_root, folder )
    described = describe_tree_path( dependency_root, storage_root )
    enrich_described( dependency_root, described )
    short_name = described.get( 'short_name' )
    if short_name:
        qualifier = described.get( 'qualifier' ) or ''
        return (
            '{}{}'.format( short_name, qualifier ),
            remainder,
            dependency_root,
        )

    decoded = _decode_git_ssh_folder( folder )
    if decoded:
        return decoded, remainder, dependency_root
    return None


def build_source_page_title( display_path, source_path, env ):
    """Build centred title fields for a source page."""
    parts = _dependency_title_parts( source_path, env )
    if parts:
        prefix, suffix, dependency_root = parts
        title = {
            'title_split': True,
            'title_prefix': prefix,
            'title_suffix': suffix,
            'title_include_split': False,
        }
        include_parts = _split_location_include_remainder(
            dependency_root,
            suffix,
        )
        if include_parts:
            include_prefix, include_path = include_parts
            title[ 'title_include_split' ] = True
            title[ 'title_include_prefix' ] = include_prefix
            title[ 'title_include_path' ] = include_path
        return title
    return {
        'title_split': False,
        'title_single': display_path,
        'title_include_split': False,
    }


def display_path_on_disk( path ):
    """Shorten an on-disk path with a leading ``~/`` when under the home directory."""
    if not path:
        return path
    try:
        real_path = os.path.realpath( path )
        home = os.path.realpath( os.path.expanduser( '~' ) )
        if os.path.commonpath( [ real_path, home ] ) == home:
            rel = os.path.relpath( real_path, home )
            return '~/' + rel.replace( os.sep, '/' )
    except ( OSError, ValueError ):
        pass
    return path.replace( os.sep, '/' )


def format_rule_label_html( profile, rule_id ):
    """Render ``profile::rule_id`` with bold weight on the rule id only."""
    return (
        '<span class="prof-rule-profile">{}::</span>'
        '<span class="prof-rule-id">{}</span>'
    ).format( html.escape( profile ), html.escape( rule_id ) )


def _message_name_html( placeholder ):
    return '<span class="prof-message-name">{}</span>'.format(
        html.escape( placeholder ),
    )


def _quoted_message_name_html():
    return "'{}'".format( _message_name_html( VIOLATION_MESSAGE_PLACEHOLDER ) )


def _highlight_attribute_literals( rendered_html ):
    """Wrap ``[[attribute]]`` literals in summary messages with warn styling."""
    return _ATTR_LITERAL_RE.sub(
        lambda match: '<span class="prof-attr-literal">{}</span>'.format( match.group( 0 ) ),
        rendered_html,
    )


def _render_summary_template( template ):
    """Render a summary template, muting ``{name}`` / ``{type}`` placeholders only."""
    placeholder_spans = {
        '{name}': _message_name_html( VIOLATION_MESSAGE_PLACEHOLDER ),
        '{type}': _message_name_html( VIOLATION_TYPE_PLACEHOLDER ),
    }
    parts = re.split( r'(\{name\}|\{type\})', template )
    rendered = []
    for part in parts:
        if part in placeholder_spans:
            rendered.append( placeholder_spans[ part ] )
        elif part:
            rendered.append( html.escape( part ) )
    return _highlight_attribute_literals( ''.join( rendered ) )


def format_violation_message_html( normalised_message, profile=None, rule_id=None ):
    """Render a canonical violation message for summary tables."""
    if not normalised_message:
        return ''
    if profile == std_init.PROFILE_NAME:
        template = std_init.summary_display_template( normalised_message )
        if template:
            return _render_summary_template( template )
    display = _NORMALISED_PLACEHOLDER_RE.sub(
        "'{}'".format( VIOLATION_MESSAGE_PLACEHOLDER ),
        normalised_message,
    )
    escaped = html.escape( display )
    quoted_placeholder = html.escape(
        "'{}'".format( VIOLATION_MESSAGE_PLACEHOLDER ),
    )
    return _highlight_attribute_literals(
        escaped.replace( quoted_placeholder, _quoted_message_name_html() ),
    )


def collect_file_violations( inventory ):
    files = {}
    for location in inventory.locations():
        file_entry = files.setdefault(
            location.path,
            {
                'path': location.path,
                'total_references': 0,
                'rules': defaultdict( int ),
                'rule_lines': defaultdict( set ),
                'lines': defaultdict( list ),
                'violations': [],
            },
        )
        rule_key = ( location.profile, location.rule_id )
        file_entry[ 'total_references' ] += location.reference_count
        file_entry[ 'rules' ][ rule_key ] += location.reference_count
        file_entry[ 'rule_lines' ][ rule_key ].add( location.line )
        line_record = {
            'line': location.line,
            'column': location.column,
            'profile': location.profile,
            'rule_id': location.rule_id,
            'message': location.raw_message,
            'normalised_message': location.normalised_message,
            'references': location.reference_count,
        }
        file_entry[ 'lines' ][ location.line ].append( line_record )
        file_entry[ 'violations' ].append( line_record )

    for file_entry in files.values():
        file_entry[ 'violations' ].sort(
            key=lambda item: ( item[ 'line' ], item[ 'column' ], item[ 'rule_id' ] ),
        )
        summary = []
        rule_messages = {}
        for record in file_entry[ 'violations' ]:
            key = ( record[ 'profile' ], record[ 'rule_id' ] )
            rule_messages.setdefault( key, record[ 'normalised_message' ] )
        for ( profile, rule_id ), count in sorted(
            file_entry[ 'rules' ].items(),
            key=lambda item: ( -item[ 1 ], item[ 0 ][ 0 ], item[ 0 ][ 1 ] ),
        ):
            violation_message = rule_messages.get( ( profile, rule_id ) )
            summary.append(
                {
                    'profile': profile,
                    'rule_id': rule_id,
                    'label': '{}::{}'.format( profile, rule_id ),
                    'rule_label_html': format_rule_label_html( profile, rule_id ),
                    'line_count': len( file_entry[ 'rule_lines' ][ ( profile, rule_id ) ] ),
                    'count': count,
                    'violation_message': violation_message,
                    'violation_message_html': format_violation_message_html(
                        violation_message,
                        profile=profile,
                        rule_id=rule_id,
                    ),
                },
            )
        file_entry[ 'rule_summary' ] = summary
        file_entry[ 'unique_line_count' ] = len( file_entry[ 'lines' ] )
    return files


def _load_source_lines( source_path ):
    try:
        with open( source_path, 'r', encoding='utf-8', errors='replace' ) as handle:
            return handle.read().splitlines()
    except OSError as error:
        logger.debug(
            "Profiles source page: could not read [{}]: {}".format(
                source_path, error,
            )
        )
        return []


def _line_gutter_label( line_records ):
    if not line_records:
        return ''
    by_rule = defaultdict( int )
    for record in line_records:
        by_rule[ record[ 'rule_id' ] ] += record[ 'references' ]
    labels = []
    for rule_id, count in sorted( by_rule.items() ):
        labels.append( '{} ({})'.format( rule_id, count ) )
    return '\n'.join( labels )


def compute_gutter_width_ch( file_entry ):
    """Return a ``ch`` width that fits the longest gutter label in this file."""
    max_len = 0
    for records in file_entry.get( 'lines', {} ).values():
        label = _line_gutter_label( records )
        for part in label.split( '\n' ):
            max_len = max( max_len, len( part ) )
    return max( max_len + 1, 12 )


def build_source_view_lines( source_path, file_entry ):
    source_lines = _load_source_lines( source_path )
    rendered = []
    line_numbers = sorted( file_entry[ 'lines' ].keys() ) if not source_lines else range(
        1, len( source_lines ) + 1,
    )

    if source_lines:
        for lineno in line_numbers:
            text = source_lines[ lineno - 1 ] if lineno <= len( source_lines ) else ''
            records = file_entry[ 'lines' ].get( lineno, [] )
            primary = records[ 0 ] if records else None
            rendered.append(
                {
                    'lineno': lineno,
                    'kind': 'violation' if records else 'plain',
                    'text': text,
                    'column': primary[ 'column' ] if primary else None,
                    'gutter': _line_gutter_label( records ),
                    'title': primary[ 'message' ] if primary else '',
                },
            )
        return rendered

    for lineno in line_numbers:
        records = file_entry[ 'lines' ][ lineno ]
        primary = records[ 0 ]
        rendered.append(
            {
                'lineno': lineno,
                'kind': 'violation',
                'text': '',
                'column': primary[ 'column' ],
                'gutter': _line_gutter_label( records ),
                'title': primary[ 'message' ],
            },
        )
    return rendered


def write_source_pages(
    inventory,
    destination,
    env,
    link_style,
    link_base,
    index_basename,
    get_template,
):
    """Write marked-up source pages and return ``path -> page_relpath`` map."""
    from cuppa.cpp.profiles_report.report_html import source_href

    files = collect_file_violations( inventory )
    if not files:
        return {}, []

    output_dir = os.path.join( destination, BY_SOURCE_DIR )
    os.makedirs( output_dir, exist_ok=True )

    template = get_template()
    page_map = {}
    written = []
    for source_path in sorted( files.keys() ):
        file_entry = files[ source_path ]
        display = display_path_for_report( source_path, env )
        page_rel = source_page_relpath( source_path )
        page_abs = os.path.join( destination, page_rel )
        page_map[ source_path ] = page_rel

        source_lines = build_source_view_lines( source_path, file_entry )
        title = build_source_page_title( display, source_path, env )
        gutter_width_ch = compute_gutter_width_ch( file_entry )
        index_href = '../{}'.format( index_basename )
        with open( page_abs, 'w', encoding='utf-8' ) as handle:
            handle.write(
                template.render(
                    file_entry=file_entry,
                    source_path=source_path,
                    source_path_display=display_path_on_disk( source_path ),
                    display_path=display,
                    source_lines=source_lines,
                    source_language=language_for_source( source_path ),
                    gutter_width_ch=gutter_width_ch,
                    index_href=index_href,
                    breadcrumbs=source_breadcrumbs(
                        index_href,
                        display,
                        title_split=title.get( 'title_split', False ),
                        title_prefix=title.get( 'title_prefix', '' ),
                        title_suffix=title.get( 'title_suffix', '' ),
                    ),
                    original_href=source_href(
                        source_path,
                        None,
                        link_style,
                        link_base,
                        display,
                    ),
                    **title,
                )
            )
        written.append( page_abs )

    return page_map, written


def annotate_file_links( file_entry, source_page_map, link_style, link_base, display ):
    """Attach report page hrefs for templates and JSON."""
    from cuppa.cpp.profiles_report.report_html import source_href

    page_rel = source_page_map.get( file_entry[ 'path' ] )
    if page_rel:
        file_entry[ 'page_href' ] = page_rel
        file_entry[ 'href' ] = page_rel
    else:
        file_entry[ 'href' ] = source_href(
            file_entry[ 'path' ],
            None,
            link_style,
            link_base,
            display,
        )
    for location in file_entry.get( 'locations', [] ):
        page = source_page_map.get( file_entry[ 'path' ] )
        if page:
            location[ 'href' ] = '{}#L{}'.format( page, location.get( 'line' ) )
        else:
            location[ 'href' ] = source_href(
                file_entry[ 'path' ],
                location.get( 'line' ),
                link_style,
                link_base,
                display,
            )
