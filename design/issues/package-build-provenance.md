# A published package should record what it was built from

- **Status:** issue draft
- **Related:** [`plans/package-develop-local.md`](../plans/package-develop-local.md) (`package_source`, `--clone-develop` for packages); [`plans/package-build-publish-deps.md`](../plans/package-build-publish-deps.md) (cascade, `--clone-publishers`); [`cuppa_publish_manifest.py`](../../cuppa/package_managers/cuppa_publish_manifest.py); [`cuppa_dependency_manifest.py`](../../cuppa/package_managers/cuppa_dependency_manifest.py); [#297](https://github.com/ja11sop/cuppa/issues/297)
- **Updated:** 2026-09-17
- **Impact:** minor — new manifest fields and a report of them; consuming a package is unchanged, and nothing new is required of a publisher

## Problem

Neither manifest a package carries says what produced it. `cuppa-dependency.json` describes the
edges a consumer must resolve, and `cuppa-publish.json` adds `package_source` for **each
dependency** so cascade can find their publisher trees. Neither records the repository, the
branch, or the commit behind the binaries in the archive they sit beside.

So an archive cannot answer the questions asked of it when something goes wrong:

- Which commit of `widget` is in this `widget_debian_gcc15_rel_x86_64_cxx2c.tar.gz`? A consumer
  crashing inside `widget` has a stack trace and no way to map it to a revision.
- Which commit is a rolling version? A package published as `develop` is republished from a moving
  branch, so its version number identifies nothing. Two `develop` archives a week apart are
  indistinguishable from the outside.
- What did an audit ship? Answering needs a person who remembers what was checked out.

A second, smaller consequence turned up while implementing `--clone-develop` for package
dependencies. A manifest records the sources of the package's **dependencies**, never its own, so
the only tree that knows where `widget` comes from is a tree that depends on `widget`. A consumer
that publishes gets that from its own staged manifest; a consumer that does not now declares
`package_source` itself. That works, and this proposal is not needed to make it work.

## The two repositories a package has, and why only one is identity

A packaging project is commonly a thin repository whose `sconstruct` declares the library it
packages as a `location_dependency` and publishes the result. So there are two repositories, and
they answer different questions:

| Repository | What it is | Where cuppa knows it today |
|------------|-----------|----------------------------|
| **Packaged source** | The library actually compiled into the archive | Resolved at build time by the location machinery, which retrieved that tree and can report its revision |
| **Publisher tree** | The project whose `sconstruct` builds and publishes — the recipe | `package_source` on a consumer's edge, or `--publisher-root`; never recorded by the package itself |

**Only the packaged source is identity.** Revision 1 and revision N of a packaging repository can
both build and publish exactly `widget 1.2.3`, and it does not matter which one did, so long as
*a* revision of the recipe can. Recording the recipe's branch and commit would suggest a
distinction that carries no meaning, and would make two identical archives look different.

The publisher's URL is still worth recording, but as a *where to find the recipe* hint for
`--clone-develop` and cascade — not as a claim about what the archive contains. Its revision is
deliberately omitted.

One consequence to accept honestly: a recipe can affect the bytes, by patching the source or
changing flags, and the record above will not show that. That is the price of treating the recipe
as interchangeable, and it is the right trade while a packaging repository stays a thin wrapper.

## Proposal

Record provenance in `cuppa-publish.json` at publish time, as a `built_from` object:

```json
{
  "cuppa_publish_format": 2,
  "package": "widget",
  "version": "1.2",
  "built_from": {
    "sources": [
      {
        "name": "widget",
        "url": "https://github.com/example/widget",
        "branch": "develop",
        "revision": "fedcba9876543210fedcba9876543210fedcba98",
        "modified": false
      }
    ],
    "publisher_url": "https://gitlab.example/packages/widget.git"
  },
  "dependencies": []
}
```

`sources` is the substance: the location dependencies the build was made from, whose revisions the
location machinery already resolves because it retrieved those trees. `modified` belongs here
rather than on the recipe, since a `--develop` build can substitute a working copy for a retrieved
tree, and then the revision alone does not describe what was compiled.

`publisher_url` comes from the working copy the publish ran in, via the same `Git.remote_url`
already used to check a reused clone.

A surface to read it back should land with the fields — a `--list-dependencies` column or a
report on a downloaded package — since a JSON file nobody reads is not provenance.

## What has to be handled, not discovered later

**Credentials.** CI checkouts routinely carry tokenised remotes such as
`https://gitlab-ci-token:<token>@gitlab.example/packages/widget.git`. Recording origin verbatim
would publish a secret inside an archive handed to every consumer. Userinfo must be stripped
before the URL is written, matching the care already taken to keep expanded tokens out of clone
configuration.

**Trust.** A URL inside a downloaded archive that tells a machine what to clone and build is the
category that made `--clone-publishers` opt-in. A recorded `publisher_url` may be a hint to
`--clone-develop` and cascade, never an authority: a consumer's own declaration wins, and nothing
should clone from this field without the same opt-in. A publisher's origin may in any case be an
SSH or internal-host form no consumer can use.

**Truth.** A recorded revision is a lie if the tree it names was dirty. That is why `modified`
sits beside each source revision, and it is the same judgement cascade already makes about
publishing from a working copy holding local work.

**Compatibility.** Older consumers read `cuppa-publish.json` for edges. Adding an object is
additive, but the format version should step and readers must tolerate its absence, since archives
published before this exist and will not be rebuilt.

## Out of scope

- Reproducible builds. This records what was built from, not a guarantee that rebuilding it gives
  the same bytes.
- Signing or attestation. Provenance here is a convenience for humans debugging and auditing, and
  is only as trustworthy as the registry it came from.
- Making `--clone-develop` depend on it. That path works from a declaration or the consumer's own
  staged manifest today, and should keep working for packages published before this lands.
