# Cuppa integration tests

Full documentation (generated `sconstruct` / `sconscript`, commands, and expectations) is part of the Antora site:

- **[Integration tests](https://ja11sop.github.io/cuppa/cuppa/integration-tests.html)**
- Source: [`docs/modules/ROOT/pages/integration-tests.adoc`](../../docs/modules/ROOT/pages/integration-tests.adoc)
- Per-scenario pages: [`docs/modules/ROOT/pages/integration/`](../../docs/modules/ROOT/pages/integration/)

## How to run

```sh
pytest -m integration
```

Requires a C++ compiler (`g++` preferred). Companion stubs next to each `test_*.py` link to the matching docs page.
