#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

"""Common + delta display models for multi-build roll-up tables."""

from cuppa.cpp.profiles_report.build_catalog import catalog_lookup


def _tuple_key( key ):
    if isinstance( key, list ):
        return tuple( key )
    return key


def _bucket_maps( variant_counts, catalog ):
    by_key = {}
    for entry in variant_counts or []:
        build_key = tuple( entry.get( 'build_key', () ) )
        by_key[ build_key ] = entry
    build_keys = [ tuple( item[ 'build_key' ] ) for item in catalog ]
    key_sets = {}
    ref_maps = {}
    row_peak_maps = {}
    for build_key in build_keys:
        bucket = by_key.get( build_key, {} )
        key_sets[ build_key ] = {
            _tuple_key( item )
            for item in bucket.get( 'violation_identity_keys', [] )
        }
        ref_maps[ build_key ] = {}
        row_peak_maps[ build_key ] = {}
        for item in bucket.get( 'violation_refs', [] ):
            key = _tuple_key( item[ 'key' ] )
            ref_maps[ build_key ][ key ] = item[ 'refs' ]
            row_peak_maps[ build_key ][ key ] = item.get( 'row_peak', item[ 'refs' ] )
    return build_keys, key_sets, ref_maps, row_peak_maps, by_key


def _metric_for_keys( keys, per_build_maps, build_keys ):
    total = 0
    for key in keys:
        total += max(
            per_build_maps.get( build_key, {} ).get( key, 0 )
            for build_key in build_keys
        )
    return total


def _metric_for_exclusive_keys( exclusive, per_build_map ):
    return sum( per_build_map.get( key, 0 ) for key in exclusive )


def compute_violation_metric_display( variant_counts, catalog ):
    """Return common/delta violations, union refs, and peak refs for one roll-up row."""
    if len( catalog ) <= 1:
        return { 'multi_build': False }

    build_keys, key_sets, ref_maps, row_peak_maps, _by_key = _bucket_maps(
        variant_counts,
        catalog,
    )
    common_keys = set.intersection( *( key_sets[ build_key ] for build_key in build_keys ) )
    lookup = catalog_lookup( catalog )
    deltas = []
    for build_key in build_keys:
        entry = lookup[ build_key ]
        exclusive = key_sets[ build_key ] - common_keys
        if not exclusive:
            continue
        deltas.append(
            {
                'build_id': entry[ 'build_id' ],
                'build_label': entry[ 'build_label' ],
                'violations': len( exclusive ),
                'refs': _metric_for_exclusive_keys(
                    exclusive,
                    row_peak_maps[ build_key ],
                ),
                'peak_refs': _metric_for_exclusive_keys(
                    exclusive,
                    ref_maps[ build_key ],
                ),
            },
        )
    common = {
        'violations': len( common_keys ),
        'refs': _metric_for_keys( common_keys, row_peak_maps, build_keys ),
        'peak_refs': _metric_for_keys( common_keys, ref_maps, build_keys ),
    }
    totals = {
        'violations': common[ 'violations' ] + sum(
            item[ 'violations' ] for item in deltas
        ),
        'refs': common[ 'refs' ] + sum( item[ 'refs' ] for item in deltas ),
        'peak_refs': common[ 'peak_refs' ] + sum(
            item[ 'peak_refs' ] for item in deltas
        ),
    }
    return {
        'multi_build': True,
        'build_order': [ entry[ 'build_id' ] for entry in catalog ],
        'common': common,
        'deltas': deltas,
        'totals': totals,
    }


def peak_refs_total_for_row( variant_counts, catalog ):
    """Return session peak-ref total for one roll-up row (matches By-Rule **Peak refs**)."""
    display = compute_violation_metric_display( variant_counts, catalog )
    if display.get( 'multi_build' ):
        return display[ 'totals' ][ 'peak_refs' ]
    total = 0
    for entry in variant_counts or []:
        total += entry.get(
            'peak_references',
            entry.get( 'total_references', 0 ),
        )
    return total


def compute_rule_count_display( variant_counts, catalog ):
    """Return common/delta distinct rule counts for a by-file row."""
    if len( catalog ) <= 1:
        return { 'multi_build': False }

    lookup = catalog_lookup( catalog )
    build_keys = [ tuple( item[ 'build_key' ] ) for item in catalog ]
    by_key = {
        tuple( entry.get( 'build_key', () ) ): entry
        for entry in ( variant_counts or [] )
    }
    rule_sets = {}
    for build_key in build_keys:
        bucket = by_key.get( build_key, {} )
        rule_sets[ build_key ] = set( bucket.get( 'rule_ids', [] ) )
    common_rules = set.intersection( *( rule_sets[ build_key ] for build_key in build_keys ) )
    deltas = []
    for build_key in build_keys:
        entry = lookup[ build_key ]
        exclusive = rule_sets[ build_key ] - common_rules
        if not exclusive:
            continue
        deltas.append(
            {
                'build_id': entry[ 'build_id' ],
                'build_label': entry[ 'build_label' ],
                'rules': len( exclusive ),
            },
        )
    return {
        'multi_build': True,
        'build_order': [ entry[ 'build_id' ] for entry in catalog ],
        'common': { 'rules': len( common_rules ) },
        'deltas': deltas,
    }


