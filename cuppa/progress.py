
#          Copyright Jamie Allsop 2013-2015
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   Progress
#-------------------------------------------------------------------------------

import atexit
import logging
import os.path
import sys
import threading

from cuppa.colourise import as_colour, as_emphasised, as_info, as_notice, as_subdued
from cuppa.log import logger

from SCons.Script import Action


class NotifyProgress(object):

    _callbacks = set()
    _sconscript_env_hooks = set()

    _sconstruct_begin = None
    _sconstruct_end   = None
    _begin    = {}
    _end      = {}
    _started  = {}
    _finished = {}
    _inventory_report_mode = False

    @classmethod
    def set_inventory_report_mode( cls, enabled ):
        cls._inventory_report_mode = bool( enabled )

    @classmethod
    def inventory_report_mode( cls ):
        return cls._inventory_report_mode

    @classmethod
    def register_callback( cls, env, callback ):
        if env:
            if not 'cuppa_progress_callbacks' in env:
                env['cuppa_progress_callbacks'] = set()
            env['cuppa_progress_callbacks'].add( callback )
        else:
            cls._callbacks.add( callback )


    @classmethod
    def register_sconscript_env_hook( cls, hook ):
        """Register a callback invoked once each sconscript env is ready to build.

        Hooks receive the cloned sconscript construction ``env`` (after
        ``build_dir`` / ``sconscript_file`` are set). Intended for rebinding
        per-sconscript services such as ``SPAWN`` without coupling ``construct``
        to individual features.
        """
        cls._sconscript_env_hooks.add( hook )


    @classmethod
    def notify_sconscript_env_ready( cls, env ):
        """Invoke registered sconscript-env hooks; errors propagate to the build."""
        for hook in cls._sconscript_env_hooks:
            hook( env )


    @classmethod
    def call_callbacks( cls, event, sconscript, variant, env, target, source ):
        if 'cuppa_progress_callbacks' in env:
            for callback in env['cuppa_progress_callbacks']:
                callback( event, sconscript, variant, env, target, source )
        for callback in cls._callbacks:
            callback( event, sconscript, variant, env, target, source )


    @classmethod
    def variant( cls, env ):
        return os.path.split(env['build_dir'])[0]


    @classmethod
    def scope_from_env( cls, env ):
        """Return ``(sconscript, variant_dir)`` for a construction env, or ``None``."""
        try:
            if not env.get( 'build_dir' ) or not env.get( 'sconscript_file' ):
                return None
            return ( cls.sconscript( env ), cls.variant( env ) )
        except ( AttributeError, KeyError, TypeError ):
            return None


    @classmethod
    def toolchain_name( cls, env ):
        try:
            return env[ 'toolchain' ].name()
        except ( AttributeError, KeyError, TypeError ):
            return None


    @classmethod
    def sconscript( cls, env ):
        return env['sconscript_file']


    @classmethod
    def key( cls, env ):
        return cls.sconscript( env ) + "/" + cls.variant( env )


    @classmethod
    def add( cls, env, target ):

        if '_pre_sconscript_phase_' in env and env['_pre_sconscript_phase_']:
            return

        empty_env       = env['empty_env']
        sconscript_env  = env['sconscript_env']

        sconscript    = cls.sconscript( sconscript_env )
        variant       = cls.variant( env )

        if not cls._sconstruct_begin:
            cls._sconstruct_begin = progress( '#SconstructBegin', 'sconstruct_begin', None, None, empty_env )

        if not sconscript in cls._begin:
            cls._begin[sconscript] = progress( 'Begin', 'begin', sconscript, None, sconscript_env )

        begin = cls._begin[sconscript]

        env.Requires( begin, cls._sconstruct_begin )

        if variant not in cls._started:
            cls._started[variant] = progress( 'Starting', 'started', sconscript, variant, env )

        env.Requires( target, cls._started[variant] )
        env.Requires( cls._started[variant], begin )

        if variant not in cls._finished:
            cls._finished[variant] = progress( 'Finished', 'finished', sconscript, variant, env )

        file_deps = [ '#' + env['sconscript_file'], '#' + env['sconstruct_file'] ]
        # Depends enforces build order. Requires alone does not — inventory mode previously
        # let Finished run before long Run/Test actions completed ([#215]).
        env.Depends( cls._finished[variant], file_deps )
        env.Depends( cls._finished[variant], target )
        finished = cls._finished[variant]

        if not sconscript in cls._end:
            cls._end[sconscript] = progress( 'End', 'end', sconscript, None, sconscript_env )

        end = env.Requires( cls._end[sconscript], finished )

        if not cls._sconstruct_end:
            cls._sconstruct_end = progress( '#SconstructEnd', 'sconstruct_end', None, None, empty_env )

        env.Requires( cls._sconstruct_end, end )


