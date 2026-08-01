# Plan: SCons Tool → Cuppa dependency wrapper (#27)

- **Status:** proposal
- **Related:** [`ROADMAP.md`](../../ROADMAP.md) — SCons Tool dependencies; GitHub [#27](https://github.com/ja11sop/cuppa/issues/27)
- **Updated:** 2026-07-30

This is also the paste-ready summary for issue #27.

## Problem

SCons Tools (for example Qt) already know how to imbue an environment with flags, builders, and emitters.
Cuppa has a richer model (variants, toolchains, `BuildWith`, location/package deps, plugins).
Today, bridging a Tool into Cuppa means hand-writing a full dependency class (see in-tree `build_with_qt4` / `build_with_qt5`).

Issue #27 asks for a **reusable wrapper facility** so an existing Tool can be declared once, used as `env.BuildWith('name')`, and optionally shipped as a **pip-installable** package discovered via `cuppa.dependency.plugins`.

## Goals

1. **Facility** — Public factory (working name `cuppa.scons_tool_dependency(...)`) that produces a Cuppa dependency class with the usual shape: `add_options` / `add_to_env` / `create` / `__call__(env, toolchain, variant)` / `name` / identity helpers.
2. **Apply Tool** — In `__call__`, invoke `SCons.Script.Tool(tool_name, toolpath=…)(env)` so the Tool’s builders and variables appear on the Cuppa variant env.
3. **Hooks** — Optional `prepare(env)` (detect install dirs, set `QTnDIR`, etc.) and `after(env, toolchain, variant)` (e.g. `MergeFlags('-fPIC')`) so Tool-specific logic stays outside the core facility.
4. **Tool provenance** — Support Tool modules already on `toolpath` / `PYTHONPATH`, and optionally fetch a Tool tree via `cuppa.location.Location` (as Qt does today with `scons_qt5`).
5. **Pip plugins** — Document packaging a thin wrapper that registers under `cuppa.dependency.plugins` so `pip install cuppa-foo-tool` + `requirements.txt` is enough for Cuppa to auto-discover it (same path as existing method/profile plugins in `construct.py`).
6. **Tests & docs** — Unit test with a tiny fake Tool (no Qt in CI); Antora docs under extending / dependencies; roadmap IDs `scons-tool-dep`, `scons-tool-pip`, `scons-tool-tests`.

## Non-goals

- Rewriting upstream Tools as Cuppa-native code.
- Auto-scanning the filesystem for undeclared Tools.
- Making every SCons Tool a first-class Cuppa package in this repository.
- Flipping defaults for in-tree Qt behaviour in the first PR (migration is a follow-up).

## Design sketch

```text
sconscript / plugin package
        |
        v
scons_tool_dependency(name, tool=..., toolpath|location=..., prepare=..., after=...)
        |
        v
Cuppa dependency factory  --add_dependency-->  env['dependencies'][name]
        |
        v
env.BuildWith('name')  -->  prepare(env)  -->  Tool(...)(env)  -->  after(env, toolchain, variant)
```

### Suggested public API (illustrative)

```python
from cuppa import scons_tool_dependency

qt5 = scons_tool_dependency(
    'qt5',
    tool='qt5',
    location='hg+https://…/scons_qt5',  # optional; or toolpath=[...]
    extra_sub_path='qt5',
    prepare=_detect_qt5dir,             # optional callable(env) -> None
    after=_qt5_after,                   # optional callable(env, toolchain, variant)
    sys_includes=lambda env: [env['QT5DIR']],  # optional
)

cuppa.run(dependencies=[qt5], default_dependencies=['qt5'])
```

Pip package `setup.cfg` / `pyproject.toml`:

```ini
[options.entry_points]
cuppa.dependency.plugins =
    qt5 = my_cuppa_qt5:qt5_dependency_class
```

`construct.py` already loads `cuppa.dependency.plugins` and calls `add_to_env(cuppa_env, add_dependency)`.

### Mapping from Qt today

| Qt wrapper step | Facility |
|-----------------|----------|
| `retrieve_tool` + `Location` | `location=` / `extra_sub_path=` |
| Detect `QTnDIR` / pkg-config | `prepare=` |
| `Tool('qtN', toolpath=…)(env)` | core `__call__` |
| `MergeFlags('-fPIC')` | `after=` |
| `sys_includes` | optional hook / attribute |

## Implementation phases

### Phase A — Core facility (ship)

1. Add module (e.g. `cuppa/build_with_scons_tool.py`) implementing the factory and dependency class.
2. Export from `cuppa/__init__.py` beside `location_dependency` / `package_dependency`.
3. Unit tests: fake Tool under a temp `toolpath` that sets a sentinel env var / builder; assert `BuildWith` applies it per variant.
4. Docs: extending.adoc + dependencies.adoc — “Wrapping a SCons Tool”, pip entry-point example, contrast with hand-written deps.
5. CHANGELOG Unreleased; keep ROADMAP IDs in sync.

### Phase B — Pip packaging guide

1. Document a minimal third-party layout (`pyproject.toml`, entry point, thin module that only calls `scons_tool_dependency`).
2. Optional: `examples/scons_tool_plugin/` smoke (no publish required).

### Phase C — Migrate in-tree Qt (follow-up)

1. Refactor `build_with_qt4` / `build_with_qt5` to use the facility + prepare/after hooks.
2. Behaviour should remain equivalent; treat detection edge cases carefully.
3. Only after Phase A is stable.

## Acceptance criteria

- [ ] Public factory usable from `sconstruct` / `cuppa.run(dependencies=[…])`.
- [ ] `env.BuildWith(name)` applies the named Tool on each active variant env.
- [ ] Fake-Tool unit (and/or integration) test passes on Linux CI without Qt.
- [ ] Docs describe in-tree use and pip `cuppa.dependency.plugins` packaging.
- [ ] ROADMAP section **SCons Tool dependencies** reflects shipped vs remaining IDs.
- [ ] Issue #27 updated with this plan; closed or left open until Phase A lands (maintainer choice).

## References

- In-tree: `cuppa/dependencies/build_with_qt4.py`, `build_with_qt5.py`
- Plugin load: `cuppa/construct.py` (`cuppa.dependency.plugins`)
- Entry points helper: `cuppa/utility/entry_points.py`
- Extending docs: `docs/modules/ROOT/pages/extending.adoc`
- Roadmap: `ROADMAP.md` § SCons Tool dependencies
