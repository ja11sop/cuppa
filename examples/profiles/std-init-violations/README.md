# std::init violation fixture

Multi-file example under `examples/profiles/std-init-violations/` that deliberately
violates each documented `std::init` rule from
[P4222](https://wg21.link/P4222) and
[ProfilesFramework.rst](https://github.com/cppalliance/clang/blob/profiles-framework/clang/docs/ProfilesFramework.rst).
Use it to capture Alliance Clang diagnostic text for classifier tables, golden tests, and
the Antora pages under `docs/modules/ROOT/pages/cxx-profiles/std-init/`.

## Layout

| Source | Rule id(s) |
|--------|------------|
| `uninit_decl.cpp` | `uninit_decl` |
| `static_runtime_init.cpp` | `static_runtime_init` |
| `ctor_uninit_member.cpp` | `ctor_uninit_member` |
| `ref_to_uninit.cpp` | `ref_to_uninit` |
| `uninit_read.cpp` | `uninit_read` |
| `uninit_write.cpp` | `uninit_write` |
| `marker_rules.cpp` | `pointer_marker`, `union_marker`, `static_marker`, `uninit_with_initializer` |
| `destroy_rules.cpp` | `destroy_uninit`, `double_destroy` |

Each file uses the **Readable style** layout described in `AGENTS.md`: section markers,
snake_case types, spaces inside call parentheses.

## Prerequisites

- A Profiles-capable Clang toolchain archive registered with cuppa (see
  xref:toolchains/clang.adoc[Clang] and `design/archive/cxx-profiles.md`).
- Cuppa with `--cxx-profiles`, `--cxx-profiles-enforce=std::init`, and
  `--cxx-disable-error-limit`.

## Build files

This directory is a self-contained cuppa project:

* `sconstruct` — calls `cuppa.run()` with the debug variant.
* `sconscript` — builds the `profiles_std_init_violations` program from every `.cpp` file.

The build is **expected to fail** during compilation because every translation unit contains
 deliberate profile violations.

## Running the example

Run commands from **this directory** (`examples/profiles/std-init-violations/`), not from the
cuppa repository root.

### Installed cuppa (recommended)

Install cuppa into your virtualenv once (editable install is fine while developing cuppa
itself):

```bash
python3 -m venv ~/.venv/cuppa
source ~/.venv/cuppa/bin/activate
pip install -U pip
pip install -e /path/to/cuppa
```

Then build from the example directory:

```bash
cd /path/to/cuppa/examples/profiles/std-init-violations
cuppa -D --dbg --offline \
  --toolchains=clang24_profiles_2026_08_07_27 \
  --cxx-profiles --cxx-profiles-enforce=std::init \
  --cxx-disable-error-limit -i
```

Replace the toolchain name with your registered Profiles archive session.

### Cuppa developers (`PYTHONPATH`)

If you invoke cuppa from a checkout **without** installing it, set `PYTHONPATH` to the
repository root and run from this example directory. Do **not** rely on `pip install -e .`
from inside the cuppa tree while also passing `PYTHONPATH=.` from the repo root — that
mixes import paths and can load stale modules.

```bash
cd /path/to/cuppa/examples/profiles/std-init-violations
PYTHONPATH=/path/to/cuppa cuppa -D --dbg --offline \
  --toolchains=clang24_profiles_2026_08_07_27 \
  --cxx-profiles --cxx-profiles-enforce=std::init \
  --cxx-disable-error-limit -i
```

## Capturing diagnostics for golden tests

From the cuppa repository root:

```bash
python3 scripts/capture_profiles_std_init_example.py \
  --toolchain=clang24_profiles_2026_08_07_27
```

Refresh `tests/fixtures/profiles_capture/std_init_golden.json` after a clean build:

```bash
cd examples/profiles/std-init-violations
rm -rf _build
PYTHONPATH=/path/to/cuppa cuppa -D --dbg --offline \
  --cxx-profiles --cxx-profiles-enforce=std::init \
  --cxx-disable-error-limit \
  --toolchains=clang24_profiles_2026_08_07_27 -i 2>&1 \
  | PYTHONPATH=/path/to/cuppa python3 ../../scripts/build_std_init_golden.py \
    > ../../tests/fixtures/profiles_capture/std_init_golden.json
```

Unit tests in `tests/unit/test_profiles_report_std_init.py` assert golden lines parse to the
expected `(profile, rule_id)` pairs.

## Destroy rules and toolchain gaps

`destroy_rules.cpp` contains the ProfilesFramework patterns for `destroy_uninit` and
`double_destroy`. The `profiles_2026_08_07_27` Alliance Clang snapshot may still report
`ref_to_uninit` at those call sites instead of the documented destroy diagnostics. Golden
entries for the destroy rules use documented Clang wording until a newer snapshot emits them
live; see `DOCUMENTED_RULE_IDS_AWAITING_LIVE_CAPTURE` in
`cuppa/cpp/profiles_report/profiles/std_init.py`.
