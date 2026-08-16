#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   C++ Profiles violation report — HTML + JSON emission (prof-report-html)
#-------------------------------------------------------------------------------

import os
import re

try:
    from urlparse import urlparse
except ImportError:
    from urllib.parse import urlparse

from jinja2 import Environment, PackageLoader, select_autoescape

from cuppa.colourise import as_notice
from cuppa.core.dependency_identity import short_name_from_git_url
from cuppa.cpp.profiles_report.profiles import std_init
from cuppa.log import logger
from cuppa.cpp.profiles_report.breadcrumbs import scope_breadcrumbs
from cuppa.cpp.profiles_report.source_pages import format_rule_label_html
from cuppa.cpp.profiles_report.source_pages import format_violation_message_html
from cuppa.cpp.profiles_report.source_pages import write_source_pages
from cuppa.test_report.html_report import initialise_test_linking

_jinja2_env = None

INDEX_BASENAME = 'cxx-profiles-index.html'
JSON_BASENAME = 'cxx-profiles-index.json'

CUPPA_PROFILES_REPORT_DOCS_BASE = (
    'https://ja11sop.github.io/cuppa/cuppa/cxx-profiles/report-overview.html'
)

_GIT_DESCRIBE = re.compile(
    r'^(?P<label>.+)-(?P<distance>\d+)-g(?P<commit>[0-9a-f]+)$',
    re.IGNORECASE,
)
_GIT_HASH = re.compile( r'^[0-9a-f]{7,40}$', re.IGNORECASE )


def _parse_revision_labels( revision ):
    if not revision:
        return None, None
    text = str( revision ).strip()
    match = _GIT_DESCRIBE.match( text )
    if match:
        return match.group( 'label' ), match.group( 'commit' )
    if _GIT_HASH.match( text ):
        return None, text[ :12 ]
    return text, None


def _repo_browse_href( repository ):
    if not repository:
        return None
    if '://' in str( repository ):
        parsed = urlparse( str( repository ) )
        if parsed.scheme in ( 'http', 'https' ):
            path = ( parsed.path or '' ).rstrip( '/' )
            if path.endswith( '.git' ):
                path = path[:-4]
            return '{}{}'.format(
                '{}://{}'.format( parsed.scheme, parsed.netloc.split( '@' )[-1] ),
                path,
            )
    short = short_name_from_git_url( repository )
    if not short or '/' not in short:
        return None
    host, path = short.split( '/', 1 )
    return 'https://{}/{}'.format( host, path )


def _hosting_style( repo_href ):
    if repo_href and 'github.com' in repo_href.lower():
        return 'github'
    return 'gitlab'


def _tag_href( repo_href, tag ):
    if not repo_href or not tag:
        return None
    base = repo_href.rstrip( '/' )
    if _hosting_style( repo_href ) == 'github':
        return '{}/releases/tag/{}'.format( base, tag )
    return '{}/-/tags/{}'.format( base, tag )


def _commit_href( repo_href, commit ):
    if not repo_href or not commit:
        return None
    base = repo_href.rstrip( '/' )
    if _hosting_style( repo_href ) == 'github':
        return '{}/commit/{}'.format( base, commit )
    return '{}/-/commit/{}'.format( base, commit )


def _location_dependency_label( repository, branch ):
    if not repository:
        return ''
    text = str( repository ).strip()
    scp = re.match( r'^git@([^:]+):(.+)$', text )
    if scp:
        host, path = scp.group( 1 ), scp.group( 2 )
        if path.endswith( '.git' ):
            path = path[:-4]
        base = '{}:{}'.format( host, path )
    else:
        base = short_name_from_git_url( repository ) or text
        if base.endswith( '.git' ):
            base = base[:-4]
    if branch:
        return '{}@{}'.format( base, branch )
    return base


def build_vcs_provenance( repository, branch, revision ):
    """Build location-dependency-style VCS labels and browse links for report headers."""
    location_label = _location_dependency_label( repository, branch )
    tag, commit = _parse_revision_labels( revision )
    repo_href = _repo_browse_href( repository )
    return {
        'location_label': location_label,
        'repo_href': repo_href,
        'tag': tag,
        'tag_href': _tag_href( repo_href, tag ),
        'commit': commit,
        'commit_href': _commit_href( repo_href, commit ),
    }


