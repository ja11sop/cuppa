#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   C++20 modules compile helpers (named modules + header units)
#-------------------------------------------------------------------------------

import os

from SCons.Node import Node
from SCons.Script import Flatten

import cuppa.progress
from cuppa.colourise import as_error, as_info, as_notice, as_warning
from cuppa.cpp.module_scanner import ModuleScan, is_interface_source, scan_file
from cuppa.log import logger


REGISTRY_KEY = '_cuppa_module_registry'


def get_registry( env ):
    registry = env.get( REGISTRY_KEY )
    if registry is None:
        registry = {
            'named': {},
            'headers': {},
        }
        env[ REGISTRY_KEY ] = registry
    return registry


def modules_dir( env ):
    from cuppa.toolchains.cxx_modules_support import modules_build_dir
    return modules_build_dir( env )


def object_target_for( env, source, obj_prefix, obj_suffix ):
    target = os.path.splitext( os.path.split( str( source ) )[1] )[0]
    if not source.path.startswith( env['build_root'] ):
        if os.path.isabs( str( source ) ):
            return env.File( os.path.join( obj_prefix + target + obj_suffix ) )
        return env.File( os.path.join( env['build_dir'], obj_prefix + target + obj_suffix ) )
    offset_dir = os.path.relpath( os.path.split( source.path )[0], env['build_dir'] )
    return env.File( os.path.join( offset_dir, obj_prefix + target + obj_suffix ) )


def _source_abspath( source ):
    """Prefer the real source node path (not a VariantDir build mirror)."""
    try:
        src = source.srcnode()
        path = src.get_abspath() if hasattr( src, 'get_abspath' ) else str( src )
        if path and os.path.exists( path ):
            return path
    except Exception:
        pass
    if hasattr( source, 'get_abspath' ):
        path = source.get_abspath()
        if path and os.path.exists( path ):
            return path
    return str( source )


def _scan_source( source ):
    path = _source_abspath( source )
    try:
        return scan_file( path )
    except Exception as exc:
        logger.warn(
            "Could not scan [{}] for modules: {}"
            .format( as_warning( path ), as_warning( str( exc ) ) )
        )
        return ModuleScan( None, None, [] )


def lookup_header_entry( registry, name ):
    headers = registry['headers']
    if name in headers:
        return headers[name]
    basename = os.path.basename( name )
    if basename in headers:
        return headers[basename]
    normalised = name.replace( '\\', '/' )
    for key, entry in headers.items():
        key_norm = key.replace( '\\', '/' )
        if key_norm.endswith( normalised ) or normalised.endswith( key_norm ):
            return entry
    return None


def resolve_import_nodes( env, imports ):
    registry = get_registry( env )
    nodes = []
    missing = []
    for item in imports:
        if item.kind == 'named':
            entry = registry['named'].get( item.name )
            if entry:
                nodes.append( entry['bmi'] )
            else:
                missing.append( item.name )
        else:
            entry = lookup_header_entry( registry, item.name )
            if entry:
                nodes.append( entry['bmi'] )
            else:
                missing.append( item.name )
    return nodes, missing


def register_named_module( env, module_name, bmi_path, bmi_node ):
    registry = get_registry( env )
    registry['named'][module_name] = {
        'bmi': bmi_node,
        'path': bmi_path,
    }
    toolchain = env['toolchain']
    if hasattr( toolchain, 'write_module_mapper' ):
        toolchain.write_module_mapper( env )


def register_header_unit( env, header_path, bmi_path, bmi_node ):
    registry = get_registry( env )
    entry = {
        'bmi': bmi_node,
        'path': bmi_path,
        'header': header_path,
    }
    keys = {
        header_path,
        os.path.basename( header_path ),
        header_path.replace( '\\', '/' ),
    }
    if 'sconscript_dir' in env:
        try:
            rel = os.path.relpath( header_path, env['sconscript_dir'] )
            keys.add( rel )
            keys.add( rel.replace( '\\', '/' ) )
        except ValueError:
            pass
    for key in keys:
        if key:
            registry['headers'][key] = entry
    toolchain = env['toolchain']
    if hasattr( toolchain, 'write_module_mapper' ):
        toolchain.write_module_mapper( env )


def ensure_modules_enabled( env ):
    if not env.get( 'modules' ):
        logger.error(
            "C++ modules support requires {} (or env['modules']=True)"
            .format( as_error( '--modules' ) )
        )
        return False
    toolchain = env['toolchain']
    if not toolchain.supports_modules( env ):
        logger.error(
            "Toolchain [{}] does not support C++ modules in this cuppa build"
            .format( as_error( toolchain.name() ) )
        )
        return False
    return True


