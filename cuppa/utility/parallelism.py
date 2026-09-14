#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   Parallel job count helpers
#-------------------------------------------------------------------------------

"""How many CPUs Cuppa should treat as available under ``--parallel``.

The ``cuppa`` entry point may shrink process affinity (leave cores free for the
OS). Automatic ``-j`` / ``cmake --build --parallel`` must use that restricted
set, not raw ``cpu_count()``, or the log and tool ``-j`` disagree with affinity.
"""

import multiprocessing
import os


def effective_cpu_count():
    """Return CPUs available to this process (affinity-aware), else logical count.

    Prefers ``os.sched_getaffinity`` (Linux), then ``psutil`` CPU affinity, then
    ``multiprocessing.cpu_count()``.
    """
    try:
        return len( os.sched_getaffinity( 0 ) )
    except ( AttributeError, OSError ):
        pass
    try:
        import psutil
        affinity = psutil.Process().cpu_affinity()
        if affinity:
            return len( affinity )
    except Exception:
        pass
    return multiprocessing.cpu_count()
