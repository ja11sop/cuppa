# Plan: `--list-dependencies` requires closure under referenced

- **Status:** done
- **Related:** [`gitlab-package-transitive.md`](gitlab-package-transitive.md) (`gl-dep-list`); [`removal-options.md`](removal-options.md) Phase 3 listing; [`package-build-publish-deps.md`](package-build-publish-deps.md) (cascade consume stacks); [`dependencies-docs-four-hubs.md`](dependencies-docs-four-hubs.md) (Antora Using/Managing/Publishing/Authoring); ROADMAP Dependencies / packages
- **Updated:** 2026-09-26
- **Impact:** minor — listing / wipe classification of GitLab package closure; `--list-scope` vocabulary (Option A); no consume solver change

## Problem

Traveling-manifest `requires` under GitLab version leaves are **labels only**. Transitive
packages (grpc, protobuf, …) sit as top-level **unreferenced** identities even when a tip
resolve selected the parent extract. That misleads reclaim
(`--force-wipe-unreferenced-dependencies`) and makes the referenced section look thinner than
the real package closure.

Separately, operators usually want “what this resolve uses vs leftovers,” but the default
`--list-scope=all` used **resolve-identity** grouping (unused siblings hang under
`referenced`). That conflates leaf bind with report grouping.

## Goals

1. Treat the on-disk **traveling-manifest closure** of tip-selected GitLab extracts as
   **referenced** for listing and wipe (pass A).
2. Nest that closure under the tip’s `requires` group as **real** package trees.
3. Keep nested `requires` under those packages as **label** edges.
4. Leave tip-declared identities at the top level under resolve-identity `referenced`.
5. Expose **usage** vs **resolve-identity** report groupings via `--list-scope` (Option A)
   without changing the meaning of leaf `referenced` / wipe protection.

## Non-goals

- Changing BuildWith / consume apply (already walks manifests).
- Conan / repository / archive requires graphs.
- Split `--list-style` × `--list-scope` (Option C) — deferred until usage experience.

## Settled decisions (pass A)

| Topic | Decision |
|-------|----------|
| Tip vs closure | Tip = resolve-selected GitLab extract (existing `referenced` / `missing` / `cached`). Closure = packages reachable via traveling manifests from tip extracts. |
| Top-level gitlab under referenced | Tip-declared identities only. |
| Closure-only packages | Nested under each tip version’s `requires` as full identity trees; excluded from top-level referenced **and** unreferenced. |
| Tip `requires` shape | Flat forest of the tip’s closure. Leaf-first Kahn then **reversed** for display. Soft on cycles. |
| Nested `requires` | Label edges only (`name version`, libs remark). |
| Unused versions / toolchains under nest | Hang under the nested identity; only tip-matching **tool_variants** get ``referenced`` / ``in use``. |
| Wipe | Tip-matching closure toolchains are ``referenced`` (protected). Other nested variants stay ``unreferenced``. |

## Settled decisions (Option A — list scopes)

Two **orthogonal** axes:

1. **Leaf bind** — `referenced` / `missing` / `cached` vs `unreferenced` (wipe, paint, REMARK). Unchanged.
2. **Report grouping** — how leaves are partitioned into top-level sections.

| Grouping | Section labels | Unused siblings of a tip identity | Unused nest toolchains under tip `requires` |
|----------|----------------|-----------------------------------|-----------------------------------------------|
| **usage** | `used` then `unused` | In **`unused`** | In **`unused`** as top-level identities; used → requires keeps tip-matching only |
| **resolve-identity** | `referenced` then `unreferenced` | Stay under the **`referenced`** identity | Stay under nested identities in tip `requires` (Pass A) |

| `--list-scope` | Grouping | Rows / sections |
|----------------|----------|-----------------|
| **`all` (default)** | usage | All rows; `used` then `unused` |
| **`resolve`** | resolve-identity | All rows; Pass A `referenced` then `unreferenced` |
| **`referenced`** | resolve-identity | Identities with ≥1 resolve-bound leaf (siblings included); referenced section only |
| **`unreferenced`** | resolve-identity | Identities with no resolve-bound leaf |
| **`compact`** | usage | Resolve-bound leaves only (`used` section); **used-only** |

Withdrawn: earlier Pass B draft that made `referenced` mean used-only.

Nested `requires` labels: prefer edges from tip-selected / `closure_in_use` variants
(`in_use_only=True`); if none contribute, fall back to unioning all variants under the
version (orphan-only packages still show declared edges).

Downloads share the same `--list-scope` rules (section chrome may say “used downloads” /
“unused downloads”).

Option C (`--list-style` × `--list-scope`) remains a later exploration.

## Progress snapshot

| Slice | Status |
|-------|--------|
| Settled decisions (pass A) | Done — 2026-09-25 |
| Promote closure paths + nest sized trees | Done |
| Unit / integration / doc samples (pass A) | Done |
| Docs HTML samples + Antora polish | Done — 2026-09-26 |
| Settled decisions (Option A scopes) | Done — 2026-09-26 |
| Implement Option A grouping + scopes | Done — 2026-09-26 |
| Tests / docs / CHANGELOG for Option A | Done — 2026-09-26 |

## Implementation notes

- Promotion runs on enriched leaf rows before / inside `build_tree` (idempotent).
- Match manifest `package` / `name` to on-disk family with a normalised key (case, `_` / `-`).
- Recalculate `unreferenced_bytes` after promotion in `_collect_rows` (leaf-state based).
- `build_tree(..., grouping='usage'|'identity')` and the downloads twin; `apply_list_scope`
  chooses grouping from scope.
- Usage grouping filters nest leaves in the tip ``requires`` forest to resolve-bound
  states and promotes leftover nest toolchains/versions as top-level ``unused``
  identities. Identity grouping keeps Pass A (all nest variants under ``requires``).
