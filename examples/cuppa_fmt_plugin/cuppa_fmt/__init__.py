#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

"""Example Cuppa dependency plugin: fmt via ``location_dependency``.

Install this package (``pip install -e examples/cuppa_fmt_plugin``) so Cuppa
discovers ``fmt`` through ``cuppa.dependency.plugins``. Consumer projects can
then use::

    cuppa.run(default_dependencies=['fmt'])

without listing the dependency class in ``cuppa.run(dependencies=[…])``.

This builds {fmt} from a pinned GitHub archive (not Conan). Prefer
``examples/conan_fmt_plugin`` when you want ConanCenter binaries instead.
"""

import cuppa


class fmt(
    cuppa.location_dependency(
        'fmt',
        sys_include='include',
        # 12.2.0+ includes <cstdlib> so malloc/free are declared under
        # Clang + libc++ (see fmtlib/fmt#4477). 11.1.4 fails on that combo.
        location='https://github.com/fmtlib/fmt/archive/refs/tags/12.2.0.zip',
        linktype='static',
    )
):
    """Fetch fmt, compile its sources, and append a static library to the env."""

    def __call__( self, env, toolchain, variant ):
        super( fmt, self ).__call__( env, toolchain, variant )
        sources = env.Glob( self.local_sub_path( 'src/format.cc' ) )
        sources += env.Glob( self.local_sub_path( 'src/os.cc' ) )
        library = self.build_library_from_source( env, sources, 'fmt' )
        env.AppendUnique( STATICLIBS=[ library ] )
