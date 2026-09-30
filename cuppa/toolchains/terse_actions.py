#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   Terse action words for toolchain tools
#-------------------------------------------------------------------------------

"""Verbs for a compiler, archiver, indexer, or linker command.

Gcc and Clang share this speller: ``gcc-ar-16`` and ``llvm-ranlib`` are the
same kinds of tool. ``cl`` uses it too (``cl``, ``lib``, ``link``). A toolchain
``spell_terse_action`` calls ``spell_tool_command`` and may override it.
An empty return means the command is not one of these tools.
"""

import os.path


_OBJECT_SUFFIXES = ( ".o", ".obj", ".os" )
_ARCHIVE_SUFFIXES = ( ".a", ".lib" )
_SHARED_SUFFIXES = ( ".so", ".dll", ".dylib" )
_GCC_DRIVERS = ( "g++", "gcc", "clang++", "clang", "c++", "cc" )


def command_tokens( command ):
    if not command:
        return []
    return str( command ).replace( "\n", " " ).split()


def tool_basename( command ):
    """Executable name, without a directory or a trailing ``.exe``."""
    tokens = command_tokens( command )
    if not tokens:
        return ""
    tool = os.path.basename( tokens[0].strip( "'\"" ) )
    if tool.lower().endswith( ".exe" ):
        tool = tool[:-4]
    return tool.lower()


def _target_name( target ):
    node = target[0] if isinstance( target, ( list, tuple ) ) and target else target
    if node is None:
        return ""
    path = getattr( node, "path", None )
    text = str( path if path else node ).replace( "\\", "/" )
    return os.path.basename( text ).lower()


def _is_archiver( tool ):
    """``ar``, ``lib``, ``gcc-ar``, ``gcc-ar-16``, ``llvm-ar``."""
    if tool in ( "ar", "lib" ):
        return True
    return tool.endswith( "-ar" ) or "-ar-" in tool


def _is_gcc_driver( tool ):
    """``g++``, ``g++-16``, ``clang++``. Not ``gcc-ar-16`` (that is an archiver)."""
    for name in _GCC_DRIVERS:
        if tool == name or tool.startswith( name + "-" ):
            return True
    return False


def _is_msvc_driver( tool ):
    return tool in ( "cl", "link" )


def spell_tool_command( command, target ):
    """``compile`` / ``archive`` / ``index`` / ``link`` / ``link-shared``, or empty."""
    text = str( command or "" ).lstrip().lower()
    # SCons prints these instead of a tool command. They are copies.
    if text.startswith( "install file:" ) or text.startswith( "install directory:" ):
        return "copy"
    if text.startswith( "copy(" ):
        return "copy"
    if text.startswith( "move(" ):
        return "move"
    tool = tool_basename( command )
    if not tool:
        return ""
    if tool in ( "asciidoctor", "asciidoctor-pdf" ):
        return "asciidoc"
    # Versioned indexers (``gcc-ranlib-16``) must win over the ``.a`` suffix.
    if "ranlib" in tool:
        return "index"
    tokens = [ token.lower() for token in command_tokens( command ) ]
    name = _target_name( target )
    if "-c" in tokens or "/c" in tokens:
        return "compile"
    if name.endswith( _SHARED_SUFFIXES ) or ".so." in name or "-shared" in tokens or "/dll" in tokens:
        return "link-shared"
    if _is_archiver( tool ) or name.endswith( _ARCHIVE_SUFFIXES ):
        return "archive"
    if name.endswith( _OBJECT_SUFFIXES ):
        return "compile"
    if _is_gcc_driver( tool ) or _is_msvc_driver( tool ):
        return "link"
    return ""
