# Cuppa dependency plugin: fmt from source (location_dependency)

Thin example package that registers an ``fmt`` dependency by subclassing
``cuppa.location_dependency``, fetching {fmt} from GitHub, building a static
library from ``src/format.cc`` / ``src/os.cc``, and linking it into consumers.

This is the non-Conan supply chain. For a Conan-backed ``fmt`` plugin instead,
see ``examples/conan_fmt_plugin/``. Both examples register the dependency name
``fmt`` — install only one of them in a given environment.

See the Cuppa docs: Extending cuppa (pip dependency plugins).