class VariantCompletionTracker(object):
    """Track Progress variant paths that started but have not yet finished."""

    def __init__( self ):
        self._lock = threading.Lock()
        self._open_variants = set()
        self._complete_variants = set()

    def note_progress( self, event, variant ):
        if event == 'started' and variant:
            with self._lock:
                self._open_variants.add( variant )
                self._complete_variants.discard( variant )
        elif event == 'finished' and variant:
            with self._lock:
                self._open_variants.discard( variant )
                self._complete_variants.add( variant )

    def incomplete_variants( self ):
        with self._lock:
            return self._open_variants - self._complete_variants


def progress( label, event, sconscript, variant, env ):
    # Use the unwrapped builder when Cuppa has wrapped Command with
    # MethodWithProgress — otherwise NotifyProgress.add → Command →
    # NotifyProgress.add recurses forever (Command returns a NodeList).
    command = getattr( env, '_Command', None ) or env.Command
    return command( label, [], progress_action( label, event, sconscript, variant, env ) )


class Progress(object):

    def __init__( self, event, sconscript, variant, env ):
        self._event   = event
        self._file    = sconscript
        self._variant = variant
        self._env     = env

    def __call__( self, target, source, env ):
        NotifyProgress.call_callbacks( self._event, self._file, self._variant, self._env, target, source )
        return None


def progress_action( label, event, sconscript, variant, env ):

    progress = Progress( event, sconscript, variant, env )

    description = None

    if logger.isEnabledFor( logging.INFO ):
        stage = ""
        name  = ""
        if label.startswith("#"):
            stage = as_notice( label[1:] )
        elif not variant:
            stage = as_notice(label) + " sconscript: ["
            name = as_notice( sconscript ) + "]"
        else:
            stage = as_notice(label) + " variant: ["
            name = as_info( variant ) + "]"

        description = "Progress( {}{} )".format( stage, name )

    return Action( progress, description )


_terse_command = threading.local()
_terse_children = threading.local()
_pending_lock = threading.Lock()
# Commands stashed by a job thread and not yet consumed by a spawn. A Python
# action prints before it runs and never spawns, so the next print on that
# thread (or process exit) writes the line back out.
_pending_commands = {}


def terse_counts_prefix():
    """Leading counts segment reserved for Phase 2. Empty until then."""
    return ""


def _is_progress_command( cmd ):
    return bool( cmd ) and cmd.lstrip().startswith( "Progress(" )


def _env_get( env, key, default=None ):
    if not env or not hasattr( env, "get" ):
        return default
    return env.get( key, default )


def _first_node( nodes ):
    if not nodes:
        return None
    if isinstance( nodes, ( list, tuple ) ):
        return nodes[0] if nodes else None
    return nodes


def _node_path( node ):
    if node is None:
        return ""
    path = getattr( node, "path", None )
    if path:
        return str( path )
    return str( node )


def _node_basename( nodes ):
    text = _node_path( _first_node( nodes ) ).replace( "\\", "/" )
    if not text:
        return ""
    return os.path.basename( text ) or text


def _iter_nodes( nodes ):
    if nodes is None or isinstance( nodes, ( str, bytes ) ):
        return []
    if hasattr( nodes, "attributes" ):
        return [ nodes ]
    if isinstance( nodes, ( list, tuple ) ):
        return list( nodes )
    try:
        return list( nodes )
    except TypeError:
        return [ nodes ]


