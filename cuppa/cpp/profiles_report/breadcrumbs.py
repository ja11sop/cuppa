#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   C++ Profiles report — breadcrumb trails for HTML pages
#-------------------------------------------------------------------------------

INDEX_SCOPES_FRAGMENT = '#scopes'
INDEX_ROLLUP_FILES_FRAGMENT = '#rollup-files'


def _crumb( label, href=None, *, monospace=False, active=False ):
    return {
        'label': label,
        'href': href,
        'monospace': monospace,
        'active': active,
    }


def scope_breadcrumbs( index_name, scope ):
    """Return breadcrumb crumbs for a per-scope report page."""
    variant_label = '{} ({})'.format(
        scope[ 'variant_display' ],
        scope[ 'toolchain' ],
    )
    return [
        _crumb( 'Profiles report', href=index_name ),
        _crumb(
            scope[ 'sconscript' ],
            href='{}{}'.format( index_name, INDEX_SCOPES_FRAGMENT ),
            monospace=True,
        ),
        _crumb( variant_label, monospace=True, active=True ),
    ]


def source_breadcrumbs(
    index_href,
    display_path,
    title_split=False,
    title_prefix='',
    title_suffix='',
):
    """Return breadcrumb crumbs for a marked-up source file page."""
    rollup_href = '{}{}'.format( index_href, INDEX_ROLLUP_FILES_FRAGMENT )
    crumbs = [
        _crumb( 'Profiles report', href=index_href ),
        _crumb( 'By source', href=rollup_href ),
    ]
    if title_split:
        crumbs.append( _crumb( title_prefix, monospace=True ) )
        crumbs.append( _crumb( title_suffix, monospace=True, active=True ) )
    else:
        crumbs.append( _crumb( display_path, monospace=True, active=True ) )
    return crumbs
