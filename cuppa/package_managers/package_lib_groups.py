#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

"""Named library groups for GitLab package ``use_libs`` tokens.

See ``design/plans/gitlab-package-lib-groups.md``. Authors declare groups that
expand to concrete library stems. Consumer ``use_libs`` tokens and traveling
manifest edge ``use_libs`` share the same vocabulary (leaves and/or groups).
"""

from __future__ import annotations

from typing import Any, Mapping

import SCons.Errors

from cuppa.colourise import as_info, as_notice, as_subdued
from cuppa.log import logger
from cuppa.utility.types import is_string


def normalise_lib_groups( value: Any ) -> dict[str, list[str]] | None:
    """Return ``{group: [leaf, ...]}``, or ``None`` when the field was omitted.

    Empty dict is kept (author cleared groups). Values must be a mapping of
    string group names to sequences of stem strings.
    """
    if value is None:
        return None
    if not isinstance( value, Mapping ):
        raise SCons.Errors.StopError(
                "Package lib_groups must be a mapping of group name → library "
                "list; got [{}]".format( type( value ).__name__ )
        )
    out: dict[str, list[str]] = {}
    for key, members in value.items():
        name = str( key )
        if is_string( members ):
            stems = [ str( members ) ]
        else:
            try:
                stems = [ str( item ) for item in members ]
            except TypeError as exc:
                raise SCons.Errors.StopError(
                        "Package lib_groups[{}] must be a library name or list; "
                        "got [{}]".format( name, type( members ).__name__ )
                ) from exc
        out[name] = stems
    return out


def expand_one_token(
        token: str,
        groups: Mapping[str, list[str]] | None,
        *,
        _stack: frozenset[str] | None = None,
) -> list[str]:
    """Expand one ``use_libs`` token to ordered concrete stems.

    When ``token`` names a group, members expand (nested groups recurse with
    cycle detection). Otherwise the token is treated as a leaf stem.
    """
    text = str( token )
    table = groups or {}
    if text not in table:
        return [ text ]
    stack = _stack or frozenset()
    if text in stack:
        raise SCons.Errors.StopError(
                "Package lib_groups cycle involving [{}]".format( text )
        )
    nested = stack | frozenset( [ text ] )
    expanded: list[str] = []
    seen: set[str] = set()
    for member in table[text]:
        member_text = str( member )
        # Group names shadow leaves at the token level, but a group may still
        # list its same-named primary stem as a member (e.g. ``kms`` →
        # ``[kms, kms_protos, …]``). Treat that self-reference as a leaf.
        if member_text == text:
            if member_text not in seen:
                seen.add( member_text )
                expanded.append( member_text )
            continue
        for leaf in expand_one_token( member_text, table, _stack=nested ):
            if leaf not in seen:
                seen.add( leaf )
                expanded.append( leaf )
    return expanded


def expand_use_lib_tokens(
        tokens,
        groups: Mapping[str, list[str]] | None,
) -> list[str]:
    """Expand a ``use_libs`` token list; preserve order; drop duplicate leaves."""
    expanded: list[str] = []
    seen: set[str] = set()
    for token in tokens:
        for leaf in expand_one_token( token, groups ):
            if leaf not in seen:
                seen.add( leaf )
                expanded.append( leaf )
    return expanded


def show_libs_for_token(
        token: str,
        groups: Mapping[str, list[str]] | None,
) -> list[str]:
    """Return the concrete stems ``token`` would link (group or leaf)."""
    return expand_one_token( token, groups )


def catalogue_lib_groups(
        groups: Mapping[str, list[str]] | None,
        linkable_stems=None,
) -> dict:
    """Return a discovery catalogue for ``show_all_libs``.

    Keys:
      - ``groups``: each declared group → fully expanded leaf list
      - ``ungrouped``: linkable stems not covered by any group expansion
        (empty when ``linkable_stems`` is omitted)
    """
    table = groups or {}
    expanded_groups = {
            name: expand_one_token( name, table )
            for name in table
    }
    covered: set[str] = set()
    for leaves in expanded_groups.values():
        covered.update( leaves )
    ungrouped: list[str] = []
    if linkable_stems is not None:
        for stem in linkable_stems:
            text = str( stem )
            if text not in covered:
                ungrouped.append( text )
    return {
            "groups": expanded_groups,
            "ungrouped": ungrouped,
    }


def report_show_libs_for( package_id: str, token: str, leaves: list[str] ) -> None:
    """Log a short configure-time expansion for one token."""
    if leaves:
        body = ", ".join( leaves )
    else:
        body = "(none)"
    logger.info(
            "show_libs_for [{}] on package [{}] → [{}]".format(
                    as_info( token ),
                    as_notice( package_id ),
                    as_info( body ),
            )
    )


def report_show_all_libs( package_id: str, catalogue: dict ) -> None:
    """Log a grouped configure-time catalogue."""
    groups = catalogue.get( "groups" ) or {}
    ungrouped = catalogue.get( "ungrouped" ) or []
    logger.info(
            "show_all_libs for package [{}]: {} group(s), {} ungrouped stem(s)".format(
                    as_notice( package_id ),
                    as_info( str( len( groups ) ) ),
                    as_info( str( len( ungrouped ) ) ),
            )
    )
    for name in sorted( groups ):
        leaves = groups[name]
        leaf_text = ", ".join( leaves ) if leaves else "(none)"
        logger.info(
                "{}{} → [{}]".format(
                        as_subdued( "  " ),
                        as_info( name ),
                        as_notice( leaf_text ),
                )
        )
    if ungrouped:
        logger.info(
                "{}ungrouped → [{}]".format(
                        as_subdued( "  " ),
                        as_notice( ", ".join( ungrouped ) ),
                )
        )