def jinja2_templates():
    global _jinja2_env
    if _jinja2_env:
        return _jinja2_env
    _jinja2_env = Environment(
        loader=PackageLoader( 'cuppa', 'cpp/templates' ),
        autoescape=select_autoescape( [ 'html', 'xml' ] ),
    )
    return _jinja2_env


def default_report_directory( env ):
    """Return the default Profiles report directory under ``artifacts_root``."""
    if env.get( 'abs_artifacts_root' ):
        return os.path.join( env[ 'abs_artifacts_root' ], 'cxx-profiles' )
    sconstruct_dir = env.get( 'sconstruct_dir' ) or os.getcwd()
    artifacts_root = env.get( 'artifacts_root', '_artifacts' )
    if os.path.isabs( artifacts_root ):
        return os.path.join( artifacts_root, 'cxx-profiles' )
    return os.path.join( sconstruct_dir, artifacts_root, 'cxx-profiles' )


def resolve_report_directory( env ):
    """Return the output directory for Profiles HTML/JSON reports."""
    option = env.get( 'cxx_profiles_report' )
    if option is True or option is None:
        return default_report_directory( env )
    if isinstance( option, str ):
        path = option
        if path.endswith( os.sep ) or os.path.isdir( path ):
            return path
        if not os.path.exists( path ) and not path.endswith( '.html' ):
            return path
        return os.path.dirname( path ) or default_report_directory( env )
    return default_report_directory( env )


def display_path( path, report_root, sconstruct_dir ):
    """Rebase absolute paths under report_root or sconstruct_dir when possible."""
    if not path:
        return path
    for root in ( report_root, sconstruct_dir ):
        if not root:
            continue
        try:
            rel = os.path.relpath( path, root )
        except ValueError:
            continue
        if not rel.startswith( '..' ):
            return rel
    return path


def source_href( path, line, link_style, link_base, display ):
    """Build a clickable href for a diagnostic location."""
    from cuppa.reports.link_style import source_file_href
    return source_file_href( path, line, link_style, link_base, display )


def rule_reference( profile, rule_id ):
    if profile == std_init.PROFILE_NAME:
        return std_init.RULE_DOC_REFERENCES.get( rule_id, {} )
    return {}


def rule_doc_href( profile, rule_id ):
    if profile == std_init.PROFILE_NAME:
        return std_init.rule_doc_href( rule_id )
    return None


def overview_doc_href( anchor=None ):
    """Return the published cuppa docs URL for Overview tab interpretation."""
    if anchor:
        return '{}#{}'.format( CUPPA_PROFILES_REPORT_DOCS_BASE, anchor )
    return CUPPA_PROFILES_REPORT_DOCS_BASE


def overview_doc_hrefs():
    """Return Overview guide links keyed for Jinja templates."""
    return {
        'inventory': overview_doc_href( 'violation-totals' ),
        'codebase_reach': overview_doc_href( 'codebase-reach-tier-1' ),
        'violation_density': overview_doc_href( 'violation-density-tier-2' ),
        'rule_concentration': overview_doc_href( 'rule-concentration' ),
        'profile_matrices': overview_doc_href( 'profile-matrices' ),
        'build_breakdown': overview_doc_href( 'build-breakdown' ),
        'guide': overview_doc_href(),
    }


def rule_link_tooltip( profile, rule_id, sample_message=None ):
    """Plain-text tooltip for violated-rule index links."""
    text = '{}::{}'.format( profile, rule_id )
    if sample_message:
        return '{} — {}'.format( text, sample_message )
    return text


def variant_display_from_dir( variant_dir ):
    """Return ``variant/arch/abi`` from a cuppa variant directory path."""
    parts = variant_dir.strip( '/' ).split( '/' )
    if len( parts ) >= 3:
        return '/'.join( parts[ -3: ] )
    if parts:
        return parts[ -1 ]
    return '_unknown'


def _format_count_list( entries, limit=5 ):
    parts = []
    for label, count in entries[ :limit ]:
        parts.append( '{} ({})'.format( label, count ) )
    text = ', '.join( parts )
    if len( entries ) > limit:
        text = '{}, ...'.format( text )
    return text


