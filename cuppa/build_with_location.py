#          Copyright Jamie Allsop 2014-2020
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   build_with_location
#-------------------------------------------------------------------------------

import os

import cuppa.location
from cuppa.log import logger
from cuppa.colourise import as_notice, as_error, as_info


class LocationDependencyException(Exception):
    def __init__(self, value):
        self.parameter = value
    def __str__(self):
        return repr(self.parameter)


class base(object):

    _name = None
    _cached_locations = {}
    _default_location = None
    _default_develop = None
    _default_include = None
    _default_sys_include = None
    _includes = None
    _sys_includes = None
    _extra_sub_path = None
    _source_path = None
    _linktype = None
    _prebuilt_objects = {}
    _prebuilt_libraries = {}


    @classmethod
    def location_option( cls ):
        return cls._name + "-location"

    @classmethod
    def develop_option( cls ):
        return cls._name + "-develop"

    @classmethod
    def branch_path_option( cls ):
        return cls._name + "-branch-path"

    @classmethod
    def include_option( cls ):
        return cls._name + "-include"

    @classmethod
    def sys_include_option( cls ):
        return cls._name + "-sys-include"

    @classmethod
    def extra_sub_path_option( cls ):
        return cls._name + "-extra_sub_path"

    @classmethod
    def source_path_option( cls ):
        return cls._name + "-source-path"

    @classmethod
    def linktype_option( cls ):
        return cls._name + "-linktype"


    @classmethod
    def add_options( cls, add_option ):

        add_option( '--' + cls.location_option(), dest=cls.location_option(), type='string', nargs=1, action='store',
                    help = cls._name + ' location to build against' )

        add_option( '--' + cls.develop_option(), dest=cls.develop_option(), type='string', nargs=1, action='store',
                    help = cls._name + ' location to build against when in develop mode' )

        add_option( '--' + cls.branch_path_option(), dest=cls.branch_path_option(), type='string', nargs=1, action='store',
                    help = cls._name + ' branch_path to build against if using path-based branching (as in Subversion). Providing a branch_path is optional' )

        add_option( '--' + cls.include_option(), dest=cls.include_option(), type='string', nargs=1, action='store',
                    help = cls._name + ' include sub-directory to be added to the include path. Optional' )

        add_option( '--' + cls.sys_include_option(), dest=cls.sys_include_option(), type='string', nargs=1, action='store',
                    help = cls._name + ' include sub-directory to be added to the system include path. Optional' )

        add_option( '--' + cls.extra_sub_path_option(), dest=cls.extra_sub_path_option(), type='string', nargs=1, action='store',
                    help = cls._name + ' extra (relative) sub path to locate the dependency. Optional' )

        add_option( '--' + cls.source_path_option(), dest=cls.source_path_option(), type='string', nargs=1, action='store',
                    help = cls._name + ' path to source files. Optional' )

        add_option( '--' + cls.linktype_option(), dest=cls.linktype_option(), type='string', nargs=1, action='store',
                    help = cls._name + ' linktype: static (default) or shared. Optional' )


    @classmethod
    def add_to_env( cls, env, add_dependency  ):
        add_dependency( cls._name, cls.create )


    @classmethod
    def location_id( cls, env ):
        location    = env.get_option( cls.location_option() )
        develop     = env.get_option( cls.develop_option() )
        branch_path = env.get_option( cls.branch_path_option() )

        use_develop = env.get_option( "develop" )

        if not location and cls._default_location:
            location = cls._default_location
        if not location and branch_path:
            location = env['branch_root']
        if not location and env['thirdparty']:
            location = env['thirdparty']
        if not location:
            logger.debug( "No location specified for dependency [{}]. Dependency not available.".format( cls._name.title() ) )
            return None

        if location:
            location = os.path.expanduser( location )

        if not develop and cls._default_develop:
            develop = cls._default_develop

        if develop:
            develop = os.path.expanduser( develop )

        return (location, develop, branch_path, use_develop)


    @classmethod
    def _get_location( cls, env ):

        import SCons.Errors

        location_id = cls.location_id( env )
        if not location_id:
            return None
        if location_id not in cls._cached_locations:
            location = location_id[0]
            develop = location_id[1]
            branch_path = location_id[2]
            use_develop = location_id[3]
            try:
                cls._cached_locations[location_id] = cuppa.location.Location(
                        env,
                        location,
                        develop=develop,
                        branch_path=branch_path,
                        extra_sub_path=cls._extra_sub_path
                )
                logger.debug( "Adding location [{}]({}) to cached locations".format(
                        as_notice( cls._name.title() ),
                        as_notice( str(location_id) )
                ) )
            except cuppa.location.LocationException as error:
                logger.error(
                        "Could not get location for [{}] at [{}] (and develop [{}], use=[{}]) with branch_path [{}] and extra sub path [{}]. Failed with error [{}]"
                        .format(
                                as_notice( cls._name.title() ),
                                as_info( str(location) ),
                                as_info( str(develop) ),
                                as_notice( str(use_develop and True or False) ),
                                as_notice( str(branch_path) ),
                                as_notice( str(cls._extra_sub_path) ),
                                as_error( str(error) )
                        )
                )
                raise SCons.Errors.StopError( error )
        else:
            logger.debug( "Loading location [{}]({}) from cached locations".format(
                    as_notice( cls._name.title() ),
                    as_notice( str(location_id) )
            ) )

        return cls._cached_locations[location_id]


    @classmethod
    def create( cls, env ):

        location = cls._get_location( env )
        if not location:
            return None

        if not cls._includes:
            include = env.get_option( cls.include_option() )
            cls._includes = include and [include] or []

        if not cls._sys_includes:
            sys_include = env.get_option( cls.sys_include_option() )
            cls._sys_includes = sys_include and [sys_include] or []

        if cls._default_include:
            cls._includes.extend( cls._default_include )

        if cls._default_sys_include:
            cls._sys_includes.extend( cls._default_sys_include )

        if not cls._source_path:
            cls._source_path = env.get_option( cls.source_path_option() )

        if not cls._linktype:
            cls._linktype = env.get_option( cls.linktype_option() )

        return cls( env, location, includes=cls._includes, sys_includes=cls._sys_includes, source_path=cls._source_path, linktype=cls._linktype )


    @classmethod
    def abs_path_from( cls, path, local_location, base_path ):
        path = os.path.isabs(path) and path or os.path.join( local_location, path )
        return os.path.isabs(path) and path or os.path.join( base_path, path )


    def __init__( self, env, location, includes=[], sys_includes=[], source_path=None, linktype=None ):

        self._location = location

        if not includes and not sys_includes:
            sys_includes = [self._location.local()]

        self._includes = []
        for include in includes:
            if include:
                self._includes.append( self.abs_path_from( include, self._location.local(), env['sconstruct_dir'] ) )

        self._sys_includes = []
        for include in sys_includes:
            if include:
                self._sys_includes.append( self.abs_path_from( include, self._location.local(), env['sconstruct_dir'] ) )

        self._includes = [ i for i in set(self._includes) ]
        self._sys_includes = [ i for i in set(self._sys_includes) ]

        if not source_path:
            source_path = self._location.local()

        if source_path:
            self._source_path = self.abs_path_from( source_path, self._location.local(), env['sconstruct_dir'] )

        if not linktype:
            self._linktype = "static"
        else:
            self._linktype = linktype


    def __call__( self, env, toolchain, variant ):
        env.AppendUnique( INCPATH = self._includes )
        env.AppendUnique( SYSINCPATH = self._sys_includes )


    @classmethod
    def lazy_create_node( cls, variant_key, cached_nodes ):
        if not cls._name in cached_nodes:
            cached_nodes[cls._name] = {}

        if not variant_key in cached_nodes[cls._name]:
            cached_nodes[cls._name][variant_key] = {}

        return cached_nodes[cls._name][variant_key]


    def build_library_from_source( self, env, sources=None, library_name=None, linktype=None ):

        from SCons.Script import Flatten

        if not self._source_path and not sources:
            logger.warn( "Attempting to build library when source path is None" )
            return None

        if not library_name:
            library_name = self._name

        if not linktype:
            linktype = self._linktype

        variant_key = env['tool_variant_dir']

        prebuilt_objects   = self.lazy_create_node( variant_key, self._prebuilt_objects )
        prebuilt_libraries = self.lazy_create_node( variant_key, self._prebuilt_libraries )

        local_dir = self._location.local()
        local_folder = self._location.local_folder()

        build_dir = os.path.abspath( os.path.join( env['abs_build_root'], local_folder, env['tool_variant_working_dir'] ) )
        final_dir = os.path.abspath( os.path.normpath( os.path.join( build_dir, env['final_dir'] ) ) )

        logger.debug( "build_dir for [{}] = [{}]".format( as_info(self._name), build_dir ) )
        logger.debug( "final_dir for [{}] = [{}]".format( as_info(self._name), final_dir ) )

        obj_suffix = env['OBJSUFFIX']
        obj_builder = env.StaticObject
        lib_builder = env.BuildStaticLib

        if linktype == "shared":
            obj_suffix = env['SHOBJSUFFIX']
            obj_builder = env.SharedObject
            lib_builder = env.BuildSharedLib

        if not sources:
            sources = env.RecursiveGlob( "*.cpp", start=self._source_path, exclude_dirs=[ env['build_dir'] ] )
            sources.extend( env.RecursiveGlob( "*.cc", start=self._source_path, exclude_dirs=[ env['build_dir'] ] ) )
            sources.extend( env.RecursiveGlob( "*.c", start=self._source_path, exclude_dirs=[ env['build_dir'] ] ) )

        objects = []
        for source in Flatten( [sources] ):
            rel_path = os.path.relpath( str(source), local_dir )
            rel_obj_path = os.path.splitext( rel_path )[0] + obj_suffix
            obj_path = os.path.join( build_dir, rel_obj_path )
            if not rel_obj_path in prebuilt_objects:
                prebuilt_objects[rel_obj_path] = obj_builder( obj_path, source )
            objects.append( prebuilt_objects[rel_obj_path] )

        if not linktype in prebuilt_libraries:
            library = lib_builder( library_name, objects, final_dir = final_dir )
            if linktype == "shared":
                library = env.Install( env['abs_final_dir'], library )
            prebuilt_libraries[linktype] = library
        else:
            logger.trace( "using existing library = [{}]".format( str(prebuilt_libraries[linktype]) ) )

        return prebuilt_libraries[linktype]


    def location( self ):
        return self._location


    def local_sub_path( self, *paths ):
        return os.path.join( self._location.local(), *paths )


    def local_abs_path( self, *paths ):
        return os.path.abspath( os.path.join( self._location.local(), *paths ) )


    def includes( self ):
        return self._includes


    def sys_includes( self ):
        return self._sys_includes


    @classmethod
    def name( cls ):
        return cls._name

    def version( self ):
        return str(self._location.version())

    def repository( self ):
        return self._location.repository()

    def branch( self ):
        return self._location.branch()

    def revisions( self ):
        return self._location.revisions()



class LibraryMethod(object):

    def __init__( self, location_dependency, update_env, sources=None, library_name=None, linktype=None ):
        self._location_dependency = location_dependency
        self._update_env = update_env
        self._sources = sources
        self._library_name = library_name
        self._linktype = linktype


    def __call__( self, env ):
        self._update_env( env )
        return self._location_dependency.build_library_from_source( env, self._sources, self._library_name, self._linktype )



def location_dependency( name, location=None, develop=None, include=None, sys_include=None, extra_sub_path=None, source_path=None, linktype=None ):

    from SCons.Script import Flatten

    flattened_includes = [ i for i in Flatten( [include] ) if i is not None ]
    flattened_sys_includes = [ i for i in Flatten( [sys_include] ) if i is not None ]

    return type(
            'BuildWith' + name.title(),
            ( base, ),
            {   '_name': name,
                '_default_location': location,
                '_default_develop': develop,
                '_default_include': flattened_includes,
                '_default_sys_include': flattened_sys_includes,
                '_extra_sub_path': extra_sub_path,
                '_source_path': source_path,
                '_linktype': linktype
            }
    )
