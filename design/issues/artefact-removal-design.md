# Decide how to remove artefacts written outside the build root

- **Status:** issue draft
- **Related:** [`design/plans/removal-options.md`](../plans/removal-options.md) §4.6, Phase 6
- **Updated:** 2026-08-01

File this as a GitHub issue, then delete this draft. This is a design pass, not an
implementation: the deliverable is a decision.

---

## Summary

Projects write generated output beyond `build_root` — collated coverage indexes under
`_artifacts/`, generated sources, copied runtime files, reports. The build removal options
deliberately stay inside the build root, so none of that is covered. Removing it is a real need,
but the mechanism is not obvious enough to guess at.

## Questions to answer

1. **What does SCons `--clean` already remove?** It removes tracked targets, so the honest
   question is what is left over that it misses: directories rather than files, output from
   `Command` actions whose targets are not fully declared, and anything produced by an invocation
   whose graph can no longer be constructed. This wants measuring on a real project before any
   option is designed.
2. **Graph discovery or project declaration?** Asking SCons needs no project cooperation and
   cannot drift from what was actually built. Declaration — `artefact_roots=[ '_artifacts' ]` in
   the `sconstruct`, or an `env.ArtefactRoot(...)` call — is explicit and coarse, and fits the
   containment rules the removal options already apply. The likely answer is both: declaration
   for trees a project knows it owns, discovery for the rest, with the report saying which
   mechanism found each path.
3. **What are the containment rules?** A declared root must resolve inside the project directory;
   a declaration pointing elsewhere should be an error rather than an instruction.

## Deliverable

- Evidence recorded in [`design/plans/removal-options.md`](../plans/removal-options.md) §4.6:
  what `--clean` leaves behind on at least one real project, and the mechanism chosen.
- A follow-up implementation issue for `--remove-artefacts` (`--remove-artifacts` accepted as a
  spelling alias) once the mechanism is settled.

## Not blocked, and not blocking

Every other option in the removal plan is useful without this, which is why it is last. Until it
is resolved, the documentation should say plainly that artefact trees outside the build root are
not removed by the build options.
