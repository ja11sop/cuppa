#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

from cuppa.cpp.profiles_report.constants import UNCLASSIFIED_RULE_ID
from cuppa.cpp.profiles_report.profiles import std_init

_PROFILE_CLASSIFIERS = {
    std_init.PROFILE_NAME: std_init.classify,
}


def classify_rule( profile, normalised_message ):
    """Map ``(profile, normalised_message)`` to a Profiles rule id."""
    classifier = _PROFILE_CLASSIFIERS.get( profile )
    if classifier is None:
        return UNCLASSIFIED_RULE_ID
    return classifier( normalised_message )
