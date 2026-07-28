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


def header_bmi_path( env, header_path, extension ):
    label = header_path
    base = env.get( 'sconscript_dir' ) or env.get( 'base_path' )
    if base:
        try:
            label = os.path.relpath( header_path, base )
        except ValueError:
            label = os.path.basename( header_path )
    # Keep labels stable and short when given an absolute path outside the project
    if os.path.isabs( label ):
        label = os.path.basename( header_path )
    return os.path.join(
        modules_build_dir( env ),
        sanitize_header_filename( label ) + extension,
    )


def mapper_path( env ):
    return os.path.join( modules_build_dir( env ), 'module-mapper.txt' )


def write_gcc_module_mapper( env ):
    """Write a GCC module mapper covering registered named modules and header units."""
    from cuppa.cpp.cxx_modules import get_registry

    registry = get_registry( env )
    root = modules_build_dir( env )
    base = env.get( 'sconscript_dir' ) or env.get( 'base_path' )
    lines = [ '$root {}'.format( root ) ]

    for name, entry in sorted( registry['named'].items() ):
        bmi = os.path.abspath( entry['path'] )
        if bmi.startswith( root + os.sep ):
            rel = os.path.relpath( bmi, root )
            lines.append( '{} {}'.format( name, rel ) )
        else:
            lines.append( '{} {}'.format( name, bmi ) )

    seen_bmis = set()
    for key, entry in registry['headers'].items():
        header = entry.get( 'header', key )
        bmi = os.path.abspath( entry['path'] )
        if bmi in seen_bmis:
            continue
        seen_bmis.add( bmi )
        if bmi.startswith( root + os.sep ):
            rel = os.path.relpath( bmi, root )
        else:
            rel = bmi

        candidates = set()
        for candidate in ( header, key, entry.get( 'header' ) ):
            if not candidate:
                continue
            candidates.add( candidate )
            candidates.add( os.path.basename( candidate ) )
            candidates.add( './' + os.path.basename( candidate ) )
            normalised = candidate.replace( '\\', '/' )
            candidates.add( normalised )
            candidates.add( './' + normalised.lstrip( './' ) )
            if base:
                try:
                    rel_header = os.path.relpath( candidate, base ).replace( '\\', '/' )
                    candidates.add( rel_header )
                    candidates.add( './' + rel_header.lstrip( './' ) )
                except ValueError:
                    pass

        for candidate in sorted( c for c in candidates if c ):
            lines.append( '{} {}'.format( candidate, rel ) )

    path = mapper_path( env )
    with open( path, 'w' ) as handle:
        handle.write( '\n'.join( lines ) + '\n' )
    return path
