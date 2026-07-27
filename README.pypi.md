# Cuppa

[![Latest Version](https://img.shields.io/pypi/v/cuppa.svg)](https://pypi.org/project/cuppa/)
[![Boost License](https://img.shields.io/badge/license-Boost-blue.svg)](https://www.boost.org/LICENSE_1_0.txt)

**Cuppa** is an extensible C++ build system on top of [SCons](https://www.scons.org/). It keeps `sconscript` files declarative while handling toolchains, variants, dependencies, tests, and coverage.

```sh
pip install cuppa
```

```python
import cuppa
cuppa.run()
```

```sh
cuppa -D --dbg --test
```

- Source and full docs: https://github.com/ja11sop/cuppa
- Documentation site: https://ja11sop.github.io/cuppa/
- License: [Boost Software License 1.0](https://www.boost.org/LICENSE_1_0.txt)
