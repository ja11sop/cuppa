# Plan: `cuppa.run` accepts dependency objects in `default_dependencies`

- **Status:** proposal
- **Related:** [`ROADMAP.md`](../../ROADMAP.md); [`gitlab-package-latest.md`](../archive/gitlab-package-latest.md) (motivating consume ergonomics); [`dependency-resolve.md`](../archive/dependency-resolve.md) (BuildWith tokens remain strings); `cuppa/construct.py` `_normalise_with_defaults`
- **Updated:** 2026-09-04
- **Impact:** minor — accept dependency factories/classes where names are required today; strings stay valid

## Why

The natural depend-on shape is one object used in both lists:

```python
google_cloud_cpp = cuppa.package_dependency(
    'google_cloud_cpp',
    # ...
)

cuppa.run(
    dependencies = [ google_cloud_cpp ],
    default_dependencies = [ google_cloud_cpp ],
)
```

Today `default_dependencies` effectively wants **names**. Callers must write either
`google_cloud_cpp.name()` (preferred, less error-prone) or a duplicated string
`'google_cloud_cpp'`. That is easy to mistype and clutters every sconstruct that registers a
custom package or location dependency.

The same friction appears for profiles if callers hold profile factories and must pass name
strings into `default_profiles`.

## Goals

1. Accept **dependency objects** (and equivalently callables / classes that expose `.name()`)
   in `default_dependencies`, normalising to the registry name before `BUILD_WITH` / listing.
2. Keep **strings** (and typed BuildWith tokens if ever used here) fully supported —
   backwards compatible.
3. Prefer documenting the object form as the primary teach path once shipped.
4. Apply the same normalisation to `dependencies=` entries that are already objects (already
   typical) and to `default_profiles` / `profiles` if the same pattern applies with negligible
   extra scope.

## Non-goals

- Changing BuildWith resolve / type selectors ([`dependency-resolve.md`](../archive/dependency-resolve.md)).
- Requiring objects everywhere (strings remain first-class).
- Auto-adding every `dependencies=` entry to `default_dependencies` (explicit default list stays).

## Settled decisions (proposed)

| Topic | Decision |
|-------|----------|
| Object in `default_dependencies` | Call `.name()` (classmethod or instance) to obtain the registry key; reject with a clear error if no name can be derived. |
| String in `default_dependencies` | Unchanged. |
| Mix of objects and strings | Allowed in one list. |
| `dependencies=` | Continue to accept factories/classes as today; ensure normalisation is shared so object→name is one code path. |
| `default_profiles` | Same object-or-string normalisation if profiles already expose `.name()` — confirm in implementation. |
| Docs | Update package consume examples to pass the object into both lists; keep `.name()` as an explicit alternative. |

## Ideal example (target docs)

```python
google_cloud_cpp = cuppa.package_dependency(
    'google_cloud_cpp',
    registry = 'https://git.example.com/api/v4/projects/registry',
    package  = 'google-cloud-cpp',
    version  = 'latest',
)

cuppa.run(
    dependencies = [ google_cloud_cpp ],
    default_dependencies = [ google_cloud_cpp ],
)
```

## Work slices

| ID | Slice | Notes |
|----|--------|-------|
| `run-dep-obj-rules` | This plan | **This change** |
| `run-dep-obj-normalise` | Shared coerce-to-name for run() dependency/profile lists; unit tests | |
| `run-dep-obj-docs` | packages / gitlab / methods examples | With or after normalise |
| `run-dep-obj-issue` | File `impact:minor` issue when implementing | |

## Refusal rules

- Do not break existing string `default_dependencies`.
- Do not invent a second registration API; only widen what `cuppa.run` accepts.
- Do not silently ignore objects that lack a resolvable name.

## Progress snapshot

| Slice | Status |
|-------|--------|
| `run-dep-obj-rules` | Done (this document) |
| Remaining | Not started |

## Open questions

- Exact type check: `callable` + `.name`, class with `name()`, or duck-typing only?
- Whether `default_dependencies = dependencies` (aliasing the same list) should be documented as
  supported once objects work.
