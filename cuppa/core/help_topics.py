#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   Structured CLI help topics (cuppa help / --help-topic=)
#-------------------------------------------------------------------------------

"""Additive topic / single-option help beside SCons' flat ``--help`` dump.

Bare ``cuppa --help`` / ``-h`` still go through SCons after the project loads.
``cuppa help`` and ``--help-topic=`` are handled in ``cuppa.__main__`` without
needing ``-D``. See ``design/plans/cli-help-topics.md``.
"""

from __future__ import annotations

import sys

from cuppa.colourise import as_emphasised, as_info, as_notice, as_subdued
from cuppa.core import options as cuppa_options
from cuppa.utility.storage import wrapped


# Bootstrap topic → dest list (B-module-map). Extend as topics grow; later
# registrations can carry ``topics=`` tags without breaking this table.
_TOPIC_DESTS = {
        "configure": (
                "show_conf",
                "show_global_conf",
                "save_conf",
                "save_global_conf",
                "update_conf",
                "update_global_conf",
                "remove_settings",
                "remove_global_settings",
                "clear_conf",
                "clear_global_conf",
                "use_conf",
        ),
        "storage": (
                "build_root",
                "artefacts_root",
                "artifacts_root",
                "storage_root",
                "dependencies_root",
                "downloads_root",
                "download_root",
                "cache_root",
                "deep-clean",
                "list_builds",
                "remove_builds",
                "remove_all_builds",
                "list_format",
                "list_available_reports",
        ),
        "output": (
                "raw_output",
                "scons_output",
                "standard_output",
                "minimal_output",
                "native_output",
                "normal_output",
                "terse_output",
                "terse_output_show_actions",
                "show_test_cases",
                "ignore_duplicates",
                "show_test_output",
                "suppress_process_output",
                "quiet_heartbeat",
        ),
}

_TOPIC_BLURBS = {
        "configure": "Project and global configure.conf / ~/.cuppaconfig flags",
        "storage": "Build / dependency roots and local storage maintenance",
        "output": "Transcript, colour, spawn processor, and heartbeat flags",
}

# Stable display order for the index.
_TOPIC_ORDER = ( "configure", "storage", "output" )


def topic_ids() -> tuple[str, ...]:
    return _TOPIC_ORDER


_catalog_loaded = False


def ensure_cuppa_option_catalog() -> None:
    """Register Cuppa-owned options into the help catalog once per process.

    Uses real ``AddOption`` when SCons allows it (works outside a project).
    Configure flags register at import; base/storage/output via
    ``add_base_options``.
    """
    global _catalog_loaded
    if _catalog_loaded and cuppa_options.option_catalog():
        return
    import cuppa.configure
    from cuppa.core import base_options
    cuppa.configure.add_configure_options()
    base_options.add_base_options()
    _catalog_loaded = True


def reset_help_catalog_state() -> None:
    """Tests: clear catalog load latch and option catalog."""
    global _catalog_loaded
    _catalog_loaded = False
    cuppa_options.reset_option_catalog()


def _records_for_topic( topic: str ) -> list[dict]:
    dests = _TOPIC_DESTS.get( topic ) or ()
    catalog = cuppa_options.option_catalog()
    records = []
    for dest in dests:
        record = catalog.get( dest )
        if record is not None:
            records.append( record )
    return records


def _flag_label( record: dict ) -> str:
    flags = [ flag for flag in record.get( "flags" ) or () if flag.startswith( "--" ) ]
    if not flags:
        flags = list( record.get( "flags" ) or () )
    label = ", ".join( flags ) if flags else "--" + str( record.get( "dest" ) )
    metavar = record.get( "metavar" )
    if metavar and record.get( "takes_value" ):
        label = "{}={}".format( label.split( "," )[0], metavar )
    return label


def _related_dests( dest: str ) -> list[str]:
    """Global/project twins: ``show_conf`` ↔ ``show_global_conf``."""
    if dest.endswith( "_global_conf" ):
        twin = dest[: -len( "_global_conf" ) ] + "_conf"
    elif dest.endswith( "_conf" ) and not dest.endswith( "_global_conf" ):
        twin = dest[: -len( "_conf" ) ] + "_global_conf"
    elif dest.endswith( "_global_settings" ):
        twin = dest[: -len( "_global_settings" ) ] + "_settings"
    elif dest.endswith( "_settings" ) and not dest.endswith( "_global_settings" ):
        twin = dest[: -len( "_settings" ) ] + "_global_settings"
    else:
        return []
    catalog = cuppa_options.option_catalog()
    return [ twin ] if twin in catalog and twin != dest else []


def find_option_record( token: str ) -> dict | None:
    """Resolve ``--offline``, ``offline``, or a unique flag substring."""
    ensure_cuppa_option_catalog()
    catalog = cuppa_options.option_catalog()
    key = token.strip()
    if not key:
        return None
    if key.startswith( "--" ):
        for record in catalog.values():
            if key in ( record.get( "flags" ) or () ):
                return record
        # ``--foo=BAR`` → try ``--foo``
        if "=" in key:
            return find_option_record( key.split( "=", 1 )[0] )
        return None
    if key in catalog:
        return catalog[ key ]
    # dest with hyphens as in deep-clean
    hyphen = key.replace( "_", "-" )
    if hyphen in catalog:
        return catalog[ hyphen ]
    underscore = key.replace( "-", "_" )
    if underscore in catalog:
        return catalog[ underscore ]
    return None


