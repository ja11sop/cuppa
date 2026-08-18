#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   Session-wide HTML report options (--reports-link-style)
#-------------------------------------------------------------------------------

from cuppa.reports.link_style import (
    REPORTS_HOST_ENV_KEYS,
    REPORT_LINK_STYLES,
    parse_host_list,
)


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
        add_option(
            '--reports-remote-provider-hints',
            dest='reports_remote_provider_hints',
            action='store_true',
            default=None,
            help='When remote link_style hits an unmapped host, append GH/GL/BB/GT/AD '
                 'hint links that try common provider URL shapes',
        )
        add_option(
            '--no-reports-remote-provider-hints',
            dest='reports_remote_provider_hints',
            action='store_false',
            help='Disable provider hint links for unmapped remote hosts',
        )
        for provider, env_key in REPORTS_HOST_ENV_KEYS.items():
            flag = '--{}='.format( env_key.replace( '_', '-' ) )
            provider_label = provider.replace( '_', ' ' )
            add_option(
                flag,
                dest=env_key,
                default=None,
                help='Extra ' + provider_label + ' host suffixes for remote link_style '
                     '(comma-separated; defaults still apply)',
            )

    @classmethod
    def get_options( cls, env ):
        link_style = env.get_option( 'reports_link_style' )
        if link_style:
            env[ 'reports_link_style' ] = link_style

        hints = env.get_option( 'reports_remote_provider_hints' )
        if hints is not None:
            env[ 'reports_remote_provider_hints' ] = hints

        for env_key in REPORTS_HOST_ENV_KEYS.values():
            raw = env.get_option( env_key )
            parsed = parse_host_list( raw )
            if parsed:
                env[ env_key ] = parsed

    @classmethod
    def add_to_env( cls, cuppa_env ):
        pass
