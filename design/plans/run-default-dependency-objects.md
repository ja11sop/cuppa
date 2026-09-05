# Plan: `cuppa.run` accepts dependency objects in `default_dependencies`

- **Status:** proposal
- **Related:** [`ROADMAP.md`](../../ROADMAP.md) — 1.11.0; [`gitlab-package-latest.md`](../archive/gitlab-package-latest.md) (motivating consume ergonomics); [`dependency-resolve.md`](../archive/dependency-resolve.md) (BuildWith tokens remain strings); `cuppa/construct.py` `_normalise_with_defaults`
- **Updated:** 2026-09-05
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

## Semantics (what the two lists mean)

The parameter names are easy to misread as “all deps” vs “extra deps.” The real split is
**register** vs **auto-apply**:

| Argument | Meaning today |
|----------|----------------|
| `dependencies` | **Import / register** these dependency factories with the session so the sconstruct and its sconscripts can look them up (by name / object) and call `BuildWith` when they choose. |
| `default_dependencies` | Of those registered imports, treat this **subset** as automatically `BuildWith()`’d in **every** sconscript (session defaults). |

So `default_dependencies` is not a second registration list. It is an applied-by-default
filter over the registered set (plus built-ins where that already applies). Putting an object
in both lists means: register it, and also auto-apply it everywhere.

That is why the object-in-both-lists ergonomics matter: callers hold one factory and express
both “available” and “on by default” without duplicating a string name.

### Naming — clarify now; explore clearer names later

Docs for this workstream must spell out the register vs auto-apply story in Antora (concepts /
methods / package consume), even while the CLI/`cuppa.run` identifiers stay
`dependencies` / `default_dependencies`.

Separately, consider whether more obvious names would reduce confusion for new projects, for
example (illustrative only — not settled):

| Role | Current | Possible directions |
|------|---------|---------------------|
| Register / import | `dependencies` | `import_dependencies`, `registered_dependencies`, `available_dependencies` |
| Auto `BuildWith` everywhere | `default_dependencies` | `auto_dependencies`, `session_dependencies`, `with_dependencies` |

Any rename is a **compatibility** decision (aliases, deprecation window, or docs-only
vocabulary). First cut of this plan: **keep the current keys**, teach the semantics clearly,
and keep rename options in open questions — do not block object normalisation on a rename.

## Goals

1. Accept **dependency objects** (and equivalently callables / classes that expose `.name()`)
   in `default_dependencies`, normalising to the registry name before `BUILD_WITH` / listing.
2. Keep **strings** (and typed BuildWith tokens if ever used here) fully supported —
   backwards compatible.
3. Prefer documenting the object form as the primary teach path once shipped.
4. Document the **register vs auto-apply** semantics (and any chosen naming) so consume tutorials
   do not imply `default_dependencies` is a second import list.
5. Apply the same normalisation to `dependencies=` entries that are already objects (already
   typical) and to `default_profiles` / `profiles` if the same pattern applies with negligible
   extra scope.

## Non-goals

- Changing BuildWith resolve / type selectors ([`dependency-resolve.md`](../archive/dependency-resolve.md)).
- Requiring objects everywhere (strings remain first-class).
- Auto-adding every `dependencies=` entry to `default_dependencies` (explicit default list stays).
- Renaming `dependencies` / `default_dependencies` in the first implementation cut (see open
  questions).

## Settled decisions (proposed)

| Topic | Decision |
|-------|----------|
| Object in `default_dependencies` | Call `.name()` (classmethod or instance) to obtain the registry key; reject with a clear error if no name can be derived. |
| String in `default_dependencies` | Unchanged. |
| Mix of objects and strings | Allowed in one list. |
| `dependencies=` | Continue to accept factories/classes as today; ensure normalisation is shared so object→name is one code path. |
| Semantics in docs | Teach register (`dependencies`) vs auto-`BuildWith` (`default_dependencies`) explicitly; examples show one object in both lists when both apply. |
| Rename of run() keys | **Not** in the first cut. Explore aliases / clearer names as a follow-on once semantics are documented; preserve string and object forms under current names. |
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
    # Register: sconstruct / sconscripts may BuildWith this package.
    dependencies = [ google_cloud_cpp ],
    # Auto-apply: every sconscript gets BuildWith('google_cloud_cpp') by default.
    default_dependencies = [ google_cloud_cpp ],
)
```

## Work slices

| ID | Slice | Notes |
|----|--------|-------|
| `run-dep-obj-rules` | This plan (including semantics / naming note) | **This change** |
| `run-dep-obj-normalise` | Shared coerce-to-name for run() dependency/profile lists; unit tests | |
| `run-dep-obj-docs` | packages / gitlab / methods / concepts: object-in-both-lists **and** register vs auto-apply wording | With or after normalise |
| `run-dep-obj-naming` | Optional follow-on: evaluate aliases or clearer `cuppa.run` keys | After docs teach current semantics; compatibility plan required |
| `run-dep-obj-issue` | File `impact:minor` issue when implementing | |

## Refusal rules

- Do not break existing string `default_dependencies`.
- Do not invent a second registration API; only widen what `cuppa.run` accepts.
- Do not silently ignore objects that lack a resolvable name.
- Do not rename run() keys in the first cut without a deprecation / alias story.

## Progress snapshot

| Slice | Status |
|-------|--------|
| `run-dep-obj-rules` | Done (this document; semantics note added) |
| Remaining | Not started |

## Open questions

- Exact type check: `callable` + `.name`, class with `name()`, or duck-typing only?
- Whether `default_dependencies = dependencies` (aliasing the same list) should be documented as
  supported once objects work.
- Whether clearer `cuppa.run` parameter names (or aliases) are worth a compatibility cycle, and
  which pair best matches register vs auto-apply without colliding with BuildWith vocabulary.
