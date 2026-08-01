# Report and update the local working copies used by `--develop`

- **Status:** issue draft
- **Related:** [`design/plans/removal-options.md`](../plans/removal-options.md) §3.5, §3.6, Phase 5
- **Updated:** 2026-08-01

File this as a GitHub issue, then delete this draft.

---

## Summary

`--develop` swaps a retrieved dependency for a local working copy, and says nothing about the
state of that copy. You can be building your feature branch against a dependency parked on
someone else's spike branch, or one that has not been pulled since March, and the only symptom is
a compile error that makes no sense, a test that fails only on your machine, or one that passes
only on your machine. A develop path that does not exist is not checked at all today: the swap
happens regardless and the failure surfaces much later as a missing include.

Add `--list-develop` to report what you are actually building against, and `--update-develop` to
bring the out-of-date copies forward where that cannot lose work.

## Why it is worth doing early

It is independent of everything else in the storage plan: no storage roots, no inventory, nothing
removed. It is small, it is immediately useful to anyone working across two repositories at once,
and it carries no migration risk.

## Scope

**`--list-develop`** — one row per dependency with a develop location configured, whether or not
`--develop` is active, plus a count of those without one. Columns: dependency, branch, upstream,
state, path. It does no network access; ahead and behind are relative to the last fetch and the
output says so.

Classification and severity, which is where the value is:

| Situation | Severity |
|-----------|----------|
| Branch equals the branch being built, or the default branch | ok |
| Any other branch, or detached HEAD | warning |
| Behind upstream, or diverged | warning |
| Ahead or modified, on the branch being built | note — this is the intended workflow |
| Ahead or modified, on the default branch | warning — local work that no other build will see |
| No upstream tracking branch | note — ahead and behind cannot be answered |
| Not a working copy | warning |
| Path does not exist | error |

The default-branch case deserves the warning because your build reads the working copy while
every build that does not use `--develop` resolves the dependency to the published default
branch, so the divergence only shows up in CI or on someone else's machine. The warning should
name the remedy: put the work on a branch named for the branch being built, commit, and push.

**`--update-develop`** — fetch, then fast-forward only those copies that are clean and strictly
behind their upstream. Everything else is skipped and reported with the reason. It is safe by
construction: a fast-forward of a clean tree discards nothing and leaves nothing to recover from.
It never stashes, resets, rewrites history, or switches branches, and `--offline` makes it an
error rather than a silent no-op.

**Implementation notes**

- Extract develop-path resolution from `Location.__init__` (`~` expansion and the `#` anchor to
  `sconstruct_dir`) into a shared helper, so the report cannot disagree with the swap it
  describes.
- Add `Git.get_working_copy_state()` using `git status --porcelain` and
  `git rev-list --left-right --count @{upstream}...HEAD`. Subversion, Mercurial, and Bazaar report
  branch and revision from the existing `info()` support and `unknown` for the rest.
- The branch being built is already in `cuppa_env['current_branch']`.
- Register with the other location options, run after dependency registration, and exit the way
  `--dump` does.

## Out of scope

- `--update-develop=fetch-only` / `=allow-rebase` / `=allow-merge`. Everything beyond
  fast-forwarding is a judgement about someone's unpublished work and should be designed after
  these two options have shown which states people actually reach.
- Printing the warnings automatically during any `--develop` build. Worth doing once the
  classification has proved itself, with a way to silence it.

## Acceptance criteria

- [ ] Classification is a pure function of `(project branch, default branch, copy branch,
      upstream, ahead, behind, modified, path exists)`, with a unit test per row of the table
      above — including the pair that differ only by branch.
- [ ] Path resolution is tested against the same helper the develop swap uses, including a
      relative path anchored to the sconstruct directory and a `~` path.
- [ ] `--update-develop` is a second pure decision over the same state: fast-forward only when
      clean and strictly behind, skip with a reason otherwise, refuse under `--offline`.
- [ ] Exit status is zero for a report, non-zero when a develop path does not exist.
- [ ] `dependencies.adoc` gains a "Checking your develop copies" section covering both options,
      what each state means, and the one thing `--update-develop` changes.

## Reference

[`design/plans/removal-options.md`](../plans/removal-options.md) §3.5 and §3.6.
