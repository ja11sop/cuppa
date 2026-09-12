#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   External build-system helpers (cmake, later b2, …)
#-------------------------------------------------------------------------------

"""Public helpers for driving external build systems from Cuppa sconscripts.

Prefer ``cuppa.buildsys.cmake`` for CMake argv helpers. Graph methods live in
``cuppa.methods.cmake`` (``env.CMakeConfigure`` / ``CMakeBuild`` / ``CMakeInstall``).
"""
