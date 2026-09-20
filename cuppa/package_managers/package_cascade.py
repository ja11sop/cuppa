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
import re
import shutil
import subprocess
import sys
from collections import defaultdict, deque

import SCons.Errors

from cuppa import timer
from cuppa.colourise import (
        as_emphasised,
        as_error,
        as_error_label,
        as_info,
        as_info_label,
        as_notice,
        as_subdued,
        as_warning,
)
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
COLLECT_CASCADE_OPTION = "collect-cascade"
UPDATE_PUBLISHERS_OPTION = "update-publishers"
PUBLISHER_ROOT_OPTION = "publisher-root"
CLONE_OPTION = "clone-publishers"
MODIFIED_DEVELOP_OPTION = "publish-modified-develop"
NESTED_ENV = "CUPPA_CASCADE_NESTED"
STAGE_PACKAGE_OPTION = "stage-package"
STAGE_DEVELOP_OPTION = "stage-develop"
STAGE_DEVELOP_PLAN_OPTION = "stage-develop-plan"

# Where clones land under the storage root when no publisher root was given.
PUBLISHERS_DIRNAME = "publishers"

# Same rule glyph as the dependency listing tree.
RULE = '-'

# Flags emphasised on the plan's command-line banner (bold info).
_PLAN_BANNER_EXACT = frozenset( {
        "--" + CASCADE_OPTION,
        "--" + CASCADE_PLAN_OPTION,
        "--" + COLLECT_CASCADE_OPTION,
        "--" + UPDATE_PUBLISHERS_OPTION,
        "--" + CLONE_OPTION,
        "--" + PUBLISHER_ROOT_OPTION,
        "--" + MODIFIED_DEVELOP_OPTION,
        "--" + STAGE_DEVELOP_OPTION,
        "--" + STAGE_DEVELOP_PLAN_OPTION,
        "--develop",
        "--publish-package",
} )


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


def cascade_collect_enabled( env ) -> bool:
    getter = getattr( env, "get_option", None )
    if not callable( getter ):
        return False
    return bool( getter( COLLECT_CASCADE_OPTION ) )


def cascade_update_enabled( env ) -> bool:
    getter = getattr( env, "get_option", None )
    if not callable( getter ):
        return False
    return bool( getter( UPDATE_PUBLISHERS_OPTION ) )


def cascade_stop_before_build( env ) -> bool:
    """Plan, collect, or update-without-publish: resolve/report, do not nested-build."""
    if cascade_plan_enabled( env ) or cascade_collect_enabled( env ):
        return True
    if not cascade_update_enabled( env ):
        return False
    getter = getattr( env, "get_option", None )
    if callable( getter ) and getter( "publish-package" ):
        return False
    return True


def _no_exec_enabled( env ) -> bool:
    """SCons ``-n`` / ``--no-exec`` — dry-run that still runs configure."""
    getter = getattr( env, "get_option", None )
    if callable( getter ):
        return bool( getter( "no_exec" ) )
    try:
        return bool( SCons.Script.GetOption( "no_exec" ) )
    except Exception:
        return False


def _clean_enabled( env ) -> bool:
    """SCons ``-c`` / ``--clean`` — remove targets rather than build/publish."""
    if env is not None:
        try:
            if env.get( "clean" ):
                return True
        except Exception:
            pass
        getter = getattr( env, "get_option", None )
        if callable( getter ):
            return bool( getter( "clean" ) )
    try:
        return bool( SCons.Script.GetOption( "clean" ) )
    except Exception:
        return False


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


def stage_develop_enabled( env ) -> bool:
    """Whether ``--stage-develop`` asked to nest-build develop trees with an sconstruct."""
    getter = getattr( env, "get_option", None )
    if callable( getter ) and getter( STAGE_DEVELOP_OPTION ):
        return True
    return bool( env.get( "stage_develop" ) or env.get( STAGE_DEVELOP_OPTION ) )


def stage_develop_plan_enabled( env ) -> bool:
    """Whether ``--stage-develop-plan`` asked for a dry-run of location stage order."""
    getter = getattr( env, "get_option", None )
    if callable( getter ) and getter( STAGE_DEVELOP_PLAN_OPTION ):
        return True
    return bool(
            env.get( "stage_develop_plan" ) or env.get( STAGE_DEVELOP_PLAN_OPTION )
    )


def develop_mode_enabled( env ) -> bool:
    getter = getattr( env, "get_option", None )
    if callable( getter ) and getter( "develop" ):
        return True
    return bool( env.get( "develop" ) )


def require_stage_develop_with_develop( env ) -> None:
    if stage_develop_enabled( env ) and not develop_mode_enabled( env ):
        raise SCons.Errors.StopError(
                "--{} requires --develop (it nest-builds package and location "
                "develop trees that have an sconstruct)"
                .format( STAGE_DEVELOP_OPTION )
        )


def require_stage_develop_plan_with_develop( env ) -> None:
    if stage_develop_plan_enabled( env ) and not develop_mode_enabled( env ):
        raise SCons.Errors.StopError(
                "--{} requires --develop (it reports the location develop "
                "stage order without building)"
                .format( STAGE_DEVELOP_PLAN_OPTION )
        )


def _location_stage_roots( env ) -> set:
    """Absolute develop roots already nest-built for location ``--stage-develop``."""
    key = "_cuppa_location_stage_develop_roots"
    roots = env.get( key )
    if roots is None:
        roots = set()
        try:
            env[key] = roots
        except Exception:
            pass
    return roots


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


def publisher_lookup_root( env ) -> str:
    """Forest searched for an existing publisher tree.

    Same path as :func:`publisher_clone_root`: an explicit ``--publisher-root`` when
    set, otherwise ``<storage-root>/publishers``. Looking where clones land means a
    tree created by ``--clone-publishers`` is found again without re-passing that
    flag, matching how ``downloads_root`` / ``dependencies_root`` fall back to
    ``storage_root``.
    """
    return publisher_clone_root( env )


def publisher_clone_destination( env, entry: dict ) -> str:
    """``{root}/{name}`` — the first shape :func:`_resolve_under_publisher_root`
    looks in, so a clone is found again by the same rules that failed to find it.

    Keyed by dependency name like the rest of the product: the consume cache is
    already ``downloads_root/packages/{package}/{version}`` with no registry in
    the key. Two dependencies claiming one destination from different URLs is
    refused rather than resolved by inventing a registry-qualified path here.
    """
    return os.path.join( publisher_lookup_root( env ), str( entry["name"] ) )


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


def dependency_develop_cli_flag( env, entry: dict ) -> str | None:
    """``--<name>-<manager>-develop`` for this edge when the tip registered that dependency."""
    factory = _tip_dependency_factory( env, entry )
    if factory is None:
        return None
    owner = _factory_owner( factory )
    name = entry.get( "name" ) or getattr( owner, "_name", None )
    manager = getattr( owner, "_package_manager", None )
    if not name or not manager:
        return None
    from cuppa.package_managers.gitlab import GitlabPackageDependency
    return "--" + GitlabPackageDependency.option_id( manager, name, "develop" )


def _remember_plan_lookup( entry: dict, env ) -> None:
    """Stash lookup-root and develop CLI flag for plan judgements built later."""
    entry["_lookup_root"] = publisher_lookup_root( env )
    flag = dependency_develop_cli_flag( env, entry )
    if flag:
        entry["_develop_cli_flag"] = flag


def _plan_banner_emphasises( arg: str ) -> bool:
    """Whether ``arg`` is a cascade / develop flag the plan banner should emphasise."""
    if arg in _PLAN_BANNER_EXACT:
        return True
    if not arg.startswith( "--" ):
        return False
    flag, _, _value = arg.partition( "=" )
    if flag in _PLAN_BANNER_EXACT:
        return True
    if flag.endswith( "-develop" ) or flag.endswith( "-package-source" ):
        return True
    return False


def colour_plan_command_line( argv=None ) -> str:
    """``cuppa …`` with cascade-relevant flags as emphasised info."""
    if argv is None:
        argv = sys.argv
    tokens = list( argv )
    if not tokens:
        return "cuppa"
    # Operators type ``cuppa``; argv[0] is often a path to scons or python -m cuppa.
    first = os.path.basename( str( tokens[0] ) )
    if first in ( "cuppa", "scons" ) or first.startswith( "cuppa" ):
        display = [ "cuppa" ] + [ str( t ) for t in tokens[1:] ]
    elif first in ( "python", "python3" ) and len( tokens ) >= 3 and str( tokens[1] ) == "-m":
        display = [ "cuppa" ] + [ str( t ) for t in tokens[3:] ]
    else:
        display = [ "cuppa" ] + [ str( t ) for t in tokens[1:] ]

    parts = []
    for arg in display:
        if arg == "--cuppa-mode" or arg.startswith( "--cuppa-mode=" ):
            continue
        if _plan_banner_emphasises( arg ):
            if "=" in arg and arg.startswith( "--" ):
                flag, _, value = arg.partition( "=" )
                parts.append( as_emphasised( as_info( flag ) ) + "=" + as_info( value ) )
            else:
                parts.append( as_emphasised( as_info( arg ) ) )
        else:
            parts.append( arg )
    return " ".join( parts )


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
    """Whether a develop path is a publisher project rather than a built package prefix.

    ``env`` is accepted for call-site symmetry with cascade helpers; the test is the
    tree shape alone. Under ``--develop``, consume builds that tree locally and links
    the staged package (slice D); cascade may still upload afterward.
    """
    del env  # reserved for call-site symmetry; inference is path-shaped only
    return develop_names_a_publisher_tree( path )


def looks_like_package_stage( path: str ) -> bool:
    """True when ``path`` has the include/ and lib/ layout a staged package needs."""
    return (
            os.path.isdir( os.path.join( path, "include" ) )
            and os.path.isdir( os.path.join( path, "lib" ) )
    )


