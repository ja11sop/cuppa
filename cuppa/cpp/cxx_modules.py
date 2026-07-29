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
from cuppa.cpp.module_scanner import (
    ModuleScan,
    is_interface_source,
    module_bmi_name,
    owning_module_name,
    parse_header_unit_declaration,
    qualify_relative_import,
    sanitize_module_filename,
    scan_file,
    std_module_imports_from_scan,
)
from cuppa.log import logger
import SCons.Errors
import json
import shutil


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
    """
    Map a source to its object node.

    Module interface suffixes (.cppm / .cxxm / .ccm) keep the extension in the
    object stem (e.g. calc.cppm → calc.cppm.o) so they do not collide with a
    same-basename implementation unit (calc.cpp → calc.o).
    """
    from cuppa.cpp.module_scanner import INTERFACE_SUFFIXES

    basename = os.path.split( str( source ) )[1]
    stem, ext = os.path.splitext( basename )
    if ext.lower() in INTERFACE_SUFFIXES:
        target = basename  # keep "calc.cppm" so object is calc.cppm.o
    else:
        target = stem
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
        return ModuleScan( None, None, [], False )


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


def named_import_names( scan ):
    """Qualified named-module import names for registry / transitive BMI flags."""
    if not scan:
        return []
    owner = owning_module_name( scan )
    names = []
    for item in scan.imports:
        if item.kind != 'named':
            continue
        names.append( qualify_relative_import( item.name, owner ) )
    return names


def collect_named_bmi_nodes( registry, module_name, seen=None ):
    """Transitive BMI nodes for a named module and its recorded imports."""
    if seen is None:
        seen = set()
    if not module_name or module_name in seen:
        return []
    seen.add( module_name )
    entry = registry['named'].get( module_name )
    if not entry:
        return []
    nodes = [ entry['bmi'] ]
    for dep in entry.get( 'imports', [] ):
        nodes.extend( collect_named_bmi_nodes( registry, dep, seen ) )
    return nodes


def resolve_import_nodes( env, imports, owning_module=None ):
    registry = get_registry( env )
    nodes = []
    missing = []
    seen = set()
    for item in imports:
        if item.kind == 'named':
            name = qualify_relative_import( item.name, owning_module )
            entry = registry['named'].get( name )
            if entry:
                for node in collect_named_bmi_nodes( registry, name, seen ):
                    if node not in nodes:
                        nodes.append( node )
            else:
                missing.append( name )
        else:
            entry = lookup_header_entry( registry, item.name )
            if entry:
                nodes.append( entry['bmi'] )
            else:
                missing.append( item.name )
    return nodes, missing


def register_named_module( env, module_name, bmi_path, bmi_node, imports=None ):
    registry = get_registry( env )
    entry = registry['named'].setdefault( module_name, {
        'bmi': bmi_node,
        'path': bmi_path,
        'imports': [],
    } )
    entry['bmi'] = bmi_node
    entry['path'] = bmi_path
    if imports is not None:
        entry['imports'] = list( imports )
    from cuppa.toolchains.cxx_modules_support import register_mapper_for_clean
    register_mapper_for_clean( env, bmi_node )
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
    kind, name, declared = parse_header_unit_declaration( header_path )
    keys.add( name )
    keys.add( declared )
    if kind == 'angle':
        keys.add( '<' + name + '>' )
    if 'sconscript_dir' in env and kind == 'quoted' and not header_path.startswith( '<' ):
        try:
            rel = os.path.relpath( header_path, env['sconscript_dir'] )
            keys.add( rel )
            keys.add( rel.replace( '\\', '/' ) )
        except ValueError:
            pass
    for key in keys:
        if key:
            registry['headers'][key] = entry
    from cuppa.toolchains.cxx_modules_support import register_mapper_for_clean
    register_mapper_for_clean( env, bmi_node )
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


def _collect_std_imports( classified ):
    needed = set()
    for kind, source, scan in classified:
        if kind == 'object' or not scan:
            continue
        needed |= std_module_imports_from_scan( scan )
    return needed


