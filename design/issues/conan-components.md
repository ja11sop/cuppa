# Conan publisher: `cpp_info.components` / multi-lib selection

- **Status:** issue draft
- **Related:** [`ROADMAP.md`](../../ROADMAP.md) — `conan-publish-recipe`; follows GitHub [#29](https://github.com/ja11sop/cuppa/issues/29)
- **Updated:** 2026-07-30

Not scheduled work. File this as a GitHub issue when the components work is picked up, then
delete this draft.

## Summary

Cuppa’s Conan publisher generates a flat `cpp_info.libs = […]` list. That is enough when every consumer always links every library in the package. This issue tracks **first-class multi-target packages** via Conan components, and clarifies what is already covered without them.

## Background — flat multi-lib (mostly done)

If one package ships `libfoo.a` and `libfoo_util.a` and **every** consumer should link both:

- Cuppa already auto-detects multiple libs under the stage `lib/` dir, or accepts `libs=['foo', 'foo_util']`.
- No components API is required.

Improve flat multi-lib only if we need explicit link **order**, omitting a lib, or different include roots without splitting packages — still often solvable with `libs=` / hand-written `conanfile=`.

## Problem — components

Some products need **one Conan reference** with **independently linkable** sub-targets (CMake-style `pkg::core` / `pkg::net`):

```python
def package_info(self):
    self.cpp_info.components["core"].libs = ["mylib_core"]
    self.cpp_info.components["net"].libs = ["mylib_net"]
    self.cpp_info.components["net"].requires = ["core"]
```

Without components, consumers either link everything or maintain separate Conan packages per library.

## Why Cuppa is not ready for a thin publisher-only change

- Consumer path uses Conan **SConsDeps** and applies aggregated `info['conandeps']` via `MergeFlags`.
- There is **no** Cuppa API today to say “BuildWith this Conan dep but only component `net`”.
- Shipping `components=` on the generated recipe without a consumer selection story is incomplete for the usual Cuppa workflow (hand-written recipes can already declare components for CMake/other generators).

## Work if we take this later

1. **Publisher API** (generated recipe): e.g. `components={'core': {'libs': ['mylib_core']}, 'net': {'libs': ['mylib_net'], 'requires': ['core']}}` or load from a small YAML/JSON beside the sconscript.
2. **Consumer API**: decide how Cuppa selects components — options to evaluate:
   - Document “use hand-written conanfile + non-SConsDeps generator” (weak).
   - Extend `conan_deps` / BuildWith with `components=['net']` and map to SConsDeps / custom flag merging.
   - Prefer **split packages** as the supported Cuppa pattern and only document components for advanced `conanfile=` authors.
3. **Tests:** multi-lib package; consumer links only one component; link failure if wrong component.
4. **Docs:** packages.adoc honesty about SConsDeps aggregation limits.

## Alternatives (prefer until then)

- One Conan package per library (`mylib_core/1.0`, `mylib_net/1.0`) with `requires=` between them.
- Hand-written `conanfile=` with `cpp_info.components` for teams that consume from CMake/other tools primarily.
- Flat `libs=[...]` when always-link-all is acceptable.

## Acceptance criteria (future)

- [ ] Generated or structured API can emit Conan components for a Cuppa-built multi-lib package.
- [ ] A Cuppa consumer can depend on a **subset** of those components without linking unused libs (or we explicitly document that Cuppa only supports always-link-all / split packages).
- [ ] Docs and ROADMAP updated; integration coverage for the chosen consumer model.

## References

- Conan `package_info` / `cpp_info.components`
- Cuppa [`conan-publish-plan.md`](../archive/conan-publish-plan.md), [`cuppa/package_managers/conan.py`](../../cuppa/package_managers/conan.py), [`cuppa/build_with_conan.py`](../../cuppa/build_with_conan.py)
- Related: modules/BMI Conan parity (done; Cuppa-native `modules/` path)
