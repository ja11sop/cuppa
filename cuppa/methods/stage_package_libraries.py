#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   StagePackageLibraries / CollectPackageLibraries
#-------------------------------------------------------------------------------

"""Stage or collect Cuppa package shared libraries for tip programs.

See ``design/plans/package-runtime-deploy.md`` and
``cuppa.package_managers.stage_package_libraries``.
"""

from __future__ import annotations

import cuppa.progress
from cuppa.package_managers.stage_package_libraries import (
        collect_package_libraries,
        stage_package_libraries_for_programs,
)


class StagePackageLibrariesMethod:
    """Copy package shared libs under ``$ORIGIN/lib`` (Windows: beside the exe).

    Also ensures relocatable ORIGIN / ``@loader_path`` RPATH on the program
    nodes. No-op when the env has no shared package link contributions.
    """

    def __call__( self, env, programs, **_kwargs ):
        installed = stage_package_libraries_for_programs( env, programs )
        if not installed:
            return []
        return cuppa.progress.label_terse_action(
                installed, "copy", paths="transfer",
        )


    @classmethod
    def add_to_env( cls, cuppa_env ):
        cuppa_env.add_method( "StagePackageLibraries", cls() )


class CollectPackageLibrariesMethod:
    """Copy package shared libs into an explicit destination (Docker / assembly)."""

    def __call__( self, env, destination, programs=None, **_kwargs ):
        installed = collect_package_libraries(
                env, destination, programs=programs,
        )
        if not installed:
            return []
        return cuppa.progress.label_terse_action(
                installed, "copy", paths="transfer",
        )


    @classmethod
    def add_to_env( cls, cuppa_env ):
        cuppa_env.add_method( "CollectPackageLibraries", cls() )
