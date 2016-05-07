#          Copyright Jamie Allsop 2014-2015
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   build_with_location
#-------------------------------------------------------------------------------

import os

import cuppa.location
from cuppa.log import logger
from cuppa.colourise import as_notice, as_error


class LocationDependencyException(Exception):
    def __init__(self, value):
        self.parameter = value
    def __str__(self):
        return repr(self.parameter)


class base(object):

    _name = None
    _cached_locations = {}
    _default_include = None
    _default_sys_include = None
    _includes = None
    _sys_includes = None

    @classmethod
    def add_options( cls, add_option ):
        location_name    = cls._name + "-location"
        branch_name      = cls._name + "-branch"
        include_name     = cls._name + "-include"
        sys_include_name = cls._name + "-sys-include"

        add_option( '--' + location_name, dest=location_name, type='string', nargs=1, action='store',
                    help = cls._name + ' location to build against' )

        add_option( '--' + branch_name, dest=branch_name, type='string', nargs=1, action='store',
                    help = cls._name + ' branch to build against. Providing a branch is optional' )

        add_option( '--' + include_name, dest=include_name, type='string', nargs=1, action='store',
                    help = cls._name + ' include sub-directory to be added to the include path. Optional' )

        add_option( '--' + sys_include_name, dest=sys_include_name, type='string', nargs=1, action='store',
                    help = cls._name + ' include sub-directory to be added to the system include path. Optional' )


    @classmethod
    def add_to_env( cls, env, add_dependency  ):
        add_dependency( cls._name, cls.create )


    @classmethod
    def location_id( cls, env ):
        location = env.get_option( cls._name + "-location" )
        branch   = env.get_option( cls._name + "-branch" )

        if not location and branch:
            location = env['branch_root']
        if not location and branch:
            location = env['thirdparty']
        if not location:
            logger.debug( "No location specified for dependency [{}]. Dependency not available.".format( cls._name.title() ) )
            return None

        return (location, branch)


    @classmethod
    def _get_location( cls, env ):
        location_id = cls.location_id( env )
        if not location_id:
            return None
        if location_id not in cls._cached_locations:
            location = location_id[0]
            branch = location_id[1]
            try:
                cls._cached_locations[location_id] = cuppa.location.Location( env, location, branch )
            except cuppa.location.LocationException as error:
                logger.error(
                        "Could not get location for [{}] at [{}] with branch [{}]. Failed with error [{}]"
                        .format( as_notice( cls._name.title() ), as_notice( str(location) ), as_notice( str(branch) ), as_error( error ) )
                )
                return None

        return cls._cached_locations[location_id]


    @classmethod
    def create( cls, env ):

        location = cls._get_location( env )
        if not location:
            return None

        if not cls._includes:
            include = env.get_option( cls._name + "-include" )
            cls._includes = include and [include] or []

        if not cls._sys_includes:
            sys_include = env.get_option( cls._name + "-sys-include" )
            cls._sys_includes = sys_include and [sys_include] or []

        if cls._default_include:
            cls._includes.append( cls._default_include )

        if cls._default_sys_include:
            cls._sys_includes.append( cls._default_sys_include )

        return cls( env, location, includes=cls._includes, sys_includes=cls._sys_includes)


    def __init__( self, env, location, includes=[], sys_includes=[] ):

        self._location = location

        if not includes and not sys_includes:
            includes = [self._location.local()]

        self._includes = []
        for include in includes:
            if include:
                self._includes.append( os.path.isabs(include) and include or os.path.join( self._location.local(), include ) )

        self._sys_includes = []
        for include in sys_includes:
            if include:
                self._sys_includes.append( os.path.isabs(include) and include or os.path.join( self._location.local(), include ) )


    def __call__( self, env, toolchain, variant ):
        env.AppendUnique( INCPATH = self._includes )
        env.AppendUnique( SYSINCPATH = self._sys_includes )

    def local_sub_path( self, *paths ):
        return os.path.join( self._location.local(), *paths )

    def name( self ):
        return self._name

    def version( self ):
        return str(self._location.version())

    def repository( self ):
        return self._location.repository()

    def branch( self ):
        return self._location.branch()

    def revisions( self ):
        return self._location.revisions()


def location_dependency( name, include=None, sys_include=None ):
    return type( 'BuildWith' + name.title(), ( base, ), { '_name': name, '_default_include': include, '_default_sys_include': sys_include } )



