#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   Structured CLI help topics (--help-topic= / cuppa help)
#-------------------------------------------------------------------------------

"""Additive topic / single-option help beside SCons' flat ``--help`` dump.

Bare ``cuppa --help`` / ``-h`` still go through SCons after the project loads.
``--help-topic=`` (Cuppa flag style) and optional ``cuppa help …`` sugar are
handled in ``cuppa.__main__`` without needing ``-D``. See
``design/plans/cli-help-topics.md``.
"""

from __future__ import annotations

from cuppa.colourise import (
        as_badge,
        as_emphasised,
        as_info,
        as_notice,
        as_subdued,
        colouriser,
)
from cuppa.core import options as cuppa_options
from cuppa.utility import storage
from cuppa.utility.console_report import write_report_lines
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


def _help_title( headline: str ) -> str:
    """``[help]:`` chip + emphasised headline — same family as Options Error."""
    return "{}: {}".format( as_badge( "notice", "help" ), as_emphasised( headline ) )


def _wrap_under( prefix: str, text: str, width: int ) -> list[str]:
    body = wrapped( text, max( width - len( prefix ), 40 ) )
    if isinstance( body, str ):
        pieces = body.splitlines() or [ text ]
    else:
        pieces = list( body ) or [ text ]
    lines = []
    branch = prefix
    # Keep hanging indent for wrapped prose under a tree stem.
    hang = " " * len( prefix )
    for index, piece in enumerate( pieces ):
        lines.append( ( branch if index == 0 else hang ) + piece )
    return lines


def format_topic_index_lines( width: int = 78 ) -> list[str]:
    ensure_cuppa_option_catalog()
    tee, elbow, pipe, gap = storage.glyphs()
    stub = pipe.rstrip()
    lines = [
            "",
            _help_title(
                    "{} topics".format( as_emphasised( str( len( _TOPIC_ORDER ) ) ) )
            ),
            as_subdued( stub ),
    ]
    total = len( _TOPIC_ORDER )
    for index, topic in enumerate( _TOPIC_ORDER ):
        last = index == total - 1
        first = elbow if last else tee
        carried = gap if last else pipe
        blurb = _TOPIC_BLURBS.get( topic, "" )
        count = len( _records_for_topic( topic ) )
        head = "{} {}{}".format(
                as_info( topic ),
                as_subdued( "(" ),
                as_emphasised( str( count ) ),
        ) + as_subdued( ")" )
        lines.append( as_subdued( first ) + head )
        if blurb:
            for piece in _wrap_under( as_subdued( carried ) + "  ", blurb, width ):
                lines.append( piece )
        if not last:
            lines.append( as_subdued( stub ) )
    lines.extend( [
            "",
            as_subdued(
                    "Pass --help-topic=<topic>, --help-topic=--flag, or "
                    "cuppa help … (sugar). Bare --help / -h after -D is still "
                    "SCons' flat dump."
            ),
            "",
    ] )
    return lines


def format_topic_help_lines( topic: str, width: int = 78 ) -> list[str]:
    ensure_cuppa_option_catalog()
    if topic not in _TOPIC_DESTS:
        known = ", ".join( _TOPIC_ORDER )
        return [
                "",
                _help_title( "unknown topic [{}]".format( topic ) ),
                as_subdued( "Known topics: {}.".format( known ) ),
                "",
        ]
    records = _records_for_topic( topic )
    blurb = _TOPIC_BLURBS.get( topic, "" )
    tee, elbow, pipe, gap = storage.glyphs()
    stub = pipe.rstrip()
    headline = topic
    if blurb:
        headline = "{} — {}".format( topic, blurb )
    lines = [ "", _help_title( headline ), as_subdued( stub ) ]
    if not records:
        lines.append( as_subdued( elbow ) + as_subdued( "(no matching options yet)" ) )
        lines.append( "" )
        return lines
    total = len( records )
    for index, record in enumerate( records ):
        last = index == total - 1
        first = elbow if last else tee
        carried = gap if last else pipe
        lines.extend( _format_option_tree_lines( record, first, carried, width ) )
        if not last:
            lines.append( as_subdued( stub ) )
    lines.append( "" )
    return lines