def scope_profile_summary_items( scope ):
    items = []
    for profile in scope.get( 'profiles', [] ):
        items.append(
            (
                profile[ 'profile' ],
                profile.get( 'unique_line_count', 0 ),
            ),
        )
    items.sort( key=lambda entry: ( -entry[ 1 ], entry[ 0 ] ) )
    return items


def scope_rule_summary_items( scope ):
    items = []
    for profile in scope.get( 'profiles', [] ):
        for rule in profile.get( 'rules', [] ):
            items.append(
                {
                    'profile': profile[ 'profile' ],
                    'rule_id': rule[ 'rule_id' ],
                    'count': rule.get( 'unique_line_count', 0 ),
                    'label_html': format_rule_label_html(
                        profile[ 'profile' ],
                        rule[ 'rule_id' ],
                    ),
                },
            )
    items.sort(
        key=lambda entry: ( -entry[ 'count' ], entry[ 'rule_id' ] ),
    )
    return items


def scope_profile_summaries( scope ):
    return _format_count_list( scope_profile_summary_items( scope ) )


def scope_rule_summaries( scope ):
    return _format_count_list(
        [
            (
                '{}::{}'.format( entry[ 'profile' ], entry[ 'rule_id' ] ),
                entry[ 'count' ],
            )
            for entry in scope_rule_summary_items( scope )
        ],
    )


def enrich_scope_view( scope ):
    variant_display = variant_display_from_dir( scope[ 'variant_dir' ] )
    scope[ 'variant_display' ] = variant_display
    parts = variant_display.split( '/', 1 )
    scope[ 'variant_display_tail' ] = parts[ 1 ] if len( parts ) > 1 else ''
    scope[ 'scope_path_suffix' ] = scope.get( 'sconscript', '' ).lstrip( './' )
    scope.setdefault(
        'unique_rule_count',
        sum( len( profile.get( 'rules', [] ) ) for profile in scope.get( 'profiles', [] ) ),
    )
    scope[ 'profiles_summary_items' ] = scope_profile_summary_items( scope )
    scope[ 'rules_summary_items' ] = scope_rule_summary_items( scope )
    scope[ 'profiles_summary' ] = scope_profile_summaries( scope )
    scope[ 'rules_summary' ] = scope_rule_summaries( scope )
    return scope


def _safe_selector( label, prefix ):
    safe = ''.join(
        ch if ch.isalnum() else '-'
        for ch in label
    ).strip( '-' )
    while '--' in safe:
        safe = safe.replace( '--', '-' )
    return '{}-{}'.format( prefix, safe or 'group' )


def build_sconscript_groups( scope_pages ):
    grouped = {}
    for page in scope_pages:
        sconscript = page[ 'scope' ][ 'sconscript' ]
        grouped.setdefault( sconscript, [] ).append( page )

    groups = []
    for sconscript in sorted( grouped.keys() ):
        entries = sorted(
            grouped[ sconscript ],
            key=lambda page: page[ 'scope' ][ 'variant_dir' ],
        )
        groups.append(
            {
                'sconscript': sconscript,
                'selector': _safe_selector( sconscript, 'sconscript' ),
                'entries': entries,
            },
        )
    return groups


def report_header_context( env ):
    sconstruct_dir = env.get( 'sconstruct_dir' ) or os.getcwd()
    project_name = os.path.basename( sconstruct_dir.rstrip( os.sep ) ) or sconstruct_dir
    link_env = dict( env )
    link_env.setdefault( 'current_branch', '' )
    link_env.setdefault( 'current_revision', '' )
    vcs = initialise_test_linking( link_env, link_style='raw' )
    if isinstance( vcs, tuple ):
        url, repository, branch, _remote, revision = vcs
    else:
        url, repository, branch, revision = vcs, '', '', ''
    provenance = build_vcs_provenance( repository or url, branch, revision )
    return {
        'report_project': project_name,
        'report_uri': url or 'Local',
        'report_branch': branch or '',
        'report_revision': revision or '',
        'vcs_provenance': provenance,
    }


