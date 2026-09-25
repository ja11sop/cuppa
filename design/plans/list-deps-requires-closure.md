# Plan: `--list-dependencies` requires closure under referenced

- **Status:** done
- **Related:** [`gitlab-package-transitive.md`](gitlab-package-transitive.md) (`gl-dep-list`); [`removal-options.md`](removal-options.md) Phase 3 listing; [`package-build-publish-deps.md`](package-build-publish-deps.md) (cascade consume stacks); ROADMAP Dependencies / packages
- **Updated:** 2026-09-26
- **Impact:** minor — listing / wipe classification of GitLab package closure; no consume solver change

## Problem

Traveling-manifest `requires` under GitLab version leaves are **labels only**. Transitive
packages (grpc, protobuf, …) sit as top-level **unreferenced** identities even when a tip
resolve selected the parent extract. That misleads reclaim
(`--force-wipe-unreferenced-dependencies`) and makes the referenced section look thinner than
the real package closure.

## Goals

1. Treat the on-disk **traveling-manifest closure** of tip-selected GitLab extracts as
   **referenced** for listing and wipe.
2. Nest that closure under the tip’s `requires` group as **real** package trees (versions →
   toolchains, sizes, last-used), not only `name version` labels.
3. Keep nested `requires` under those packages as **label** edges (no recursive sized forests).
4. Leave tip-declared identities at the top level under `referenced` → gitlab packages.

## Non-goals (this slice — pass A)

- **Split identities:** non-selected versions / toolchains of a referenced package stay under
  that identity (same as today’s tip boost siblings). Defer moving unused variants to
  `unreferenced` and any redefinition of `--list-scope=compact`. When that lands, switch
  ``_requires_entries_from_variants(..., in_use_only=True)`` so nested labels only union
  edges from in-use extracts.
- Changing BuildWith / consume apply (already walks manifests).
- Conan / repository / archive requires graphs.

## Settled decisions (pass A)

| Topic | Decision |
|-------|----------|
| Tip vs closure | Tip = resolve-selected GitLab extract (existing `referenced` / `missing` / `cached`). Closure = packages reachable via traveling manifests from tip extracts. |
| Top-level gitlab under referenced | Tip-declared identities only. |
| Closure-only packages | Nested under each tip version’s `requires` as full identity trees; excluded from top-level referenced **and** unreferenced. |
| Tip `requires` shape | Flat forest of the tip’s closure. Same leaf-first Kahn as cascade, then **reversed** for display (dependent-first / heaviest first when descending). Soft on cycles. Declaration order breaks ties before reverse. |
| Nested `requires` | Label edges only (`name version`, libs remark). |
| Unused versions / toolchains | Still hang under the nested identity (no split). Only tip-matching **tool_variants** get ``referenced`` / ``in use``; sibling toolchains stay ``unreferenced`` under the nest (wipe can reclaim them). |
| Manifest source for ``requires`` labels | **Union** of edges from every toolchain variant under the version (dedupe by package+version). Pass B: union only from tip-matching / in-use variants (``in_use_only``). |
| Spacers | Blank hanging-pipe rows between toolchain leaves and ``requires``, and between nested closure identities. |
| Wipe | Tip-matching closure toolchains are ``referenced`` (protected). Other nested variants stay ``unreferenced`` and remain wipe candidates. |
| `--list-scope=compact` | Unchanged until split pass. |

## Pass B (deferred)

After smoke on a tip with a large GitLab stack: split tip-selected version/toolchain into
referenced only; park other variants under unreferenced; decide whether `compact` becomes the
strict default for “what this resolve needs.”

## Progress snapshot

| Slice | Status |
|-------|--------|
| Settled decisions (pass A) | Done — 2026-09-25 |
| Promote closure paths + nest sized trees | Done |
| Unit / integration / doc samples | Done |
| Docs HTML samples + Antora table/label polish | Done — 2026-09-26 |
| Pass B (split + compact) | Open (deferred) |

## Implementation notes

- Promotion runs on enriched leaf rows before / inside `build_tree` (idempotent) so unit tests
  and doc samples that skip `_collect_rows` still see nesting.
- Match manifest `package` / `name` to on-disk family with a normalised key (case, `_` / `-`).
- Recalculate `unreferenced_bytes` after promotion in `_collect_rows`.
