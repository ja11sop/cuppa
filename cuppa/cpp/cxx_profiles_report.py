#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   Backward-compatible import path — prefer ``cuppa.cpp.profiles_report``
#-------------------------------------------------------------------------------

from cuppa.cpp.profiles_report import *  # noqa: F401,F403 pylint: disable=wildcard-import,unused-wildcard-import

from cuppa.cpp.profiles_report import __all__  # noqa: F401
