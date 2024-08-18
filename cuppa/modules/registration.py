
#          Copyright Jamie Allsop 2011-2024
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   Registraion
#-------------------------------------------------------------------------------

import traceback

from cuppa.log import logger
from cuppa.colourise import as_notice, as_info


def get_module_list( path, base=None ):
    from os import listdir
    from re import match
    from os.path import dirname
    paths = listdir( dirname( path ) )

    def unique( seq ):
        seen = set()
        seen_add = seen.add
        return [ x for x in seq if x not in seen and not seen_add(x) ]

    return unique( [ base and '.'.join( [ base, f.replace('.py','') ] ) or f.replace('.py','') for f in paths for f in paths if match( r"[^_.~].*\.py$", f ) ] )


def add_to_env( module_name, env, *args ):
    __call_classmethod_for_classes_in_module( 'cuppa', module_name, __package('cuppa'), "add_to_env", env, *args )


def add_options( module_name ):
    import SCons.Script
    __call_classmethod_for_classes_in_module( 'cuppa', module_name, __package('cuppa'), "add_options", SCons.Script.AddOption )


def get_options( module_name, env ):
    __call_classmethod_for_classes_in_module( 'cuppa', module_name, __package('cuppa'), "get_options", env )


def init_env_for_variant( module_name, sconscript_exports ):
    __call_classmethod_for_classes_in_module( 'cuppa', module_name, __package('cuppa'), "init_env_for_variant", sconscript_exports )


#-------------------------------------------------------------------------------

import inspect
import sys
import logging


def try_load_module( package, name, path ):
    module = None
    pathname = None

    try:
        import imp
        try:
            filehandle, pathname, description = imp.find_module( name, path and [ path ] or None )
            try:
                try:
                    qualified_name = package and package + "." + name or name
                    module = sys.modules[ qualified_name ]
                except KeyError:
                    try:
                        module = imp.load_module( name, filehandle, pathname, description )
                        # print( "Load module [{}] from [{}]".format( str(module), str(pathname) ) )
                    except ImportError:
                        pass
            finally:
                if filehandle:
                    filehandle.close()
        except ImportError:
            pass

    except ImportError:
        import importlib
        try:
            qualified_name = package and package + "." + name or name
            module = sys.modules[ qualified_name ]
        except KeyError:
            spec = importlib.machinery.PathFinder.find_spec( name, path and [ path ] or None )
            if spec is not None:
                #try:
                module = importlib.util.module_from_spec( spec )
                # we shouldn't do this but review to be clear why
                # -> sys.modules[spec.name] = module
                spec.loader.exec_module( module )
                pathname = spec.origin
                #except ModuleNotFoundError:
                #    pass

    return module, pathname


def __package( name ):
    package = None

    try:
        import imp
        try:
            filehandle, pathname, description = imp.find_module( name, None )
            try:
                try:
                    module = sys.modules[ name ]
                except KeyError:
                    module = imp.load_module( name, filehandle, pathname, description )
                package = pathname
            finally:
                if filehandle:
                    filehandle.close()
        except ImportError:
            pass

    except ImportError:
        import importlib
        spec = importlib.machinery.BuiltinImporter.find_spec( name )
        if spec:
            module = importlib.util.module_from_spec( spec )
            sys.modules[spec.name] = module
            spec.loader.exec_module( module )
            package = spec.parent

    return package


def __call_classmethod_for_classes_in_module( package, name, path, method, *args, **kwargs ):

    module, pathname = try_load_module( package, name, path )
    if module:
        for member_name in dir( module ):

            member = getattr( module, member_name )

            if inspect.ismodule( member ):
                if package:
                    parent_package = package + "." + name
                else:
                    parent_package = name
                __call_classmethod_for_classes_in_module( parent_package, member_name, pathname, method, *args, **kwargs )

            elif inspect.isclass( member ):
                try:
                    function = getattr( member, method )
                    if callable( function ):
                        try:
                            function( *args, **kwargs )
                        except Exception as error:
                            if logger.isEnabledFor( logging.EXCEPTION ):
                                logger.error( "[{}] in [{}] failed with error [{}]".format( as_info(str(method)), as_notice(str(member)), as_info(str(error)) ) )
                                traceback.print_exc()
                            raise error
                except AttributeError:
                    pass

#-------------------------------------------------------------------------------
