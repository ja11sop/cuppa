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
# name for named may be "mod", "mod:part", or ":part" (relative partition)

ModuleScan = namedtuple(
    'ModuleScan',
    [ 'export_module', 'module_declaration', 'imports', 'private_fragment' ]
)


# Primary / partition names: foo, foo.bar, foo:part — not ":private" (handled separately)
_MODULE_ID = r'[A-Za-z_][\w.]*(?::[A-Za-z_][\w.]*)?'
_RELATIVE_PARTITION = r':[A-Za-z_][\w.]*'

_PRIVATE_FRAGMENT_RE = re.compile( r'^\s*module\s+:private\s*;' )
_EXPORT_MODULE_RE = re.compile(
    r'^\s*export\s+module\s+({id})\s*;'.format( id=_MODULE_ID )
)
_MODULE_RE = re.compile(
    r'^\s*module\s+({id})\s*;'.format( id=_MODULE_ID )
)
_IMPORT_NAMED_RE = re.compile(
    r'^\s*(?:export\s+)?import\s+({id}|{rel})\s*;'.format(
        id=_MODULE_ID, rel=_RELATIVE_PARTITION
    )
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
    private_fragment = False
    imports = []

    for raw_line in cleaned.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        if _PRIVATE_FRAGMENT_RE.match( line ):
            private_fragment = True
            continue

        match = _EXPORT_MODULE_RE.match( line )
        if match:
            export_module = match.group( 1 )
            continue

        match = _MODULE_RE.match( line )
        if match:
            name = match.group( 1 )
            if module_declaration is None and export_module is None:
                module_declaration = name
            elif export_module is None:
                module_declaration = name
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

    return ModuleScan( export_module, module_declaration, imports, private_fragment )


def scan_file( path ):
    with open( path, 'r' ) as handle:
        return scan_source_text( handle.read() )


def primary_module_name( module_name ):
    """geo:point -> geo; geo -> geo; :point -> None."""
    if not module_name:
        return None
    if module_name.startswith( ':' ):
        return None
    return module_name.split( ':', 1 )[0]


def qualify_relative_import( name, owning_module ):
    """Turn `:part` into `owning_primary:part` when an owning module is known."""
    if not name or not name.startswith( ':' ):
        return name
    primary = primary_module_name( owning_module )
    if not primary:
        return name
    return primary + name


def owning_module_name( scan ):
    if not scan:
        return None
    return scan.export_module or scan.module_declaration


def module_bmi_name( scan ):
    """
    Module name that produces a BMI for this translation unit, if any.

    - `export module M` / `export module M:part` → BMI M / M:part
    - `module M:part` (implementation partition) → BMI M:part
    - `module M` (implementation unit) → no BMI of its own
    - `module :private` → handled separately; not a BMI name
    """
    if not scan:
        return None
    if scan.export_module:
        return scan.export_module
    decl = scan.module_declaration
    if decl and ':' in decl:
        return decl
    return None


def is_interface_source( path, scan=None ):
    suffix = os.path.splitext( path )[1].lower()
    if suffix in INTERFACE_SUFFIXES:
        return True
    if scan is None:
        return False
    return bool( scan.export_module )


def sanitize_module_filename( name ):
    return name.replace( ':', '--' ).replace( '.', '--' )


def sanitize_header_filename( header_path ):
    normalised = str( header_path ).replace( '\\', '/' ).lstrip( './' )
    if normalised.startswith( '<' ) and normalised.endswith( '>' ):
        normalised = 'angle--' + normalised[1:-1]
    return 'header--' + normalised.replace( '/', '--' ).replace( ' ', '_' ).replace( '<', '' ).replace( '>', '' )


def parse_header_unit_declaration( header ):
    """
    Return (kind, name, declared) for a HeaderUnit argument.

    kind is 'angle' for '<span>' or 'quoted' for project paths / "hdr".
    name is the lookup key used by import <name> / import "name".
    declared is the canonical spelling stored in the registry.
    """
    text = str( header ).strip()
    if len( text ) >= 2 and text.startswith( '<' ) and text.endswith( '>' ):
        inner = text[1:-1].strip()
        return 'angle', inner, '<' + inner + '>'
    if len( text ) >= 2 and text[0] == '"' and text[-1] == '"':
        inner = text[1:-1]
        return 'quoted', inner, inner
    return 'quoted', text, text


def std_module_imports_from_scan( scan ):
    """Return the set of standard library module names imported by scan."""
    if not scan:
        return set()
    found = set()
    for item in scan.imports:
        if item.kind == 'named' and item.name in ( 'std', 'std.compat' ):
            found.add( item.name )
    return found