def format_topic_index( width: int = 78 ) -> str:
    ensure_cuppa_option_catalog()
    lines = [
            as_emphasised( "cuppa help" ) + " — topic index",
            "",
            as_subdued( "Bare cuppa --help / -h still prints SCons' full dump after -D." ),
            as_subdued( "Use cuppa help <topic>, cuppa help --flag, or --help-topic=<topic>." ),
            "",
    ]
    for topic in _TOPIC_ORDER:
        blurb = _TOPIC_BLURBS.get( topic, "" )
        count = len( _records_for_topic( topic ) )
        head = as_info( topic ) + as_subdued( " ({})".format( count ) )
        lines.append( "  {}  {}".format( head, blurb ) )
    lines.append( "" )
    lines.append( as_subdued( "Topics grow as Cuppa wires more families; see design/plans/cli-help-topics.md." ) )
    return "\n".join( lines ) + "\n"


def format_topic_help( topic: str, width: int = 78 ) -> str:
    ensure_cuppa_option_catalog()
    if topic not in _TOPIC_DESTS:
        known = ", ".join( _TOPIC_ORDER )
        return (
                "Unknown help topic [{}]. Known topics: {}.\n"
                .format( topic, known )
        )
    records = _records_for_topic( topic )
    blurb = _TOPIC_BLURBS.get( topic, "" )
    lines = [
            as_emphasised( "cuppa help {}".format( topic ) )
            + ( " — " + blurb if blurb else "" ),
            "",
    ]
    if not records:
        lines.append( as_subdued( "(no matching options in the catalog yet)" ) )
        return "\n".join( lines ) + "\n"
    for record in records:
        lines.extend( _format_option_block( record, width ) )
        lines.append( "" )
    return "\n".join( lines ).rstrip() + "\n"


def format_option_help( token: str, width: int = 78 ) -> str:
    record = find_option_record( token )
    if record is None:
        return "Unknown option or dest [{}]. Try cuppa help for topics.\n".format( token )
    lines = [ as_emphasised( "cuppa help {}".format( _flag_label( record ).split( "=" )[0] ) ), "" ]
    lines.extend( _format_option_block( record, width ) )
    related = _related_dests( record[ "dest" ] )
    if related:
        lines.append( "" )
        lines.append( as_notice( "Related:" ) )
        for dest in related:
            twin = cuppa_options.option_catalog().get( dest )
            if twin:
                lines.append( "  " + as_info( _flag_label( twin ) ) )
    lines.append( "" )
    return "\n".join( lines )


def _format_option_block( record: dict, width: int ) -> list[str]:
    flag = as_info( _flag_label( record ) )
    dest = as_subdued( "dest=" + str( record.get( "dest" ) ) )
    lines = [ "  {}  {}".format( flag, dest ) ]
    help_text = " ".join( str( record.get( "help" ) or "" ).split() )
    if help_text:
        body = wrapped( help_text, max( width - 6, 40 ) )
        if isinstance( body, str ):
            body_lines = body.splitlines() or [ help_text ]
        else:
            body_lines = list( body ) or [ help_text ]
        for line in body_lines:
            lines.append( "      " + line )
    return lines


def parse_help_argv( argv ):
    """Return ``('index'|'topic'|'option'|'error', payload)`` or ``None``.

    Recognises ``help …`` as argv[0], and ``--help-topic=`` / ``--help-topic``
    anywhere. Does not claim bare ``--help`` / ``-h`` (SCons keeps those).
    """
    if not argv:
        return None
    if argv[0] == "help":
        rest = argv[1:]
        if not rest:
            return ( "index", None )
        token = rest[0]
        if token in _TOPIC_DESTS or token == "all":
            if token == "all":
                return ( "error", "Topic [all] is not implemented yet; use cuppa -D --help." )
            return ( "topic", token )
        return ( "option", token )

    topic = None
    for index, arg in enumerate( argv ):
        if arg.startswith( "--help-topic=" ):
            topic = arg.split( "=", 1 )[1]
            break
        if arg == "--help-topic" and index + 1 < len( argv ):
            topic = argv[ index + 1 ]
            break
    if topic is None:
        return None
    topic = topic.strip()
    if not topic:
        return ( "index", None )
    if topic in _TOPIC_DESTS:
        return ( "topic", topic )
    # Allow ``--help-topic=--offline`` / dest as single-option lookup.
    return ( "option", topic )


def render_help_request( kind, payload, out=None, width: int = 78 ) -> int:
    """Write help text. Exit 0 on success, 2 on unknown topic/option."""
    out = out or sys.stdout
    if kind == "index":
        out.write( format_topic_index( width=width ) )
        return 0
    if kind == "topic":
        text = format_topic_help( payload, width=width )
        out.write( text )
        return 0 if payload in _TOPIC_DESTS else 2
    if kind == "option":
        text = format_option_help( payload, width=width )
        out.write( text )
        return 0 if not text.startswith( "Unknown" ) else 2
    if kind == "error":
        out.write( str( payload ) + "\n" )
        return 2
    return 2


def argv_requests_structured_help( argv ) -> bool:
    return parse_help_argv( argv ) is not None
