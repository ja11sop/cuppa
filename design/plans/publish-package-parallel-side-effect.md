# Plan: `PublishPackage` archive as SCons SideEffect under `--parallel`

- **Status:** in progress
- **Related:** [#317](https://github.com/ja11sop/cuppa/issues/317); [#318](https://github.com/ja11sop/cuppa/issues/318); shipped [#319](https://github.com/ja11sop/cuppa/pull/319); [`ROADMAP.md`](../../ROADMAP.md) — `publish-package-parallel`; [`manage_packages.py`](../../cuppa/methods/manage_packages.py) (`PublishPackageMethod`, `publish_package_sources`); [`gitlab.py`](../../cuppa/package_managers/gitlab.py) (`build_package`, `package_archive`); BMI precedent [`cxx_modules.py`](../../cuppa/cpp/cxx_modules.py) / [`gcc.py`](../../cuppa/toolchains/gcc.py); distinct from [`parallel-job-count.md`](parallel-job-count.md) ([#298](https://github.com/ja11sop/cuppa/issues/298)); soak context [`../archive/cascade-defer-404.md`](../archive/cascade-defer-404.md) / [#316](https://github.com/ja11sop/cuppa/pull/316)
- **Updated:** 2026-09-21
- **Impact:** `patch`

## Problem

Deep publisher soaks (e.g. project D cascade) need `--parallel --jobs=N` for compile time.
`--publish-package` under `-j` can fail immediately after a successful archive create:

```text
Package […/final/<pkg>_….tar.gz] created
scons: *** [….published] Source `…/final/<pkg>_….tar.gz' not found, needed by target `….published'.
```

Observed on nested cascade session 1 (`abseil_cpp`) while soaking Slice F. The
archive was on disk after the failure; SCons had raced the publish source check.

## Cause

| Piece | Role |
|-------|------|
| `env.Command( .packaged, …, build_package )` | Declared target is the stamp only |
| `build_package` | Writes `.tar.gz` / `.zip` then `Touch`es `.packaged` |
| `publish_package_sources` | Lists `.packaged` **and** the archive so MD5-timestamp retars invalidate upload |
| Archive File node | **Not** a Command target and **not** an `env.SideEffect` of `.packaged` |

With `-j`, SCons can treat the missing archive as a required source with no producer
and stop before packaging finishes. Serial builds hide the race.

## Settled approach

Declare the archive as a side effect of the package Command (same pattern as BMI
side effects):

```python
built_package = env.Command( package, [ source, publisher.sources() ], publisher.build_package )
# …
archive = getattr( publisher, "package_archive", None )
if callable( archive ):
    path = archive()
    if path is not None:
        env.SideEffect( env.File( path ) if not hasattr( path, "get_path" ) else path, built_package )
```

Keep `publish_package_sources` as-is (invalidation still needs the archive as a
publish source). Do **not** make the archive the sole Command target — the
`.packaged` stamp contract stays.

## Verification

- Unit: graph wiring asserts `SideEffect` registration when `package_archive` is set
  (mock env), plus existing `publish_package_sources` tests unchanged
- Integration: `--publish-package --parallel` on a small package fixture (widget-scale)
- Soak: re-run project D cascade with `--parallel --jobs=12` after the fix

## Workaround (until shipped)

None needed after [#319](https://github.com/ja11sop/cuppa/pull/319) — live soak under
`--publish-package --parallel` succeeded (2026-09-21).

## Non-goals

- `--parallel=N` CLI spelling ([#298](https://github.com/ja11sop/cuppa/issues/298))
- Changing cascade session parallelism across nested cuppa processes
- Lazy fetch / Slice F defer-404 behaviour

## Progress snapshot

| Item | State |
|------|--------|
| Settled approach (SideEffect) | Done |
| Code + unit tests | Done on [#319](https://github.com/ja11sop/cuppa/pull/319) |
| Live soak with `--publish-package --parallel` | **Done** 2026-09-21 |
