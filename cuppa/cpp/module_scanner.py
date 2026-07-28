#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   Lightweight C++20 modules import / export scanner
#-------------------------------------------------------------------------------

from collections import namedtuple
import os
import re


ModuleImport = namedtuple( 'ModuleImport', [ 'kind', 'name' ] )
# kind: 'named' | 'header_quoted' | 'header_angle'

ModuleScan = namedtuple(
    'ModuleScan',
    [ 'export_module', 'module_declaration', 'imports' ]
)


_EXPORT_MODULE_RE = re.compile(
    r'^\s*export\s+module\s+([A-Za-z_][\w.]*)\s*;'
)
_MODULE_RE = re.compile(
    r'^\s*module\s+([A-Za-z_][\w.]*)\s*;'
)
_IMPORT_NAMED_RE = re.compile(
    r'^\s*(?:export\s+)?import\s+([A-Za-z_][\w.]*)\s*;'
)
_IMPORT_QUOTED_RE = re.compile(
    r'^\s*(?:export\s+)?import\s+"([^"]+)"\s*;'
)
_IMPORT_ANGLE_RE = re.compile(
    r'^\s*(?:export\s+)?import\s+<([^>]+)>\s*;'
)


INTERFACE_SUFFIXES = ( '.cppm', '.cxxm', '.ccm' )


def strip_comments( text ):
    """Remove // line and /* */ block comments (string-literal unaware)."""
    out = []
    i = 0
    n = len( text )
    while i < n:
        if text[i:i+2] == '//':
            while i < n and text[i] != '\n':
                i += 1
            continue
        if text[i:i+2] == '/*':
            i += 2
            while i + 1 < n and text[i:i+2] != '*/':
                i += 1
            i = min( i + 2, n )
            continue
        out.append( text[i] )
        i += 1
    return ''.join( out )


def scan_source_text( text ):
    cleaned = strip_comments( text )
    export_module = None
    module_declaration = None
    imports = []

    for raw_line in cleaned.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        match = _EXPORT_MODULE_RE.match( line )
        if match:
            export_module = match.group( 1 )
            continue

        match = _MODULE_RE.match( line )
        if match:
            if module_declaration is None and export_module is None:
                module_declaration = match.group( 1 )
            elif export_module is None:
                module_declaration = match.group( 1 )
            continue

        match = _IMPORT_QUOTED_RE.match( line )
        if match:
            imports.append( ModuleImport( 'header_quoted', match.group( 1 ) ) )
            continue

        match = _IMPORT_ANGLE_RE.match( line )
        if match:
            imports.append( ModuleImport( 'header_angle', match.group( 1 ) ) )
            continue

        match = _IMPORT_NAMED_RE.match( line )
        if match:
            imports.append( ModuleImport( 'named', match.group( 1 ) ) )
            continue

    return ModuleScan( export_module, module_declaration, imports )


def scan_file( path ):
    with open( path, 'r' ) as handle:
        return scan_source_text( handle.read() )


def is_interface_source( path, scan=None ):
    suffix = os.path.splitext( path )[1].lower()
    if suffix in INTERFACE_SUFFIXES:
        return True
    if scan is None:
        return False
    return bool( scan.export_module )


def sanitize_module_filename( name ):
    return name.replace( '.', '--' )


def sanitize_header_filename( header_path ):
    normalised = header_path.replace( '\\', '/' ).lstrip( './' )
    return 'header--' + normalised.replace( '/', '--' ).replace( ' ', '_' )