def label_terse_action( nodes, action, paths=None ):
    """Remember ``action`` on each product node. A later status line reads it.

    Do not label a node that has more than one tool action. A static library is
    both ``archive`` and ``index``; the toolchain tells those apart from the
    command. One label would hide that.

    ``paths="transfer"`` prints ``source → dest`` even when the action word is
    shared with a single-file action (``run`` is both a program and a redirect).
    """
    if not action:
        return nodes
    for node in _iter_nodes( nodes ):
        attributes = getattr( node, "attributes", None )
        if attributes is None:
            continue
        try:
            attributes.cuppa_terse_action = action
            if paths:
                attributes.cuppa_terse_paths = paths
        except Exception:
            continue
    return nodes


def _explicit_terse_action( target ):
    """The method label, from whichever target carries it.

    An emitter often puts an intermediate file first. The label may be on a
    later product node in the same action.
    """
    for node in _iter_nodes( target ):
        attributes = getattr( node, "attributes", None )
        if attributes is None:
            continue
        label = str( getattr( attributes, "cuppa_terse_action", "" ) or "" )
        if label:
            return label
    return ""


def spell_terse_action( command, target, env=None ):
    """Short action word for one tool run. Not the Cuppa method name.

    A method label wins, then the active toolchain, then the shared tool
    speller. Anything else is ``run``. ``link`` is only a compiler driver
    producing a program.
    """
    label = _explicit_terse_action( target )
    if label:
        return label
    toolchain = _env_get( env, "toolchain" )
    spell = getattr( toolchain, "spell_terse_action", None )
    if callable( spell ):
        word = spell( command, target )
        if word:
            return word
    from cuppa.toolchains.terse_actions import spell_tool_command
    return spell_tool_command( command, target ) or "run"


def _coloured_sconscript( label ):
    """Mute the directory. The leaf is info, not notice, beside ``[ok]``."""
    if "/" not in label:
        return as_info( label )
    directory, leaf = label.rsplit( "/", 1 )
    return as_subdued( directory + "/" ) + as_info( leaf )


def _sconscript_label( env ):
    path = str( _env_get( env, "sconscript_file", "" ) or "" ).replace( "\\", "/" )
    if path.startswith( "./" ):
        path = path[2:]
    if path == "sconscript":
        return ""
    if path.endswith( "/sconscript" ):
        return path[: -len( "/sconscript" )]
    if path.endswith( ".sconscript" ):
        return path[: -len( ".sconscript" )]
    return path


def _variant_name( env ):
    variant = _env_get( env, "variant" )
    if variant is None:
        return ""
    name = variant.name() if hasattr( variant, "name" ) else variant
    return str( name )


def _variant_cell( env ):
    """Toolchain, variant, arch, and abi. ``dbg`` alone is ambiguous across scripts."""
    toolchain = _env_get( env, "toolchain" )
    toolchain_name = toolchain.name() if hasattr( toolchain, "name" ) else ""
    parts = [
            str( part ) for part in (
                    toolchain_name,
                    _variant_name( env ),
                    _env_get( env, "target_arch", "" ) or "",
                    _env_get( env, "abi", "" ) or "",
            ) if part
    ]
    return "_".join( parts )


def _coloured_variant_cell( env ):
    """Mute the build cell, but leave ``dbg`` / ``rel`` / ``cov`` plain."""
    cell = _variant_cell( env )
    name = _variant_name( env )
    if not cell:
        return ""
    if not name:
        return as_subdued( cell )
    if cell == name:
        return name
    token = "_" + name + "_"
    if token in cell:
        before, after = cell.split( token, 1 )
        return as_subdued( before + "_" ) + name + as_subdued( "_" + after )
    if cell.startswith( name + "_" ):
        return name + as_subdued( cell[ len( name ): ] )
    if cell.endswith( "_" + name ):
        return as_subdued( cell[ : -len( name ) ] ) + name
    return as_subdued( cell )


