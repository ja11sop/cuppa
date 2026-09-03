
#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   Stable public Antora URLs for generated Profiles reports
#-------------------------------------------------------------------------------

"""Canonical published-docs prefix after multi-version Pages.

Unversioned paths such as ``/cuppa/cuppa/cxx-profiles/…`` 404 once the site
uses ``latest_version_segment: latest``. Reports must link the durable
``/cuppa/latest/…`` tree so they track the current release, not a missing
unversioned URL.
"""

CUPPA_DOCS_SITE = 'https://ja11sop.github.io/cuppa'
CUPPA_DOCS_STABLE_BASE = CUPPA_DOCS_SITE + '/cuppa/latest'