def report_header_context_from_metadata( metadata ):
    """Build report header fields from saved JSON metadata (anonymised regen)."""
    metadata = metadata or {}
    report_uri = metadata.get( 'report_uri' ) or ''
    report_branch = metadata.get( 'report_branch' ) or ''
    report_revision = metadata.get( 'report_revision' ) or ''
    provenance = build_vcs_provenance( report_uri, report_branch, report_revision )
    return {
        'report_project': metadata.get( 'report_project' ) or '',
        'report_uri': report_uri or 'Local',
        'report_branch': report_branch,
        'report_revision': report_revision,
        'vcs_provenance': provenance,
    }


def build_file_rule_variant_counts( file_entry ):
    """Build per-build inventory violated-rule breakdown for the by-file table."""
    rules = file_entry.get( 'rules', [] )
    if not rules:
        return []

    variant_rule_refs = file_entry.get( 'variant_rule_refs', [] )
    if isinstance( variant_rule_refs, dict ):
        variant_rule_refs = [
            {
                'variant_label': label,
                'build_key': [ label, '', '' ],
                'rules': refs_by_rule,
            }
            for label, refs_by_rule in sorted( variant_rule_refs.items() )
        ]

    result = []
    for variant in variant_rule_refs:
        refs_by_rule = variant.get( 'rules', {} )
        variant_rules = []
        for rule in rules:
            count = refs_by_rule.get( rule[ 'rule_id' ], 0 )
            if not count:
                continue
            variant_rules.append(
                {
                    'rule_index': rule[ 'rule_index' ],
                    'total_references': count,
                    'rule_tooltip': rule[ 'rule_tooltip' ],
                    'doc_href': rule.get( 'doc_href' ),
                },
            )
        if variant_rules:
            result.append(
                {
                    'build_key': variant.get( 'build_key' ),
                    'variant_label': variant.get( 'variant_label' ),
                    'rule_count': len( variant_rules ),
                    'rule_ids': sorted( refs_by_rule.keys() ),
                    'rules': variant_rules,
                },
            )
    return result


def enrich_file_rules( file_entry ):
    """Attach rule indices, labels, and per-variant roll-ups for by-file tables."""
    profile_name = file_entry.get( 'profile' ) or std_init.PROFILE_NAME
    rules = file_entry.get( 'rules', [] )
    if not rules:
        file_entry[ 'rule_variant_counts' ] = []
        file_entry.setdefault( 'unique_rule_count', 0 )
        return file_entry

    rules = sorted(
        rules,
        key=lambda entry: ( -entry[ 'total_references' ], entry[ 'rule_id' ] ),
    )
    file_entry[ 'rules' ] = rules
    file_entry[ 'unique_rule_count' ] = len( rules )
    for index, rule in enumerate( rules, start=1 ):
        rule[ 'rule_index' ] = index
        rule[ 'rule_reference' ] = rule_reference( profile_name, rule[ 'rule_id' ] )
        rule[ 'doc_href' ] = rule_doc_href( profile_name, rule[ 'rule_id' ] )
        rule[ 'rule_tooltip' ] = rule_link_tooltip(
            profile_name,
            rule[ 'rule_id' ],
            rule.get( 'sample_normalised_message' ),
        )
        rule[ 'rule_label_html' ] = format_rule_label_html(
            profile_name,
            rule[ 'rule_id' ],
        )
        rule[ 'violation_message_html' ] = format_violation_message_html(
            rule.get( 'sample_normalised_message' ),
            profile=profile_name,
            rule_id=rule[ 'rule_id' ],
        )
    file_entry[ 'rule_variant_counts' ] = build_file_rule_variant_counts( file_entry )
    return file_entry


def file_path_tooltip_text( file_entry ):
    """Plain-text path for HTML ``title`` tooltips on file links."""
    if file_entry.get( 'title_split' ):
        if file_entry.get( 'title_include_split' ):
            return '{}{}{}'.format(
                file_entry.get( 'title_prefix', '' ),
                file_entry.get( 'title_include_prefix', '' ),
                file_entry.get( 'title_include_path', '' ),
            )
        if file_entry.get( 'title_suffix_only' ):
            return (
                file_entry.get( 'title_suffix' )
                or file_entry.get( 'display_path' )
                or file_entry.get( 'path', '' )
            )
        prefix = file_entry.get( 'title_prefix', '' )
        suffix = file_entry.get( 'title_suffix', '' )
        if prefix and suffix:
            if prefix.endswith( '/' ):
                return '{}{}'.format( prefix, suffix )
            return '{}/{}'.format( prefix, suffix )
        return prefix or suffix
    return file_entry.get( 'display_path' ) or file_entry.get( 'path', '' )