def _slash( path ):
    return os.path.normpath( str( path ) ).replace( "\\", "/" )


def _under( path, root ):
    """True when ``path`` is ``root`` or a file inside it. No ``..`` climb."""
    if not path or not root:
        return False
    path = os.path.normcase( os.path.normpath( path ) )
    root = os.path.normcase( os.path.normpath( root ) )
    if path == root:
        return True
    return path.startswith( root + os.sep )


def _to_abs( raw, env ):
    """Absolute path. Relative node paths are from the project root, as SCons stores them."""
    if os.path.isabs( raw ):
        return os.path.normpath( raw )
    anchor = _env_get( env, "base_path" ) or os.getcwd()
    return os.path.normpath( os.path.join( anchor, raw ) )


def _home_display( abs_path ):
    """``~/...`` with ``/`` separators on every platform. Absolute when not under home."""
    home = os.path.normpath( os.path.expanduser( "~" ) )
    path = os.path.normpath( abs_path )
    if not home or home == "~":
        return path.replace( "\\", "/" )
    if os.path.normcase( path ) == os.path.normcase( home ):
        return "~"
    prefix = home + os.sep
    if os.path.normcase( path ).startswith( os.path.normcase( prefix ) ):
        return ( "~" + path[ len( home ): ] ).replace( "\\", "/" )
    return path.replace( "\\", "/" )


def _project_display( abs_path, env ):
    base = _env_get( env, "base_path", "" ) or ""
    if not base:
        return ""
    base = os.path.normpath( base )
    path = os.path.normpath( abs_path )
    if not _under( path, base ) or os.path.normcase( path ) == os.path.normcase( base ):
        return ""
    try:
        return os.path.relpath( path, base ).replace( "\\", "/" )
    except ValueError:
        return ""


def _is_file( path, env ):
    if not path:
        return False
    candidate = path if os.path.isabs( path ) else _to_abs( path, env )
    return os.path.isfile( candidate )


def _origin_path( node, env ):
    """Source-tree path when the file exists there, not only as a variant copy."""
    raw = _node_path( node )
    srcnode = getattr( node, "srcnode", None )
    if callable( srcnode ):
        try:
            origin = srcnode()
        except Exception:
            origin = None
        if origin is not None and origin is not node:
            origin_path = _node_path( origin )
            if (
                    origin_path
                    and not _is_variant_working_path( origin_path, env )
                    and _is_file( origin_path, env )
            ):
                return origin_path
    stripped = _strip_variant_working( raw, env )
    if stripped and _is_file( stripped, env ):
        return stripped
    return raw


def _is_variant_working_path( raw, env ):
    text = _slash( raw )
    tool = _slash( _env_get( env, "tool_variant_dir", "" ) or "" ).strip( "/" )
    if tool and ( "/" + tool + "/working/" ) in ( "/" + text ):
        return True
    build_dir = _env_get( env, "build_dir", "" ) or ""
    if not build_dir:
        return False
    return _under( _to_abs( raw, env ), _to_abs( build_dir, env ) )


def _strip_variant_working( raw, env ):
    """``.../<tool>/<variant>/<arch>/<abi>/working/<file>`` → source-tree path."""
    if not raw:
        return ""
    text = _slash( raw )
    tool = _slash( _env_get( env, "tool_variant_dir", "" ) or "" ).strip( "/" )
    needle = "/" + tool + "/working/" if tool else ""
    rest = ""
    if needle and needle in ( "/" + text ):
        rest = ( "/" + text ).split( needle, 1 )[1]
    else:
        build_dir = _env_get( env, "build_dir", "" ) or ""
        if build_dir:
            abs_raw = _to_abs( raw, env )
            abs_dir = _to_abs( build_dir, env )
            if _under( abs_raw, abs_dir ):
                rest = os.path.relpath( abs_raw, abs_dir ).replace( "\\", "/" )
    if not rest or rest == ".":
        return ""
    script = _sconscript_label( env )
    if script:
        return script + "/" + rest
    return rest


