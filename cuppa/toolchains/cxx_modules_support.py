#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   Shared helpers for GCC/Clang C++ modules BMI paths and mappers
#-------------------------------------------------------------------------------

import os

from cuppa.cpp.module_scanner import sanitize_header_filename, sanitize_module_filename


def effective_build_dir( env ):
    """Prefer abs_build_dir so BMI/mapper paths stay stable regardless of cwd."""
    path = env.get( 'abs_build_dir' ) or env['build_dir']
    return os.path.abspath( path )


def modules_build_dir( env ):
    path = os.path.join( effective_build_dir( env ), 'modules' )
    if not os.path.isdir( path ):
        try:
            os.makedirs( path )
        except OSError:
            if not os.path.isdir( path ):
                raise
    return path


def named_bmi_path( env, module_name, extension ):
    return os.path.join(
        modules_build_dir( env ),
        sanitize_module_filename( module_name ) + extension,
    )


def _strip_prefix_path( path, prefix ):
    if not path or not prefix:
        return None
    try:
        rel = os.path.relpath( os.path.normpath( path ), os.path.normpath( prefix ) )
    except ValueError:
        return None
    if rel == os.curdir:
        return ''
    if rel.startswith( '..' ):
        return None
    return rel


def header_unit_label( env, header_path ):
    """
    Stable project-relative label for header-unit BMI names / mapper keys.

    Trust already-relative declarations (e.g. include/widget.hpp). Absolute or
    VariantDir paths are stripped back to the same form so GCC sees the spelling
    used on the compile line rather than _build/.../working/... .
    """
    if not header_path:
        return 'header'

    path = os.path.normpath( str( header_path ) )
    build_dir = env.get( 'build_dir' )
    abs_build = env.get( 'abs_build_dir' )
    sconscript_dir = env.get( 'sconscript_dir' ) or env.get( 'base_path' )

    if os.path.isabs( path ):
        for prefix in ( abs_build, build_dir, sconscript_dir ):
            stripped = _strip_prefix_path( path, prefix )
            if stripped is not None:
                path = stripped
                break
    elif build_dir:
        # Relative path under the variant dir (not a user declaration)
        stripped = _strip_prefix_path( path, build_dir )
        if stripped is not None:
            path = stripped

    if os.path.isabs( path ):
        path = os.path.basename( path )

    label = path.replace( '\\', '/' ).lstrip( './' )
    # Fallback if a VariantDir-relative path slipped through
    parts = label.split( '/' )
    if parts and parts[0] == '_build' and 'working' in parts:
        idx = parts.index( 'working' )
        rest = '/'.join( parts[idx + 1:] )
        if rest:
            label = rest
    return label or os.path.basename( str( header_path ) )


def header_bmi_path( env, header_path, extension ):
    label = header_unit_label( env, header_path )
    return os.path.join(
        modules_build_dir( env ),
        sanitize_header_filename( label ) + extension,
    )


def mapper_path( env ):
    return os.path.join( modules_build_dir( env ), 'module-mapper.txt' )


def register_mapper_for_clean( env, bmi_node ):
    """Ensure the GCC module mapper is removed by scons --clean / -c."""
    if bmi_node is None:
        return
    try:
        env.Clean( bmi_node, mapper_path( env ) )
    except Exception:
        pass


def _header_mapper_candidates( env, names ):
    """Expand header spellings GCC might look up in the module mapper."""
    base = env.get( 'sconscript_dir' ) or env.get( 'base_path' )
    candidates = set()
    for name in names:
        if not name:
            continue
        label = header_unit_label( env, name )
        for candidate in ( name, label ):
            if not candidate:
                continue
            candidates.add( candidate )
            candidates.add( os.path.basename( candidate ) )
            normalised = candidate.replace( '\\', '/' )
            candidates.add( normalised )
            if not os.path.isabs( candidate ):
                candidates.add( './' + normalised.lstrip( './' ) )
            if label:
                candidates.add( label )
                candidates.add( './' + label.lstrip( './' ) )
            if base and os.path.isabs( str( candidate ) ):
                try:
                    rel_header = os.path.relpath( candidate, base ).replace( '\\', '/' )
                    if not rel_header.startswith( '..' ):
                        candidates.add( rel_header )
                        candidates.add( './' + rel_header.lstrip( './' ) )
                except ValueError:
                    pass
    return candidates


def write_gcc_module_mapper( env ):
    """Write a GCC module mapper covering registered named modules and header units."""
    from cuppa.cpp.cxx_modules import get_registry

    path = mapper_path( env )
    # Avoid recreating the mapper during a clean run; Clean targets remove the
    # previous build's copy once BMI nodes are registered with env.Clean.
    if env.get( 'clean' ):
        return path

    registry = get_registry( env )
    root = modules_build_dir( env )
    lines = [ '$root {}'.format( root ) ]

    for name, entry in sorted( registry['named'].items() ):
        bmi = os.path.abspath( entry['path'] )
        if bmi.startswith( root + os.sep ):
            rel = os.path.relpath( bmi, root )
            lines.append( '{} {}'.format( name, rel ) )
        else:
            lines.append( '{} {}'.format( name, bmi ) )

    # Union all registry keys / header spellings per BMI. Using only the first
    # dict entry is flaky (set insertion order) and often drops the compile-line
    # spelling include/foo.hpp in favour of a VariantDir path.
    by_bmi = {}
    for key, entry in registry['headers'].items():
        bmi = os.path.abspath( entry['path'] )
        group = by_bmi.setdefault( bmi, set() )
        group.add( key )
        header = entry.get( 'header' )
        if header:
            group.add( header )

    for bmi, names in sorted( by_bmi.items() ):
        if bmi.startswith( root + os.sep ):
            rel = os.path.relpath( bmi, root )
        else:
            rel = bmi
        for candidate in sorted( c for c in _header_mapper_candidates( env, names ) if c ):
            lines.append( '{} {}'.format( candidate, rel ) )

    with open( path, 'w' ) as handle:
        handle.write( '\n'.join( lines ) + '\n' )
    return path
