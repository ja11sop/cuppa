#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

from cuppa.cpp.profiles_report.profiles import std_init

_PROFILE_MODULES = {
    std_init.PROFILE_NAME: std_init,
}


def profile_module( profile_name ):
    return _PROFILE_MODULES.get( profile_name )


def documented_rule_ids_for_profile( profile_name ):
    module = profile_module( profile_name )
    if module is None:
        return []
    documented = getattr( module, 'documented_rule_ids', None )
    if callable( documented ):
        return list( documented() )
    return []