def _display_source_path( raw, env ):
    """Project-relative, else ``~/...``, else absolute. Never a ``../`` climb."""
    if not raw:
        return ""
    text = str( raw ).replace( "\\", "/" )
    if text.startswith( "~/" ) or text == "~":
        return text
    climbs = text == ".." or text.startswith( "../" )
    if not os.path.isabs( raw ) and not climbs:
        shown = _slash( raw )
        return "" if shown in ( "", "." ) else shown
    abs_path = _to_abs( raw, env )
    shown = _project_display( abs_path, env ) or _home_display( abs_path )
    if shown in ( "", "." ):
        return ""
    return shown


def _compile_file_parts( source, env ):
    """Source location in the project tree, or ``~/...`` when it lives outside."""
    node = _first_node( source )
    raw = _origin_path( node, env ) if node is not None else ""
    shown = _display_source_path( raw, env )
    if not shown:
        return "", ""
    directory, filename = os.path.split( shown )
    if directory in ( "", "." ):
        directory = ""
    return directory, filename or shown


def _coloured_file( directory, filename ):
    if not filename:
        return ""
    if directory:
        return as_subdued( directory + "/" ) + as_emphasised( filename )
    return as_emphasised( filename )


def _rel_inside( abs_path, root ):
    """Path of ``abs_path`` inside ``root``, or ``None`` when it is not inside."""
    root = os.path.normpath( root )
    path = os.path.normpath( abs_path )
    if not _under( path, root ):
        return None
    if os.path.normcase( path ) == os.path.normcase( root ):
        return ""
    try:
        return os.path.relpath( path, root ).replace( "\\", "/" )
    except ValueError:
        return None


def _strip_artifact_folder( relative, env ):
    """Drop the ``<sconscript>_<variant>`` directory already named on the line."""
    flat = str( _env_get( env, "flat_build_base", "" ) or "" ).replace( "\\", "/" ).strip( "/" )
    relative = str( relative or "" ).replace( "\\", "/" ).strip( "/" )
    if not flat or not relative:
        return relative
    head, _sep, tail = relative.partition( "/" )
    if os.path.normcase( head ) == os.path.normcase( flat ):
        return tail
    return relative


def _locate( raw, env ):
    """``(root, relative)`` for a path on a status line.

    ``root`` is ``working`` or ``final`` for this variant's build, or
    ``artifacts`` for this variant's folder under the artefacts root. Any
    other path there is a normal project path. Otherwise ``relative`` is the
    project path, ``~/...``, or an absolute path.
    """
    if not raw:
        return "", ""
    text = str( raw ).replace( "\\", "/" )
    if text.startswith( "~/" ) or text == "~":
        return "", text
    abs_path = _to_abs( raw, env )
    roots = (
            ( "final", "abs_final_dir" ),
            ( "working", "abs_build_dir" ),
            ( "artifacts", "abs_artefacts_root" ),
    )
    for token, key in roots:
        root = _env_get( env, key, "" ) or ""
        if token == "artifacts" and not root:
            root = _env_get( env, "abs_artifacts_root", "" ) or ""
        if not root:
            continue
        root_abs = root if os.path.isabs( root ) else _to_abs( root, env )
        relative = _rel_inside( abs_path, root_abs )
        if relative is None:
            continue
        if token == "artifacts":
            # ``<artifacts>`` is this variant's folder, not the artefacts root.
            # ``_artifacts/documentation/...`` is a real path and stays as-is.
            variant_relative = _strip_artifact_folder( relative, env )
            if variant_relative == relative:
                continue
            return token, variant_relative
        return token, relative
    return "", _display_source_path( raw, env )


def _coloured_transfer_end( token, relative, dest ):
    """One side of ``source → dest``.

    The source is entirely subdued. The destination directory is subdued and
    its filename is info-coloured and bold, not the info highlight.
    ``<working>``, ``<final>``, and
    ``<artifacts>`` mark build locations so they are not read as project paths.
    """
    relative = str( relative or "" ).replace( "\\", "/" ).strip( "/" )
    directory, filename = os.path.split( relative ) if relative else ( "", "" )
    if directory in ( "", "." ):
        directory = ""
    prefix = ( "<" + token + ">/" ) if token else ""
    if dest:
        head = prefix + ( directory + "/" if directory else "" )
        shown = as_subdued( head ) if head else ""
        if filename:
            shown += as_emphasised( as_info( filename ) )
        elif token:
            shown = as_subdued( "<" + token + ">" )
        return shown
    if token and relative:
        return as_subdued( prefix + relative )
    if token:
        return as_subdued( "<" + token + ">" )
    return as_subdued( relative ) if relative else ""


