# Cuppa dependency plugin: fmt via Conan 2

Thin example package that registers a Conan-backed `fmt` dependency through
the `cuppa.dependency.plugins` entry point. After `pip install` (or
`pip install -e .`), Cuppa discovers it automatically — no
`cuppa.run(dependencies=[…])` list is required.

See the Cuppa docs: Dependencies (Conan) and Extending cuppa.