def enrich_model_for_html(
    model,
    env,
    link_style,
    link_base,
    report_root,
    sconstruct_dir,
    source_page_map=None,
    suppress_source_links=False,
):
    """Attach display paths and hrefs for template rendering."""
    from cuppa.cpp.profiles_report.build_catalog import build_catalog_from_scopes
    from cuppa.cpp.profiles_report.source_pages import (
        annotate_file_links,
        build_source_page_title,
        display_path_for_report,
    )
    from cuppa.cpp.profiles_report.anonymise import env_is_anonymised
    from cuppa.cpp.profiles_report.variant_roll_up_display import attach_roll_up_displays

    source_page_map = source_page_map or {}
    model[ 'build_catalog' ] = build_catalog_from_scopes( model.get( 'scopes', [] ) )

    def enrich_file( file_entry ):
        display = display_path_for_report( file_entry[ 'path' ], env )
        if not env_is_anonymised( env ) and display == file_entry[ 'path' ]:
            display = display_path( file_entry[ 'path' ], report_root, sconstruct_dir )
        file_entry[ 'display_path' ] = display
        file_entry.update( build_source_page_title( display, file_entry[ 'path' ], env ) )
        annotate_file_links(
            file_entry,
            source_page_map,
            link_style,
            link_base,
            display,
            suppress_source_links=suppress_source_links,
        )
        file_entry[ 'path_tooltip' ] = file_path_tooltip_text( file_entry )
        enrich_file_rules( file_entry )
        return file_entry

    def enrich_rule_variant_files( rule ):
        for variant in rule.get( 'variant_counts', [] ):
            for file_entry in variant.get( 'files', [] ):
                enrich_file( file_entry )

    def assign_rule_file_indices( rule ):
        index_by_path = {}
        for index, file_entry in enumerate( rule.get( 'files', [] ), start=1 ):
            file_entry[ 'file_index' ] = index
            index_by_path[ file_entry[ 'path' ] ] = index
        for variant in rule.get( 'variant_counts', [] ):
            for file_entry in variant.get( 'files', [] ):
                file_entry[ 'file_index' ] = index_by_path.get(
                    file_entry[ 'path' ],
                )

    def enrich_rule( rule, profile_name ):
        rule[ 'reference' ] = rule_reference( profile_name, rule[ 'rule_id' ] )
        rule[ 'violation_message_html' ] = format_violation_message_html(
            rule.get( 'sample_normalised_message' ),
            profile=profile_name,
            rule_id=rule[ 'rule_id' ],
        )
        enrich_rule_variant_files( rule )
        for file_entry in rule.get( 'files', [] ):
            enrich_file( file_entry )
        assign_rule_file_indices( rule )

    def enrich_profile( profile ):
        for rule in profile.get( 'rules', [] ):
            enrich_rule( rule, profile[ 'profile' ] )
        for file_entry in profile.get( 'files', [] ):
            file_entry.setdefault( 'profile', profile[ 'profile' ] )
            enrich_file( file_entry )
        return profile

    for scope in model.get( 'scopes', [] ):
        enrich_scope_view( scope )
        for profile in scope.get( 'profiles', [] ):
            enrich_profile( profile )
        from cuppa.cpp.profiles_report.build_rollups import scope_detail_tables

        scope[ 'rules' ], scope[ 'files' ] = scope_detail_tables( scope )

    for file_entry in model.get( 'rollup', {} ).get( 'files', [] ):
        enrich_file( file_entry )
    for rule in model.get( 'rollup', {} ).get( 'rules', [] ):
        enrich_rule( rule, rule[ 'profile' ] )

    attach_roll_up_displays( model )

    from cuppa.cpp.profiles_report.build_rollups import build_views_from_model
    from cuppa.cpp.profiles_report.context_summary import _build_scope_breakdown

    model[ 'build_views' ] = build_views_from_model( model )
    model[ 'build_inventory' ] = _build_scope_breakdown(
        model,
        model.get( 'rollup', {} ),
    )

    return model