def _transfer_field( target, source, env ):
    source_token, source_path = _locate( _node_path( _first_node( source ) ), env )
    dest_token, dest_path = _locate( _node_path( _first_node( target ) ), env )
    source_text = _coloured_transfer_end( source_token, source_path, dest=False )
    dest_text = _coloured_transfer_end( dest_token, dest_path, dest=True )
    if source_text and dest_text:
        return source_text + " " + as_subdued( "→" ) + " " + dest_text
    return source_text or dest_text


def _paths_style( nodes ):
    for node in _iter_nodes( nodes ):
        attributes = getattr( node, "attributes", None )
        if attributes is None:
            continue
        style = str( getattr( attributes, "cuppa_terse_paths", "" ) or "" )
        if style:
            return style
    return ""


_TRANSFER_ACTIONS = ( "copy", "expand", "render" )
_SOURCE_ACTIONS = ( "markdown", "asciidoc" )


def _file_field( action, target, source, env ):
    if action in _TRANSFER_ACTIONS or _paths_style( target ) == "transfer":
        return _transfer_field( target, source, env )
    if action == "compile" or str( action ).startswith( "compile-" ) or action in _SOURCE_ACTIONS:
        directory, filename = _compile_file_parts( source, env )
        if filename:
            return _coloured_file( directory, filename )
    return _coloured_file( "", _node_basename( target ) )


def _status_marker( status ):
    if status == "warn":
        return as_colour( "warning", "[warn]" )
    if status == "error":
        return as_colour( "error", "[error]" )
    return as_colour( "success", "[ok]" )


def format_terse_line( status, command, target, source, env ):
    """``[status] sconscript · variant · action · file``. Counts prefix stays empty until Phase 2."""
    parts = []
    prefix = terse_counts_prefix()
    if prefix:
        parts.append( prefix )
    parts.append( _status_marker( status ) )

    fields = []
    script = _sconscript_label( env )
    if script:
        fields.append( _coloured_sconscript( script ) )
    cell = _coloured_variant_cell( env )
    if cell:
        fields.append( cell )
    action = spell_terse_action( command, target, env )
    fields.append( action )
    file_text = _file_field( action, target, source, env )
    if file_text:
        fields.append( file_text )
    if fields:
        parts.append( ( " " + as_subdued( "·" ) + " " ).join( fields ) )
    return " ".join( parts )


def format_terse_success( command, target, source, env ):
    return format_terse_line( "ok", command, target, source, env )


def stash_terse_command( cmd, target, source, env ):
    _terse_command.cmd = cmd
    _terse_command.target = target
    _terse_command.source = source
    _terse_command.env = env
    with _pending_lock:
        _pending_commands[ threading.get_ident() ] = ( cmd, target, source, env )


def note_terse_child( command, lines, failed=False ):
    """Remember a tool this Python action started, for the status line.

    The action calls this instead of printing the command. A clean tool is
    dropped. A warning, an error line, or a non-zero exit is printed before
    the summary. Safe under ``-j`` because the note stays on this job thread.
    """
    children = getattr( _terse_children, "items", None )
    if children is None:
        children = []
        _terse_children.items = children
    children.append( ( command, list( lines or [] ), bool( failed ) ) )


def take_terse_children():
    """Return and clear child tools noted on this job thread."""
    children = list( getattr( _terse_children, "items", None ) or [] )
    _terse_children.items = []
    return children


