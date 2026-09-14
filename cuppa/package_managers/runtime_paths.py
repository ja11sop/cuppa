#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   Package runtime search paths (GitLab + Conan)
#-------------------------------------------------------------------------------

"""Prepend package ``lib/`` / ``bin/`` dirs into the construction ``ENV``.

Consumers need these paths so host tools (``protoc``, ``grpc_cpp_plugin``) and
``--test`` / ``--run`` binaries can load shared libraries from a non-system
package prefix. Conan historically did this via ``MergeFlags``; GitLab packages
share the same helper so behaviour cannot diverge.

SCons ``PrependENVPath`` removes an existing occurrence of a path before
prepending (``delete_existing=1``), so repeated ``BuildWith`` apply stays
bounded.
"""

import cuppa.build_platform


def apply_package_runtime_paths( env, lib_dirs=(), bin_dirs=() ):
    """Prepend runtime search paths for package libs and binaries.

    - ``bin_dirs`` → ``PATH`` on every platform
    - ``lib_dirs`` → ``PATH`` on Windows, ``DYLD_LIBRARY_PATH`` on Darwin,
      ``LD_LIBRARY_PATH`` elsewhere

    Empty or ``None`` entries are skipped. Directory existence is not required
    (callers may pass planned layout paths).
    """
    platform_name = cuppa.build_platform.name()

    for path in bin_dirs:
        if path:
            env.PrependENVPath( 'PATH', path )

    if platform_name == 'Windows':
        for path in lib_dirs:
            if path:
                env.PrependENVPath( 'PATH', path )
    elif platform_name == 'Darwin':
        for path in lib_dirs:
            if path:
                env.PrependENVPath( 'DYLD_LIBRARY_PATH', path )
    else:
        for path in lib_dirs:
            if path:
                env.PrependENVPath( 'LD_LIBRARY_PATH', path )