def ensure_std_modules( env, classified ):
    """Build and register std / std.compat BMIs when imported."""
    needed = _collect_std_imports( classified )
    if not needed:
        return

    from cuppa.methods.modules import ensure_import_std_dialect_floor
    ensure_import_std_dialect_floor( env )

    toolchain = env['toolchain']
    if not hasattr( toolchain, 'supports_import_std' ) or not toolchain.supports_import_std( env ):
        raise SCons.Errors.StopError(
            "import std / std.compat requires GCC 15+, Clang 18+ with libc++, "
            "or MSVC toolset 14.3+ with STL modules/std.ixx "
            "(toolchain [{}] is not eligible; for Clang pass --clang-stdlib=libc++)"
            .format( toolchain.name() )
        )

    registry = get_registry( env )
    # std.compat imports std — always build std first when compat is needed.
    if 'std.compat' in needed:
        needed.add( 'std' )
    order = [ name for name in ( 'std', 'std.compat' ) if name in needed ]
    for name in order:
        if name in registry['named']:
            continue
        if not hasattr( toolchain, 'build_std_module' ):
            raise SCons.Errors.StopError(
                "Toolchain [{}] cannot build the {} module"
                .format( toolchain.name(), name )
            )
        bmi_node = toolchain.build_std_module( env, name )
        if bmi_node is None:
            raise SCons.Errors.StopError(
                "Failed to build standard library module [{}] for toolchain [{}]"
                .format( name, toolchain.name() )
            )
        if name == 'std.compat' and 'std' in registry['named']:
            env.Depends( bmi_node, registry['named']['std']['bmi'] )
            registry['named'][name]['imports'] = [ 'std' ]


def validate_module_imports( env, classified ):
    """Fail if any import cannot be resolved after BMI pre-registration."""
    missing_entries = []
    for kind, source, scan in classified:
        if kind == 'object' or not scan:
            continue
        owner = owning_module_name( scan )
        _, missing = resolve_import_nodes( env, scan.imports, owning_module=owner )
        for name in missing:
            missing_entries.append( ( str( source ), name ) )
    if not missing_entries:
        return
    lines = [
        "Unresolved C++ module imports (declare HeaderUnit / include the interface in this Build):"
    ]
    for source, name in missing_entries:
        lines.append( "  [{}] imports [{}]".format( source, name ) )
    raise SCons.Errors.StopError( "\n".join( lines ) )


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
        bmi_name = module_bmi_name( scan )
        if bmi_name or is_interface_source( str( source ), scan ):
            classified.append( ( 'bmi', source, scan ) )
        else:
            classified.append( ( 'tu', source, scan ) )

    ensure_std_modules( env, classified )

    # Pre-register BMI nodes so partition / re-export Depends resolve regardless
    # of source list order (primary may appear before its partitions).
    for kind, source, scan in classified:
        if kind != 'bmi':
            continue
        name = module_bmi_name( scan )
        if not name:
            name = os.path.splitext( os.path.basename( str( source ) ) )[0]
        bmi_path = toolchain.module_bmi_path( env, name )
        bmi_node = env.File( bmi_path )
        register_named_module(
            env, name, bmi_path, bmi_node, imports=named_import_names( scan )
        )

    validate_module_imports( env, classified )

    objects = []

    def _build_one( source, scan, extra_flags, is_bmi=False ):
        if dependencies:
            env.Depends( source, Flatten( [ dependencies ] ) )

        target = object_target_for( env, source, obj_prefix, obj_suffix )
        build_kwargs = dict( kwargs )
        build_kwargs['CPPPATH'] = env['SYSINCPATH'] + env['INCPATH']

        owner = owning_module_name( scan )
        imported_nodes, missing = resolve_import_nodes(
            env, scan.imports if scan else [], owning_module=owner
        )
        if missing:
            # Should have been caught by validate_module_imports; keep as error.
            raise SCons.Errors.StopError(
                "Unresolved C++ module imports for [{}]: {}"
                .format( str( source ), ', '.join( missing ) )
            )

        module_name = None
        bmi_path = None
        bmi_node = None
        if is_bmi:
            module_name = module_bmi_name( scan )
            if not module_name:
                module_name = os.path.splitext( os.path.basename( str( source ) ) )[0]
            entry = get_registry( env )['named'].get( module_name )
            bmi_path = entry['path'] if entry else toolchain.module_bmi_path( env, module_name )
            bmi_node = entry['bmi'] if entry else env.File( bmi_path )
            register_named_module(
                env,
                module_name,
                bmi_path,
                bmi_node,
                imports=named_import_names( scan ),
            )
            cxx_flags = list( env.get( 'CXXFLAGS', [] ) )
            exported = bool( scan and scan.export_module )
            cxx_flags.extend(
                toolchain.interface_module_flags(
                    env, module_name, bmi_path, exported=exported
                )
            )
            for flag in toolchain.consume_module_flags( env, scan ):
                if flag not in cxx_flags:
                    cxx_flags.append( flag )
            build_kwargs['CXXFLAGS'] = cxx_flags
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

        if not is_bmi and scan and scan.module_declaration:
            decl = scan.module_declaration
            primary = decl.split( ':', 1 )[0]
            for candidate in ( decl, primary ):
                entry = get_registry( env )['named'].get( candidate )
                if entry:
                    for node in obj_nodes:
                        env.Depends( node, entry['bmi'] )
                    break

        return obj_nodes

    for kind, source, scan in classified:
        if kind == 'object':
            objects.append( source )
        elif kind == 'bmi':
            objects.extend( _build_one( source, scan, [], is_bmi=True ) )

    for kind, source, scan in classified:
        if kind != 'tu':
            continue
        consume_flags = toolchain.consume_module_flags( env, scan )
        objects.extend( _build_one( source, scan, consume_flags, is_bmi=False ) )

    cuppa.progress.NotifyProgress.add( env, objects )
    return objects