def _output_severity( lines ):
    """``error`` if any line is an error, else ``warn``, else ``ok``.

    Asciidoctor writes ``asciidoctor: ERROR:`` and still exits 0. The status
    line should say what the tool said. The action's own return code is
    unchanged, so SCons still decides whether the build failed.
    """
    severity = "ok"
    for line in lines or []:
        folded = str( line ).lower()
        if ": error:" in folded or folded.startswith( "error:" ):
            return "error"
        if ": warning:" in folded or folded.startswith( "warning:" ):
            severity = "warn"
    return severity


def take_terse_command():
    """Return and clear the command stashed on this job thread."""
    cmd = getattr( _terse_command, "cmd", None )
    target = getattr( _terse_command, "target", None )
    source = getattr( _terse_command, "source", None )
    env = getattr( _terse_command, "env", None )
    _terse_command.cmd = None
    _terse_command.target = None
    _terse_command.source = None
    _terse_command.env = None
    with _pending_lock:
        _pending_commands.pop( threading.get_ident(), None )
    return cmd, target, source, env


def _write_command( cmd ):
    if cmd:
        sys.stdout.write( cmd + "\n" )


def flush_unconsumed_terse_command():
    """Reprint a command whose action did not spawn on this thread."""
    cmd, _target, _source, _env = take_terse_command()
    _write_command( cmd )


def flush_terse_commands():
    """Reprint commands still stashed when the process exits."""
    with _pending_lock:
        leftover = list( _pending_commands.values() )
        _pending_commands.clear()
    for cmd, _target, _source, _env in leftover:
        _write_command( cmd )


def _shows_notify_progress( env ):
    """True when ``--terse-output-notify-progress`` is set on this env."""
    if not env or not hasattr( env, "get" ):
        return False
    return bool( env.get( "terse_output_notify_progress" ) )


def terse_print_cmd_line( cmd, target, source, env ):
    """SCons ``PRINT_CMD_LINE_FUNC`` for ``--terse-output``.

    Progress lines are dropped unless ``--terse-output-notify-progress`` is
    set. ``-Q`` still omits them, because ``progress_action`` only builds the
    description at info. Tool commands are stashed and printed later, only
    when that run warns or fails. Show and execute run on the same SCons job
    thread, so a per-thread stash pairs them under ``-j``. A command that
    never reaches a spawn is written back on the next print, or at process exit.
    """
    flush_unconsumed_terse_command()
    if _is_progress_command( cmd ):
        if _shows_notify_progress( env ):
            sys.stdout.write( cmd + "\n" )
        return
    stash_terse_command( cmd, target, source, env )


atexit.register( flush_terse_commands )


def _chunk_lines( chunk ):
    if not chunk:
        return []
    text = chunk[:-1] if chunk.endswith( "\n" ) else chunk
    if not text:
        return []
    return text.split( "\n" )


def render_terse_spawn( returncode, errors, warnings, buffered_lines, command, target, source, env, summary ):
    """Lines to print after a terse tool run.

    A clean exit with no warnings is one success line. A warning or failure
    prints the command and the processed output first, then the status line
    as the summary.
    """
    if not returncode and not errors and not warnings:
        status = "ok"
    elif returncode or errors:
        status = "error"
    else:
        status = "warn"
    status_line = format_terse_line( status, command, target, source, env )
    if status == "ok":
        return [ status_line ]
    lines = []
    if command:
        lines.append( command )
    for chunk in buffered_lines or []:
        lines.extend( _chunk_lines( chunk ) )
    lines.extend( _chunk_lines( summary ) )
    lines.append( status_line )
    return lines


class _TersePythonCallable( object ):
    """Run a Python action, then print its terse status line.

    Installed only on environments that asked for ``--terse-output``. A shared
    builder still used without that flag calls the original and stops.
    """

    def __init__( self, original ):
        self._original = original
        name = getattr( original, "__name__", None ) or original.__class__.__name__
        self.__name__ = name
        inner = getattr( original, "strfunction", None )
        if callable( inner ):
            self.strfunction = inner

    def __call__( self, target, source, env, **ignored ):
        if not _env_get( env, "terse_output" ):
            return self._original( target=target, source=source, env=env )
        try:
            result = self._original( target=target, source=source, env=env )
        except ( KeyboardInterrupt, SystemExit ):
            raise
        except Exception:
            _report_python_action( target, source, env, failed=True )
            raise
        _report_python_action( target, source, env, failed=bool( result ) )
        return result


