# Profiles std::init violation fixture

Minimal example that deliberately violates several documented `std::init` rules so you can
capture Alliance Clang diagnostic text for classifier tables and golden tests.

## Prerequisites

- A Profiles-capable Clang toolchain archive (see `design/archive/cxx-profiles.md`).
- Cuppa with `--cxx-profiles`, `--cxx-profiles-enforce=std::init`, and
  `--cxx-disable-error-limit`.

## Capturing diagnostic lines

From this directory:

```bash
cuppa -D --dbg --offline \
  --toolchains=<your_profiles_clang_archive> \
  --cxx-profiles --cxx-profiles-enforce=std::init \
  --cxx-disable-error-limit --cxx-profiles-report -i
```

Copy representative ` under profile 'std::init'` lines into
`tests/fixtures/profiles_capture/std_init_golden.json` (one entry per rule id). Unit tests in
`tests/unit/test_profiles_report_std_init.py` assert the golden lines parse to the expected
`(profile, rule_id)` pairs.

## Documented rules not yet in the golden file

`cuppa/cpp/profiles_report/profiles/std_init.py` lists additional P4222 / ProfilesFramework.rst
rule ids (`uninit_read`, `destroy_uninit`, …) awaiting capture from extended examples or live
trees. Extend `violations.cpp` when Clang emits new message shapes.
