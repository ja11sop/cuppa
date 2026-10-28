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

``--parallel`` / ``--parallel=N`` option values are normalised here so construct
and the wrapper share one spelling.
"""

import multiprocessing
import os
from collections import namedtuple


ParallelRequest = namedtuple(
        'ParallelRequest',
        ( 'enabled', 'jobs' ),
)
"""``enabled`` is True when Cuppa affinity / parallel mode is on.

``jobs`` is ``None`` for bare ``--parallel`` (auto count) or a positive int for
``--parallel=N``.
"""


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


def argv_requests_parallel( args ):
    """True when argv enables Cuppa ``--parallel`` (bare or ``--parallel=N``)."""
    for arg in args:
        if not isinstance( arg, str ):
            continue
        if arg == '--parallel' or arg.startswith( '--parallel=' ):
            return True
    return False


def parse_parallel_option( value ):
    """Normalise the SCons ``--parallel`` option value.

    Registration uses ``nargs='?'`` with ``const='auto'`` so:

    * absent → ``None`` → disabled
    * ``--parallel`` → ``'auto'`` → enabled, auto job count
    * ``--parallel=N`` → ``'N'`` → enabled, explicit count (``N >= 1``)

    Space form ``--parallel 12`` is **not** consumed as a value by SCons (the
    ``12`` stays a target); prefer ``--parallel=12`` in docs.

    Returns :class:`ParallelRequest`. Raises ``ValueError`` with an operator
    message when the value is not a positive integer.
    """
    if value is None or value is False:
        return ParallelRequest( False, None )
    if value is True:
        # Legacy store_true / tests that still pass a bool.
        return ParallelRequest( True, None )
    if isinstance( value, int ):
        if value < 1:
            raise ValueError(
                    "--parallel count must be an integer >= 1 (got {})".format( value )
            )
        return ParallelRequest( True, value )
    text = str( value ).strip()
    if text in ( '', 'auto' ):
        # Bare ``--parallel`` stores const ``auto``. Empty ``--parallel=`` is
        # rejected as unclear.
        if text == '':
            raise ValueError(
                    "--parallel= requires a positive integer (use bare --parallel for auto)"
            )
        return ParallelRequest( True, None )
    try:
        count = int( text, 10 )
    except ( TypeError, ValueError ):
        raise ValueError(
                "--parallel=N requires a positive integer (got {!r})".format( value )
        )
    if count < 1:
        raise ValueError(
                "--parallel count must be an integer >= 1 (got {})".format( count )
        )
    return ParallelRequest( True, count )


def resolve_parallel_job_count( request, num_jobs, effective_cpus=None ):
    """Choose the SCons / CMake job count for a parallel request.

    ``num_jobs`` is the current SCons ``num_jobs`` option (default ``1``).

    * ``--parallel=N`` with ``--jobs`` / ``-j`` also set (``num_jobs != 1``) →
      ``ValueError`` (conflict; prefer one spelling).
    * ``--parallel=N`` alone → ``N`` (may exceed affinity; caller may warn).
    * bare ``--parallel`` with ``num_jobs == 1`` → ``effective_cpus`` (auto).
    * bare ``--parallel`` with ``num_jobs != 1`` → keep ``num_jobs``
      (``--parallel --jobs=M``).
    * parallel disabled → ``num_jobs`` unchanged.

    Returns ``(job_count, mode)`` where ``mode`` is ``\"automatically\"``,
    ``\"manually\"``, or ``\"explicit\"`` (``--parallel=N``).
    """
    if not request.enabled:
        return int( num_jobs ), "manually"

    jobs_opt = int( num_jobs )
    if request.jobs is not None:
        if jobs_opt != 1:
            raise ValueError(
                    "do not combine --parallel={} with --jobs={} / -j; "
                    "pass --parallel={} alone (affinity + count) or "
                    "--parallel --jobs={}".format(
                            request.jobs, jobs_opt, request.jobs, jobs_opt,
                    )
            )
        return request.jobs, "explicit"

    if jobs_opt == 1:
        if effective_cpus is None:
            effective_cpus = effective_cpu_count()
        return int( effective_cpus ), "automatically"

    return jobs_opt, "manually"
