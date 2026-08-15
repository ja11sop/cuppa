#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

"""Merged table rows for **Violations By-Build** and per-scope detail pages."""

from cuppa.cpp.profiles_report.inventory import _sort_files, _sort_rules


_DISPLAY_KEYS = (
    'variant_display',
    'refs_display',
    'peak_refs_display',
    'build_refs_display',
    'violating_files_display',
    'rules_display',
    'violated_rules_display',
)


def _build_key_tuple( build_key ):
    if isinstance( build_key, list ):
        return tuple( build_key )
    return build_key


def _find_variant_entry( variant_counts, build_key ):
    key = _build_key_tuple( build_key )
    for entry in variant_counts or []:
        if tuple( entry.get( 'build_key', () ) ) == key:
            return entry
    return None


def _strip_roll_up_displays( row ):
    for name in _DISPLAY_KEYS:
        row.pop( name, None )
    return row


def _rule_file_row_for_build( file_entry, build_key ):
    variant = _find_variant_entry( file_entry.get( 'variant_counts' ), build_key )
    if not variant or variant.get( 'unique_line_count', 0 ) == 0:
        return None
    row = dict( file_entry )
    _strip_roll_up_displays( row )
    row[ 'variant_counts' ] = [ variant ]
    row[ 'unique_line_count' ] = variant.get( 'unique_line_count', 0 )
    row[ 'total_references' ] = variant.get(
        'union_references',
        variant.get( 'total_references', 0 ),
    )
    row[ 'peak_references' ] = variant.get(
        'peak_references',
        variant.get( 'total_references', 0 ),
    )
    return row


def _rule_row_for_build( rule, build_key ):
    variant = _find_variant_entry( rule.get( 'variant_counts' ), build_key )
    if not variant or variant.get( 'unique_line_count', 0 ) == 0:
        return None

    files = []
    for file_entry in rule.get( 'files', [] ):
        file_row = _rule_file_row_for_build( file_entry, build_key )
        if file_row is not None:
            files.append( file_row )

    row = {
        'profile': rule[ 'profile' ],
        'rule_id': rule[ 'rule_id' ],
        'total_references': variant.get(
            'union_references',
            variant.get( 'total_references', 0 ),
        ),
        'peak_references': variant.get(
            'peak_references',
            variant.get( 'total_references', 0 ),
        ),
        'unique_line_count': variant.get( 'unique_line_count', 0 ),
        'variant_counts': [ variant ],
        'sample_normalised_message': rule.get( 'sample_normalised_message' ),
        'violation_message_html': rule.get( 'violation_message_html' ),
        'reference': rule.get( 'reference' ),
        'files': files,
    }
    return row


def _file_rule_row_for_build( rule, build_key ):
    variant = _find_variant_entry( rule.get( 'variant_counts' ), build_key )
    if not variant or variant.get( 'total_references', 0 ) == 0:
        return None
    row = dict( rule )
    _strip_roll_up_displays( row )
    row[ 'variant_counts' ] = [ variant ]
    row[ 'unique_line_count' ] = variant.get( 'unique_line_count', 0 )
    row[ 'total_references' ] = variant.get(
        'union_references',
        variant.get( 'total_references', 0 ),
    )
    row[ 'peak_references' ] = variant.get(
        'peak_references',
        variant.get( 'total_references', 0 ),
    )
    return row


def _filter_rule_variant_counts( file_entry, build_key ):
    filtered = []
    for variant in file_entry.get( 'rule_variant_counts', [] ) or []:
        if tuple( variant.get( 'build_key', () ) ) != _build_key_tuple( build_key ):
            continue
        if not variant.get( 'rules' ):
            continue
        filtered.append( variant )
    return filtered


