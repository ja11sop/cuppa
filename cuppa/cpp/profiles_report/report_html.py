#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   C++ Profiles violation report — HTML + JSON emission (prof-report-html)
#-------------------------------------------------------------------------------

import json
import os

from jinja2 import Environment, PackageLoader, select_autoescape

from cuppa.colourise import as_notice
from cuppa.cpp.profiles_report.profiles import std_init
from cuppa.log import logger
from cuppa.test_report.html_report import initialise_test_linking

_jinja2_env = None

INDEX_BASENAME = 'cxx-profiles-index.html'
JSON_BASENAME = 'cxx-profiles-index.json'


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
    if not path or link_style not in ( 'local', 'gitlab', 'github' ):
        return None
    if link_style == 'local':
        if link_base:
            joined = os.path.join( link_base, display )
            return '{}#L{}'.format( joined, line ) if line else joined
        return None
    if link_style in ( 'gitlab', 'github' ) and link_base:
        return '{}/{}#L{}'.format( link_base.rstrip( '/' ), display, line )
    return None


def rule_reference( profile, rule_id ):
    if profile == std_init.PROFILE_NAME:
        return std_init.RULE_DOC_REFERENCES.get( rule_id, {} )
    return {}


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


def scope_profile_summaries( scope ):
    items = []
    for profile in scope.get( 'profiles', [] ):
        total = sum( rule[ 'total_references' ] for rule in profile.get( 'rules', [] ) )
        items.append( ( profile[ 'profile' ], total ) )
    items.sort( key=lambda entry: ( -entry[ 1 ], entry[ 0 ] ) )
    return _format_count_list( items )


def scope_rule_summaries( scope ):
    items = []
    for profile in scope.get( 'profiles', [] ):
        for rule in profile.get( 'rules', [] ):
            items.append(
                (
                    '{}::{}'.format( profile[ 'profile' ], rule[ 'rule_id' ] ),
                    rule[ 'total_references' ],
                ),
            )
    items.sort( key=lambda entry: ( -entry[ 1 ], entry[ 0 ] ) )
    return _format_count_list( items )


def enrich_scope_view( scope ):
    scope[ 'variant_display' ] = variant_display_from_dir( scope[ 'variant_dir' ] )
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
        url, _repository, branch, _remote, revision = vcs
    else:
        url, branch, revision = vcs, '', ''
    return {
        'report_project': project_name,
        'report_uri': url or 'Local',
        'report_branch': branch or '',
        'report_revision': revision or '',
    }


def enrich_model_for_html( model, link_style, link_base, report_root, sconstruct_dir ):
    """Attach display paths and hrefs for template rendering."""

    def enrich_file( file_entry ):
        display = display_path( file_entry[ 'path' ], report_root, sconstruct_dir )
        file_entry[ 'display_path' ] = display
        file_entry[ 'href' ] = source_href(
            file_entry[ 'path' ],
            None,
            link_style,
            link_base,
            display,
        )
        for location in file_entry.get( 'locations', [] ):
            location[ 'href' ] = source_href(
                file_entry[ 'path' ],
                location.get( 'line' ),
                link_style,
                link_base,
                display,
            )
        return file_entry

    def enrich_profile( profile ):
        for rule in profile.get( 'rules', [] ):
            rule[ 'reference' ] = rule_reference( profile[ 'profile' ], rule[ 'rule_id' ] )
            for file_entry in rule.get( 'files', [] ):
                enrich_file( file_entry )
        for file_entry in profile.get( 'files', [] ):
            enrich_file( file_entry )
        return profile

    for scope in model.get( 'scopes', [] ):
        enrich_scope_view( scope )
        for profile in scope.get( 'profiles', [] ):
            enrich_profile( profile )

    for file_entry in model.get( 'rollup', {} ).get( 'files', [] ):
        enrich_file( file_entry )
    for rule in model.get( 'rollup', {} ).get( 'rules', [] ):
        rule[ 'reference' ] = rule_reference( rule[ 'profile' ], rule[ 'rule_id' ] )

    return model


def write_profiles_reports(
    inventory,
    env,
    incomplete_scopes=None,
):
    """Write session HTML index, per-scope pages, and JSON under the report directory."""
    if inventory.total_references() == 0:
        return None

    destination = resolve_report_directory( env )
    os.makedirs( destination, exist_ok=True )

    link_style = env.get( 'cxx_profiles_report_link_style' ) or 'local'
    report_root = env.get( 'cxx_profiles_report_root' ) or env.get( 'sconstruct_dir' )
    sconstruct_dir = env.get( 'sconstruct_dir' ) or os.getcwd()

    model = inventory.as_report_model()
    link_base = initialise_test_linking( env, link_style=link_style )

    enrich_model_for_html( model, link_style, link_base, report_root, sconstruct_dir )

    context_base = {
        'link_style': link_style,
        'report_root': report_root,
        'sconstruct_dir': sconstruct_dir,
        'incomplete_scopes': sorted( incomplete_scopes or [] ),
    }
    header_context = report_header_context( env )
    header_context[ 'session_summary' ] = (
        '{} references, {} unique locations'.format(
            model[ 'rollup' ][ 'total_references' ],
            model[ 'rollup' ][ 'unique_locations' ],
        )
    )

    index_template = jinja2_templates().get_template( 'cxx_profiles_index.html' )
    scope_template = jinja2_templates().get_template( 'cxx_profiles_scope.html' )

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
                scope_pages=scope_pages,
                sconscript_groups=sconscript_groups,
                **header_context,
                **context_base
            )
        )

    json_path = os.path.join( destination, JSON_BASENAME )
    with open( json_path, 'w', encoding='utf-8' ) as handle:
        json.dump( model, handle, indent=2, sort_keys=True )
        handle.write( '\n' )

    logger.info(
        "C++ Profiles report: {} ({} scope(s), {} references)".format(
            as_notice( index_path ),
            len( model[ 'scopes' ] ),
            model[ 'rollup' ][ 'total_references' ],
        )
    )
    return {
        'index_path': index_path,
        'session_paths': [ index_path, json_path ],
        'scope_paths': scope_paths,
        'model': model,
    }
