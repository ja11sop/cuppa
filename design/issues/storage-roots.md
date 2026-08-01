# Rename the storage roots and add `--storage-root`

- **Status:** issue draft
- **Related:** [`design/plans/removal-options.md`](../plans/removal-options.md) §3.1, §8, Phase 1; [`ROADMAP.md`](../../ROADMAP.md) — Storage roots, listing, and removal options
- **Updated:** 2026-08-01

File this as a GitHub issue, then delete this draft.

---

## Summary

Cuppa's two shared storage roots are named close to backwards. `download_root` does not hold
downloads, it holds extracted, ready-to-use dependency trees; `cache_root` is where the
downloaded archives actually live. Both sit under `~/_cuppa`, a visible folder in a place where
every comparable tool is hidden, and there is no single option that moves them together.

Rename them, add a `--storage-root` that both derive from, and move the default to `~/.cuppa`,
keeping the old options and environment keys working as deprecated aliases.

## Why this first

Everything else in this family — listing, removal, purging — talks about these paths. Doing the
rename up front means each later change and review uses one vocabulary instead of translating
between old and new names. It is also self-contained: no new actions, no deletion, and the alias
layer keeps existing `~/.cuppaconfig` files and third-party dependency plugins working.

## Scope

| Option | Env key | Default |
|--------|---------|---------|
| `--storage-root` | `storage_root` | `~/.cuppa` |
| `--dependencies-root` | `dependencies_root` | `<storage_root>/dependencies` (was `download_root`) |
| `--downloads-root` | `downloads_root` | `<storage_root>/downloads` (was `cache_root`) |

- Resolution precedence in one place: an explicit root wins, otherwise it derives from
  `storage_root`; deprecated aliases feed the explicit slot. Every reader takes the resolved
  value so no subsystem re-implements the rule.
- `--storage-root` does not move `build_root`, which stays project-relative.
- Fallback: when an old folder exists and the new one does not, keep using the old one and say so
  once at info level. The default *location* changes, not just the name, so this is what stops a
  machine-wide re-download.
- Report the resolved roots at info level on the first retrieval of a run.
- Update every internal reader: `cuppa/location.py`, `cuppa/package_managers/gitlab.py`,
  `cuppa/build_with_conan.py`, `cuppa/dependencies/…`.

## Out of scope

Any listing or removal option. Those depend on this and are tracked separately.

## Acceptance criteria

- [ ] A project using `--download-root` / `--cache-root` builds exactly as before, with a
      deprecation notice.
- [ ] `--storage-root` derives both roots; an explicit `--dependencies-root` or
      `--downloads-root` overrides its half and leaves the other derived; command line and
      `~/.cuppaconfig` combine with the same precedence.
- [ ] An existing `~/_cuppa/_download` tree is still used rather than silently re-fetched.
- [ ] Unit tests cover precedence, aliases, and the old-folder fallback.
- [ ] Integration test: a project built with `--storage-root=<tmp>` puts both roots underneath
      it, and adding `--downloads-root` moves only the downloads half.
- [ ] Documentation states plainly that dependencies and downloads are **shared between projects
      by default**, what that gains and costs, and the single option that makes a project
      self-contained — in `build-layout.adoc` where the roots are introduced, and again in
      `install.adoc` / `quickstart.adoc`. `cli-reference.adoc` and `configuration.adoc` cover the
      flags and keys.
- [ ] `CHANGELOG.md` under both Deprecated (old options) and Changed (default location), with the
      one option that restores the previous behaviour.

## Reference

Full rationale, including why the hidden root and why the swapped names:
[`design/plans/removal-options.md`](../plans/removal-options.md) §8.