def build_header_unit( env, header, **kwargs ):
    if not ensure_modules_enabled( env ):
        return None

    toolchain = env['toolchain']
    kind, name, declared = parse_header_unit_declaration( header )

    modules_dir( env )
    from cuppa.toolchains.cxx_modules_support import header_unit_label
    label = header_unit_label( env, declared )
    bmi_path = toolchain.header_unit_bmi_path( env, label )

    if kind == 'angle':
        bmi_node = toolchain.build_header_unit(
            env, None, bmi_path, declared=declared, system_header=name, **kwargs
        )
        register_header_unit( env, declared, bmi_path, bmi_node )
        register_header_unit( env, name, bmi_path, bmi_node )
    else:
        if not isinstance( header, Node ):
            header_node = env.File( header )
        else:
            header_node = header
            try:
                src = header_node.srcnode()
                declared = os.path.relpath(
                    src.get_abspath(),
                    env.get( 'sconscript_dir' ) or os.getcwd(),
                )
                label = header_unit_label( env, declared )
                bmi_path = toolchain.header_unit_bmi_path( env, label )
            except Exception:
                pass
        header_path = _source_abspath( header_node )
        bmi_node = toolchain.build_header_unit(
            env, header_node, bmi_path, declared=label, **kwargs
        )
        register_header_unit( env, header_path, bmi_path, bmi_node )
        register_header_unit( env, str( header_node ), bmi_path, bmi_node )
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
        .format( as_info( declared ), as_notice( bmi_path ) )
    )
    return bmi_node


MODULE_MAP_FILENAME = 'module-map.json'


def packaged_modules_dir( final_dir ):
    return os.path.join( final_dir, 'modules' )