def render_profiles_reports(
    model,
    env,
    incomplete_scopes=None,
    inventory=None,
    skip_source_pages=False,
    write_json=True,
    parsed_files=None,
    translation_units=None,
    context=None,
    metadata=None,
):
    """Render HTML (and optionally JSON) from a serialised report view model."""
    rollup = model.get( 'rollup', {} )
    if rollup.get( 'total_references', 0 ) == 0:
        return None

    destination = resolve_report_directory( env )
    os.makedirs( destination, exist_ok=True )

    from cuppa.reports.link_style import initialise_report_linking, resolve_report_link_style
    link_style = resolve_report_link_style(
        env,
        per_report_env_key='cxx_profiles_report_link_style',
    )
    report_root = env.get( 'cxx_profiles_report_root' ) or env.get( 'sconstruct_dir' )
    sconstruct_dir = env.get( 'sconstruct_dir' ) or os.getcwd()

    link_base = initialise_report_linking( env, link_style=link_style )
    from cuppa.cpp.profiles_report.anonymise import env_is_anonymised
    suppress_source_links = env_is_anonymised( env )

    templates = jinja2_templates()
    source_page_map = {}
    source_written = []
    if not skip_source_pages and not suppress_source_links:
        if inventory is None:
            from cuppa.cpp.profiles_report.report_json import inventory_from_report_model
            inventory = inventory_from_report_model( model )
        source_page_map, source_written = write_source_pages(
            inventory,
            destination,
            env,
            link_style,
            link_base,
            INDEX_BASENAME,
            lambda: templates.get_template( 'cxx_profiles_source_file.html' ),
        )

    enrich_model_for_html(
        model,
        env,
        link_style,
        link_base,
        report_root,
        sconstruct_dir,
        source_page_map=source_page_map,
        suppress_source_links=suppress_source_links,
    )

    context_base = {
        'link_style': link_style,
        'report_root': report_root,
        'sconstruct_dir': sconstruct_dir,
        'incomplete_scopes': sorted( incomplete_scopes or [] ),
        'overview_doc_inventory': overview_doc_href( 'violation-totals' ),
        'overview_doc_codebase_reach': overview_doc_href( 'codebase-reach-tier-1' ),
        'overview_doc_violation_density': overview_doc_href( 'violation-density-tier-2' ),
        'overview_doc_rule_concentration': overview_doc_href( 'rule-concentration' ),
        'overview_doc_profile_matrices': overview_doc_href( 'profile-matrices' ),
        'overview_doc_build_breakdown': overview_doc_href( 'build-breakdown' ),
    }
    from cuppa.cpp.profiles_report.anonymise import metadata_is_anonymised

    if metadata_is_anonymised( metadata ):
        header_context = report_header_context_from_metadata( metadata )
    else:
        header_context = report_header_context( env )
    header_context[ 'session_stats' ] = {
        'unique_violation_count': rollup[ 'unique_violation_count' ],
        'unique_rule_count': rollup[ 'unique_rule_count' ],
        'total_references': rollup[ 'total_references' ],
        'files_with_violations': len( rollup.get( 'files', [] ) ),
    }

    if context is None:
        from cuppa.cpp.profiles_report.context_summary import (
            build_report_context,
            resolve_context_mode,
        )
        context = build_report_context(
            model,
            env,
            parsed_files=parsed_files,
            translation_units=translation_units,
            context_mode=resolve_context_mode( env ),
        )

    index_template = templates.get_template( 'cxx_profiles_index.html' )
    scope_template = templates.get_template( 'cxx_profiles_scope.html' )

    scope_pages = []
    scope_paths = {}
    for scope in model[ 'scopes' ]:
        scope_html = '{}.html'.format( scope[ 'report_stem' ] )
        scope_pages.append(
            {
                'stem': scope[ 'report_stem' ],
                'html': scope_html,
                'scope': scope,
            },
        )
        scope_path = os.path.join( destination, scope_html )
        scope_paths[ scope[ 'report_stem' ] ] = [ scope_path ]
        with open( scope_path, 'w', encoding='utf-8' ) as handle:
            handle.write(
                scope_template.render(
                    scope=scope,
                    index_name=INDEX_BASENAME,
                    breadcrumbs=scope_breadcrumbs( INDEX_BASENAME, scope ),
                    **header_context,
                    **context_base
                )
            )

    index_path = os.path.join( destination, INDEX_BASENAME )
    sconscript_groups = build_sconscript_groups( scope_pages )
    with open( index_path, 'w', encoding='utf-8' ) as handle:
        handle.write(
            index_template.render(
                model=model,
                build_views=model.get( 'build_views', [] ),
                build_inventory=model.get( 'build_inventory' ),
                scope_pages=scope_pages,
                sconscript_groups=sconscript_groups,
                context=context,
                **header_context,
                **context_base
            )
        )

    json_path = os.path.join( destination, JSON_BASENAME )
    if write_json:
        from cuppa.cpp.profiles_report.report_json import dump_report_json
        with open( json_path, 'w', encoding='utf-8' ) as handle:
            dump_report_json(
                handle,
                model,
                env,
                inventory=inventory,
                incomplete_scopes=incomplete_scopes,
                context=context,
                parsed_files=parsed_files,
                translation_units=translation_units,
            )

    logger.info(
        "C++ Profiles report: {} ({} scope(s), {} references)".format(
            as_notice( index_path ),
            len( model[ 'scopes' ] ),
            rollup[ 'total_references' ],
        )
    )
    session_paths = [ index_path ]
    if write_json:
        session_paths.append( json_path )
    session_paths.extend( source_written )
    return {
        'index_path': index_path,
        'session_paths': session_paths,
        'scope_paths': scope_paths,
        'source_paths': source_written,
        'model': model,
    }


