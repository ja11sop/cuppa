#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

"""Rewrite installed pkg-config files so they follow the extract.

Upstream CMake records the install prefix as an absolute path. After
``cmake --install``, :func:`relocate_pkgconfig` turns paths under that prefix
into ``${pcfiledir}`` / ``${prefix}`` references. A file whose ``prefix`` is
already ``${pcfiledir}/...`` is left alone.

See ``design/plans/package-public-defines.md``.
"""

from __future__ import annotations

import os
import re

from cuppa.log import logger


_ASSIGN = re.compile( r"^([A-Za-z_][A-Za-z0-9_]*)=(.*)\Z" )
_ABS_PATH = re.compile( r"/[^\s\"']+" )
_CACHE_PREFIX = re.compile(
        r"^CMAKE_INSTALL_PREFIX:[A-Za-z_]*=(.*)\Z",
        re.MULTILINE,
)


def _norm( path: str ) -> str:
    return os.path.normpath( os.path.abspath( path ) )


def _within( path: str, root: str ) -> bool:
    path = _norm( path )
    root = _norm( root )
    return path == root or path.startswith( root + os.sep )


def _slash_rel( path: str, root: str ) -> str:
    rel = os.path.relpath( _norm( path ), _norm( root ) )
    return rel.replace( os.sep, "/" )


def _pcfiledir_ref( install_prefix: str, pc_dir: str ) -> str:
    rel = _slash_rel( install_prefix, pc_dir )
    if rel == ".":
        return "${pcfiledir}"
    return "${pcfiledir}/" + rel


def _prefix_ref( path: str, install_prefix: str ) -> str | None:
    """``${prefix}`` or ``${prefix}/rest`` when ``path`` is under the prefix."""
    if not path or not os.path.isabs( path ):
        return None
    if not _within( path, install_prefix ):
        return None
    if _norm( path ) == _norm( install_prefix ):
        return "${prefix}"
    return "${prefix}/" + _slash_rel( path, install_prefix )


def _unquote( value: str ) -> str:
    text = value.strip()
    if len( text ) >= 2 and text[0] == text[-1] and text[0] in "\"'":
        return text[1:-1]
    return text


def _rewrite_inline( text: str, install_prefix: str ) -> str:
    matches = list( _ABS_PATH.finditer( text ) )
    if not matches:
        return text
    pieces = []
    last = 0
    for match in matches:
        token = match.group( 0 )
        # Drop a trailing punctuation that a greedy scan can swallow.
        suffix = ""
        while token.endswith( ( ",", ";", ")" ) ):
            suffix = token[-1] + suffix
            token = token[:-1]
        replacement = _prefix_ref( token, install_prefix )
        pieces.append( text[last:match.start()] )
        if replacement is None:
            pieces.append( match.group( 0 ) )
        else:
            pieces.append( replacement + suffix )
        last = match.end()
    pieces.append( text[last:] )
    return "".join( pieces )


def _rewrite_value( key: str, value: str, install_prefix: str, pc_ref: str ) -> str:
    raw = _unquote( value )
    if key == "prefix":
        if raw.startswith( "${pcfiledir}" ):
            return raw
        if os.path.isabs( raw ) and _within( raw, install_prefix ):
            return pc_ref
        return raw
    if raw.startswith( "${" ) and _ABS_PATH.search( raw ) is None:
        return raw
    if os.path.isabs( raw ) and " " not in raw:
        mapped = _prefix_ref( raw, install_prefix )
        if mapped is not None:
            return mapped
        return raw
    return _rewrite_inline( raw, install_prefix )


