#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   Session-wide HTML report options (--reports-link-style)
#-------------------------------------------------------------------------------

from cuppa.reports.link_style import REPORT_LINK_STYLES


class ReportsLinkStyleMethod:
    """Session-wide source link style for HTML reports."""

    @classmethod
    def add_options( cls, add_option ):
        add_option(
            '--reports-link-style',
            dest='reports_link_style',
            default=None,
            choices=list( REPORT_LINK_STYLES ),
            help='Source link targets for HTML reports this session emits '
                 '(local, gitlab, github, or remote; overridden per report where a '
                 'report-specific link-style flag exists)',
        )

    @classmethod
    def get_options( cls, env ):
        link_style = env.get_option( 'reports_link_style' )
        if link_style:
            env[ 'reports_link_style' ] = link_style

    @classmethod
    def add_to_env( cls, cuppa_env ):
        pass
