# Add listing and removal options for builds, dependencies, and downloads

- **Status:** issue draft
- **Related:** [`design/plans/removal-options.md`](../plans/removal-options.md) §3.2, §3.3, §4, §5, Phases 2–4; [`ROADMAP.md`](../../ROADMAP.md) — Storage roots, listing, and removal options
- **Updated:** 2026-08-01

File this as a GitHub issue, then delete this draft. Depends on the storage roots issue; fill in
its number once both are filed.

---

## Summary

There is no supported way to see what cuppa has put on disk, and no supported way to remove any
of it. The advice today is `du -sh` and `rm -rf`, which is platform-specific, easy to aim at the
wrong path, and unnecessary — cuppa knows exactly which folder belongs to which variant and which
dependency.

Add read-only listings, explicit removal options, and the safety model that governs them.

## Why it matters

Working across branches leaves branch-qualified dependency trees behind indefinitely and nothing
ever reports them, so a shared root grows unnoticed until a disk fills. The listing gap matters
as much as the removal gap: you cannot decide what to remove without seeing what is there and
what still uses it.

## Scope

Expected to land as three or four pull requests, in this order.

**Builds** (plan Phase 2)

- [ ] `--remove-build` — every `<tool_variant_dir>` subtree under `build_root` matching the
      current toolchain / variant / arch / ABI selection, including per-sconscript nesting and
      per-location dependency build folders.
- [ ] `--remove-all-builds` — the build root itself.
- [ ] `--list-builds`.
- [ ] `cuppa/core/build_layout.py`: shared `tool_variant_dir` composition, extracted from
      `construct.py`, so removal and building cannot drift.
- [ ] Shared table renderer: header row, columns padded to their widest value, totals, and
      `--list-format=json`. Every later listing reuses it.
- [ ] The safety model (plan §5): containment, no symlink traversal, refusal of suspicious roots,
      never touching `--develop` working copies, report-before-acting, `-n` dry run, and exit
      status.

**Dependencies and the inventory** (plan Phase 3)

- [ ] `storage_paths()` protocol on dependencies, implemented for location, GitLab package,
      Conan, and Boost. Dependencies without it are reported as skipped, never guessed at.
- [ ] Resolve-only mode with retrieval disabled, reusing `retrieval_disabled_reason()`.
- [ ] Inventory under `<dependencies_root>/.cuppa-inventory/`: one JSON file per entry, atomic
      writes, `last_used` / `used_by` touched on resolve, sizes sampled and lazily refreshed with
      `--exact-sizes` to force a full walk.
- [ ] `--list-dependencies`, including the `LAST USED` column and the `unreferenced` marking.
- [ ] `--remove-dependencies=dep1,dep2` and `--remove-all-dependencies`, scoped to what the
      current selection uses and reporting what they leave for other selections.

**Downloads** (plan Phase 4)

- [ ] `--list-downloads`.
- [ ] `--purge-dependencies=` / `--purge-all-dependencies`.

## Out of scope

- Artefacts written outside the build root; that needs its own design pass and issue.
- `--remove-unreferenced-dependencies` and `--remove-dependencies-older-than=`, which should wait
  until the inventory has been used enough to trust its picture.
- Replacing SCons `--clean`. That removes targets; these remove folders, and work when the graph
  can no longer be described.

## Acceptance criteria

- [ ] Build two variants, remove one, the other survives; remove all builds, the root is gone.
- [ ] Listings change nothing on disk and `-n` removes nothing while reporting the same paths.
- [ ] The inventory is advisory: every path is re-verified on disk and re-checked for containment
      before removal, and an entry whose path is gone is reported and dropped.
- [ ] Unknown dependency names are an error that lists the known ones.
- [ ] Unit coverage for scope resolution, size formatting and totals, containment guards, and
      inventory concurrency and staleness.
- [ ] `build-layout.adoc` gains a "Listing and removing build output and dependencies" section
      that replaces the current "remove the folder by hand" advice; `dependencies.adoc` documents
      `storage_paths()` for dependency authors.

## Reference

[`design/plans/removal-options.md`](../plans/removal-options.md) — §3.2 listings, §3.3 removal,
§4 scope resolution, §4.5 the inventory, §5 safety model.