def rewrite_pc_text( text: str, install_prefix: str, pc_dir: str ) -> str:
    """Return ``text`` with absolute install paths made ``${pcfiledir}``-relative.

    Unchanged when ``prefix`` already uses ``${pcfiledir}``, or when nothing
    under ``install_prefix`` is absolute.
    """
    if text is None:
        return text
    for line in text.splitlines():
        matched = _ASSIGN.match( line.strip() )
        if matched and matched.group( 1 ) == "prefix" and "${pcfiledir}" in matched.group( 2 ):
            return text

    pc_ref = _pcfiledir_ref( install_prefix, pc_dir )
    has_prefix = False
    changed = False
    rewritten = []
    newline = "\r\n" if "\r\n" in text else "\n"
    ends_with_newline = text.endswith( ( "\n", "\r" ) )
    lines = text.splitlines()
    for line in lines:
        matched = _ASSIGN.match( line.strip() )
        if matched is None or line.strip().startswith( "#" ):
            updated = _rewrite_inline( line, install_prefix )
            if updated != line:
                changed = True
            rewritten.append( updated )
            continue
        key = matched.group( 1 )
        value = matched.group( 2 ).strip()
        if key == "prefix":
            has_prefix = True
        new_value = _rewrite_value( key, value, install_prefix, pc_ref )
        if new_value != value:
            changed = True
            rewritten.append( "{}={}".format( key, new_value ) )
        else:
            rewritten.append( line )

    if not has_prefix and changed:
        rewritten.insert( 0, "prefix={}".format( pc_ref ) )
    if not changed:
        return text
    body = newline.join( rewritten )
    if ends_with_newline:
        body += newline
    return body


def relocate_pkgconfig( prefix: str ) -> list[str]:
    """Rewrite ``*.pc`` under ``prefix``. Returns paths that changed.

    Relative to ``prefix``, forward slashes. A second call returns an empty
    list.
    """
    if not prefix or not os.path.isdir( prefix ):
        return []
    root = _norm( prefix )
    changed = []
    for dirpath, dirnames, filenames in os.walk( root ):
        dirnames[:] = [ name for name in dirnames if name != ".git" ]
        for filename in sorted( filenames ):
            if not filename.endswith( ".pc" ):
                continue
            path = os.path.join( dirpath, filename )
            try:
                with open( path, encoding="utf-8", errors="replace" ) as handle:
                    original = handle.read()
            except OSError:
                continue
            updated = rewrite_pc_text( original, root, dirpath )
            if updated == original:
                continue
            with open( path, "w", encoding="utf-8" ) as handle:
                handle.write( updated )
            rel = os.path.relpath( path, root ).replace( os.sep, "/" )
            changed.append( rel )
    if changed:
        logger.info(
                "Rewrote pkg-config prefix in [{}] ({})".format(
                        root, ", ".join( changed ),
                )
        )
    return changed


def cmake_cache_install_prefix( build_dir: str ) -> str | None:
    """``CMAKE_INSTALL_PREFIX`` from ``CMakeCache.txt``, or ``None``."""
    if not build_dir:
        return None
    cache = os.path.join( build_dir, "CMakeCache.txt" )
    try:
        with open( cache, encoding="utf-8", errors="replace" ) as handle:
            text = handle.read()
    except OSError:
        return None
    matched = _CACHE_PREFIX.search( text )
    if not matched:
        return None
    value = matched.group( 1 ).strip()
    return value or None


def prefix_in_package_tree( env, prefix: str ) -> bool:
    """True when ``prefix`` sits inside this package's build or final tree.

    A system dest such as ``/usr`` is outside those trees and is not rewritten.
    """
    if not prefix:
        return False
    roots = []
    for key in ( "sconstruct_dir", "abs_final_dir", "abs_build_dir" ):
        try:
            value = env[key]
        except Exception:
            value = None
        if value:
            roots.append( str( value ) )
    return any( _within( prefix, root ) for root in roots )


def relocate_cmake_install( env, build_dir: str ) -> list[str]:
    """Rewrite ``*.pc`` for the prefix recorded in this CMake build.

    No-op when the cache has no prefix, or the prefix is outside the package
    tree. Used by ``env.CMakeInstall`` after ``cmake --install``.
    """
    prefix = cmake_cache_install_prefix( build_dir )
    if not prefix or not prefix_in_package_tree( env, prefix ):
        return []
    return relocate_pkgconfig( prefix )
