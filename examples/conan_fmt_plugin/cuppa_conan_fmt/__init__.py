#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

"""Example Cuppa dependency plugin: fmt via Conan 2 (SConsDeps).

Install this package (``pip install -e examples/conan_fmt_plugin``) so Cuppa
discovers the ``fmt`` dependency through the ``cuppa.dependency.plugins``
entry point. Consumer projects can then use::

    cuppa.run(auto_enable_dependencies=['fmt'])

without listing the dependency class in ``cuppa.run(import_dependencies=[…])``.
"""

import cuppa

# ``conan_dependency`` returns a type with ``add_to_env`` / ``create`` /
# ``name`` — the shape Cuppa expects from ``cuppa.dependency.plugins``.
FmtConan = cuppa.conan_dependency(
    'fmt',
    # 12.0+: Clang 21+ / libc++ (fmtlib/fmt#4477). Pin ConanCenter's latest 12.x.
    requires=['fmt/12.1.0'],
)
