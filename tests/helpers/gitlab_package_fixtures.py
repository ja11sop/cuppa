#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

"""Offline GitLab package extract fixtures (no live registry)."""

from pathlib import Path

from cuppa.package_managers.cuppa_dependency_manifest import write_manifest


def plant_transitive_gitlab_chain( storage, tool_variant="gcc153_rel_x86_64_cxx2c" ):
    """Plant alpha → beta → gamma extracts with ``cuppa-dependency.json``.

    Headers form an include chain (``alpha.hpp`` → ``beta.hpp`` → ``gamma.hpp``)
    so a consumer that only ``BuildWith('alpha')`` can compile against all three
    include paths when transitive apply works.
    """
    storage = Path( storage )
    deps = storage / "dependencies"
    alpha = deps / tool_variant / "alpha" / "1.0.0"
    beta = deps / tool_variant / "beta" / "2.0.0"
    gamma = deps / tool_variant / "gamma" / "3.0.0"

    ( alpha / "include" ).mkdir( parents=True )
    ( beta / "include" ).mkdir( parents=True )
    ( gamma / "include" ).mkdir( parents=True )

    ( gamma / "include" / "gamma.hpp" ).write_text(
            "#pragma once\ninline int gamma_value() { return 3; }\n",
            encoding="utf-8",
    )
    ( beta / "include" / "beta.hpp" ).write_text(
            "#pragma once\n#include <gamma.hpp>\n"
            "inline int beta_value() { return gamma_value() + 1; }\n",
            encoding="utf-8",
    )
    ( alpha / "include" / "alpha.hpp" ).write_text(
            "#pragma once\n#include <beta.hpp>\n"
            "inline int alpha_value() { return beta_value() + 1; }\n",
            encoding="utf-8",
    )

    write_manifest(
            str( alpha ),
            [
                    {
                            "name": "beta",
                            "package": "beta",
                            "version": "2.0.0",
                            "registry": "same",
                            "use_libs": ["beta"],
                    },
            ],
    )
    write_manifest(
            str( beta ),
            [
                    {
                            "name": "gamma",
                            "package": "gamma",
                            "version": "3.0.0",
                            "registry": "same",
                            "use_libs": ["gamma"],
                    },
            ],
    )
    return {
            "tool_variant": tool_variant,
            "alpha": alpha,
            "beta": beta,
            "gamma": gamma,
    }
