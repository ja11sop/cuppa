#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   Coverage workflow helpers (parallel collection policy)
#-------------------------------------------------------------------------------

from cuppa.log import logger


# Stable token for tests and log greps (must appear in the warning even when colourised).
PARALLEL_COVERAGE_COLLECTION_WARNING = (
    "Collecting coverage with SCons -j is not reliable"
)


def should_warn_parallel_coverage_collection(
        job_count,
        cov=False,
        test=False,
        force_test=False,
        benchmark=False,
        force_benchmark=False,
):
    """True when instrumented tests or benchmarks will run with more than one SCons job.

    Parallel *compile* of the coverage variant (``--cov`` without ``--test``) is
    fine. Parallel *collection* is not: ``.gcda`` files sit beside object files,
    often shared across binaries, and Coverage actions are not isolated per test.
    See ``design/plans/coverage-parallel.md``.
    """
    if not job_count or int( job_count ) <= 1:
        return False
    if not cov:
        return False
    return bool( test or force_test or benchmark or force_benchmark )


def parallel_coverage_collection_warning_text():
    return (
        "{token}. GCC/Clang write .gcda beside object files; those notes are "
        "shared when tests link the same library, and Coverage() can race the "
        "test process that produces them. Build the instrumented tree in parallel, "
        "then collect serially: cuppa -D --cov --parallel then "
        "cuppa -D --cov --test (no --parallel). "
        "https://github.com/ja11sop/cuppa/issues/236"
    ).format( token=PARALLEL_COVERAGE_COLLECTION_WARNING )


def maybe_warn_parallel_coverage_collection(
        job_count,
        cov=False,
        test=False,
        force_test=False,
        benchmark=False,
        force_benchmark=False,
):
    if should_warn_parallel_coverage_collection(
            job_count,
            cov=cov,
            test=test,
            force_test=force_test,
            benchmark=benchmark,
            force_benchmark=force_benchmark,
    ):
        logger.warn( parallel_coverage_collection_warning_text() )
        return True
    return False