def write_profiles_reports_from_json(
    json_path,
    env,
    skip_source_pages=False,
    write_json=False,
):
    """Re-render HTML from a saved ``cxx-profiles-index.json``."""
    from cuppa.cpp.profiles_report.anonymise import metadata_is_anonymised, set_env_anonymised
    from cuppa.cpp.profiles_report.report_json import inventory_from_report_model, load_report_model
    model, metadata, extras = load_report_model( json_path )
    merged_env = dict( env )
    anonymised = metadata_is_anonymised( metadata )
    if not anonymised and metadata.get( 'sconstruct_dir' ) and not merged_env.get( 'sconstruct_dir' ):
        merged_env[ 'sconstruct_dir' ] = metadata[ 'sconstruct_dir' ]
    if metadata.get( 'cxx_profiles_report_root' ) and not anonymised:
        merged_env.setdefault(
            'cxx_profiles_report_root',
            metadata[ 'cxx_profiles_report_root' ],
        )
    if metadata.get( 'link_style' ):
        merged_env.setdefault( 'reports_link_style', metadata[ 'link_style' ] )
    if metadata.get( 'profiles_enforce' ):
        merged_env.setdefault(
            'cxx_profiles_enforce',
            list( metadata[ 'profiles_enforce' ] ),
        )
    if anonymised:
        set_env_anonymised( merged_env )
        skip_source_pages = True
    inventory = None
    if not skip_source_pages:
        flat_locations = extras.get( 'locations' ) or None
        inventory = inventory_from_report_model(
            model,
            flat_locations=flat_locations,
        )
    return render_profiles_reports(
        model,
        merged_env,
        incomplete_scopes=metadata.get( 'incomplete_scopes' ),
        inventory=inventory,
        skip_source_pages=skip_source_pages,
        write_json=write_json,
        context=extras.get( 'context' ),
        metadata=metadata,
    )


def write_profiles_reports(
    inventory,
    env,
    incomplete_scopes=None,
    parsed_files=None,
    translation_units=None,
):
    """Write session HTML index, per-scope pages, and JSON under the report directory."""
    if inventory.total_references() == 0:
        return None

    model = inventory.as_report_model()
    return render_profiles_reports(
        model,
        env,
        incomplete_scopes=incomplete_scopes,
        inventory=inventory,
        skip_source_pages=False,
        write_json=True,
        parsed_files=parsed_files,
        translation_units=translation_units,
    )
