#          Copyright Jamie Allsop 2014-2014
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   build_with_header_library
#-------------------------------------------------------------------------------

import urlparse
import os

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
        branch_name = cls._name + "-branch"
        add_option( '--' + location_name, dest=location_name, type='string', nargs=1, action='store',
                    help = cls._name + ' location to build against' )

        add_option( '--' + branch_name, dest=branch_name, type='string', nargs=1, action='store',
                    help = cls._name + ' branch to build against. Providing a branch is optional' )


    @classmethod
    def add_to_env( cls, env, add_dependency  ):
        location = env.get_option( cls._name + "-location" )
        if not location:
            location = env['branch_root']
        if not location:
            location = env['thirdparty']
        if not location:
            print "No location specified for dependency [{}]. Dependency not available.".format( cls._name.title() )
        branch = env.get_option( cls._name + "-branch" )

        add_dependency( cls._name, cls( location, branch ) )


    def __init__( self, location, branch=None ):
        self._include = ""
        url = urlparse.urlparse( location )

        if not url.scheme:
            # Assume we have a basic file path
            self._include = branch and os.path.join( location, branch ) or location
            self._version = branch


    def __call__( self, env, toolchain, variant ):
        env.AppendUnique( INCPATH = self._include )


    def version( self ):
        return str(self._version)


def header_library_dependency( name ):
    return type( 'BuildWith' + name.title(), ( base, ), { '_name': name } )

