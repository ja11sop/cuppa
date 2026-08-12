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


def default_report_directory( sconstruct_dir ):
    return os.path.join( sconstruct_dir, '_artifacts', 'cxx-profiles' )


def resolve_report_directory( env ):
    """Return the output directory for Profiles HTML/JSON reports."""
    option = env.get( 'cxx_profiles_report' )
    sconstruct_dir = env.get( 'sconstruct_dir' ) or os.getcwd()
    if option is True or option is None:
        return default_report_directory( sconstruct_dir )
    if isinstance( option, str ):
        path = option
        if path.endswith( os.sep ) or os.path.isdir( path ):
            return path
        return os.path.dirname( path ) or default_report_directory( sconstruct_dir )
    return default_report_directory( sconstruct_dir )


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
                    **context_base
                )
            )

    index_path = os.path.join( destination, INDEX_BASENAME )
    with open( index_path, 'w', encoding='utf-8' ) as handle:
        handle.write(
            index_template.render(
                model=model,
                scope_pages=scope_pages,
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