def _partition_index_ref_items( catalog, per_build_items ):
    """Partition ``(index, refs)`` tuples across all catalog builds."""
    build_ids = [ entry[ 'build_id' ] for entry in catalog ]
    sets = {}
    item_lookup = {}
    for build_id in build_ids:
        tuple_set = set()
        for item in per_build_items.get( build_id, [] ):
            key = ( item[ 'index' ], item[ 'refs' ] )
            tuple_set.add( key )
            item_lookup[ ( build_id, key ) ] = item
        sets[ build_id ] = tuple_set
    common_tuples = set.intersection( *( sets[ build_id ] for build_id in build_ids ) )

    def _item_for_build( build_id, key ):
        item = item_lookup.get( ( build_id, key ) )
        if item is not None:
            return dict( item )
        index, refs = key
        return { 'index': index, 'refs': refs }

    def _common_item( key ):
        for build_id in build_ids:
            item = item_lookup.get( ( build_id, key ) )
            if item is not None:
                return dict( item )
        index, refs = key
        return { 'index': index, 'refs': refs }

    common_items = [ _common_item( key ) for key in sorted( common_tuples ) ]
    lookup = { entry[ 'build_id' ]: entry for entry in catalog }
    deltas = []
    for build_id in build_ids:
        exclusive = sets[ build_id ] - common_tuples
        if not exclusive:
            continue
        deltas.append(
            {
                'build_id': build_id,
                'build_label': lookup[ build_id ][ 'build_label' ],
                'items': [
                    _item_for_build( build_id, key )
                    for key in sorted( exclusive )
                ],
            },
        )
    return common_items, deltas


def compute_violating_files_display( rule, catalog ):
    """Partition violating-file index lists on a by-rule row."""
    if len( catalog ) <= 1:
        return { 'multi_build': False }

    lookup = catalog_lookup( catalog )
    file_by_index = {
        file_entry.get( 'file_index' ): file_entry
        for file_entry in rule.get( 'files', [] )
        if file_entry.get( 'file_index' ) is not None
    }
    per_build = {}
    for variant in rule.get( 'variant_counts', [] ):
        build_key = tuple( variant.get( 'build_key', () ) )
        build_id = lookup.get( build_key, {} ).get( 'build_id' )
        if not build_id:
            continue
        items = []
        for file_entry in variant.get( 'files', [] ):
            file_index = file_entry.get( 'file_index' )
            if file_index is None:
                continue
            enriched = file_by_index.get( file_index, file_entry )
            items.append(
                {
                    'index': file_index,
                    'refs': file_entry.get( 'total_references', 0 ),
                    'path': enriched.get( 'path' ),
                    'href': enriched.get( 'href' ),
                    'path_tooltip': enriched.get( 'path_tooltip' ),
                },
            )
        per_build[ build_id ] = items
    common_items, deltas = _partition_index_ref_items( catalog, per_build )
    return {
        'multi_build': True,
        'common': {
            'count': len( common_items ),
            'items': common_items,
        },
        'deltas': deltas,
    }


def _build_refs_metric_display( catalog, per_build, index_value ):
    """Return common/delta **Build refs** totals for one indexed list entry."""
    common_items, deltas = _partition_index_ref_items( catalog, per_build )
    common_refs = 0
    for item in common_items:
        if item.get( 'index' ) == index_value:
            common_refs = item.get( 'refs', 0 )
            break
    delta_rows = []
    for delta in deltas:
        for item in delta.get( 'items', [] ):
            if item.get( 'index' ) != index_value:
                continue
            delta_rows.append(
                {
                    'build_id': delta[ 'build_id' ],
                    'build_label': delta[ 'build_label' ],
                    'refs': item[ 'refs' ],
                },
            )
    total_refs = common_refs + sum( item[ 'refs' ] for item in delta_rows )
    return {
        'multi_build': True,
        'common': { 'refs': common_refs },
        'deltas': delta_rows,
        'totals': { 'refs': total_refs },
    }