def resolve_develop_package_stage(
        develop_root: str,
        package: str,
        version,
        env=None,
) -> str | None:
    """Locate ``final/<package>/<version>/`` (or another version) under a publisher tree.

    Prefers the tip's toolchain×variant layout when ``env`` supplies one, then scans
    ``_build/**/final/<package>/``. Returns the first path that looks like a staged
    package, or ``None``.
    """
    develop_root = os.path.abspath( develop_root )
    version = str( version )
    candidates: list[str] = []

    if env is not None:
        try:
            from cuppa.core.build_layout import sanitise_abi, tool_variant_dir
            toolchain = env.get( "toolchain" )
            variant = env.get( "variant" )
            arch = env.get( "target_arch" )
            abi = env.get( "abi" )
            toolchain_name = None
            if toolchain is not None:
                name_fn = getattr( toolchain, "name", None )
                toolchain_name = name_fn() if callable( name_fn ) else str( toolchain )
            variant_name = None
            if variant is not None:
                name_fn = getattr( variant, "name", None )
                variant_name = name_fn() if callable( name_fn ) else str( variant )
            if toolchain_name and variant_name and arch and abi is not None:
                tvd = tool_variant_dir(
                        toolchain_name, variant_name, arch, sanitise_abi( str( abi ) )
                )
                preferred = os.path.join(
                        develop_root, "_build", tvd, "final", package, version
                )
                candidates.append( preferred )
        except Exception:
            pass

    build_root = os.path.join( develop_root, "_build" )
    if os.path.isdir( build_root ):
        for dirpath, dirnames, _filenames in os.walk( build_root ):
            if os.path.basename( dirpath ) != "final":
                continue
            exact = os.path.join( dirpath, package, version )
            if exact not in candidates:
                candidates.append( exact )
            package_dir = os.path.join( dirpath, package )
            if os.path.isdir( package_dir ):
                try:
                    children = sorted( os.listdir( package_dir ) )
                except OSError:
                    children = []
                for child in children:
                    other = os.path.join( package_dir, child )
                    if os.path.isdir( other ) and other not in candidates:
                        candidates.append( other )
            dirnames[:] = []

    for path in candidates:
        if looks_like_package_stage( path ):
            return path
    return None


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
            entry["_cloned_now"] = False
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
    entry["_cloned_now"] = True
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
    _remember_plan_lookup( entry, env )

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
        # A configured path that is not a publisher tree is still an error without
        # --develop: the operator named a place that cannot publish.
        refusal = develop_tree_refusal( develop_dir )
        if refusal:
            raise SCons.Errors.StopError(
                    "a develop path for [{}] is configured at [{}], but {}. "
                    "Point it at the publisher project, or drop the develop path."
                    .format( name, develop_dir, refusal )
            )
        # Cascade will resolve it some other way; the plan says so rather than
        # leaving an operator to wonder why their tree was ignored.
        entry["_develop_unused"] = True

    lookup_root = publisher_lookup_root( env )

    if package_source:
        source = os.path.expanduser( str( package_source ) )
        if looks_like_url( source ):
            # An existing local tree always wins: it is what the operator planted,
            # and reusing it keeps a cascade run off the network. Search the default
            # storage publishers forest (or --publisher-root) the way downloads fall
            # back to storage_root.
            resolved = _resolve_under_publisher_root( lookup_root, name, package )
            if resolved:
                if entry.get( "_develop_unused" ):
                    # Plan will execute from the forest copy — warn that this is
                    # probably not what a configured develop path was meant for.
                    entry["_publisher_forest_hit"] = resolved
                return resolved
            url, revision = split_source_pin( source )
            if not clone_enabled( env ):
                destination = publisher_clone_destination( env, entry )
                entry["_clone_url"] = url
                entry["_clone_revision"] = revision
                entry["_clone_dir"] = destination
                if entry.get( "_develop_unused" ):
                    # Usable develop tree configured; forgetting --develop is the
                    # primary warning. Soft-graded in plan mode — see _node_judgements.
                    raise SCons.Errors.StopError(
                            "cascade will not use the develop tree for [{}] at [{}] "
                            "because --develop was not passed, and no publisher tree "
                            "was found under [{}]. Pass --develop, pass --{}, or set "
                            "--{}."
                            .format(
                                    name,
                                    storage.display_path( entry["_develop_dir"] ),
                                    storage.display_path( lookup_root ),
                                    CLONE_OPTION,
                                    PUBLISHER_ROOT_OPTION,
                            )
                    )
                # Cloneable URL, no local tree, clone flag off: a real run stops here.
                # Plan mode soft-grades this as a warning (+ notes), not a broken graph.
                entry["_needs_clone_opt_in"] = True
                raise SCons.Errors.StopError(
                        "package_source for [{}] is a URL [{}] and no local "
                        "working tree was found under [{}]. Pass --{} to clone it, "
                        "or set --{} to a forest that already holds it."
                        .format(
                                name,
                                source,
                                storage.display_path( lookup_root ),
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

    resolved = _resolve_under_publisher_root( lookup_root, name, package )
    if resolved:
        if entry.get( "_develop_unused" ):
            entry["_publisher_forest_hit"] = resolved
        return resolved
    if entry.get( "_develop_unused" ):
        raise SCons.Errors.StopError(
                "cascade will not use the develop tree for [{}] at [{}] because "
                "--develop was not passed, and no publisher tree was found under "
                "[{}]. Pass --develop or set --{}."
                .format(
                        name,
                        storage.display_path( entry["_develop_dir"] ),
                        storage.display_path( lookup_root ),
                        PUBLISHER_ROOT_OPTION,
                )
        )
    if not publisher_root_option( env ):
        raise SCons.Errors.StopError(
                "dependency [{}] has no package_source and no publisher tree was "
                "found under [{}]; set --{} or give the dependency a "
                "package_source"
                .format( name, storage.display_path( lookup_root ), PUBLISHER_ROOT_OPTION )
        )
    raise SCons.Errors.StopError(
            "could not resolve publisher for [{}] under --{}=[{}] "
            "(tried {{root}}/{{name}}, {{root}}/{{package}}, and one-level nesting)"
            .format( name, PUBLISHER_ROOT_OPTION, lookup_root )
    )


def _claim_clone_destination( claims, destination: str, entry: dict, url: str ) -> None:
    if claims is None:
        return
    claimed = claims.get( destination )
    if claimed and not _same_repository( claimed[1], url ):
        raise SCons.Errors.StopError(
                "cascade cannot clone both [{}] from [{}] and [{}] from [{}] "
                "into [{}]: two repositories claim one directory. Set --{} so "
                "they land apart, or plant one tree under a different path."
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
            # Remediable by an opt-in flag: plan mode reports a warning (+ notes), not
            # a broken graph. A real run still raised above.
            if nodes[key].get( "_develop_unused" ):
                continue
            if nodes[key].get( "_needs_clone_opt_in" ):
                continue
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


def _package_identity( name, version ) -> str:
    """``name [==version]`` — both emphasised info (plan intro, nodes, and tip line)."""
    emphasised = as_emphasised( as_info( str( name ) ) )
    pin = as_emphasised( as_info( str( version ) ) )
    return "{} [=={}]".format( emphasised, pin )


def _plan_dependency_label( entry ) -> str:
    """``name [==version]`` with optional subdued ``(package_source)`` when the edge carries one."""
    label = _package_identity( entry.get( "name" ), entry.get( "version" ) )
    source = entry.get( "package_source" )
    if source:
        label = "{} ({})".format( label, as_subdued( str( source ) ) )
    return label


def _plan_node_under( continuation, marker_width: int ) -> str:
    """Hang nested glyphs under a numbered plan node (``continuation`` is pipe or gap)."""
    return continuation + " " * ( marker_width + 2 )


# Branches that read as "the published default" without a configured name.
_STAGE_DEFAULT_BRANCHES = frozenset( { "master", "main" } )


def _display_stage_repo_url( url ) -> str | None:
    """``host/org/repo`` for a stage-plan label. Local paths are omitted."""
    if not url:
        return None
    from cuppa.core.dependency_identity import short_name_from_git_url
    return short_name_from_git_url( str( url ).strip() )


def _location_configured_url( env, name ) -> str | None:
    """Configured ``location=`` URL for a dependency name, when ``location_id`` is available."""
    dependencies = env.get( "dependencies" ) or {}
    factory = dependencies.get( name )
    if factory is None:
        return None
    dependency = getattr( factory, "__self__", factory )
    location_id = getattr( dependency, "location_id", None )
    if not callable( location_id ):
        return None
    try:
        identity = location_id( env )
        if identity:
            return identity[0]
    except ( TypeError, IndexError, KeyError, AttributeError ):
        return None
    return None


def _observed_origin_url( root ) -> str | None:
    """Origin URL of a working copy, or None when it is not a git tree."""
    from cuppa.scms.git import Git
    try:
        _url, repository, _branch, _remote, _revision = Git.info( root )
    except ( OSError, TypeError, ValueError, Git.Error ):
        return None
    return repository or None


def _checkout_ref( copy, root ) -> str | None:
    """Branch, tag, or ``detached`` actually checked out — not the declared pin."""
    from cuppa.scms.git import Git
    if not copy.is_working_copy:
        return None
    if not copy.detached and copy.branch:
        return copy.branch
    try:
        revision = ( Git.get_revision( root ) or "" ).strip()
    except ( OSError, TypeError, ValueError, Git.Error ):
        revision = ""
    if revision and "~" not in revision and "^" not in revision:
        if revision.startswith( "tags/" ):
            revision = revision[ len( "tags/" ) : ]
        return revision
    return "detached"


def _tip_stage_branch( env ) -> str | None:
    """Branch of the project running the plan (the one other develops are judged against)."""
    from cuppa.develop import inspect

    root = env.get( "sconstruct_dir" )
    if not root:
        return None
    copy = inspect( "tip", root )
    if copy.detached or not copy.branch:
        return None
    return copy.branch


def _stage_branch_unexpected( ref, tip_branch, env ) -> bool:
    """True when the checkout is neither the tip branch nor a default branch."""
    if not ref or ref == "detached":
        return bool( ref )
    acceptable = set( _STAGE_DEFAULT_BRANCHES )
    for key in ( "location_default_branch", "location_base_branch" ):
        configured = env.get( key )
        if configured:
            acceptable.add( str( configured ) )
    if tip_branch:
        acceptable.add( tip_branch )
    return ref not in acceptable


def _format_stage_repo_hint( short, ref, state, unexpected ) -> str:
    """Muted ``(host/org/repo@branch state)``; an off-branch ref is a warning."""
    parts = [ as_subdued( " (" ) ]
    if short and ref:
        parts.append( as_subdued( "{}@".format( short ) ) )
        parts.append( as_warning( ref ) if unexpected else as_subdued( ref ) )
        parts.append( as_subdued( " {}".format( state ) ) )
    elif short:
        parts.append( as_subdued( "{} {}".format( short, state ) ) )
    elif ref:
        parts.append( as_warning( ref ) if unexpected else as_subdued( ref ) )
        parts.append( as_subdued( " {}".format( state ) ) )
    else:
        parts.append( as_subdued( state ) )
    parts.append( as_subdued( ")" ) )
    return "".join( parts )


def _stage_repo_state_hint(
        env, name, root, tip_branch=None, wants_only=False
) -> str:
    """Muted ``(host/org/repo@branch state)`` from the develop working copy."""
    from cuppa.develop import inspect, state_summary

    if wants_only:
        short = _display_stage_repo_url( _location_configured_url( env, name ) )
        if short:
            return as_subdued( " (wants {})".format( short ) )
        return ""

    copy = inspect( name, root )
    state = state_summary( copy )
    short = _display_stage_repo_url(
            _observed_origin_url( root ) or _location_configured_url( env, name )
    )
    ref = _checkout_ref( copy, root )
    return _format_stage_repo_hint(
            short,
            ref,
            state,
            _stage_branch_unexpected( ref, tip_branch, env ),
    )


def _plain_count_phrase( count, noun, plural_noun=None ) -> str:
    """``N noun`` without colour — safe to nest inside an info-label chip."""
    word = noun if count == 1 else ( plural_noun or noun + "s" )
    return "{} {}".format( count, word )


def _cascade_stop_summary( option: str, summary ) -> str:
    """Info-label chip for plan/collect finish lines (through the semicolon)."""
    return as_info_label( "--{}: {}".format( option, summary ) )


def _footer_flag( option: str ) -> str:
    """Emphasised info ``--flag`` for finish-line advice (stands out in plain prose)."""
    name = option if str( option ).startswith( "--" ) else "--" + option
    return as_emphasised( as_info( name ) )


def _cascade_plan_summary( summary ) -> str:
    """Info-label chip for the plan's definitive summary (through the semicolon)."""
    return _cascade_stop_summary( CASCADE_PLAN_OPTION, summary )


def _lookup_root_for( entry ) -> str:
    root = entry.get( "_lookup_root" )
    if root:
        return storage.display_path( root )
    return storage.display_path(
            os.path.join( os.path.expanduser( storage_defaults.storage_root ), PUBLISHERS_DIRNAME )
    )


def _display_path_marking_leaf( path, leaf ) -> str:
    """``display_path`` with the trailing ``leaf`` wrapped in ``{…}`` for colouring.

    Judgement prose highlight turns ``[root/{name}]`` into a severity-coloured
    root and package name separated by a plain ``/``, so the forest and the
    package directory read as two visual units inside one bracketed path.
    """
    displayed = storage.display_path( str( path ) )
    if not leaf:
        return displayed
    leaf = str( leaf )
    if displayed == leaf:
        return "{" + leaf + "}"
    if displayed.endswith( "/" + leaf ):
        return displayed[ : -len( leaf ) ] + "{" + leaf + "}"
    return displayed


def _publisher_root_alternative_note( entry, collect=False ) -> str:
    base = (
            "alternatively, use --{} to choose a different publisher root than the "
            "default of [{}]".format( PUBLISHER_ROOT_OPTION, _lookup_root_for( entry ) )
    )
    if collect:
        return base + " and pass --{}".format( CLONE_OPTION )
    return base


def _develop_path_alternative_note( entry, collect=False ) -> str:
    flag = entry.get( "_develop_cli_flag" )
    if collect:
        if flag:
            return (
                    "alternatively, set {} to a filesystem path and pass --develop; "
                    "if that path exists, collect uses that tree instead of cloning"
                    .format( flag )
            )
        return (
                "alternatively, set a develop path for this dependency "
                "(develop= or --<name>-<manager>-develop=) and pass --develop; "
                "if that path exists, collect uses that tree instead of cloning"
        )
    if flag:
        return (
                "alternatively, set {} to a filesystem path and pass --develop; "
                "if that path exists, cascade publishes from it".format( flag )
        )
    return (
            "alternatively, set a develop path for this dependency "
            "(develop= or --<name>-<manager>-develop=) and pass --develop; "
            "if that path exists, cascade publishes from it"
    )


def _executable_noun( collect=False ) -> str:
    return "collect" if collect else "plan"


def _node_judgements( entry, collect=False ) -> list[tuple[str, str]]:
    """``(severity, prose)`` under one package node, error then warning then note.

    Warnings name the primary intent that needs a flag; notes list alternatives
    separately. Prose uses ``[brackets]`` for paths and other values
    ``highlight_values`` should colour, and bare ``--flags`` for CLI options.
    ``collect`` retargets verbs for ``--collect-cascade`` rather than a publish plan.
    """
    items: list[tuple[str, str]] = []
    if entry.get( "_resolve_error" ):
        items.append( ( "error", entry["_resolve_error"] ) )
    objections = entry.get( "_work_objections" )
    if objections:
        severity, _colour, verdict = _work_verdict( entry )
        items.append( (
                severity,
                "publishing from this tree has {} ({})".format(
                        ", ".join( objections ), verdict
                ),
        ) )

    develop_unused = entry.get( "_develop_unused" )
    forest_hit = entry.get( "_publisher_forest_hit" )
    needs_clone = entry.get( "_needs_clone_opt_in" )
    lookup = _lookup_root_for( entry )
    clone_dir = entry.get( "_clone_dir" )
    clone_url = entry.get( "_clone_url" )
    clone_pin = entry.get( "_clone_revision" )
    executable = _executable_noun( collect )

    if develop_unused:
        items.append( (
                "warning",
                "a develop tree is configured at [{}] but --develop was not passed; "
                "pass --develop to make this {} executable".format(
                        storage.display_path( entry["_develop_dir"] ),
                        executable,
                ),
        ) )
        if forest_hit:
            leaf = entry.get( "name" ) or entry.get( "package" )
            items.append( (
                    "warning",
                    "otherwise, cascade will use the existing publisher tree at [{}]; "
                    "that is probably not what you intended".format(
                            _display_path_marking_leaf( forest_hit, leaf ),
                    ),
            ) )

    if needs_clone:
        destination = storage.display_path( clone_dir ) if clone_dir else lookup
        source = entry.get( "package_source" ) or clone_url or ""
        items.append( (
                "warning",
                "package_source is a URL [{}] and no local working tree was found under [{}]; "
                "pass --{} to clone into [{}] and make this {} executable".format(
                        source,
                        lookup,
                        CLONE_OPTION,
                        destination,
                        executable,
                ),
        ) )

    # Notes: alternatives and planned-clone detail (never "rewrite package_source").
    if develop_unused and forest_hit:
        items.append( ( "note", _publisher_root_alternative_note( entry, collect ) ) )
    elif develop_unused and not entry.get( "_publisher_dir" ):
        # Soft-graded: no tree was resolved without --develop.
        if clone_dir and clone_url:
            items.append( (
                    "note",
                    "alternatively, cascade will look under [{}] for a publisher tree. "
                    "As none exists there yet, pass --{} to clone into [{}] and make "
                    "this {} executable".format(
                            lookup,
                            CLONE_OPTION,
                            storage.display_path( clone_dir ),
                            executable,
                    ),
            ) )
        else:
            items.append( (
                    "note",
                    "alternatively, cascade will look under [{}] for a publisher tree "
                    "(nothing found there yet)".format( lookup ),
            ) )
        items.append( ( "note", _publisher_root_alternative_note( entry, collect ) ) )

    if needs_clone:
        items.append( ( "note", _publisher_root_alternative_note( entry, collect ) ) )
        items.append( ( "note", _develop_path_alternative_note( entry, collect ) ) )

    if entry.get( "_clone_dir" ) and not needs_clone and not develop_unused:
        # --clone-publishers set: plan the fetch rather than performing it.
        items.append( (
                "note",
                "would clone [{}]{} into [{}]".format(
                        clone_url,
                        " at [{}]".format( clone_pin ) if clone_pin else "",
                        storage.display_path( clone_dir ),
                ),
        ) )
        items.append( (
                "note",
                "its own package dependencies are not known until that tree exists, "
                "so nothing is planned beneath it",
        ) )
    return items


# Bare setting name in judgement prose — colour at message severity, no brackets
# (unlike paths/URLs, the token is fixed).
_PACKAGE_SOURCE_TOKEN = re.compile( r'(?<![\w.-])package_source(?![\w-])' )
# ``[prefix/{leaf}]`` in judgement prose — leaf is the package directory name.
_PATH_LEAF_IN_BRACKETS = re.compile( r'\[([^\[\]]*?)\{([^{}\]]+)\}([^\[\]]*)\]' )


def _highlight_path_leaf_brackets( text, colour ):
    """Colour ``[root/{leaf}]`` as severity root, plain ``/``, severity leaf.

    Brackets stay plain. Protects the result from a second ``highlight_values``
    pass (ANSI CSI uses ``[``).
    """
    protected = []

    def protect( match ):
        prefix, leaf, suffix = match.group( 1 ), match.group( 2 ), match.group( 3 )
        if prefix.endswith( "/" ):
            root = prefix[ : -1 ]
            sep = "/"
        else:
            root = prefix
            sep = "/" if root and leaf else ""
        coloured = (
                "["
                + ( colour( root ) if root else "" )
                + sep
                + colour( leaf )
                + ( colour( suffix ) if suffix else "" )
                + "]"
        )
        protected.append( coloured )
        return "\0PL{}\0".format( len( protected ) - 1 )

    text = _PATH_LEAF_IN_BRACKETS.sub( protect, text )
    text = storage.highlight_values( text, colour )
    for index, coloured in enumerate( protected ):
        text = text.replace( "\0PL{}\0".format( index ), coloured )
    return text


def _append_highlighted_prose( lines, text, colour, first_branch, carried_branch, prose_width ):
    """Wrap prose under a tree branch; colour ``[bracketed]`` values, bare ``--flags``,
    ``[prefix/{leaf}]`` path leaves, and the fixed ``package_source`` setting name.
    """
    wrap_width = max( prose_width - len( first_branch ), storage.NARROWEST_PROSE )
    branch = first_branch
    for piece in storage.wrapped( text, wrap_width ):
        highlighted = _highlight_path_leaf_brackets( piece, colour )
        highlighted = _PACKAGE_SOURCE_TOKEN.sub(
                lambda match: colour( match.group( 0 ) ), highlighted
        )
        lines.append( as_subdued( branch ) + highlighted )
        branch = carried_branch


def _append_severity_groups( lines, judgements, under, prose_width, encoding=None ):
    """Hang error / warning / note groups under a package node (judgement-tree shape).

    Stub lines before each severity heading and before each message match
    ``_judgement_tree_lines``: they keep the hanging branches readable.
    """
    colour_for = { "error": as_error, "warning": as_warning, "note": as_info }
    heading_for = { "error": "error", "warning": "warning", "note": "note" }
    groups = []
    for severity in ( "error", "warning", "note" ):
        group = [ text for sev, text in judgements if sev == severity ]
        if group:
            groups.append( ( severity, group ) )
    tee, elbow, pipe, gap = storage.glyphs( encoding )
    nested_stub = pipe.rstrip()
    for group_index, ( severity, group ) in enumerate( groups ):
        last_group = group_index == len( groups ) - 1
        colour = colour_for[severity]
        lines.append( as_subdued( under + nested_stub ) )
        heading = "{} {}".format(
                len( group ),
                heading_for[severity] if len( group ) == 1 else heading_for[severity] + "s",
        )
        lines.append(
                as_subdued( under + ( elbow if last_group else tee ) ) + colour( heading )
        )
        under_severity = under + ( gap if last_group else pipe )
        for index, text in enumerate( group ):
            last = index == len( group ) - 1
            lines.append( as_subdued( under_severity + nested_stub ) )
            first = under_severity + ( elbow if last else tee )
            carried = under_severity + ( gap if last else pipe )
            _append_highlighted_prose( lines, text, colour, first, carried, prose_width )


def cascade_plan_lines(
        nodes, order, tip_package, tip_version, encoding=None, argv=None, mode=None,
        clean=False,
) -> list[str]:
    """Publish order, leaf-first: package nodes first, judgements nested beneath.

    Packages stay in publish order (the point of this report). Errors, warnings, and
    notes hang under each package the way a judgement tree hangs under a severity
    heading — severity coloured on the heading and on ``[bracketed]`` values only.

    The invoking command line is shown above the tree so recommended flags can be
    compared with flags already present (cascade-relevant ones are emphasised info).

    ``mode`` is ``cascade-plan`` (default), ``collect-cascade``, or
    ``update-publishers`` — collect/update retarget the header and judgement verbs.
    ``clean`` retargets the intro for ``-c`` / ``--clean`` (nested sessions remove
    targets; nothing is published).
    """
    collect = mode == COLLECT_CASCADE_OPTION
    updating = mode == UPDATE_PUBLISHERS_OPTION
    tee, elbow, pipe, gap = storage.glyphs( encoding )
    judgements_by_key = {
            key: _node_judgements( nodes[key], collect=collect ) for key in order
    }

    error_count = sum(
            1 for key in order
            for severity, _ in judgements_by_key[key] if severity == "error"
    )
    warning_count = sum(
            1 for key in order
            for severity, _ in judgements_by_key[key] if severity == "warning"
    )
    note_count = sum(
            1 for key in order
            for severity, _ in judgements_by_key[key] if severity == "note"
    )

    tip = _package_identity( tip_package, tip_version )
    if collect:
        intro = (
                "Printing Cascade plan for collecting packages for {} given the command:"
                .format( tip )
        )
    elif updating:
        intro = (
                "Printing Cascade plan for updating publisher trees for {} "
                "given the command:".format( tip )
        )
    elif clean:
        intro = (
                "Printing Cascade plan for cleaning package {} given the command:"
                .format( tip )
        )
    else:
        intro = (
                "Printing Cascade plan for building and publishing package {} "
                "given the command:".format( tip )
        )
    lines = [
            "",
            intro,
            colour_plan_command_line( argv ),
            "",
            "Cascade plan: {} (this package) with {}: {}".format(
                    tip,
                    storage.emphasised_count_phrase(
                            len( order ), "package dependency", "package dependencies"
                    ),
                    storage.format_severity_count_brackets(
                            errors=error_count,
                            warnings=warning_count,
                            notes=note_count,
                    ),
            ),
            as_subdued( pipe.rstrip() ),
    ]
    total = len( order )
    marker_width = len( "{} of {}".format( total, total ) ) if total else len( "0 of 0" )
    # Outer pipe + pad past the ordinal so nested glyphs hang under the label.
    # Packages are never the last outer sibling — the tip line is — so under stays pipe.
    under = _plan_node_under( pipe, marker_width )
    prose_width = max( storage.WIDEST_PROSE - len( under ), storage.NARROWEST_PROSE )
    stub = pipe.rstrip()

    for ordinal, key in enumerate( order, start=1 ):
        last = ordinal == total
        entry = nodes[key]
        marker = "{} of {}".format( ordinal, total ).rjust( marker_width )
        lines.append( "{}{}  {}".format(
                as_subdued( tee ), marker, _plan_dependency_label( entry )
        ) )
        judgements = judgements_by_key[key]
        has_publisher = bool( entry.get( "_publisher_dir" ) )
        if has_publisher:
            # Breathing space from the package node before nested leaves.
            lines.append( as_subdued( under + stub ) )
            publisher = entry["_publisher_dir"]
            # Nested under the package like a judgement leaf: elbow when alone,
            # tee when errors/warnings/notes follow.
            branch = elbow if not judgements else tee
            lines.append( "{}using publisher at [{}]{}".format(
                    as_subdued( under + branch ),
                    as_notice( storage.display_path( str( publisher ) ) ),
                    " (develop)" if entry.get( "_from_develop" ) else "",
            ) )
        if judgements:
            _append_severity_groups( lines, judgements, under, prose_width, encoding )
        if not last:
            lines.append( as_subdued( stub ) )

    lines.append( as_subdued( stub ) )
    if clean:
        lines.append( "{}then clean {} from this tree".format(
                as_subdued( elbow ), tip
        ) )
        lines.extend( _cascade_clean_cmake_note_lines() )
    else:
        lines.append( "{}then {} from this tree".format( as_subdued( elbow ), tip ) )
    return lines


def _cascade_clean_cmake_note_lines() -> list[str]:
    """Explain why a nested clean can look thinner than a tip CMake wipe."""
    return [
            "",
            (
                    "cascade note: -c removes publisher working/final stamps and any "
                    "paths registered with env.Clean. Out-of-tree CMake -B trees under "
                    "location downloads are removed only when the publisher uses "
                    "CMakeConfigure/CMakeBuild (or registers Clean itself). Raw Command "
                    "wrappers leave those objects in place, so the next rebuild can look "
                    "like an incremental Ninja build even though Cuppa still re-packages "
                    "and re-uploads."
            ),
    ]


def session_begin_lines(
        ordinal,
        total,
        label,
        publisher_dir,
        command,
        width=None,
        kind: str = "cascade session",
        tree_word: str = "publisher",
) -> list[str]:
    """Banner opening one nested session, so the extra ``scons`` run is visible.

    ``kind`` distinguishes cascade publishes from develop-local stages. The
    ``kind N of M`` chip is an info-label — jumping sconstruct is meant to read loud.
    ``tree_word`` is ``publisher`` for package/cascade nests and ``project`` for
    location develop stages.
    """
    head = as_info_label( "{} {} of {}".format( kind, ordinal, total ) )
    return [
            "",
            as_subdued( RULE * ( width or storage.WIDEST_PROSE ) ),
            "{}: {}".format( head, as_info( str( label ) ) ),
            "  {} [{}]".format(
                    tree_word,
                    as_notice( storage.display_path( str( publisher_dir ) ) ),
            ),
            "  command [{}]".format( as_notice( str( command ) ) ),
    ]


def session_end_lines(
        ordinal,
        total,
        label,
        elapsed_nanosecs=None,
        kind: str = "cascade session",
        width=None,
) -> list[str]:
    """Banner closing one nested session. Claims nothing about what was uploaded.

    Telling an up-to-date no-op from a real upload needs the registry query that
    Phase 2c builds; see ``design/plans/package-build-publish-deps.md``. The rule
    under the finished chip mirrors the opening banner so return to the tip session
    is as visible as the jump out.
    """
    taken = ""
    if elapsed_nanosecs is not None:
        taken = " in {}".format(
                as_notice( timer.as_duration_string( elapsed_nanosecs ) )
        )
    head = as_info_label( "{} {} of {} finished".format( kind, ordinal, total ) )
    return [
            "{}: {}{}".format( head, as_info( str( label ) ), taken ),
            as_subdued( RULE * ( width or storage.WIDEST_PROSE ) ),
            "",
    ]


def sessions_complete_lines(
        total, tip_package, tip_version, width=None, clean=False
) -> list[str]:
    """Banner handing the console back to this package's build (or clean)."""
    nested = storage.emphasised_count_phrase(
            total,
            "nested clean" if clean else "nested publish",
            "nested cleans" if clean else "nested publishes",
    )
    resume = "resuming clean of this package" if clean else "resuming this package"
    return [
            "",
            as_subdued( RULE * ( width or storage.WIDEST_PROSE ) ),
            "{}: {}; {} {}".format(
                    as_info_label( "cascade sessions complete" ),
                    nested,
                    resume,
                    _package_identity( tip_package, tip_version ),
            ),
    ]


def write_lines( lines, out=None ) -> None:
    """Emit report lines unprefixed — tree glyphs do not survive log labels."""
    stream = out if out is not None else sys.stdout
    for line in lines:
        stream.write( line + "\n" )


def _raise_options_error( headline, reasons, short_message, encoding=None, out=None ):
    """Print an Options Error tree on stdout, then raise a short ``StopError``.

    Surprising refusals (invalid flag combinations) deserve a readable report
    before the critical exception line. ``headline`` is the title after the
    chip. ``reasons`` is a list of ``(prose, colour)`` branches — typically a
    why branch coloured with ``as_error`` and a remedy branch coloured with
    emphasised info so the positive next flags stand out. Bare ``--flags`` and
    ``[bracketed]`` values take that branch's colour.
    """
    tee, elbow, pipe, gap = storage.glyphs( encoding )
    stub = pipe.rstrip()
    lines = [
            "",
            "{}: {}".format(
                    as_error_label( as_emphasised( "Options Error" ) ),
                    storage.highlight_values( headline, as_error ),
            ),
    ]
    total = len( reasons )
    for index, ( reason, colour ) in enumerate( reasons ):
        last = index == total - 1
        lines.append( as_subdued( stub ) )
        first = elbow if last else tee
        carried = gap if last else pipe
        wrap_width = max( storage.WIDEST_PROSE - len( first ), storage.NARROWEST_PROSE )
        branch = first
        for piece in storage.wrapped( reason, wrap_width ):
            lines.append(
                    as_subdued( branch ) + storage.highlight_values( piece, colour )
            )
            branch = carried
    lines.append( "" )
    write_lines( lines, out=out )
    raise SCons.Errors.StopError( short_message )


# Plan reports recorded during the sconscript read; see finish_plan_only().
_plan_reports: list[dict] = []


def reset_plan_reports() -> None:
    del _plan_reports[:]


def plan_reports() -> list[dict]:
    return list( _plan_reports )


def record_plan_report(
        tip_package,
        tip_version,
        error_count,
        clone_count=0,
        needs_clone_opt_in=0,
        unused_develop=0,
        mode=None,
        trees_collected=0,
        trees_updated=0,
) -> None:
    _plan_reports.append( {
            "package": str( tip_package ),
            "version": str( tip_version ),
            "errors": int( error_count ),
            "clones": int( clone_count ),
            "needs_clone_opt_in": int( needs_clone_opt_in ),
            "unused_develop": int( unused_develop ),
            "mode": mode or CASCADE_PLAN_OPTION,
            "trees_collected": int( trees_collected ),
            "trees_updated": int( trees_updated ),
    } )


def finish_plan_only( env=None, out=None ) -> int:
    """Closing line and exit status for ``--cascade-plan`` (and collect via env)."""
    return finish_cascade_stop( env=env, out=out )


def finish_cascade_stop( env=None, out=None ) -> int:
    """Closing line and exit status for plan / collect / update-without-publish.

    Called once the sconscript read is done (the ``--dump`` pattern in
    ``construct.py``) rather than from the publisher, so a run with several tips,
    toolchains, or sconscripts reports all of them instead of only the first.

    ``env`` lets the missing-cascade-flag refusal be reported here too: a project
    that constructs no publisher never reaches the refusal in
    :func:`maybe_run_cascade`.

    Exit status follows hard resolve errors only. Opt-in warnings (``--clone-publishers``
    needed, unused develop) leave the run reviewable with exit 0.
    """
    stream = out if out is not None else sys.stdout
    collect = False
    update = False
    if env is not None:
        if cascade_collect_enabled( env ):
            collect = True
        elif cascade_update_enabled( env ) and cascade_stop_before_build( env ):
            update = True
    elif _plan_reports:
        mode = _plan_reports[0].get( "mode" )
        if mode == COLLECT_CASCADE_OPTION:
            collect = True
        elif mode == UPDATE_PUBLISHERS_OPTION:
            update = True
    if collect:
        option = COLLECT_CASCADE_OPTION
        no_side_effects = "nothing was collected, built, published, or uploaded."
        verb = "collect"
    elif update:
        option = UPDATE_PUBLISHERS_OPTION
        no_side_effects = "nothing was built, published, or uploaded."
        verb = "update"
    else:
        option = CASCADE_PLAN_OPTION
        no_side_effects = "nothing was built, published, uploaded, or cloned."
        verb = "plan"

    if not _plan_reports:
        if env is not None and not cascade_enabled( env ):
            write_lines( [
                    "",
                    "{}: requires --{}, which is the flag it {}."
                    .format(
                            as_info_label( "--" + option ),
                            CASCADE_OPTION,
                            (
                                    "collects for" if collect else
                                    "updates for" if update else
                                    "plans"
                            ),
                    ),
            ], out=stream )
            return 1
        write_lines( [
                "",
                "{}; Run from a project that publishes a GitLab package with "
                "env.PublishPackage.".format(
                        _cascade_stop_summary(
                                option,
                                "no GitLab package publisher was constructed, so "
                                "there is no cascade to {}".format( verb ),
                        )
                ),
        ], out=stream )
        return 1

    errors = sum( report["errors"] for report in _plan_reports )
    clones = sum( report.get( "clones", 0 ) for report in _plan_reports )
    needs_clone = sum(
            report.get( "needs_clone_opt_in", 0 ) for report in _plan_reports
    )
    unused_develop = sum(
            report.get( "unused_develop", 0 ) for report in _plan_reports
    )
    trees_collected = sum(
            report.get( "trees_collected", 0 ) for report in _plan_reports
    )
    trees_updated = sum(
            report.get( "trees_updated", 0 ) for report in _plan_reports
    )
    packages = _plain_count_phrase( len( _plan_reports ), "package" )
    if errors:
        if collect:
            summary = "{}, {} without a publisher tree".format(
                    _plain_count_phrase(
                            trees_collected, "publisher tree", "publisher trees"
                    ) + " collected",
                    _plain_count_phrase( errors, "dependency", "dependencies" ),
            )
            remediation = (
                    "Plant the missing trees, pass {} to fetch the ones with "
                    "a URL package_source, or set {}.".format(
                            _footer_flag( CLONE_OPTION ),
                            _footer_flag( PUBLISHER_ROOT_OPTION ),
                    )
            )
        elif update:
            summary = "{}, {} without a publisher tree".format(
                    _plain_count_phrase(
                            trees_updated, "publisher tree", "publisher trees"
                    ) + " updated",
                    _plain_count_phrase( errors, "dependency", "dependencies" ),
            )
            remediation = (
                    "Plant the missing trees, pass {} with {} to clone them, "
                    "or set {}.".format(
                            _footer_flag( COLLECT_CASCADE_OPTION ),
                            _footer_flag( CLONE_OPTION ),
                            _footer_flag( PUBLISHER_ROOT_OPTION ),
                    )
            )
        else:
            summary = "{} planned, {} without a publisher tree".format(
                    packages,
                    _plain_count_phrase( errors, "dependency", "dependencies" ),
            )
            remediation = (
                    "Plant the missing trees, pass {} to fetch the ones with "
                    "a URL package_source, or set {}. Then re-run with {} to "
                    "execute.".format(
                            _footer_flag( CLONE_OPTION ),
                            _footer_flag( PUBLISHER_ROOT_OPTION ),
                            _footer_flag( "publish-package" ),
                    )
            )
        write_lines( [
                "",
                "{}. {}".format( _cascade_stop_summary( option, summary ), remediation ),
        ], out=stream )
        return 1

    if collect:
        summary = "{} collected".format(
                _plain_count_phrase(
                        trees_collected, "publisher tree", "publisher trees"
                )
        )
        if clones:
            summary = "{}, {} newly cloned".format(
                    summary,
                    _plain_count_phrase( clones, "publisher tree", "publisher trees" ),
            )
        if trees_updated:
            summary = "{}, {} updated".format(
                    summary,
                    _plain_count_phrase(
                            trees_updated, "publisher tree", "publisher trees"
                    ),
            )
        if trees_collected == 0 and trees_updated == 0:
            detail = "nothing was collected, built, published, or uploaded."
        else:
            detail = "nothing was built, published, or uploaded."
    elif update:
        summary = "{} updated".format(
                _plain_count_phrase(
                        trees_updated, "publisher tree", "publisher trees"
                )
        )
        detail = no_side_effects
    else:
        summary = "{} planned".format( packages )
        if clones:
            summary = "{}, {} to clone first".format(
                    summary,
                    _plain_count_phrase( clones, "publisher tree", "publisher trees" ),
            )
        detail = no_side_effects

    if needs_clone or unused_develop:
        actions = []
        if collect or update:
            if needs_clone:
                actions.append(
                        "pass {} to clone missing publisher trees".format(
                                _footer_flag( CLONE_OPTION )
                        )
                )
            if unused_develop:
                actions.append(
                        "pass {} to use a configured develop tree".format(
                                _footer_flag( "develop" )
                        )
                )
        else:
            # Plan reviews a publish run: opt-ins are useless without --publish-package.
            publish = _footer_flag( "publish-package" )
            if needs_clone:
                actions.append(
                        "pass {} along with {} to clone missing publisher trees"
                        .format( _footer_flag( CLONE_OPTION ), publish )
                )
            if unused_develop:
                actions.append(
                        "pass {} along with {} to publish from a configured develop tree"
                        .format( _footer_flag( "develop" ), publish )
                )
        detail = "{}; {}".format( ", or ".join( actions ), detail )
    elif not collect and not update and clones:
        detail = "pass {} along with {} to execute; {}".format(
                _footer_flag( CLONE_OPTION ),
                _footer_flag( "publish-package" ),
                detail,
        )
    write_lines( [
            "",
            "{}; {}".format( _cascade_stop_summary( option, summary ), detail ),
    ], out=stream )
    return 0


# Flags that must not re-enter on nested publishes (exact match).
_NESTED_DROP_EXACT = frozenset( {
        "--" + CASCADE_OPTION,
        "--" + CASCADE_PLAN_OPTION,
        "--" + COLLECT_CASCADE_OPTION,
        "--" + UPDATE_PUBLISHERS_OPTION,
        "--" + PUBLISHER_ROOT_OPTION,
        "--" + CLONE_OPTION,
        "--" + MODIFIED_DEVELOP_OPTION,
        "--" + STAGE_DEVELOP_OPTION,
        "--" + STAGE_DEVELOP_PLAN_OPTION,
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


def tip_forward_args(
        argv=None,
        env=None,
        stage_only: bool = False,
        project_only: bool = False,
) -> list[str]:
    """Tip SCons/cuppa option args suitable for a nested publish, stage, or project session.

    Uses the live tip ``sys.argv`` (variant, toolchains, offline, …), not
    ``configured_options`` from ``~/.cuppaconfig`` — those conf keys are not
    all valid CLI flags and omit the tip's explicit ``--rel`` / ``--toolchains``.

    Tip dependency-scoped options are dropped when ``env`` is supplied: the child
    has never registered them.

    With ``stage_only=True``, the child builds and stages the package but does not
    upload (``--stage-package`` instead of ``--publish-package``).

    With ``project_only=True``, the child runs a normal project build/clean (no
    ``--publish-package`` / ``--stage-package``). Used for location develop trees
    under ``--stage-develop``. ``--stage-develop`` itself is always dropped so
    nesting stays single-level.
    """
    if stage_only and project_only:
        raise ValueError( "stage_only and project_only cannot both be True" )
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

    def _without( flags: list[str], *names: str ) -> list[str]:
        drop = set( names )
        prefixes = tuple( name + "=" for name in names )
        return [
                arg for arg in flags
                if arg not in drop and not any( arg.startswith( p ) for p in prefixes )
        ]

    if project_only:
        forwarded = _without( forwarded, "--publish-package", "--stage-package" )
    elif stage_only:
        forwarded = _without( forwarded, "--publish-package", "--stage-package" )
        forwarded.append( "--" + STAGE_PACKAGE_OPTION )
    else:
        forwarded = _without( forwarded, "--stage-package" )
        if "--publish-package" not in forwarded:
            forwarded.append( "--publish-package" )
    return forwarded


def argv_for_nested_publish( argv=None, env=None ) -> list[str]:
    """Full subprocess argv: ``python -m cuppa`` + :func:`tip_forward_args`."""
    return [ sys.executable, "-m", "cuppa" ] + tip_forward_args( argv, env=env )


def argv_for_nested_stage( argv=None, env=None ) -> list[str]:
    """Full subprocess argv for a nested stage-only (no upload) session."""
    return [
            sys.executable, "-m", "cuppa"
    ] + tip_forward_args( argv, env=env, stage_only=True )


def argv_for_nested_project( argv=None, env=None ) -> list[str]:
    """Full subprocess argv for a nested project build/clean (location develop)."""
    return [
            sys.executable, "-m", "cuppa"
    ] + tip_forward_args( argv, env=env, project_only=True )


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


def update_publisher_trees( env, nodes: dict, order, out=None ) -> int:
    """Fetch and fast-forward resolved publisher trees (``--update-publishers``).

    Same gates as ``--update-develop``: clean, tracking upstream, strictly behind.
    Develop-ranked trees are skipped (use ``--update-develop``). Returns how many
    trees were fast-forwarded (0 under dry-run).

    Reporting is an ACTION table shared with ``--update-develop`` (would update /
    updated / no change / leave alone / left alone). Online dry-run still fetches
    so the table is honest; only the fast-forward is skipped. On a tty the fetch
    rewrites one subdued status line, cleared before the table. Offline dry-run
    falls back to the last observation.
    """
    from cuppa.develop import (
            fetch_for_update,
            inspect,
            leave_alone_state,
            remote_check_progress,
            render_update_action_table,
            state_summary,
            update_action,
            update_action_row,
            write as develop_write,
    )
    from cuppa.scms.git import Git

    emit = out if out is not None else develop_write
    dry_run = _no_exec_enabled( env )
    offline = bool( env.get( "offline" ) )
    updated = 0
    rows = []

    emit( "" )
    if dry_run:
        if offline:
            emit( "{} {}".format(
                    as_info_label( "Dry run" ),
                    "showing what --{} would do, judged from your last update"
                    .format( UPDATE_PUBLISHERS_OPTION ),
            ) )
        else:
            emit( "{} {}".format(
                    as_info_label( "Dry run" ),
                    "checking remotes for --{}".format( UPDATE_PUBLISHERS_OPTION ),
            ) )

    leave = "leave alone" if dry_run else "left alone"

    will_fetch = not ( dry_run and offline )
    fetch_keys = []
    if will_fetch:
        for key in order:
            entry = nodes[key]
            path = entry.get( "_publisher_dir" )
            if not path or entry.get( "_from_develop" ):
                continue
            observed = inspect( entry["name"], path )
            if observed.exists and observed.scm == "git":
                fetch_keys.append( key )
    fetch_total = len( fetch_keys )
    fetch_index = { key: i for i, key in enumerate( fetch_keys, 1 ) }

    with remote_check_progress() as status:
        for key in order:
            entry = nodes[key]
            path = entry.get( "_publisher_dir" )
            if not path:
                continue
            name = entry["name"]

            if entry.get( "_from_develop" ):
                observed = inspect( name, path )
                rows.append( update_action_row(
                        leave, name, observed,
                        "develop tree (use --update-develop)", path, "ok",
                ) )
                continue

            observed = inspect( name, path )
            if not observed.exists or observed.scm != "git":
                reason = (
                        "path does not exist" if not observed.exists
                        else "not a git working copy"
                )
                rows.append( update_action_row(
                        leave, name, observed, reason, path, "warn",
                ) )
                continue

            if key in fetch_index:
                try:
                    fetch_for_update(
                            observed.path, name,
                            fetch_index[key], fetch_total, status,
                    )
                except Git.Error as error:
                    rows.append( update_action_row(
                            "failed", name, observed, str( error ), path, "error",
                    ) )
                    continue
                observed = inspect( name, path )

            action = update_action( observed )
            if not action.act:
                if action.reason == "already up to date":
                    rows.append( update_action_row(
                            "no change", name, observed, "current", path, "ok",
                    ) )
                else:
                    rows.append( update_action_row(
                            leave, name, observed,
                            leave_alone_state( observed, action ), path, "warn",
                    ) )
                continue

            if dry_run:
                rows.append( update_action_row(
                        "would update", name, observed, state_summary( observed ),
                        path, "act",
                ) )
                continue

            try:
                Git.fast_forward( observed.path )
                updated += 1
                after = inspect( name, path )
                rows.append( update_action_row(
                        "updated", name, after, "current", path, "act",
                ) )
            except Git.Error as error:
                rows.append( update_action_row(
                        "failed", name, observed, str( error ), path, "error",
                ) )

    if rows:
        for line in render_update_action_table( rows, subject_column="PACKAGE" ):
            emit( line )
    return updated



def _nested_session_env( env ) -> dict:
    """Environment for a nested cuppa subprocess (cascade publish or develop stage)."""
    nested_env = os.environ.copy()
    nested_env[NESTED_ENV] = "1"
    # Nested cuppa's stdout is a pipe (tip cuppa masks secrets), so CPython
    # block-buffers without this — the tip looks hung until the child exits.
    nested_env["PYTHONUNBUFFERED"] = "1"
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
    return nested_env


def run_nested_publish( env, publisher_dir: str, label: str, ordinal=1, total=1 ) -> None:
    argv = argv_for_nested_publish( env=env )
    nested_env = _nested_session_env( env )

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
        verb = "clean" if _clean_enabled( env ) else "publish"
        raise SCons.Errors.StopError(
                "cascade session {} of {} — {} of [{}] failed with return "
                "code [{}] (cwd={})"
                .format( ordinal, total, verb, label, completion.returncode, publisher_dir )
        )
    write_lines( session_end_lines(
            ordinal, total, label, session_timer.elapsed().wall
    ) )


def run_nested_stage( env, publisher_dir: str, label: str ) -> None:
    """Nested cuppa session that builds and stages a package without uploading."""
    argv = argv_for_nested_stage( env=env )
    nested_env = _nested_session_env( env )
    kind = "develop stage"

    write_lines( session_begin_lines(
            1, 1, label, publisher_dir, " ".join( argv ), kind=kind
    ) )
    sys.stdout.flush()
    session_timer = timer.Timer()
    completion = subprocess.run(
            argv,
            cwd=publisher_dir,
            env=nested_env,
    )
    session_timer.stop()
    if completion.returncode != 0:
        verb = "clean" if _clean_enabled( env ) else "stage"
        raise SCons.Errors.StopError(
                "develop {} of [{}] failed with return code [{}] (cwd={})"
                .format( verb, label, completion.returncode, publisher_dir )
        )
    write_lines( session_end_lines(
            1, 1, label, session_timer.elapsed().wall, kind=kind
    ) )
    sys.stdout.flush()


def run_nested_location_project(
        env,
        project_dir: str,
        label: str,
        ordinal: int = 1,
        total: int = 1,
) -> None:
    """Nested cuppa session that builds or cleans a location develop project."""
    argv = argv_for_nested_project( env=env )
    nested_env = _nested_session_env( env )
    kind = "develop stage"

    write_lines( session_begin_lines(
            ordinal, total, label, project_dir, " ".join( argv ),
            kind=kind, tree_word="project",
    ) )
    sys.stdout.flush()
    session_timer = timer.Timer()
    completion = subprocess.run(
            argv,
            cwd=project_dir,
            env=nested_env,
    )
    session_timer.stop()
    if completion.returncode != 0:
        verb = "clean" if _clean_enabled( env ) else "build"
        raise SCons.Errors.StopError(
                "develop {} of location [{}] failed with return code [{}] (cwd={})"
                .format( verb, label, completion.returncode, project_dir )
        )
    write_lines( session_end_lines(
            ordinal, total, label, session_timer.elapsed().wall, kind=kind
    ) )
    sys.stdout.flush()


_DEVELOP_KWARG_RE = re.compile(
        r"""(?<![\w.])develop\s*=\s*(?:r|u|f|rf|fr|ur|ru)?(?P<q>['"])(?P<path>(?:(?!(?P=q)).)+)(?P=q)"""
)


def _iter_sconstruct_texts( project_root: str ):
    """Yield text of the project's sconstruct / top-level sconscript files."""
    names = (
            "sconstruct", "SConstruct", "sconscript", "SConscript",
    )
    for name in names:
        path = os.path.join( project_root, name )
        if os.path.isfile( path ):
            try:
                with open( path, encoding="utf-8", errors="replace" ) as handle:
                    yield path, handle.read()
            except OSError:
                continue


def develop_paths_declared_in_tree( project_root: str ) -> list[str]:
    """``develop=`` path strings declared in a project's top-level sconstruct files."""
    found: list[str] = []
    seen: set[str] = set()
    for _path, text in _iter_sconstruct_texts( project_root ):
        for match in _DEVELOP_KWARG_RE.finditer( text ):
            value = match.group( "path" )
            if value not in seen:
                seen.add( value )
                found.append( value )
    return found


def publish_manifest_dependency_names( project_root: str ) -> list[str]:
    """Dependency names from a staged ``cuppa-publish.json``, if present."""
    try:
        manifest = read_publish_manifest( project_root )
    except Exception:
        return []
    if not manifest:
        return []
    names: list[str] = []
    for entry in manifest.get( "dependencies" ) or []:
        if isinstance( entry, dict ):
            name = entry.get( "name" ) or entry.get( "package" )
        else:
            name = str( entry )
        if name:
            names.append( str( name ) )
    return names


def location_stage_edges(
        candidates: list[tuple[str, str]],
) -> dict[str, set[str]]:
    """``name -> set of candidate names it depends on`` among the stage set.

    Edges come from ``develop=`` paths in each project's sconstruct that resolve
    to another candidate root, plus ``cuppa-publish.json`` dependency names that
    match a candidate.
    """
    from cuppa.location import develop_location

    by_root = { root: name for name, root in candidates }
    by_name = { name: root for name, root in candidates }
    edges: dict[str, set[str]] = { name: set() for name, _root in candidates }

    for name, root in candidates:
        for raw in develop_paths_declared_in_tree( root ):
            try:
                resolved = develop_location( root, raw )
            except Exception:
                continue
            if not resolved:
                continue
            abs_resolved = os.path.abspath( resolved )
            other = by_root.get( abs_resolved )
            if other and other != name:
                edges[name].add( other )
        for dep_name in publish_manifest_dependency_names( root ):
            if dep_name in by_name and dep_name != name:
                edges[name].add( dep_name )
    return edges


def order_location_stage_candidates(
        candidates: list[tuple[str, str]],
        edges: dict[str, set[str]] | None = None,
) -> list[tuple[str, str]]:
    """Leaf-first order over location stage candidates; cycles raise ``StopError``.

    When several candidates are ready (no remaining edges), preserve the input
    declaration order rather than sorting names alphabetically.
    """
    if not candidates:
        return []
    if edges is None:
        edges = location_stage_edges( candidates )
    nodes = { name: { "name": name, "root": root } for name, root in candidates }
    edge_keys = {
            name: { dep for dep in deps if dep in nodes }
            for name, deps in edges.items()
    }
    rank = { name: index for index, ( name, _root ) in enumerate( candidates ) }

    node_keys = list( nodes.keys() )
    waiting = { key: len( edge_keys.get( key, () ) ) for key in node_keys }
    dependents: dict[str, set[str]] = defaultdict( set )
    for parent, children in edge_keys.items():
        for child in children:
            dependents[child].add( parent )

    def _ready_key( key: str ):
        return ( rank.get( key, 10 ** 9 ), str( key ) )

    ready = deque(
            sorted(
                    [ key for key, count in waiting.items() if count == 0 ],
                    key=_ready_key,
            )
    )
    ordered: list[str] = []
    while ready:
        node = ready.popleft()
        ordered.append( node )
        for parent in sorted( dependents.get( node, () ), key=_ready_key ):
            waiting[parent] -= 1
            if waiting[parent] == 0:
                ready.append( parent )

    if len( ordered ) != len( node_keys ):
        raise SCons.Errors.StopError(
                "location stage-develop dependency cycle detected among {}".format(
                        [ key for key in node_keys if key not in ordered ]
                )
        )
    by_name = { name: root for name, root in candidates }
    return [ ( name, by_name[name] ) for name in ordered ]


def location_stage_candidates( env ) -> list[tuple[str, str]]:
    """Location develop trees with an sconstruct, ready for ``--stage-develop``.

    Package dependencies are skipped — they nest via ``consume_develop_package_stage``.
    Order is leaf-first across the candidate set when edges are known; otherwise tip
    ``default_dependencies`` declaration order, then remaining names sorted.
    """
    return order_location_stage_candidates( location_stage_candidate_rows( env ) )


def location_stage_candidate_rows( env ) -> list[tuple[str, str]]:
    """Unordered (declaration-preferring) stageable location develop rows."""
    from cuppa.develop import configured_develop

    dependencies = env.get( "dependencies" ) or {}
    preferred = []
    for name in list( env.get( "default_dependencies" ) or [] ) + list(
            env.get( "BUILD_WITH" ) or []
    ):
        if name not in preferred:
            preferred.append( name )

    seen_roots: set[str] = set()
    candidates: list[tuple[str, str]] = []

    def _consider( name: str ) -> None:
        if name not in dependencies:
            return
        factory = dependencies[name]
        dependency = getattr( factory, "__self__", factory )
        if getattr( dependency, "_package_manager", None ):
            return
        path = configured_develop( dependency, env )
        if not path or not develop_names_a_publisher_tree( path ):
            return
        root = os.path.abspath( path )
        if root in seen_roots:
            return
        seen_roots.add( root )
        candidates.append( ( name, root ) )

    for name in preferred:
        _consider( name )
    for name in sorted( dependencies ):
        if name not in preferred:
            _consider( name )
    return candidates


def location_stage_plan_rows( env ) -> list[dict]:
    """Rows for ``--stage-develop-plan``: stageable location develops plus skips."""
    from cuppa.develop import configured_develop

    dependencies = env.get( "dependencies" ) or {}
    preferred = []
    for name in list( env.get( "default_dependencies" ) or [] ) + list(
            env.get( "BUILD_WITH" ) or []
    ):
        if name not in preferred:
            preferred.append( name )

    names = list( preferred )
    for name in sorted( dependencies ):
        if name not in names:
            names.append( name )

    rows: list[dict] = []
    seen_roots: set[str] = set()
    for name in names:
        if name not in dependencies:
            continue
        factory = dependencies[name]
        dependency = getattr( factory, "__self__", factory )
        if getattr( dependency, "_package_manager", None ):
            continue
        path = configured_develop( dependency, env )
        if not path:
            continue
        abs_path = os.path.abspath( path )
        if abs_path in seen_roots:
            continue
        seen_roots.add( abs_path )
        if not os.path.isdir( abs_path ):
            rows.append( {
                    "name": name,
                    "path": abs_path,
                    "status": "missing",
                    "severity": "error",
                    "note": "develop path does not exist",
            } )
        elif develop_names_a_publisher_tree( abs_path ):
            rows.append( {
                    "name": name,
                    "path": abs_path,
                    "status": "stage",
                    "severity": "ok",
                    "note": "has sconstruct; will nest under --stage-develop",
            } )
        else:
            rows.append( {
                    "name": name,
                    "path": abs_path,
                    "status": "skip",
                    "severity": "warning",
                    "note": "no sconstruct; will not nest under --stage-develop",
            } )
    return rows


def location_stage_plan_edges( rows: list[dict] ) -> dict[str, set[str]]:
    """Edges among all considered location develops (including unstaged names).

    Missing paths contribute no outbound edges; inbound edges still appear when
    another tree declares them by ``develop=`` path or publish-manifest name.
    """
    from cuppa.location import develop_location

    by_root = { row["path"]: row["name"] for row in rows }
    by_name = { row["name"]: row["path"] for row in rows }
    edges: dict[str, set[str]] = { row["name"]: set() for row in rows }

    for row in rows:
        if row["status"] == "missing" or not os.path.isdir( row["path"] ):
            continue
        root = row["path"]
        name = row["name"]
        for raw in develop_paths_declared_in_tree( root ):
            try:
                resolved = develop_location( root, raw )
            except Exception:
                continue
            if not resolved:
                continue
            other = by_root.get( os.path.abspath( resolved ) )
            if other and other != name:
                edges[name].add( other )
        for dep_name in publish_manifest_dependency_names( root ):
            if dep_name in by_name and dep_name != name:
                edges[name].add( dep_name )
    return edges


def _stage_row_judgements( row, env, tip_branch=None ) -> list[tuple[str, str]]:
    """``(severity, prose)`` nested under one develop-stage plan node."""
    path = storage.display_path( row["path"] )
    if row["status"] == "missing":
        return [ (
                "error",
                "project [{}] is missing.".format( path ),
        ) ]
    if row["status"] == "skip":
        return [ (
                "warning",
                "This project is not an SCons project (no SConstruct found)",
        ) ]

    from cuppa.develop import inspect

    judgements: list[tuple[str, str]] = []
    copy = inspect( row["name"], row["path"] )
    if copy.exists and not copy.is_working_copy:
        judgements.append( (
                "note",
                "Not a working copy: expected a repository but can proceed "
                "with path only",
        ) )
    ref = _checkout_ref( copy, row["path"] )
    if _stage_branch_unexpected( ref, tip_branch, env ):
        expected = []
        if tip_branch:
            expected.append( tip_branch )
        for name in sorted( _STAGE_DEFAULT_BRANCHES ):
            if name not in expected:
                expected.append( name )
        judgements.append( (
                "warning",
                "{} branch is [{}] which deviates from the expected branches "
                "({})".format(
                        row["name"],
                        ref,
                        " or ".join( expected ),
                ),
        ) )
    return judgements


def _stage_depends_lines( deps, width, colour_for_name=None ) -> list[str]:
    """``depends on [a, b]`` with each name coloured, wrapping between names.

    Brackets, commas, and the words stay plain. ``colour_for_name(name)`` defaults
    to ``as_info``. An empty list is the no-edges sentence.
    """
    if not deps:
        return [ "no edges to other stage candidates" ]
    colour = colour_for_name or ( lambda _name: as_info( _name ) )
    prefix = "depends on ["
    lines = []
    plain = prefix
    coloured = prefix
    last = len( deps ) - 1
    for index, name in enumerate( deps ):
        extra_plain = name if index == 0 else ", " + name
        painted = colour( name )
        extra_coloured = painted if index == 0 else ", " + painted
        closing = 1 if index == last else 0
        if (
                plain != prefix
                and len( plain ) + len( extra_plain ) + closing > width
        ):
            lines.append( coloured )
            plain = name
            coloured = painted
        else:
            plain += extra_plain
            coloured += extra_coloured
    lines.append( coloured + "]" )
    return lines


def _append_stage_edge(
        lines, deps, first_branch, carried_branch, prose_width, colour_for_name=None
):
    """Hang a depends-on / no-edges line under a stage node."""
    wrap_width = max( prose_width - len( first_branch ), storage.NARROWEST_PROSE )
    branch = first_branch
    for piece in _stage_depends_lines( deps, wrap_width, colour_for_name ):
        lines.append( as_subdued( branch ) + piece )
        branch = carried_branch


def _stage_dep_colour( name, severity_by_name ):
    """Info for nestable names; error/warning for unstaged deps by their severity."""
    severity = severity_by_name.get( name )
    if severity == "error":
        return as_error( name )
    if severity == "warning":
        return as_warning( name )
    return as_info( name )


def _tip_stage_label( env ) -> str:
    root = env.get( "sconstruct_dir" )
    if root:
        return os.path.basename( os.path.abspath( root ) )
    return "this project"


def stage_develop_plan_lines( env, argv=None, encoding=None ) -> list[str]:
    """Dry-run report for location ``--stage-develop`` (cascade-plan-shaped)."""
    require_stage_develop_plan_with_develop( env )
    rows = location_stage_plan_rows( env )
    nestable = [
            ( row["name"], row["path"] )
            for row in rows if row["status"] == "stage"
    ]
    nest_edges = location_stage_edges( nestable )
    try:
        ordered_nest = order_location_stage_candidates( nestable, nest_edges )
    except SCons.Errors.StopError as error:
        raise SCons.Errors.StopError(
                "--{}: {}".format( STAGE_DEVELOP_PLAN_OPTION, error )
        ) from error

    plan_edges = location_stage_plan_edges( rows )
    tip_branch = _tip_stage_branch( env )
    judgements_by_name = {
            row["name"]: _stage_row_judgements( row, env, tip_branch )
            for row in rows
    }
    severity_by_name = {}
    for row in rows:
        judgements = judgements_by_name[row["name"]]
        if any( sev == "error" for sev, _ in judgements ):
            severity_by_name[row["name"]] = "error"
        elif any( sev == "warning" for sev, _ in judgements ):
            severity_by_name[row["name"]] = "warning"
        elif any( sev == "note" for sev, _ in judgements ):
            severity_by_name[row["name"]] = "note"
        else:
            severity_by_name[row["name"]] = "ok"

    error_count = sum(
            1 for judgements in judgements_by_name.values()
            for severity, _ in judgements if severity == "error"
    )
    warning_count = sum(
            1 for judgements in judgements_by_name.values()
            for severity, _ in judgements if severity == "warning"
    )
    note_count = sum(
            1 for judgements in judgements_by_name.values()
            for severity, _ in judgements if severity == "note"
    )

    tee, elbow, pipe, gap = storage.glyphs( encoding )
    stub = pipe.rstrip()
    nest_total = len( ordered_nest )
    ordinal_of = {
            name: index for index, ( name, _path ) in enumerate( ordered_nest, 1 )
    }
    unstaged = [ row for row in rows if row["status"] != "stage" ]
    marker_width = max(
            len( "unstaged" ),
            len( "{} of {}".format( nest_total, nest_total ) ) if nest_total else len( "0 of 0" ),
    )
    under_active = _plan_node_under( pipe, marker_width )
    prose_width = max( storage.WIDEST_PROSE - len( under_active ), storage.NARROWEST_PROSE )

    tip_name = _tip_stage_label( env )
    tip_root = env.get( "sconstruct_dir" )
    tip_hint = (
            _stage_repo_state_hint( env, tip_name, tip_root, tip_branch=tip_branch )
            if tip_root else ""
    )

    lines = [
            "",
            "Printing develop stage plan given the command:",
            colour_plan_command_line( argv ),
            "",
            "Develop stage plan: {}: {}".format(
                    storage.emphasised_count_phrase(
                            len( rows ),
                            "location project",
                            "location projects",
                    ),
                    storage.format_severity_count_brackets(
                            errors=error_count,
                            warnings=warning_count,
                            notes=note_count,
                    ),
            ),
            as_subdued( stub ),
            "{}this node {}{}".format(
                    as_subdued( tee ),
                    as_emphasised( as_info( tip_name ) ),
                    tip_hint,
            ),
            "{}{} location develop{}; {} nestable, {} unstaged".format(
                    as_subdued( tee ),
                    len( rows ),
                    "" if len( rows ) == 1 else "s",
                    nest_total,
                    len( unstaged ),
            ),
            as_subdued( stub ),
    ]

    for index, row in enumerate( rows ):
        last = index == len( rows ) - 1
        name = row["name"]
        root = row["path"]
        judgements = judgements_by_name[name]
        under = _plan_node_under( gap if last else pipe, marker_width )
        outer = elbow if last else tee
        if row["status"] == "stage":
            marker = "{} of {}".format(
                    ordinal_of[name], nest_total
            ).rjust( marker_width )
        else:
            marker = "unstaged".rjust( marker_width )

        lines.append( "{}{}  {}{}".format(
                as_subdued( outer ),
                marker,
                as_emphasised( as_info( name ) ),
                _stage_repo_state_hint(
                        env, name, root, tip_branch=tip_branch,
                        wants_only=( row["status"] == "missing" ),
                ),
        ) )

        has_project = row["status"] != "missing"
        deps = sorted( plan_edges.get( name, () ) ) if has_project else []
        show_deps = has_project and row["status"] == "stage"
        has_children = has_project or bool( judgements )

        if has_children:
            lines.append( as_subdued( under + stub ) )

        if has_project:
            more_after_project = show_deps or bool( judgements )
            project_branch = tee if more_after_project else elbow
            lines.append( "{}project [{}]".format(
                    as_subdued( under + project_branch ),
                    as_info( storage.display_path( root ) ),
            ) )

        if show_deps:
            if judgements:
                lines.append( as_subdued( under + stub ) )
            _append_stage_edge(
                    lines,
                    deps,
                    under + ( tee if judgements else elbow ),
                    under + ( pipe if judgements else gap ),
                    prose_width,
                    colour_for_name=lambda dep: _stage_dep_colour(
                            dep, severity_by_name
                    ),
            )

        if judgements:
            if has_project:
                lines.append( as_subdued( under + stub ) )
            _append_severity_groups(
                    lines, judgements, under, prose_width, encoding
            )

        if not last:
            lines.append( as_subdued( stub ) )

    lines.append( as_subdued( stub ) )
    lines.append( "{}{}".format(
            as_subdued( elbow ),
            as_info( "Stage plan summary:" ),
    ) )
    summary_under = gap
    lines.append( as_subdued( summary_under + stub ) )
    lines.append( "{}{}".format(
            as_subdued( summary_under + ( tee if unstaged else elbow ) ),
            "{} nestable".format(
                    _plain_count_phrase( nest_total, "project", "projects" )
            ),
    ) )
    if unstaged:
        missing = [ row for row in unstaged if row["status"] == "missing" ]
        lines.append( as_subdued( summary_under + stub ) )
        lines.append( "{}{}".format(
                as_subdued( summary_under + elbow ),
                "{} unstaged:".format(
                        _plain_count_phrase(
                                len( unstaged ), "project", "projects"
                        )
                ),
        ) )
        detail_under = summary_under + gap
        for detail_index, row in enumerate( unstaged ):
            last_among = detail_index == len( unstaged ) - 1
            if missing:
                branch = tee
            else:
                branch = elbow if last_among else tee
            if row["status"] == "missing":
                name_colour = as_error
            elif row["status"] == "skip":
                name_colour = as_warning
            else:
                name_colour = as_info
            lines.append( "{}{} [{}]".format(
                    as_subdued( detail_under + branch ),
                    as_emphasised( name_colour( row["name"] ) ),
                    as_info( storage.display_path( row["path"] ) ),
            ) )
        if missing:
            lines.append( as_subdued( detail_under + stub ) )
            lines.append( "{}{}".format(
                    as_subdued( detail_under + elbow ),
                    "Use --clone-develop to obtain missing projects",
            ) )

    lines.append( "" )
    lines.append( "{}; nothing was built or cleaned.".format(
            as_info_label(
                    "--{}: {} considered".format(
                            STAGE_DEVELOP_PLAN_OPTION,
                            _plain_count_phrase(
                                    len( rows ),
                                    "location project",
                                    "location projects",
                            ),
                    )
            )
    ) )
    return lines


def finish_stage_develop_plan( cuppa_env, out=None ) -> int:
    """Print ``--stage-develop-plan`` and return an exit status (develop-action style)."""
    stream = out if out is not None else sys.stdout
    require_stage_develop_plan_with_develop( cuppa_env )
    try:
        lines = stage_develop_plan_lines( cuppa_env )
    except SCons.Errors.StopError as error:
        write_lines( [ "", str( error ) ], out=stream )
        return 1
    write_lines( lines, out=stream )
    rows = location_stage_plan_rows( cuppa_env )
    if any( row["severity"] == "error" for row in rows ):
        return 1
    return 0


def run_location_stage_develop( env ) -> None:
    """Nest-build or nest-clean every qualifying location develop tree once.

    Called from construct before tip sconscripts so ``N of M`` is known and nests
    are not interleaved with tip ``BuildWith`` construction. Order is leaf-first
    across edges discovered among the candidate set.
    """
    if _is_nested():
        return
    if not stage_develop_enabled( env ):
        return
    require_stage_develop_with_develop( env )
    if env.get( "_cuppa_location_stages_ran" ):
        return
    env["_cuppa_location_stages_ran"] = True

    candidates = location_stage_candidates( env )
    if not candidates:
        return
    total = len( candidates )
    write_lines( [
            "",
            "{}: {}".format(
                    as_info_label( "develop stage" ),
                    as_notice(
                            "{} location project{}".format(
                                    total, "" if total == 1 else "s"
                            )
                    ),
            ),
    ] )
    sys.stdout.flush()
    done = _location_stage_roots( env )
    for ordinal, ( label, root ) in enumerate( candidates, 1 ):
        if root in done:
            continue
        done.add( root )
        run_nested_location_project( env, root, label, ordinal=ordinal, total=total )


def consume_develop_package_stage(
        env,
        develop_root: str,
        package: str,
        version,
        label: str | None = None,
) -> str | None:
    """Resolve (and optionally nest-build) a publisher develop stage for tip consume.

    Default (``--develop`` alone): discover an existing ``final/<package>/<version>/``.
    With ``--stage-develop``: run a nested ``--stage-package`` session first (and
    forward ``-c`` so clean nests too). Nested tip sessions return ``None`` so the
    caller can fall through to registry download.
    """
    if _is_nested():
        return None
    require_stage_develop_with_develop( env )
    label = label or package
    cleaning = _clean_enabled( env )
    do_stage = stage_develop_enabled( env )

    if do_stage:
        run_nested_stage( env, develop_root, label )
    elif cleaning:
        # Tip-only clean: leave the develop package's stage alone.
        return resolve_develop_package_stage(
                develop_root, package, version, env=env
        )

    stage = resolve_develop_package_stage( develop_root, package, version, env=env )
    if cleaning:
        return stage
    if stage:
        return stage
    if do_stage:
        raise SCons.Errors.StopError(
                "develop package [{}] built from [{}] but no usable stage was found "
                "under _build/.../final/{}/{} (need include/ and lib/)"
                .format( label, develop_root, package, version )
        )
    raise SCons.Errors.StopError(
            "develop package [{}] at [{}] has no staged "
            "_build/.../final/{}/{} (need include/ and lib/). Build that "
            "tree yourself, or pass --{} with --develop to stage it from here"
            .format(
                    label,
                    develop_root,
                    package,
                    version,
                    STAGE_DEVELOP_OPTION,
            )
    )


def maybe_run_cascade( env, publisher ) -> None:
    """Run cascade when the flag is set; no-op for nested invokes or when unset.

    Under ``--cascade-plan`` this reports the resolved order and returns without
    cloning or nested publish. Under ``--collect-cascade`` it resolves, clones
    missing trees when ``--clone-publishers`` is set, reports, and returns without
    nested publish. Under ``--update-publishers`` it fast-forwards existing
    publisher trees (and may stop, or continue into nested publish when
    ``--publish-package`` is set). ``construct.py`` exits after the sconscript
    read for stop-before-build modes.
    """
    plan_only = cascade_plan_enabled( env )
    collect_only = cascade_collect_enabled( env )
    update_publishers = cascade_update_enabled( env )
    publish = bool( env.get_option( "publish-package" ) )
    # Stop before nested build when plan/collect, or update without publish.
    stop_only = plan_only or collect_only or ( update_publishers and not publish )

    if plan_only and collect_only:
        raise SCons.Errors.StopError(
                "--{} and --{} cannot be combined; choose review or collect"
                .format( CASCADE_PLAN_OPTION, COLLECT_CASCADE_OPTION )
        )
    if plan_only and update_publishers:
        raise SCons.Errors.StopError(
                "--{} and --{} cannot be combined; plan is review-only"
                .format( CASCADE_PLAN_OPTION, UPDATE_PUBLISHERS_OPTION )
        )
    if plan_only and not cascade_enabled( env ):
        raise SCons.Errors.StopError(
                "--{} requires --{}"
                .format( CASCADE_PLAN_OPTION, CASCADE_OPTION )
        )
    if collect_only and not cascade_enabled( env ):
        raise SCons.Errors.StopError(
                "--{} requires --{}"
                .format( COLLECT_CASCADE_OPTION, CASCADE_OPTION )
        )
    if update_publishers and not cascade_enabled( env ):
        raise SCons.Errors.StopError(
                "--{} requires --{}"
                .format( UPDATE_PUBLISHERS_OPTION, CASCADE_OPTION )
        )
    if not cascade_enabled( env ):
        return
    if _is_nested():
        logger.info(
                "Cascade: nested invoke — skipping further "
                "--{}".format( CASCADE_OPTION )
        )
        return
    # Plan, collect, and update-without-publish do not need --publish-package.
    if not stop_only and not publish:
        raise SCons.Errors.StopError(
                "--{} requires --publish-package, --{}, --{}, or --{}"
                .format(
                        CASCADE_OPTION,
                        CASCADE_PLAN_OPTION,
                        COLLECT_CASCADE_OPTION,
                        UPDATE_PUBLISHERS_OPTION,
                )
        )
    if update_publishers and env.get( "offline" ) and not _no_exec_enabled( env ):
        raise SCons.Errors.StopError(
                "--{} needs the network, but --offline was specified"
                .format( UPDATE_PUBLISHERS_OPTION )
        )
    # SCons -n still runs configure in nested sessions; Configure refuses to
    # create .sconf_temp under dry-run, so the nested publish dies before any
    # builder is skipped. Update-only / collect allow -n (like --update-develop).
    if not stop_only and _no_exec_enabled( env ):
        def remedy_colour( text ):
            return as_emphasised( as_info( text ) )

        _raise_options_error(
                "--{} cannot run under -n/--no-exec".format( CASCADE_OPTION ),
                [
                        (
                                "This is because it creates nested publisher sessions and "
                                "those sessions configure, however SCons forbids creating "
                                "[.sconf_temp] in a dry-run",
                                as_error,
                        ),
                        (
                                "Use --{} to review the order, --{} to place publisher "
                                "trees, or --{} -n to preview fast-forwards, then re-run "
                                "without -n to publish".format(
                                        CASCADE_PLAN_OPTION,
                                        COLLECT_CASCADE_OPTION,
                                        UPDATE_PUBLISHERS_OPTION,
                                ),
                                remedy_colour,
                        ),
                ],
                "Invalid option combination (--{} and -n/--no-exec)".format(
                        CASCADE_OPTION
                ),
        )

    tip_package = str( getattr( publisher, "_package", "" ) )
    tip_version = str( getattr( publisher, "_version", "" ) )

    # Plan: tolerant, no clone. Collect/update-stop: tolerant, clone when allowed.
    # Full run: fail-fast, clone when allowed.
    nodes, edges = build_cascade_graph(
            env,
            publisher,
            tolerant=stop_only,
            allow_clone=collect_only or not stop_only,
    )
    if not nodes:
        logger.info(
                "Cascade: tip [{}] declares no package dependencies — nothing to {}"
                .format(
                        as_info( tip_package ),
                        "collect" if collect_only else (
                                "update" if ( update_publishers and stop_only ) else (
                                        "plan" if plan_only else "publish"
                                )
                        ),
                )
        )
        if stop_only:
            record_plan_report(
                    tip_package,
                    tip_version,
                    0,
                    mode=(
                            COLLECT_CASCADE_OPTION if collect_only
                            else UPDATE_PUBLISHERS_OPTION if update_publishers
                            else CASCADE_PLAN_OPTION
                    ),
            )
        return

    order = topological_publish_order( nodes, edges )
    report_mode = (
            COLLECT_CASCADE_OPTION if collect_only
            else UPDATE_PUBLISHERS_OPTION if ( update_publishers and stop_only )
            else CASCADE_PLAN_OPTION if plan_only
            else None
    )
    cleaning = _clean_enabled( env )
    if stop_only:
        _record_publisher_objections( env, nodes, order )
    plan_report_mode = (
            COLLECT_CASCADE_OPTION if collect_only
            else UPDATE_PUBLISHERS_OPTION if ( update_publishers and stop_only )
            else None
    )
    write_lines( cascade_plan_lines(
            nodes, order, tip_package, tip_version,
            mode=plan_report_mode, clean=cleaning
    ) )

    trees_updated = 0
    if update_publishers and not plan_only:
        if not stop_only:
            judge_publisher_trees( env, nodes, order )
        trees_updated = update_publisher_trees( env, nodes, order )

    if stop_only:
        if plan_only:
            clone_count = sum( 1 for key in order if nodes[key].get( "_clone_dir" ) )
            trees_collected = 0
        else:
            clone_count = sum(
                    1 for key in order if nodes[key].get( "_cloned_now" )
            )
            trees_collected = sum(
                    1 for key in order if nodes[key].get( "_publisher_dir" )
            )
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
                clone_count=clone_count,
                needs_clone_opt_in=sum(
                        1 for key in order if nodes[key].get( "_needs_clone_opt_in" )
                ),
                unused_develop=sum(
                        1 for key in order if nodes[key].get( "_develop_unused" )
                ),
                mode=report_mode or CASCADE_PLAN_OPTION,
                trees_collected=trees_collected,
                trees_updated=trees_updated,
        )
        return

    if not update_publishers:
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
        # Clean sessions remove targets; nothing was published, so do not wipe and
        # re-download the tip's consume cache (that only confuses a following rebuild).
        if not cleaning:
            refresh_package_consume_cache( env, entry, tip_publisher=publisher )

    write_lines( sessions_complete_lines(
            total, tip_package, tip_version, clean=cleaning
    ) )