def install_packaged_modules( env, final_dir ):
    """
    Copy named-module BMIs from the env registry into final_dir/modules/
    and write module-map.json for consumers / package archives.

    Scheduled as a SCons Command so copies run after BMIs are produced.
    """
    if not env.get( 'modules' ):
        return None
    registry = get_registry( env ).get( 'named' ) or {}
    if not registry:
        return None

    toolchain = env['toolchain']
    extension = os.path.splitext( toolchain.module_bmi_path( env, '_probe' ) )[1]
    return _schedule_module_install( env, final_dir, extension )


def _schedule_module_install( env, final_dir, extension ):
    """Defer BMI copy until after BMIs exist (SCons build phase)."""
    dest_dir = packaged_modules_dir( final_dir )
    map_path = os.path.join( dest_dir, MODULE_MAP_FILENAME )
    registry = get_registry( env )['named']
    bmi_nodes = [
        entry['bmi'] for name, entry in registry.items()
        if name not in ( 'std', 'std.compat' ) and entry.get( 'bmi' ) is not None
    ]
    if not bmi_nodes:
        return None

    def _install_action( target, source, env ):
        if not os.path.isdir( dest_dir ):
            os.makedirs( dest_dir )
        modules = {}
        for name, entry in sorted( registry.items() ):
            if name in ( 'std', 'std.compat' ):
                continue
            src = entry.get( 'path' )
            if not src or not os.path.isfile( str( src ) ):
                continue
            dst_name = sanitize_module_filename( name ) + extension
            shutil.copy2( str( src ), os.path.join( dest_dir, dst_name ) )
            modules[name] = {
                'bmi': dst_name,
                'imports': [
                    dep for dep in entry.get( 'imports', [] )
                    if dep not in ( 'std', 'std.compat' )
                ],
            }
        with open( map_path, 'w' ) as handle:
            json.dump( {
                'format': 1,
                'extension': extension,
                'modules': modules,
            }, handle, indent=2, sort_keys=True )
            handle.write( '\n' )
        return 0

    installed = env.Command( map_path, bmi_nodes, _install_action )
    env.Depends( installed, bmi_nodes )
    cuppa.progress.NotifyProgress.add( env, installed )
    return installed


def load_packaged_modules( env, modules_dir ):
    """
    Load module-map.json from modules_dir and register BMIs on env.

    Fails with StopError if the BMI extension does not match the current toolchain.
    """
    if not modules_dir:
        return False
    map_path = os.path.join( str( modules_dir ), MODULE_MAP_FILENAME )
    if not os.path.isfile( map_path ):
        return False
    if not env.get( 'modules' ):
        logger.warn(
            "Found packaged modules at [{}] but --modules is not enabled; ignoring"
            .format( as_warning( map_path ) )
        )
        return False

    with open( map_path, 'r' ) as handle:
        data = json.load( handle )

    toolchain = env['toolchain']
    expected_ext = os.path.splitext( toolchain.module_bmi_path( env, '_probe' ) )[1]
    packaged_ext = data.get( 'extension' ) or expected_ext
    if packaged_ext != expected_ext:
        raise SCons.Errors.StopError(
            "Packaged module BMI extension [{}] does not match toolchain [{}] "
            "(expected {}); rebuild the package with the same toolchain family"
            .format( packaged_ext, toolchain.name(), expected_ext )
        )

    modules = data.get( 'modules' ) or {}
    for name, spec in sorted( modules.items() ):
        bmi_name = spec.get( 'bmi' )
        if not bmi_name:
            continue
        bmi_path = os.path.join( str( modules_dir ), bmi_name )
        if not os.path.isfile( bmi_path ):
            raise SCons.Errors.StopError(
                "Packaged module [{}] BMI missing at [{}]".format( name, bmi_path )
            )
        register_named_module(
            env,
            name,
            bmi_path,
            env.File( bmi_path ),
            imports=spec.get( 'imports' ) or [],
        )
    logger.debug(
        "Loaded [{}] packaged module(s) from [{}]"
        .format( as_info( str( len( modules ) ) ), as_notice( map_path ) )
    )
    return True
