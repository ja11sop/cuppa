#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   Cascade build-and-publish of GitLab package dependencies
#-------------------------------------------------------------------------------

"""Opt-in nested publish of package dependencies before the tip package.

See ``design/plans/package-build-publish-deps.md``.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from collections import defaultdict, deque

import SCons.Errors

from cuppa import timer
from cuppa.colourise import as_error, as_info, as_notice, as_subdued, as_warning
from cuppa.core.storage_options import default as storage_defaults
from cuppa.log import logger
from cuppa.package_managers.cuppa_dependency_manifest import (
        coerce_dependency_entry,
        fill_dependency_versions,
)
from cuppa.package_managers.cuppa_publish_manifest import (
        PUBLISH_FILENAME,
        read_publish_manifest,
)
from cuppa.scms.git import Git
from cuppa.utility import storage


CASCADE_OPTION = "build-and-publish-dependencies"
CASCADE_PLAN_OPTION = "cascade-plan"
PUBLISHER_ROOT_OPTION = "publisher-root"
CLONE_OPTION = "clone-publishers"
MODIFIED_DEVELOP_OPTION = "publish-modified-develop"
NESTED_ENV = "CUPPA_CASCADE_NESTED"

# Where clones land under the storage root when no publisher root was given.
PUBLISHERS_DIRNAME = "publishers"

# Same rule glyph as the dependency listing tree.
RULE = '-'


def cascade_enabled( env ) -> bool:
    getter = getattr( env, "get_option", None )
    if not callable( getter ):
        return False
    return bool( getter( CASCADE_OPTION ) )


def cascade_plan_enabled( env ) -> bool:
    getter = getattr( env, "get_option", None )
    if not callable( getter ):
        return False
    return bool( getter( CASCADE_PLAN_OPTION ) )


def clone_enabled( env ) -> bool:
    getter = getattr( env, "get_option", None )
    if not callable( getter ):
        return False
    return bool( getter( CLONE_OPTION ) )


def develop_enabled( env ) -> bool:
    getter = getattr( env, "get_option", None )
    if not callable( getter ):
        return False
    return bool( getter( "develop" ) )


def modified_develop_publish_allowed( env ) -> bool:
    getter = getattr( env, "get_option", None )
    if not callable( getter ):
        return False
    return bool( getter( MODIFIED_DEVELOP_OPTION ) )


def publisher_root_option( env ) -> str | None:
    getter = getattr( env, "get_option", None )
    if not callable( getter ):
        return None
    value = getter( PUBLISHER_ROOT_OPTION )
    if not value:
        return None
    root = os.path.expanduser( str( value ) )
    if not os.path.isabs( root ):
        base = env.get( "sconstruct_dir" ) or env.get( "working_dir" ) or os.getcwd()
        root = os.path.abspath( os.path.join( str( base ), root ) )
    return root


def _is_nested() -> bool:
    return os.environ.get( NESTED_ENV ) == "1"


def _node_key( name: str, package: str, version: str ) -> tuple:
    return ( str( name ), str( package ), str( version ) )


def looks_like_url( value: str ) -> bool:
    lower = value.lower()
    return (
            lower.startswith( ( "http://", "https://", "git@", "ssh://", "file://" ) )
            or lower.endswith( ".git" )
    )


def split_source_pin( value: str ) -> tuple[str, str | None]:
    """Split a ``package_source`` URL into the URL and the revision it pins.

    ``Location.get_scm_system_and_info`` cannot do this: it only splits a pin off
    a ``vc+scheme`` URL (``git+ssh://…``) and returns nothing at all for the
    scp-like ``git@host:group/name`` form ``package_source`` is normally written
    in. The ambiguity to settle is the user separator in ``git@host:name``, which
    is not a pin, against ``git@host:name@develop``, which is. An ``@`` opens a
    pin only once a host or path separator has been seen, which also leaves
    ``https://user@host/group/name`` unpinned and keeps slashy revisions
    (``@feature/x``) whole.

    Only URLs are split. A filesystem ``package_source`` is taken literally,
    because a retrieved tree can legitimately be named ``capy@develop`` and
    because honouring a pin would mean switching the operator's branch.
    """
    text = str( value )
    _scheme, separator, remainder = text.partition( "://" )
    tail = remainder if separator else text
    at = tail.rfind( "@" )
    if at < 0:
        return text, None
    head = tail[:at]
    if not any( character in head for character in ":/" ):
        return text, None
    revision = tail[at + 1:]
    if not revision:
        return text, None
    return text[: len( text ) - len( revision ) - 1], revision


def publisher_clone_root( env ) -> str:
    """Where a cloned publisher tree lands.

    A bare cascade clones into a cuppa-owned tree under the storage root, so it
    never writes into the operator's working area unasked. ``--publisher-root``
    redirects it there: a flag asking cascade to search a forest is taken as
    permission to populate it, and is where someone who wants to explore or work
    on those trees would want them.
    """
    root = publisher_root_option( env )
    if root:
        return root
    storage_root = env.get( "storage_root" ) or storage_defaults.storage_root
    return os.path.join( os.path.expanduser( str( storage_root ) ), PUBLISHERS_DIRNAME )


def publisher_clone_destination( env, entry: dict ) -> str:
    """``{root}/{name}`` — the first shape :func:`_resolve_under_publisher_root`
    looks in, so a clone is found again by the same rules that failed to find it.

    Keyed by dependency name like the rest of the product: the consume cache is
    already ``downloads_root/packages/{package}/{version}`` with no registry in
    the key. Two dependencies claiming one destination from different URLs is
    refused rather than resolved by inventing a registry-qualified path here.
    """
    return os.path.join( publisher_clone_root( env ), str( entry["name"] ) )


def declared_package_source( env, entry: dict ) -> str | None:
    """A ``package_source`` the consumer declared on the dependency itself, if any.

    A publisher's ``dependencies=`` list is the usual home for this, but a consumer that
    declares ``package_dependency( …, package_source=… )`` — so ``--clone-develop`` can fill
    its develop tree — should not have to say it twice for cascade.
    """
    factory = _tip_dependency_factory( env, entry )
    if factory is None:
        return None
    source = getattr( _factory_owner( factory ), "_package_source", None )
    return str( source ) if source else None


def develop_publisher_dir( env, entry: dict ) -> str | None:
    """The develop working copy configured for this dependency, whatever ``--develop`` says.

    Resolved through the same helper the develop reports and the consume swap use, so cascade
    cannot name a path they would not.
    """
    factory = _tip_dependency_factory( env, entry )
    if factory is None:
        return None
    from cuppa.develop import configured_develop
    return configured_develop( _factory_owner( factory ), env )


def develop_names_a_publisher_tree( path: str ) -> bool:
    """Whether a develop path names a project that publishes a package.

    An sconstruct is the whole test here, where a rooted or cloned tree may also be
    recognised by its ``cuppa-publish.json``. A publisher build **stages** that manifest
    beside ``include/`` and ``lib/``, so accepting it would read a built package — which is
    what a package's ``develop=`` has meant until now — as the project that built it.
    """
    return any(
            os.path.isfile( os.path.join( path, name ) )
            for name in ( "sconstruct", "SConstruct" )
    )


def develop_tree_refusal( path: str ) -> str | None:
    """Why this develop path cannot act as a publisher tree, or None when it can.

    A package's ``develop=`` has meant a **built prefix** — the directory ``include/`` and
    ``lib/`` hang off — so an operator pointing cascade at one deserves to be told which of the
    two trees is wanted rather than a bare missing-sconstruct complaint.
    """
    if not os.path.isdir( path ):
        return "that path is not a directory"
    if develop_names_a_publisher_tree( path ):
        return None
    if any(
            os.path.exists( os.path.join( path, leaf ) )
            for leaf in ( "include", "lib", PUBLISH_FILENAME )
    ):
        return (
                "that path holds a built package, not the project that publishes it. Cascade "
                "needs the publisher project — the tree with its sconstruct"
        )
    return "that tree has no sconstruct, so nothing there can publish a package"


def develop_is_publisher_source( env, path: str ) -> bool:
    """Whether a develop path is a tree cascade publishes from rather than a package to consume.

    Consume swaps a develop path in as the prefix it links against. When cascade is running and
    that path is the publisher project, the tree is the *source* of the package, so the swap has
    to stand down and let the build take the artefact the nested publish produces.
    """
    if not cascade_enabled( env ) and not cascade_plan_enabled( env ):
        return False
    return develop_names_a_publisher_tree( path )


def develop_publish_objections( copy ) -> list[str]:
    """Why publishing from this working copy would put unreproducible bits in a registry.

    Being unable to inspect a copy is not evidence of local work, so an unknown or
    unversioned tree yields no objection here and is reported as a warning instead.
    """
    if not getattr( copy, "is_working_copy", False ):
        return []
    objections = []
    if copy.modified:
        objections.append( "uncommitted changes" )
    if copy.ahead:
        objections.append( "{} not pushed".format(
                "1 commit" if copy.ahead == 1 else "{} commits".format( copy.ahead )
        ) )
    if not copy.detached and not copy.upstream:
        objections.append( "no upstream, so its commits are only on this machine" )
    return objections


def _offline( env ) -> bool:
    getter = getattr( env, "get_option", None )
    if callable( getter ) and getter( "offline" ):
        return True
    return bool( env.get( "offline" ) )


def _same_repository( left: str, right: str ) -> bool:
    """Whether two URLs name the same repository, allowing for ``.git`` and case.

    Deliberately shallow: two spellings of one repository that this does not
    equate produce a refusal naming both URLs, which is the safe direction. The
    dangerous mistake would be treating different repositories as the same and
    publishing from the wrong tree.
    """
    def normalised( value ):
        text = str( value ).strip().rstrip( "/" )
        if text.lower().endswith( ".git" ):
            text = text[:-4]
        return text.lower()
    return normalised( left ) == normalised( right )


def clone_publisher( env, entry: dict, url: str, revision, destination: str ) -> str:
    """Clone ``url`` into ``destination`` and land on ``revision``.

    Refuses rather than guesses: no network under ``--offline``, never clobbers
    a tree it did not clone, and never switches, stashes, or resets one it
    finds. Unlike ``--clone-develop`` a pin is welcome, because publishing
    version X from tag vX is the normal case; a tag or revision lands detached.
    """
    label = node_label( entry )
    if _offline( env ):
        raise SCons.Errors.StopError(
                "cascade cannot clone the publisher for [{}] from [{}] while "
                "--offline is set. Drop --offline, or plant the tree at [{}]."
                .format( label, url, destination )
        )

    if os.path.isdir( destination ) and os.listdir( destination ):
        origin = Git.remote_url( destination )
        if origin and _same_repository( origin, url ):
            _report_existing_clone( label, destination, revision )
            return destination
        raise SCons.Errors.StopError(
                "cascade cannot clone the publisher for [{}]: [{}] already "
                "exists and is not a clone of [{}] (its remote is [{}]). Move "
                "it aside, or point --{} at a forest holding the right tree."
                .format( label, destination, url, origin or "none", PUBLISHER_ROOT_OPTION )
        )

    logger.info( "Cascade: cloning publisher for [{}] from [{}] into [{}]".format(
            as_info( label ), as_notice( url ), as_notice( destination )
    ) )
    try:
        Git.clone( url, destination, recurse_submodules=True )
        if revision:
            if Git.remote_tracking_branch_exists( destination, revision ):
                Git.checkout_tracking_branch( destination, revision )
            else:
                Git.checkout_branch( destination, revision )
            Git.update_submodules( destination )
    except Git.Error as error:
        # A half-clone left behind would be mistaken for a usable tree on the
        # next run, so the failed attempt takes its directory with it.
        shutil.rmtree( destination, ignore_errors=True )
        raise SCons.Errors.StopError(
                "cascade could not clone the publisher for [{}] from [{}]{} "
                "into [{}]: {}"
                .format(
                        label,
                        url,
                        " at [{}]".format( revision ) if revision else "",
                        destination,
                        str( error ),
                )
        )

    if not _looks_like_publisher_tree( destination ):
        raise SCons.Errors.StopError(
                "cascade cloned [{}] into [{}] for [{}], but that tree has no "
                "sconstruct or {}, so it cannot publish anything"
                .format( url, destination, label, PUBLISH_FILENAME )
        )
    return destination


def _report_existing_clone( label, destination, revision ) -> None:
    """Reuse a clone as it stands; say so when it is not where the pin asked.

    Moving it is the operator's call — cascade does not switch, stash, or reset
    a working copy, the same rule the develop commands follow.
    """
    if revision:
        try:
            branch = Git.get_branch( destination )[0]
        except Exception:
            branch = None
        if branch and branch != revision:
            logger.warn(
                    "Cascade: publisher [{}] at [{}] is on [{}], not the pinned "
                    "[{}]; using it as it stands"
                    .format(
                            as_info( label ), as_notice( destination ),
                            as_warning( str( branch ) ), as_info( str( revision ) )
                    )
            )
            return
    logger.info( "Cascade: using existing clone for [{}] at [{}]".format(
            as_info( label ), as_notice( destination )
    ) )


def resolve_publisher_dir( env, entry: dict, allow_clone=True, claims=None ) -> str | None:
    """Return a publisher working tree for ``entry``, cloning it when asked to.

    ``allow_clone=False`` plans instead of acting: where a clone would happen it
    records ``_clone_url`` / ``_clone_revision`` / ``_clone_dir`` on ``entry``
    and returns ``None``, so ``--cascade-plan`` can report the fetch it would do
    without fetching anything.

    ``claims`` maps an already-claimed clone destination to the label and URL
    that claimed it, so two dependencies wanting one directory from different
    repositories is refused rather than silently resolved.
    """
    package_source = entry.get( "package_source" ) or declared_package_source( env, entry )
    name = entry["name"]
    package = entry["package"]

    # A develop tree outranks everything else: it is the operator saying, for this
    # run, which copy of this dependency they mean. A root convention is a guess by
    # comparison, and cloning is for when there is nothing local at all.
    develop_dir = develop_publisher_dir( env, entry )
    if develop_dir:
        entry["_develop_dir"] = develop_dir
        if develop_enabled( env ):
            refusal = develop_tree_refusal( develop_dir )
            if refusal:
                raise SCons.Errors.StopError(
                        "--develop points [{}] at [{}], but {}. Point its develop path at "
                        "the publisher project, or drop --develop so cascade resolves it "
                        "from package_source."
                        .format( name, develop_dir, refusal )
                )
            entry["_from_develop"] = True
            return develop_dir
        # Cascade will resolve it some other way; the plan says so rather than
        # leaving an operator to wonder why their tree was ignored.
        entry["_develop_unused"] = True

    if package_source:
        source = os.path.expanduser( str( package_source ) )
        if looks_like_url( source ):
            # An existing local tree always wins: it is what the operator planted,
            # and reusing it keeps a cascade run off the network.
            root = publisher_root_option( env )
            resolved = _resolve_under_publisher_root( root, name, package ) if root else None
            if resolved:
                return resolved
            url, revision = split_source_pin( source )
            if not clone_enabled( env ):
                raise SCons.Errors.StopError(
                        "package_source for [{}] is a URL [{}] and no local "
                        "working tree was found{}. Pass --{} to clone it, set "
                        "--{} to a forest that already holds it, or give the "
                        "dependency a filesystem package_source."
                        .format(
                                name,
                                source,
                                " under --{}=[{}]".format( PUBLISHER_ROOT_OPTION, root )
                                        if root else "",
                                CLONE_OPTION,
                                PUBLISHER_ROOT_OPTION,
                        )
                )
            destination = publisher_clone_destination( env, entry )
            _claim_clone_destination( claims, destination, entry, url )
            if not allow_clone:
                entry["_clone_url"] = url
                entry["_clone_revision"] = revision
                entry["_clone_dir"] = destination
                return None
            return clone_publisher( env, entry, url, revision, destination )
        if not os.path.isabs( source ):
            base = env.get( "sconstruct_dir" ) or os.getcwd()
            source = os.path.abspath( os.path.join( str( base ), source ) )
        if os.path.isdir( source ):
            return source
        raise SCons.Errors.StopError(
                "package_source for [{}] is not a directory: [{}]"
                .format( name, source )
        )

    root = publisher_root_option( env )
    if not root:
        raise SCons.Errors.StopError(
                "dependency [{}] has no package_source and --{} is not set; "
                "cannot resolve a publisher working tree"
                .format( name, PUBLISHER_ROOT_OPTION )
        )
    resolved = _resolve_under_publisher_root( root, name, package )
    if resolved:
        return resolved
    raise SCons.Errors.StopError(
            "could not resolve publisher for [{}] under --{}=[{}] "
            "(tried {{root}}/{{name}}, {{root}}/{{package}}, and one-level nesting)"
            .format( name, PUBLISHER_ROOT_OPTION, root )
    )


def _claim_clone_destination( claims, destination: str, entry: dict, url: str ) -> None:
    if claims is None:
        return
    claimed = claims.get( destination )
    if claimed and not _same_repository( claimed[1], url ):
        raise SCons.Errors.StopError(
                "cascade cannot clone both [{}] from [{}] and [{}] from [{}] "
                "into [{}]: two repositories claim one directory. Give one of "
                "them a filesystem package_source, or plant its tree under --{}."
                .format(
                        claimed[0], claimed[1], node_label( entry ), url,
                        destination, PUBLISHER_ROOT_OPTION,
                )
        )
    claims[destination] = ( node_label( entry ), url )


def _resolve_under_publisher_root( root: str, name: str, package: str ) -> str | None:
    if not root or not os.path.isdir( root ):
        return None
    candidates = [
            os.path.join( root, name ),
            os.path.join( root, package ),
    ]
    for path in candidates:
        if os.path.isdir( path ) and _looks_like_publisher_tree( path ):
            return path
    try:
        children = sorted( os.listdir( root ) )
    except OSError:
        return None
    for child in children:
        child_path = os.path.join( root, child )
        if not os.path.isdir( child_path ):
            continue
        for leaf in ( name, package ):
            nested = os.path.join( child_path, leaf )
            if os.path.isdir( nested ) and _looks_like_publisher_tree( nested ):
                return nested
    return None


def _looks_like_publisher_tree( path: str ) -> bool:
    for name in ( "sconstruct", "SConstruct", PUBLISH_FILENAME ):
        if os.path.isfile( os.path.join( path, name ) ):
            return True
    return False


def _edges_from_publisher( env, publisher ) -> list[dict]:
    deps = getattr( publisher, "_dependencies", None ) or []
    if not deps:
        return []
    filled = fill_dependency_versions( env, deps ) or []
    return [ coerce_dependency_entry( item ) for item in filled ]


def _edges_from_publish_file( directory: str ) -> list[dict]:
    document = read_publish_manifest( directory )
    if not document:
        return []
    return list( document.get( "dependencies" ) or [] )


def node_label( entry ) -> str:
    """``name version (package)`` — the label cascade reports a node by."""
    return "{} {} ({})".format(
            entry.get( "name" ), entry.get( "version" ), entry.get( "package" )
    )


def build_cascade_graph( env, publisher, tolerant=False, allow_clone=True ):
    """Return ``(nodes, edges)`` for the tip's package dependency DAG.

    ``nodes`` maps node_key → entry dict (includes ``_publisher_dir``).
    ``edges`` maps parent key → set of child (dependency) keys.

    ``tolerant`` records an unresolvable publisher tree on the node as
    ``_resolve_error`` instead of raising, so ``--cascade-plan`` can report every
    tree an operator still has to plant. A real run keeps failing on the first.

    ``allow_clone=False`` plans a clone rather than performing one. A node that
    would be cloned has no tree yet, so the walk cannot read its
    ``cuppa-publish.json`` and stops there — the plan report says so rather than
    implying the dependency is a leaf.
    """
    nodes: dict[tuple, dict] = {}
    edges: dict[tuple, set[tuple]] = defaultdict( set )
    queue: deque[dict] = deque()
    claims: dict[str, tuple] = {}

    for entry in _edges_from_publisher( env, publisher ):
        if entry.get( "version" ) is None:
            raise SCons.Errors.StopError(
                    "cascade dependency [{}] has no version "
                    "(fill from BuildWith or set it explicitly)"
                    .format( entry.get( "name" ) )
            )
        queue.append( entry )

    while queue:
        entry = queue.popleft()
        key = _node_key( entry["name"], entry["package"], entry["version"] )
        if key in nodes:
            if entry.get( "package_source" ) and not nodes[key].get( "package_source" ):
                nodes[key]["package_source"] = entry["package_source"]
            continue
        nodes[key] = dict( entry )
        try:
            publisher_dir = resolve_publisher_dir(
                    env, nodes[key], allow_clone=allow_clone, claims=claims
            )
        except SCons.Errors.StopError as error:
            if not tolerant:
                raise
            nodes[key]["_publisher_dir"] = None
            nodes[key]["_resolve_error"] = str( error )
            continue
        nodes[key]["_publisher_dir"] = publisher_dir
        if publisher_dir is None:
            # Planned clone: its own dependencies live in a tree that does not
            # exist yet, so there is nothing to walk into.
            continue
        for child in _edges_from_publish_file( publisher_dir ):
            child_key = _node_key( child["name"], child["package"], child["version"] )
            edges[key].add( child_key )
            queue.append( child )

    for parent, children in list( edges.items() ):
        for child in children:
            if child not in nodes:
                raise SCons.Errors.StopError(
                        "cascade graph incomplete: [{}] requires missing node {}"
                        .format( parent, child )
                )

    return nodes, edges


def topological_publish_order( nodes: dict, edges: dict ) -> list[tuple]:
    """Leaves (no further package deps) first."""
    node_keys = list( nodes.keys() )
    waiting = { key: len( edges.get( key, () ) ) for key in node_keys }
    dependents: dict[tuple, set[tuple]] = defaultdict( set )
    for parent, children in edges.items():
        for child in children:
            dependents[child].add( parent )

    ready = deque( sorted( [ key for key, count in waiting.items() if count == 0 ], key=str ) )
    ordered: list[tuple] = []
    while ready:
        node = ready.popleft()
        ordered.append( node )
        for parent in sorted( dependents.get( node, () ), key=str ):
            waiting[parent] -= 1
            if waiting[parent] == 0:
                ready.append( parent )

    if len( ordered ) != len( node_keys ):
        raise SCons.Errors.StopError(
                "cascade dependency cycle detected among {}".format(
                        [ key for key in node_keys if key not in ordered ]
                )
        )
    return ordered


def _work_verdict( entry ):
    """``(severity, colour, what happens)`` for a tree holding work only this machine has.

    One place, so the row an operator reads and the counts in the header cannot disagree.
    """
    if not entry.get( "_from_develop" ):
        return (
                "warning", as_warning,
                "published anyway; cascade only refuses a develop tree",
        )
    if entry.get( "_work_objections_allowed" ):
        return (
                "note", as_notice,
                "allowed by --{}".format( MODIFIED_DEVELOP_OPTION ),
        )
    return (
            "error", as_error,
            "refused; commit and push, or pass --{}".format( MODIFIED_DEVELOP_OPTION ),
    )


def _publisher_plan_notes( entry, prose_width ) -> list[str]:
    """What the plan says about a node's tree: unused develop, or unpublishable as it stands."""
    lines = []
    objections = entry.get( "_work_objections" )
    if objections:
        severity, colour, verdict = _work_verdict( entry )
        text = "{}: publishing from this tree has {} ({})".format(
                severity, ", ".join( objections ), verdict
        )
        lines.extend( colour( line ) for line in storage.wrapped( text, prose_width ) )
    if entry.get( "_develop_unused" ):
        note = (
                "note: a develop tree is configured at [{}] but --develop was not passed, "
                "so it was not used".format(
                        storage.display_path( entry["_develop_dir"] )
                )
        )
        lines.extend( as_notice( line ) for line in storage.wrapped( note, prose_width ) )
    return lines


def cascade_plan_lines( nodes, order, tip_package, tip_version, encoding=None ) -> list[str]:
    """Publish order, leaf-first, with each node's resolved publisher tree.

    Order is the point of this report, so nodes stay in publish order rather
    than being grouped by severity the way a judgement tree groups a work list.
    The intro still carries the shared severity brackets.
    """
    tee, elbow, pipe, gap = storage.glyphs( encoding )
    graded = {
            key: _work_verdict( nodes[key] )[0]
            for key in order if nodes[key].get( "_work_objections" )
    }
    errors = [
            key for key in order
            if nodes[key].get( "_resolve_error" ) or graded.get( key ) == "error"
    ]
    warnings = [ key for key in order if graded.get( key ) == "warning" ]
    clones = [ key for key in order if nodes[key].get( "_clone_dir" ) ]
    develop_notes = [
            key for key in order
            if nodes[key].get( "_develop_unused" ) or graded.get( key ) == "note"
    ]
    lines = [
            "",
            "Cascade plan: {} then this package [{}]==[{}]: {}".format(
                    storage.emphasised_count_phrase(
                            len( order ), "package dependency", "package dependencies"
                    ),
                    as_info( str( tip_package ) ),
                    as_info( str( tip_version ) ),
                    storage.format_severity_count_brackets(
                            errors=len( errors ),
                            warnings=len( warnings ),
                            notes=len( clones ) + len( develop_notes ),
                    ),
            ),
            pipe.rstrip(),
    ]
    total = len( order )
    # Hang detail lines under the label, whatever width the ordinals need.
    marker_width = len( "{} of {}".format( total, total ) )
    continuation = pipe + " " * ( marker_width + 2 )
    prose_width = max(
            storage.WIDEST_PROSE - len( continuation ), storage.NARROWEST_PROSE
    )
    for ordinal, key in enumerate( order, start=1 ):
        entry = nodes[key]
        marker = "{} of {}".format( ordinal, total ).rjust( marker_width )
        lines.append( "{}{}  {}".format( tee, marker, as_info( node_label( entry ) ) ) )
        error = entry.get( "_resolve_error" )
        if error:
            wrapped = storage.wrapped( "error: " + error, prose_width )
            lines.append( continuation + as_error( wrapped[0] ) )
            lines.extend( continuation + as_error( line ) for line in wrapped[1:] )
        elif entry.get( "_clone_dir" ):
            pin = entry.get( "_clone_revision" )
            note = "note: would clone [{}]{} into [{}]".format(
                    entry.get( "_clone_url" ),
                    " at [{}]".format( pin ) if pin else "",
                    storage.display_path( entry["_clone_dir"] ),
            )
            for wrapped_line in storage.wrapped( note, prose_width ):
                lines.append( continuation + as_notice( wrapped_line ) )
            for wrapped_line in storage.wrapped(
                    "note: its own package dependencies are not known until that "
                    "tree exists, so nothing is planned beneath it",
                    prose_width,
            ):
                lines.append( continuation + as_notice( wrapped_line ) )
        else:
            publisher = entry.get( "_publisher_dir" )
            lines.append( "{}publisher [{}]{}".format(
                    continuation,
                    as_notice( storage.display_path( str( publisher ) ) if publisher else "" ),
                    " (develop)" if entry.get( "_from_develop" ) else "",
            ) )
        # Unused-develop and local-work notes still belong beside a resolve error:
        # the header may already have counted them, and silence was the soak surprise.
        for wrapped_line in _publisher_plan_notes( entry, prose_width ):
            lines.append( continuation + wrapped_line )
    lines.append( "{}then this package [{}]==[{}] from this tree".format(
            elbow, as_info( str( tip_package ) ), as_info( str( tip_version ) )
    ) )
    return lines


def session_begin_lines( ordinal, total, label, publisher_dir, command, width=None ) -> list[str]:
    """Banner opening one nested session, so the extra ``scons`` run is visible."""
    return [
            "",
            as_subdued( RULE * ( width or storage.WIDEST_PROSE ) ),
            "cascade session {} of {}: {}".format( ordinal, total, as_info( str( label ) ) ),
            "  publisher [{}]".format( as_notice( storage.display_path( str( publisher_dir ) ) ) ),
            "  command [{}]".format( as_notice( str( command ) ) ),
    ]


def session_end_lines( ordinal, total, label, elapsed_nanosecs=None ) -> list[str]:
    """Banner closing one nested session. Claims nothing about what was uploaded.

    Telling an up-to-date no-op from a real upload needs the registry query that
    Phase 2c builds; see ``design/plans/package-build-publish-deps.md``.
    """
    taken = ""
    if elapsed_nanosecs is not None:
        taken = " in {}".format(
                as_notice( timer.as_duration_string( elapsed_nanosecs ) )
        )
    return [
            "cascade session {} of {} finished: {}{}".format(
                    ordinal, total, as_info( str( label ) ), taken
            ),
    ]


def sessions_complete_lines( total, tip_package, tip_version, width=None ) -> list[str]:
    """Banner handing the console back to this package's build."""
    return [
            "",
            as_subdued( RULE * ( width or storage.WIDEST_PROSE ) ),
            "cascade sessions complete: {}; resuming this package [{}]==[{}]".format(
                    storage.emphasised_count_phrase(
                            total, "nested publish", "nested publishes"
                    ),
                    as_info( str( tip_package ) ),
                    as_info( str( tip_version ) ),
            ),
    ]


def write_lines( lines, out=None ) -> None:
    """Emit report lines unprefixed — tree glyphs do not survive log labels."""
    stream = out if out is not None else sys.stdout
    for line in lines:
        stream.write( line + "\n" )


# Plan reports recorded during the sconscript read; see finish_plan_only().
_plan_reports: list[dict] = []


def reset_plan_reports() -> None:
    del _plan_reports[:]


def plan_reports() -> list[dict]:
    return list( _plan_reports )


def record_plan_report( tip_package, tip_version, error_count, clone_count=0 ) -> None:
    _plan_reports.append( {
            "package": str( tip_package ),
            "version": str( tip_version ),
            "errors": int( error_count ),
            "clones": int( clone_count ),
    } )


def finish_plan_only( env=None, out=None ) -> int:
    """Closing line and exit status for ``--cascade-plan``.

    Called once the sconscript read is done (the ``--dump`` pattern in
    ``construct.py``) rather than from the publisher, so a run with several tips,
    toolchains, or sconscripts reports all of them instead of only the first.

    ``env`` lets the missing-cascade-flag refusal be reported here too: a project
    that constructs no publisher never reaches the refusal in
    :func:`maybe_run_cascade`.
    """
    stream = out if out is not None else sys.stdout
    if not _plan_reports:
        if env is not None and not cascade_enabled( env ):
            write_lines( [
                    "",
                    "--{}: requires --{}, which is the flag it plans."
                    .format( CASCADE_PLAN_OPTION, CASCADE_OPTION ),
            ], out=stream )
            return 1
        write_lines( [
                "",
                "--{}: no GitLab package publisher was constructed, so there is "
                "no cascade plan. Run from a project that publishes a GitLab "
                "package with env.PublishPackage.".format( CASCADE_PLAN_OPTION ),
        ], out=stream )
        return 1

    errors = sum( report["errors"] for report in _plan_reports )
    clones = sum( report.get( "clones", 0 ) for report in _plan_reports )
    planned = storage.emphasised_count_phrase( len( _plan_reports ), "package" )
    if errors:
        write_lines( [
                "",
                "--{}: {} planned, {} without a publisher tree. Plant the "
                "missing trees, pass --{} to fetch the ones with a URL "
                "package_source, set --{}, or give those dependencies a "
                "filesystem package_source.".format(
                        CASCADE_PLAN_OPTION,
                        planned,
                        storage.emphasised_count_phrase( errors, "dependency", "dependencies" ),
                        CLONE_OPTION,
                        PUBLISHER_ROOT_OPTION,
                ),
        ], out=stream )
        return 1

    would_clone = ""
    if clones:
        would_clone = ", {} to clone first".format(
                storage.emphasised_count_phrase(
                        clones, "publisher tree", "publisher trees"
                )
        )
    write_lines( [
            "",
            "--{}: {} planned{}; nothing was built, published, uploaded, or "
            "cloned.".format( CASCADE_PLAN_OPTION, planned, would_clone ),
    ], out=stream )
    return 0


# Flags that must not re-enter on nested publishes (exact match).
_NESTED_DROP_EXACT = frozenset( {
        "--" + CASCADE_OPTION,
        "--" + CASCADE_PLAN_OPTION,
        "--" + PUBLISHER_ROOT_OPTION,
        "--" + CLONE_OPTION,
        "--" + MODIFIED_DEVELOP_OPTION,
        "--amend-package-manifest",
        "--cuppa-mode",
} )

# Same flags when written as ``--flag=value``.
_NESTED_DROP_PREFIXES = tuple(
        flag + "=" for flag in (
                "--" + CASCADE_OPTION,
                "--" + PUBLISHER_ROOT_OPTION,
                "--amend-package-manifest",
        )
)

# Separate-arg forms whose following token is the value.
_NESTED_DROP_TAKES_VALUE = frozenset( {
        "--" + PUBLISHER_ROOT_OPTION,
} )

# Location dependency option getters that register tip-scoped CLI flags.
_LOCATION_OPTION_GETTERS = (
        "location_option",
        "develop_option",
        "branch_path_option",
        "include_option",
        "sys_include_option",
        "extra_sub_path_option",
        "source_path_option",
        "linktype_option",
)


def tip_dependency_option_flags( env ) -> frozenset[str]:
    """CLI flags the tip registered for its dependencies — invalid on a nested publisher.

    Nested sessions load a different sconstruct, so tip-scoped overrides such as
    ``--capy-gitlab-develop=../capy`` are both unknown there and path-wrong (relative paths
    are anchored to the tip's sconstruct directory). Global settings travel through
    ``~/.cuppaconfig``, which the child loads itself.
    """
    flags: set[str] = set()
    dependencies = env.get( "dependencies" ) or {}
    for name, factory in dependencies.items():
        owner = getattr( factory, "__self__", factory )
        for attr in _LOCATION_OPTION_GETTERS:
            getter = getattr( owner, attr, None )
            if not callable( getter ):
                continue
            try:
                option_id = getter()
            except TypeError:
                continue
            if option_id:
                flags.add( "--" + str( option_id ) )

        manager = getattr( owner, "_package_manager", None )
        dep_name = getattr( owner, "_name", None ) or name
        if not manager or not dep_name:
            continue
        from cuppa.package_managers.gitlab import GitlabPackageDependency
        for option, attributes in GitlabPackageDependency._options.items():
            option_id = GitlabPackageDependency.option_id(
                    manager, dep_name, option, attributes
            )
            flags.add( "--" + option_id )
    return frozenset( flags )


def tip_forward_args( argv=None, env=None ) -> list[str]:
    """Tip SCons/cuppa option args suitable for a nested ``--publish-package``.

    Uses the live tip ``sys.argv`` (variant, toolchains, offline, …), not
    ``configured_options`` from ``~/.cuppaconfig`` — those conf keys are not
    all valid CLI flags and omit the tip's explicit ``--rel`` / ``--toolchains``.

    Tip dependency-scoped options are dropped when ``env`` is supplied: the child
    has never registered them.
    """
    if argv is None:
        argv = sys.argv
    drop_exact = set( _NESTED_DROP_EXACT )
    drop_prefixes = list( _NESTED_DROP_PREFIXES )
    drop_takes_value = set( _NESTED_DROP_TAKES_VALUE )
    if env is not None:
        for flag in tip_dependency_option_flags( env ):
            drop_exact.add( flag )
            drop_prefixes.append( flag + "=" )
            drop_takes_value.add( flag )

    forwarded: list[str] = []
    skip_next = False
    for arg in list( argv[1:] ):
        if skip_next:
            skip_next = False
            continue
        if arg in drop_exact:
            if arg in drop_takes_value:
                skip_next = True
            continue
        if any( arg.startswith( prefix ) for prefix in drop_prefixes ):
            continue
        forwarded.append( arg )

    if "-D" not in forwarded:
        forwarded.insert( 0, "-D" )
    if "--publish-package" not in forwarded:
        forwarded.append( "--publish-package" )
    return forwarded


def argv_for_nested_publish( argv=None, env=None ) -> list[str]:
    """Full subprocess argv: ``python -m cuppa`` + :func:`tip_forward_args`."""
    return [ sys.executable, "-m", "cuppa" ] + tip_forward_args( argv, env=env )


def invalidate_package_consume_cache( env, package: str, version: str ) -> list[str]:
    """Remove download archives and extracts for ``package``/``version``.

    Cascade-internal step so the tip does not keep stale same-version bits.
    Pair with :func:`refresh_package_consume_cache` so the tip's already-resolved
    ``package_dir`` is populated again. Returns paths removed.
    """
    removed: list[str] = []
    downloads_root = env.get( "downloads_root" ) or env.get( "cache_root" )
    dependencies_root = env.get( "dependencies_root" )
    variant = None
    try:
        from cuppa.package_managers.gitlab import tool_variant
        variant = tool_variant( env )
    except Exception:
        variant = None

    if downloads_root:
        cache_dir = os.path.join( str( downloads_root ), "packages", package, str( version ) )
        if os.path.isdir( cache_dir ):
            shutil.rmtree( cache_dir )
            removed.append( cache_dir )

    if dependencies_root and variant:
        extract_pkg = os.path.join(
                str( dependencies_root ), variant, package, str( version )
        )
        if os.path.isdir( extract_pkg ):
            shutil.rmtree( extract_pkg )
            removed.append( extract_pkg )
        # Installer layout may nest under downloads/packages/.../<tool_variant>
        if downloads_root:
            alt_variant = os.path.join(
                    str( downloads_root ), "packages", package, str( version ), variant
            )
            if os.path.isdir( alt_variant ):
                shutil.rmtree( alt_variant )
                removed.append( alt_variant )

    return removed


def _tip_dependency_factory( env, entry: dict ):
    """Return the tip ``env['dependencies']`` entry for ``entry``, if any.

    Cuppa stores ``cls.create`` (callable), not the class itself — see
    ``build_with_package.base.add_to_env``.
    """
    deps = env.get( "dependencies" ) or {}
    name = entry.get( "name" )
    if name and name in deps:
        return deps[name]
    package = entry.get( "package" )
    if not package:
        return None
    for factory in deps.values():
        owner = _factory_owner( factory )
        if getattr( owner, "_package", None ) == package:
            return factory
        if getattr( owner, "_name", None ) == package:
            return factory
    return None


def _factory_owner( factory ):
    """Class that owns ``cls.create`` when ``factory`` is that classmethod."""
    owner = getattr( factory, "__self__", None )
    if owner is not None:
        return owner
    return factory


def _evict_cached_package( factory, package: str, version: str ) -> int:
    """Drop tip-cached ``GitlabPackageDependency`` instances for this pin."""
    owner = _factory_owner( factory )
    cached = getattr( owner, "_cached_packages", None )
    if not cached:
        return 0
    version = str( version )
    removed = 0
    for key in list( cached.keys() ):
        inst = cached[key]
        if (
                getattr( inst, "_package", None ) == package
                and str( getattr( inst, "_version", "" ) ) == version
        ):
            del cached[key]
            removed += 1
    return removed


def _call_tip_dependency_factory( factory, env ):
    """Invoke a tip dependency factory the same way ``BuildWith`` does."""
    create = getattr( factory, "create", None )
    if callable( create ) and create is not factory:
        return create( env )
    if callable( factory ):
        return factory( env )
    return None


def refresh_package_consume_cache( env, entry: dict, tip_publisher=None ) -> list[str]:
    """Invalidate then re-fetch/extract so the tip's ``package_dir`` is usable again.

    Cascade runs after the tip's ``BuildWith`` has already resolved paths; wiping
    alone leaves CMake pointing at an empty tree. Re-create the tip package
    dependency so download+extract repopulate the same paths.
    """
    package = entry["package"]
    version = entry["version"]
    label = node_label( entry )
    removed = invalidate_package_consume_cache( env, package, version )
    if removed:
        logger.info(
                "Cascade: invalidated consume cache for [{}]: {}"
                .format( as_info( label ), as_notice( ", ".join( removed ) ) )
        )

    factory = _tip_dependency_factory( env, entry )
    package_dir = None
    if factory is not None:
        _evict_cached_package( factory, package, version )
        try:
            built = _call_tip_dependency_factory( factory, env )
        except Exception as error:
            raise SCons.Errors.StopError(
                    "cascade re-fetch of [{}] failed: {}"
                    .format( label, error )
            ) from error
        if built is None:
            raise SCons.Errors.StopError(
                    "cascade re-fetch of [{}] returned no package"
                    .format( label )
            )
        package_obj = built.package() if hasattr( built, "package" ) else built
        package_dir = (
                package_obj.package_dir()
                if hasattr( package_obj, "package_dir" )
                else getattr( package_obj, "_package_dir", None )
        )
    else:
        registry = entry.get( "registry" )
        if not registry or registry == "same":
            registry = getattr( tip_publisher, "_registry", None ) if tip_publisher else None
        if not registry or registry == "same":
            raise SCons.Errors.StopError(
                    "cascade cannot re-fetch [{}]: tip has no BuildWith factory "
                    "and registry is unresolved"
                    .format( label )
            )
        variant = entry.get( "variant" )
        if not variant and tip_publisher is not None:
            variant = getattr( tip_publisher, "_variant", None )
        from cuppa.package_managers.gitlab import GitlabPackageDependency
        try:
            package_obj = GitlabPackageDependency(
                    env,
                    registry=registry,
                    package=package,
                    version=version,
                    variant=variant or "rel",
            )
        except Exception as error:
            raise SCons.Errors.StopError(
                    "cascade re-fetch of [{}] failed: {}"
                    .format( label, error )
            ) from error
        package_dir = package_obj.package_dir()

    logger.info(
            "Cascade: re-fetched [{}] to [{}]"
            .format( as_info( label ), as_notice( str( package_dir ) ) )
    )
    return removed


def publisher_work_report( env, nodes: dict, order ) -> list[tuple]:
    """``(key, path, objections, warning)`` for every publisher tree cascade will publish from.

    Observed once, here, so the plan and the real run describe the same state and each working
    copy is read once rather than per session.
    """
    from cuppa.develop import inspect

    observed = []
    for key in order:
        entry = nodes[key]
        path = entry.get( "_publisher_dir" )
        if not path:
            continue
        copy = inspect( entry["name"], path )
        warning = None
        if entry.get( "_from_develop" ) and not copy.is_working_copy:
            # Only said of a develop tree, which the operator named as a working copy. A
            # rooted or cloned tree that is not one is ordinary, not worth a line.
            warning = (
                    "not a working copy cuppa can read, so whether its contents are "
                    "reproducible cannot be checked"
            )
        observed.append( ( key, path, develop_publish_objections( copy ), warning ) )
    return observed


def _record_publisher_objections( env, nodes: dict, order ) -> None:
    """Put what a real run would say about each tree onto the nodes, so the plan reports it."""
    allowed = modified_develop_publish_allowed( env )
    for key, _path, objections, _warning in publisher_work_report( env, nodes, order ):
        if not objections:
            continue
        nodes[key]["_work_objections"] = objections
        nodes[key]["_work_objections_allowed"] = allowed


def judge_publisher_trees( env, nodes: dict, order ) -> None:
    """Stop before the first upload when a develop tree holds work only this machine has.

    Publishing from such a tree puts a version in the registry that nobody can rebuild from
    its history. Every offending tree is named at once, because learning about the second one
    after the first has already uploaded is no use.

    A ``--publisher-root`` or cloned tree runs the same hazard and is reported the same way,
    but only warns: those trees are how cascade shipped, and refusing them would stop a
    workflow that predates this question. Promoting that warning is a decision of its own —
    see ``design/plans/package-develop-local.md``.
    """
    observed = publisher_work_report( env, nodes, order )
    override = modified_develop_publish_allowed( env )
    refused = []
    for key, path, objections, warning in observed:
        label = node_label( nodes[key] )
        shown = storage.display_path( path )
        if warning:
            logger.warn( "Cascade: publisher [{}] at [{}] is {}".format(
                    as_info( label ), as_notice( shown ), warning
            ) )
        if not objections:
            continue
        if nodes[key].get( "_from_develop" ) and not override:
            refused.append( ( label, shown, objections ) )
            continue
        logger.warn(
                "Cascade: publishing [{}] from [{}] with {}{}".format(
                        as_info( label ),
                        as_notice( shown ),
                        as_warning( ", ".join( objections ) ),
                        " — allowed by --{}".format( MODIFIED_DEVELOP_OPTION )
                                if nodes[key].get( "_from_develop" ) else "",
                )
        )
    if not refused:
        return
    raise SCons.Errors.StopError(
            "cascade will not publish from a develop tree holding work only this machine "
            "has, because the registry version could not be rebuilt from history: {}. "
            "Commit and push, drop --develop for the publish run, or pass --{} to publish "
            "anyway."
            .format(
                    "; ".join(
                            "[{}] at [{}] has {}".format( label, shown, ", ".join( objections ) )
                            for label, shown, objections in refused
                    ),
                    MODIFIED_DEVELOP_OPTION,
            )
    )


def run_nested_publish( env, publisher_dir: str, label: str, ordinal=1, total=1 ) -> None:
    argv = argv_for_nested_publish( env=env )
    nested_env = os.environ.copy()
    nested_env[NESTED_ENV] = "1"
    root = str( env.get( "sconstruct_dir" ) or "" )
    pythonpath_parts = []
    if root:
        pythonpath_parts.append( root )
    # Prefer the Cuppa being developed (repo) when present on PYTHONPATH.
    existing = nested_env.get( "PYTHONPATH", "" )
    if existing:
        pythonpath_parts.extend( part for part in existing.split( os.pathsep ) if part )
    # Ensure this cuppa package is importable (tests / editable install).
    cuppa_root = os.path.abspath( os.path.join( os.path.dirname( __file__ ), "..", ".." ) )
    if cuppa_root not in pythonpath_parts:
        pythonpath_parts.insert( 0, cuppa_root )
    nested_env["PYTHONPATH"] = os.pathsep.join( pythonpath_parts )

    write_lines( session_begin_lines(
            ordinal, total, label, publisher_dir, " ".join( argv )
    ) )
    session_timer = timer.Timer()
    completion = subprocess.run(
            argv,
            cwd=publisher_dir,
            env=nested_env,
    )
    session_timer.stop()
    if completion.returncode != 0:
        raise SCons.Errors.StopError(
                "cascade session {} of {} — publish of [{}] failed with return "
                "code [{}] (cwd={})"
                .format( ordinal, total, label, completion.returncode, publisher_dir )
        )
    write_lines( session_end_lines(
            ordinal, total, label, session_timer.elapsed().wall
    ) )


def maybe_run_cascade( env, publisher ) -> None:
    """Run cascade when the flag is set; no-op for nested invokes or when unset.

    Under ``--cascade-plan`` this reports the resolved order and returns without
    running a nested publish; ``construct.py`` exits after the sconscript read.
    """
    plan_only = cascade_plan_enabled( env )
    if plan_only and not cascade_enabled( env ):
        raise SCons.Errors.StopError(
                "--{} requires --{}"
                .format( CASCADE_PLAN_OPTION, CASCADE_OPTION )
        )
    if not cascade_enabled( env ):
        return
    if _is_nested():
        logger.info(
                "Cascade: nested invoke — skipping further "
                "--{}".format( CASCADE_OPTION )
        )
        return
    # Plan mode publishes nothing, so it does not need the publish flag.
    if not plan_only and not env.get_option( "publish-package" ):
        raise SCons.Errors.StopError(
                "--{} requires --publish-package"
                .format( CASCADE_OPTION )
        )

    tip_package = str( getattr( publisher, "_package", "" ) )
    tip_version = str( getattr( publisher, "_version", "" ) )

    nodes, edges = build_cascade_graph(
            env, publisher, tolerant=plan_only, allow_clone=not plan_only
    )
    if not nodes:
        logger.info(
                "Cascade: tip [{}] declares no package dependencies — nothing to publish"
                .format( as_info( tip_package ) )
        )
        if plan_only:
            record_plan_report( tip_package, tip_version, 0 )
        return

    order = topological_publish_order( nodes, edges )
    if plan_only:
        _record_publisher_objections( env, nodes, order )
    write_lines( cascade_plan_lines( nodes, order, tip_package, tip_version ) )

    if plan_only:
        record_plan_report(
                tip_package,
                tip_version,
                sum(
                        1 for key in order
                        if nodes[key].get( "_resolve_error" )
                        or (
                                nodes[key].get( "_work_objections" )
                                and _work_verdict( nodes[key] )[0] == "error"
                        )
                ),
                clone_count=sum( 1 for key in order if nodes[key].get( "_clone_dir" ) ),
        )
        return

    judge_publisher_trees( env, nodes, order )

    total = len( order )
    for ordinal, key in enumerate( order, start=1 ):
        entry = nodes[key]
        run_nested_publish(
                env,
                entry["_publisher_dir"],
                node_label( entry ),
                ordinal=ordinal,
                total=total,
        )
        refresh_package_consume_cache( env, entry, tip_publisher=publisher )

    write_lines( sessions_complete_lines( total, tip_package, tip_version ) )