def compute_file_build_refs_display( file_entry, rule, catalog ):
    """Return **Build refs** for one file row (matches Violating Files ``index:refs``)."""
    if len( catalog ) <= 1:
        return { 'multi_build': False }

    file_index = file_entry.get( 'file_index' )
    if file_index is None:
        return { 'multi_build': False }

    lookup = catalog_lookup( catalog )
    per_build = {}
    for variant in rule.get( 'variant_counts', [] ):
        build_key = tuple( variant.get( 'build_key', () ) )
        build_id = lookup.get( build_key, {} ).get( 'build_id' )
        if not build_id:
            continue
        refs = None
        for variant_file in variant.get( 'files', [] ):
            if variant_file.get( 'file_index' ) == file_index:
                refs = variant_file.get( 'total_references', 0 )
                break
        if refs is None:
            per_build[ build_id ] = []
        else:
            per_build[ build_id ] = [ { 'index': file_index, 'refs': refs } ]

    return _build_refs_metric_display( catalog, per_build, file_index )


def compute_rule_build_refs_display( file_entry, rule, catalog ):
    """Return **Build refs** for one rule row (matches Violated Rules ``index:refs``)."""
    if len( catalog ) <= 1:
        return { 'multi_build': False }

    rule_index = rule.get( 'rule_index' )
    if rule_index is None:
        return { 'multi_build': False }

    lookup = catalog_lookup( catalog )
    per_build = {}
    for variant in file_entry.get( 'rule_variant_counts', [] ):
        build_key = tuple( variant.get( 'build_key', () ) )
        build_id = lookup.get( build_key, {} ).get( 'build_id' )
        if not build_id:
            continue
        refs = None
        for variant_rule in variant.get( 'rules', [] ):
            if variant_rule.get( 'rule_index' ) == rule_index:
                refs = variant_rule.get( 'total_references', 0 )
                break
        if refs is None:
            per_build[ build_id ] = []
        else:
            per_build[ build_id ] = [ { 'index': rule_index, 'refs': refs } ]

    return _build_refs_metric_display( catalog, per_build, rule_index )


def compute_violated_rules_display( file_entry, catalog ):
    """Partition violated-rule index lists on a by-file row."""
    if len( catalog ) <= 1:
        return { 'multi_build': False }

    lookup = catalog_lookup( catalog )
    per_build = {}
    for variant in file_entry.get( 'rule_variant_counts', [] ):
        build_key = tuple( variant.get( 'build_key', () ) )
        build_id = lookup.get( build_key, {} ).get( 'build_id' )
        if not build_id:
            continue
        items = []
        for rule in variant.get( 'rules', [] ):
            items.append(
                {
                    'index': rule.get( 'rule_index' ),
                    'refs': rule.get( 'total_references', 0 ),
                    'doc_href': rule.get( 'doc_href' ),
                    'rule_tooltip': rule.get( 'rule_tooltip' ),
                },
            )
        per_build[ build_id ] = items
    common_items, deltas = _partition_index_ref_items( catalog, per_build )
    return {
        'multi_build': True,
        'common': {
            'count': len( common_items ),
            'items': common_items,
        },
        'deltas': deltas,
    }


def attach_roll_up_displays( model ):
    """Attach ``variant_display`` structures to session roll-up rows."""
    catalog = model.get( 'build_catalog' ) or []
    if not catalog:
        return model

    for rule in model.get( 'rollup', {} ).get( 'rules', [] ):
        metric = compute_violation_metric_display( rule.get( 'variant_counts' ), catalog )
        rule[ 'variant_display' ] = metric
        rule[ 'refs_display' ] = metric
        rule[ 'peak_refs_display' ] = metric
        rule[ 'violating_files_display' ] = compute_violating_files_display( rule, catalog )
        for file_entry in rule.get( 'files', [] ):
            file_metric = compute_violation_metric_display(
                file_entry.get( 'variant_counts' ),
                catalog,
            )
            file_entry[ 'variant_display' ] = file_metric
            file_entry[ 'refs_display' ] = file_metric
            file_entry[ 'peak_refs_display' ] = file_metric
            file_entry[ 'build_refs_display' ] = compute_file_build_refs_display(
                file_entry,
                rule,
                catalog,
            )

    for file_entry in model.get( 'rollup', {} ).get( 'files', [] ):
        file_entry[ 'rules_display' ] = compute_rule_count_display(
            file_entry.get( 'variant_counts' ),
            catalog,
        )
        metric = compute_violation_metric_display(
            file_entry.get( 'variant_counts' ),
            catalog,
        )
        file_entry[ 'variant_display' ] = metric
        file_entry[ 'refs_display' ] = metric
        file_entry[ 'peak_refs_display' ] = metric
        file_entry[ 'violated_rules_display' ] = compute_violated_rules_display(
            file_entry,
            catalog,
        )
        for rule in file_entry.get( 'rules', [] ):
            rule_metric = compute_violation_metric_display(
                rule.get( 'variant_counts' ),
                catalog,
            )
            rule[ 'variant_display' ] = rule_metric
            rule[ 'refs_display' ] = rule_metric
            rule[ 'peak_refs_display' ] = rule_metric
            rule[ 'build_refs_display' ] = compute_rule_build_refs_display(
                file_entry,
                rule,
                catalog,
            )

    return model
