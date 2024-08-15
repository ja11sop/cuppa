
#          Copyright Jamie Allsop 2011-2018
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

    return unique( [ base and '.'.join( [ base, f.replace('.py','') ] ) or f.replace('.py','') for f in paths for f in paths if match( '[^_.~].*\.py$', f ) ] )


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

# try:
from imp import find_module as find_module
from imp import load_module as load_module
# except ImportError: # Python 3.12+
    # from importlib.util import find_spec as find_module
    # from importlib import import_module as load_module

import sys
import logging

def __package( name ):
    package = None
    try:
        filehandle, pathname, description = find_module( name, None )
        try:
            try:
                module = sys.modules[ name ]
            except KeyError:
                module = load_module( name, filehandle, pathname, description )
            package = pathname
        finally:
            if filehandle:
                filehandle.close()
    except ImportError:
        pass
    return package


def __call_classmethod_for_classes_in_module( package, name, path, method, *args, **kwargs ):
    try:
        filehandle, pathname, description = find_module( name, path and [ path ] or None )
        try:
            try:
                qualified_name = package and package + "." + name or name
                module = sys.modules[ qualified_name ]

            except KeyError:
                module = load_module( name, filehandle, pathname, description )

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
        finally:
            if filehandle:
                filehandle.close()

    except ImportError:
        pass

#-------------------------------------------------------------------------------