def format_option_help_lines( token: str, width: int = 78 ) -> list[str]:
    record = find_option_record( token )
    if record is None:
        return [
                "",
                _help_title( "unknown option [{}]".format( token ) ),
                as_subdued( "Try --help-topic= for the topic index." ),
                "",
        ]
    tee, elbow, pipe, gap = storage.glyphs()
    stub = pipe.rstrip()
    flag = _flag_label( record ).split( "=" )[0]
    lines = [ "", _help_title( flag ), as_subdued( stub ) ]
    lines.extend( _format_option_tree_lines( record, elbow, gap, width ) )
    related = _related_dests( record[ "dest" ] )
    if related:
        lines.append( as_subdued( stub ) )
        lines.append( as_subdued( elbow ) + as_notice( "Related" ) )
        for dest in related:
            twin = cuppa_options.option_catalog().get( dest )
            if twin:
                lines.append(
                        as_subdued( gap ) + "  " + as_info( _flag_label( twin ) )
                )
    lines.append( "" )
    return lines


def _format_option_tree_lines( record, first, carried, width: int ) -> list[str]:
    flag = as_info( _flag_label( record ) )
    dest = as_subdued( "dest=" + str( record.get( "dest" ) ) )
    lines = [ as_subdued( first ) + flag + "  " + dest ]
    help_text = " ".join( str( record.get( "help" ) or "" ).split() )
    if help_text:
        prefix = as_subdued( carried ) + "  "
        lines.extend( _wrap_under( prefix, help_text, width ) )
    return lines


# Back-compat string helpers for tests that assert substrings.
def format_topic_index( width: int = 78 ) -> str:
    return "\n".join( format_topic_index_lines( width=width ) ) + "\n"


def format_topic_help( topic: str, width: int = 78 ) -> str:
    return "\n".join( format_topic_help_lines( topic, width=width ) ) + "\n"


def format_option_help( token: str, width: int = 78 ) -> str:
    return "\n".join( format_option_help_lines( token, width=width ) ) + "\n"


def parse_help_argv( argv ):
    """Return ``('index'|'topic'|'option'|'error', payload)`` or ``None``.

    Prefer Cuppa flag style ``--help-topic=`` / ``--help-topic``. Also accepts
    ``help …`` as argv[0] sugar. Does not claim bare ``--help`` / ``-h``.
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
        if arg == "--help-topic" and index + 1 >= len( argv ):
            topic = ""
            break
    if topic is None:
        return None
    topic = topic.strip()
    if not topic:
        return ( "index", None )
    if topic in _TOPIC_DESTS:
        return ( "topic", topic )
    return ( "option", topic )


def render_help_request( kind, payload, out=None, width: int = 78 ) -> int:
    """Write a console report. Exit 0 on success, 2 on unknown topic/option."""
    colouriser.enable()
    if kind == "index":
        write_report_lines( format_topic_index_lines( width=width ), out=out )
        return 0
    if kind == "topic":
        lines = format_topic_help_lines( payload, width=width )
        write_report_lines( lines, out=out )
        return 0 if payload in _TOPIC_DESTS else 2
    if kind == "option":
        from cuppa.output_processor import strip_ansi
        lines = format_option_help_lines( payload, width=width )
        write_report_lines( lines, out=out )
        unknown = any(
                "unknown option" in strip_ansi( line ).lower() for line in lines
        )
        return 2 if unknown else 0
    if kind == "error":
        write_report_lines( [ "", _help_title( str( payload ) ), "" ], out=out )
        return 2
    return 2


def argv_requests_structured_help( argv ) -> bool:
    return parse_help_argv( argv ) is not None
