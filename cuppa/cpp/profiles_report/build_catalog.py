#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

"""Build inventory keys and display ids shared by Overview and roll-up tables."""

from cuppa.cpp.profiles_report.report_html import variant_display_from_dir


def build_key_from_scope( scope ):
    """Return the stable ``(variant_label, variant_display_tail, toolchain)`` tuple."""
    variant_display = variant_display_from_dir( scope.variant_dir )
    display_parts = variant_display.split( '/', 1 )
    variant_label = scope.variant_label or display_parts[ 0 ]
    variant_display_tail = display_parts[ 1 ] if len( display_parts ) > 1 else ''
    return ( variant_label, variant_display_tail, scope.toolchain )


def build_key_from_scope_dict( scope ):
    """Return ``build_key`` from a serialised scope dict."""
    variant_display = variant_display_from_dir( scope.get( 'variant_dir', '' ) )
    display_parts = variant_display.split( '/', 1 )
    variant_label = scope.get( 'variant_label', display_parts[ 0 ] )
    variant_display_tail = display_parts[ 1 ] if len( display_parts ) > 1 else ''
    toolchain = scope.get( 'toolchain', '' )
    return ( variant_label, variant_display_tail, toolchain )


def build_label_from_key( build_key ):
    """Human-readable build label for tooltips."""
    variant_label, variant_display_tail, toolchain = build_key
    if variant_display_tail:
        return '{}/{} — {}'.format(
            variant_label,
            variant_display_tail,
            toolchain,
        )
    return '{} — {}'.format( variant_label, toolchain )


def assign_build_display_ids( rows ):
    """Assign ``build_id`` values such as ``dbg1``, ``rel2`` in stable sort order."""
    counters = {}
    for row in rows:
        label = row.get( 'variant_label' ) or ''
        counters[ label ] = counters.get( label, 0 ) + 1
        row[ 'build_id' ] = '{}{}'.format( label, counters[ label ] )
        row[ 'build_label' ] = build_label_from_key( row[ 'build_key' ] )


def build_catalog_from_scopes( scopes ):
    """Ordered build inventory rows for the session."""
    rows_by_key = {}
    for scope in scopes:
        build_key = build_key_from_scope_dict( scope )
        if build_key in rows_by_key:
            continue
        variant_label, variant_display_tail, toolchain = build_key
        rows_by_key[ build_key ] = {
            'build_key': list( build_key ),
            'variant_label': variant_label,
            'variant_display_tail': variant_display_tail,
            'toolchain': toolchain,
        }
    rows = sorted(
        rows_by_key.values(),
        key=lambda entry: (
            entry[ 'variant_label' ],
            entry[ 'variant_display_tail' ],
            entry[ 'toolchain' ],
        ),
    )
    assign_build_display_ids( rows )
    return rows


def catalog_lookup( catalog ):
    """Map ``build_key`` tuple → catalog entry."""
    lookup = {}
    for entry in catalog:
        lookup[ tuple( entry[ 'build_key' ] ) ] = entry
    return lookup