def _file_row_for_build( file_entry, build_key ):
    variant = _find_variant_entry( file_entry.get( 'variant_counts' ), build_key )
    if not variant or variant.get( 'unique_line_count', 0 ) == 0:
        return None

    rules = []
    for rule in file_entry.get( 'rules', [] ):
        rule_row = _file_rule_row_for_build( rule, build_key )
        if rule_row is not None:
            rules.append( rule_row )

    row = dict( file_entry )
    _strip_roll_up_displays( row )
    row[ 'rules' ] = rules
    row[ 'variant_counts' ] = [ variant ]
    row[ 'unique_line_count' ] = variant.get( 'unique_line_count', 0 )
    row[ 'unique_rule_count' ] = variant.get(
        'unique_rule_count',
        len( rules ),
    )
    row[ 'total_references' ] = variant.get(
        'union_references',
        variant.get( 'total_references', 0 ),
    )
    row[ 'peak_references' ] = variant.get(
        'peak_references',
        variant.get( 'total_references', 0 ),
    )
    row[ 'rule_variant_counts' ] = _filter_rule_variant_counts(
        file_entry,
        build_key,
    )
    return row


def _profiles_for_build( rollup, build_key ):
    profiles = {}
    for rule in rollup.get( 'rules', [] ):
        rule_row = _rule_row_for_build( rule, build_key )
        if rule_row is None:
            continue
        profile_name = rule[ 'profile' ]
        profile = profiles.setdefault(
            profile_name,
            {
                'profile': profile_name,
                'rules': [],
                'files': [],
            },
        )
        profile[ 'rules' ].append( rule_row )

    for file_entry in rollup.get( 'files', [] ):
        file_row = _file_row_for_build( file_entry, build_key )
        if file_row is None:
            continue
        profile_name = file_entry[ 'profile' ]
        profile = profiles.setdefault(
            profile_name,
            {
                'profile': profile_name,
                'rules': [],
                'files': [],
            },
        )
        profile[ 'files' ].append( file_row )

    result = []
    for profile_name in sorted( profiles.keys() ):
        profile = profiles[ profile_name ]
        profile[ 'rules' ] = _sort_rules( profile[ 'rules' ] )
        profile[ 'files' ] = _sort_files( profile[ 'files' ] )
        profile[ 'unique_line_count' ] = sum(
            rule.get( 'unique_line_count', 0 )
            for rule in profile[ 'rules' ]
        )
        result.append( profile )
    return result


def build_views_from_model( model ):
    """Return per-build profile roll-ups for the index **Violations By-Build** tab."""
    catalog = model.get( 'build_catalog' ) or []
    rollup = model.get( 'rollup', {} )
    if not catalog or not rollup:
        return []

    views = []
    for entry in catalog:
        build_key = tuple( entry[ 'build_key' ] )
        profiles = _profiles_for_build( rollup, build_key )
        if not profiles:
            continue
        rules = _sort_rules(
            [
                rule
                for profile in profiles
                for rule in profile.get( 'rules', [] )
            ],
        )
        files = _sort_files(
            [
                file_entry
                for profile in profiles
                for file_entry in profile.get( 'files', [] )
            ],
        )
        views.append(
            {
                'build_id': entry[ 'build_id' ],
                'build_label': entry[ 'build_label' ],
                'variant_label': entry[ 'variant_label' ],
                'variant_display_tail': entry.get( 'variant_display_tail', '' ),
                'toolchain': entry[ 'toolchain' ],
                'profiles': profiles,
                'rules': rules,
                'files': files,
            },
        )
    return views


def scope_detail_tables( scope ):
    """Return merged By-Rule / By-File rows for one scope detail page."""
    rules = []
    for profile in scope.get( 'profiles', [] ):
        profile_name = profile.get( 'profile', '' )
        for rule in profile.get( 'rules', [] ):
            row = dict( rule )
            row[ 'profile' ] = profile_name
            rules.append( row )
    files = [
        file_entry
        for profile in scope.get( 'profiles', [] )
        for file_entry in profile.get( 'files', [] )
    ]
    return _sort_rules( rules ), _sort_files( files )