def _report_python_action( target, source, env, failed ):
    """Consume the stashed description. A clean run is one line.

    A warning or failure prints the tool command and its output first, then
    the status line. A child noted with ``note_terse_child`` is that tool.
    Otherwise the SCons description is used.
    """
    command, stashed_target, stashed_source, stashed_env = take_terse_command()
    children = take_terse_children()
    use_target = target or stashed_target
    use_source = source or stashed_source
    use_env = env or stashed_env or {}
    severity = "error" if failed else "ok"
    for _child_command, lines, child_failed in children:
        if child_failed:
            severity = "error"
            continue
        child_severity = _output_severity( lines )
        if child_severity == "error":
            severity = "error"
        elif child_severity == "warn" and severity == "ok":
            severity = "warn"
    spell_command = command or ""
    if children and not _explicit_terse_action( use_target ):
        spell_command = children[0][0]
    status_line = format_terse_line(
            severity,
            spell_command,
            use_target,
            use_source,
            use_env,
    )
    if severity != "ok":
        if children:
            for child_command, lines, _child_failed in children:
                _write_command( child_command )
                for line in lines:
                    _write_command( line )
        elif command:
            _write_command( command )
    sys.stdout.write( status_line + "\n" )
    sys.stdout.flush()


def _wrap_action( action ):
    """Replace a ``FunctionAction`` body without changing its build signature.

    ``FunctionAction`` stores the signature at construction. Swapping
    ``execfunction`` afterwards leaves that signature alone. Command actions
    stay on the spawn path. ``Progress`` actions stay quiet.
    """
    if action is None:
        return
    list_action = getattr( action, "list", None )
    if list_action is not None and not hasattr( action, "execfunction" ):
        for child in list_action:
            _wrap_action( child )
        return
    original = getattr( action, "execfunction", None )
    if original is None or getattr( action, "_cuppa_terse_wrapped", False ):
        return
    if isinstance( original, Progress ) or isinstance( original, _TersePythonCallable ):
        return
    action.execfunction = _TersePythonCallable( original )
    action._cuppa_terse_wrapped = True


def _wrap_builder( builder ):
    try:
        action = getattr( builder, "action", None )
    except Exception:
        return
    _wrap_action( action )


def _wrap_nodes( nodes ):
    for node in _iter_nodes( nodes ):
        executor = getattr( node, "executor", None )
        if executor is None:
            continue
        getter = getattr( executor, "get_action_list", None )
        actions = getter() if callable( getter ) else ()
        for action in actions:
            _wrap_action( action )


def _wrap_factory( env, name, after ):
    current = getattr( env, name, None )
    if current is None or getattr( current, "_cuppa_terse_factory", False ):
        return

    def factory( *args, **kwargs ):
        result = current( *args, **kwargs )
        after( result )
        return result

    factory._cuppa_terse_factory = True
    setattr( env, name, factory )


def enable_terse_python_actions( env ):
    """Give Python actions a terse status line. No effect unless ``--terse-output``."""
    if not _env_get( env, "terse_output" ):
        return
    if getattr( env, "_cuppa_terse_python_actions", False ):
        return
    try:
        env._cuppa_terse_python_actions = True
    except Exception:
        return
    builders = _env_get( env, "BUILDERS" ) or {}
    try:
        values = builders.values()
    except AttributeError:
        values = ()
    for builder in values:
        _wrap_builder( builder )
    _wrap_factory( env, "Builder", _wrap_builder )
    _wrap_factory( env, "Command", _wrap_nodes )
    # SCons keeps one process-wide install action. Wrapping ``env.Install``
    # reaches it. The printed ``Install file:`` line is then a ``copy`` status.
    for name in ( "Install", "InstallAs", "InstallVersionedLib" ):
        _wrap_factory( env, name, _wrap_nodes )