def compile_with_modules( env, sources, obj_builder, obj_prefix, obj_suffix, dependencies, kwargs ):
    if not ensure_modules_enabled( env ):
        return []

    toolchain = env['toolchain']
    modules_dir( env )
    get_registry( env )

    classified = []
    for source in Flatten( [ sources ] ):
        if not isinstance( source, Node ):
            source = env.File( source )
        if os.path.splitext( str( source ) )[1] == obj_suffix:
            classified.append( ( 'object', source, None ) )
            continue
        scan = _scan_source( source )
        if is_interface_source( str( source ), scan ):
            classified.append( ( 'interface', source, scan ) )
        else:
            classified.append( ( 'tu', source, scan ) )

    objects = []

    def _build_one( source, scan, extra_flags, is_interface=False ):
        if dependencies:
            env.Depends( source, Flatten( [ dependencies ] ) )

        target = object_target_for( env, source, obj_prefix, obj_suffix )
        build_kwargs = dict( kwargs )
        build_kwargs['CPPPATH'] = env['SYSINCPATH'] + env['INCPATH']

        imported_nodes, missing = resolve_import_nodes( env, scan.imports if scan else [] )
        if missing:
            logger.warn(
                "Module imports not yet registered for [{}]: {}"
                .format( as_notice( str( source ) ), as_warning( ', '.join( missing ) ) )
            )

        module_name = None
        bmi_path = None
        bmi_node = None
        if is_interface:
            if scan and scan.export_module:
                module_name = scan.export_module
            else:
                module_name = os.path.splitext( os.path.basename( str( source ) ) )[0]
            bmi_path = toolchain.module_bmi_path( env, module_name )
            bmi_node = env.File( bmi_path )
            # GCC module mapper must list the module before the interface is compiled
            register_named_module( env, module_name, bmi_path, bmi_node )
            build_kwargs['CXXFLAGS'] = list( env.get( 'CXXFLAGS', [] ) ) + list(
                toolchain.interface_module_flags( env, module_name, bmi_path )
            )
        else:
            build_kwargs['CXXFLAGS'] = list( env.get( 'CXXFLAGS', [] ) ) + list( extra_flags )

        obj = obj_builder( target=target, source=source, **build_kwargs )
        obj_nodes = Flatten( [ obj ] )

        if imported_nodes:
            for node in obj_nodes:
                env.Depends( node, imported_nodes )

        if module_name:
            for node in obj_nodes:
                env.SideEffect( bmi_path, node )
                env.Depends( bmi_node, node )
            logger.debug(
                "Registered module [{}] BMI [{}]"
                .format( as_info( module_name ), as_notice( bmi_path ) )
            )

        if not is_interface and scan and scan.module_declaration:
            entry = get_registry( env )['named'].get( scan.module_declaration )
            if entry:
                for node in obj_nodes:
                    env.Depends( node, entry['bmi'] )

        return obj_nodes

    for kind, source, scan in classified:
        if kind == 'object':
            objects.append( source )
        elif kind == 'interface':
            objects.extend( _build_one( source, scan, [], is_interface=True ) )

    for kind, source, scan in classified:
        if kind != 'tu':
            continue
        consume_flags = toolchain.consume_module_flags( env, scan )
        objects.extend( _build_one( source, scan, consume_flags, is_interface=False ) )

    cuppa.progress.NotifyProgress.add( env, objects )
    return objects


def build_header_unit( env, header, **kwargs ):
    if not ensure_modules_enabled( env ):
        return None

    toolchain = env['toolchain']
    declared = None
    if not isinstance( header, Node ):
        declared = str( header )
        header = env.File( header )
    else:
        try:
            src = header.srcnode()
            declared = os.path.relpath(
                src.get_abspath(),
                env.get( 'sconscript_dir' ) or os.getcwd(),
            )
        except Exception:
            declared = str( header )

    modules_dir( env )
    header_path = _source_abspath( header )
    # Prefer the user-declared spelling so BMI names stay project-relative
    # (VariantDir abspaths would otherwise embed _build/.../working/...).
    from cuppa.toolchains.cxx_modules_support import header_unit_label
    label = header_unit_label( env, declared or header_path )
    bmi_path = toolchain.header_unit_bmi_path( env, label )
    bmi_node = toolchain.build_header_unit( env, header, bmi_path, declared=label, **kwargs )
    register_header_unit( env, header_path, bmi_path, bmi_node )
    register_header_unit( env, str( header ), bmi_path, bmi_node )
    if label:
        register_header_unit( env, label, bmi_path, bmi_node )
        register_header_unit( env, label.replace( '\\', '/' ), bmi_path, bmi_node )
        register_header_unit(
            env,
            './' + label.replace( '\\', '/' ).lstrip( './' ),
            bmi_path,
            bmi_node,
        )
    cuppa.progress.NotifyProgress.add( env, bmi_node )
    logger.debug(
        "Registered header unit [{}] BMI [{}]"
        .format( as_info( label or str( header ) ), as_notice( bmi_path ) )
    )
    return bmi_node
