#          Copyright Jamie Allsop 2014-2015
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   build_with_header_library
#-------------------------------------------------------------------------------

import os

import cuppa.location


class HeaderLibraryException(Exception):
    def __init__(self, value):
        self.parameter = value
    def __str__(self):
        return repr(self.parameter)


class base(object):

    _name = None

    @classmethod
    def add_options( cls, add_option ):
        location_name = cls._name + "-location"
        branch_name   = cls._name + "-branch"
        include_name  = cls._name + "-include"
        add_option( '--' + location_name, dest=location_name, type='string', nargs=1, action='store',
                    help = cls._name + ' location to build against' )

        add_option( '--' + branch_name, dest=branch_name, type='string', nargs=1, action='store',
                    help = cls._name + ' branch to build against. Providing a branch is optional' )

        add_option( '--' + include_name, dest=include_name, type='string', nargs=1, action='store',
                    help = cls._name + ' include sub-directory to be added to the include path. Optional' )


    @classmethod
    def add_to_env( cls, env, add_dependency  ):
        location = env.get_option( cls._name + "-location" )
        if not location:
            location = env['branch_root']
        if not location:
            location = env['thirdparty']
        if not location:
            print "cuppa: No location specified for dependency [{}]. Dependency not available.".format( cls._name.title() )
        branch  = env.get_option( cls._name + "-branch" )
        include = env.get_option( cls._name + "-include" )

        add_dependency( cls._name, cls( env, location, branch=branch, includes=[include] ) )


    def __init__( self, env, location, branch=None, includes=[] ):

        self._location = cuppa.location.Location( env, location, branch )

        self._includes = []
        for include in includes:
            self._includes.append( include and os.path.join( self._location.local(), include ) or self._location.local(), )


    def __call__( self, env, toolchain, variant ):
        env.AppendUnique( INCPATH = self._includes )


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


def header_library_dependency( name ):
    return type( 'BuildWith' + name.title(), ( base, ), { '_name': name } )



