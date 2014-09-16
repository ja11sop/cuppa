
#          Copyright Jamie Allsop 2013-2014
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   asio
#-------------------------------------------------------------------------------

from exceptions   import Exception
from SCons.Script import AddOption


class AsioException(Exception):
    def __init__(self, value):
        self.parameter = value
    def __str__(self):
        return repr(self.parameter)


class Asio:

    @classmethod
    def add_options( cls ):
        AddOption( '--asio-home', dest='asio-home', type='string', nargs=1, action='store',
                   help='asio version to build against' )


    @classmethod
    def add_to_env( cls, args ):
        env = args['env']
        try:
            obj = cls( env.get_option('asio-home'),
                       env[ 'branch_root' ],
                       env[ 'platform' ],
                       env[ 'scm' ] )

            env['dependencies']['asio'] = obj
        except AsioException, (e):
            env['dependencies']['asio'] = None


    def __init__( self, branch, base, platform, scm_system ):
        if branch == None or base == None:
            raise AsioException("Cannot construct Asio Object. Invalid parameters")

        ## TODO: Check the directories below exist
        self.__scm_system = scm_system
        self.values = {}
        self.values['name']         = 'asio'
        self.values['branch']       = branch
        self.values['version']      = branch
        self.values['home']         = branch
        self.values['include']      = [ self.values['home'] ]


    def name( self ):
        return self.values['name']

    def version( self ):
        return self.values['version']

    def revisions( self, scm = None ):
        scm_system = scm and scm or self.__scm_system
        return [ scm_system.revision( self.values['home'] ) ]

    def modify( self, env, toolchain, variant ):
        env.AppendUnique( INCPATH = self.values.get( 'include' ) )


