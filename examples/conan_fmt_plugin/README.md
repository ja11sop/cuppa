# Cuppa dependency plugin: fmt via Conan 2

Thin example package that registers a Conan-backed `fmt` dependency through
the `cuppa.dependency.plugins` entry point. After `pip install` (or
`pip install -e .`), Cuppa discovers it automatically — no
`cuppa.run(dependencies=[…])` list is required.

For the same `fmt` name built from a GitHub archive with `location_dependency`
instead (no Conan), see `examples/cuppa_fmt_plugin/`. Install only one of these
plugins in a given environment — both register the dependency name `fmt`.

See the Cuppa docs: Dependencies (Conan) and Extending cuppa.
