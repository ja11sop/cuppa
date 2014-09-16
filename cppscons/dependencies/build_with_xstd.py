# -*- coding: utf-8 -*-
#-------------------------------------------------------------------------------
#   xstd
#-------------------------------------------------------------------------------

from exceptions   import Exception
from SCons.Script import AddOption


class XstdException(Exception):
    def __init__(self, value):
        self.parameter = value
    def __str__(self):
        return repr(self.parameter)


class Xstd:

    @classmethod
    def add_options( cls ):
        AddOption( '--xstd-branch', dest='xstd-branch', type='string', nargs=1, action='store',
                   help='xstd version to build against' )


    @classmethod
    def add_to_env( cls, args ):
        env = args['env']
        try:
            obj = cls( env.get_option('xstd-branch'),
                       env[ 'branch_root' ],
                       env[ 'platform' ],
                       env[ 'scm' ] )

            env['dependencies']['xstd'] = obj
        except XstdException, (e):
            env['dependencies']['xstd'] = None


    def __init__( self, branch, base, platform, scm_system ):
        if branch == None or base == None:
            raise XstdException("Cannot construct Xstd Object. Invalid parameters")

        ## TODO: Check the directories below exist
        self.__scm_system = scm_system
        self.values = {}
        self.values['name']         = 'xstd'
        self.values['branch']       = branch
        self.values['version']      = branch
        self.values['home']         = base + '/xstd/' + branch
        self.values['include']      = [ self.values['home'] ]


    def name( self ):
        return self.values['name']

    def version( self ):
        return self.values['version']

    def revisions( self, scm = None ):
        scm_system = scm and scm or self.__scm_system
        return [ scm_system.revision( self.values['home'] ) ]

    def __call__( self, env, toolchain, variant ):
        env.AppendUnique( INCPATH = self.values.get( 'include' ) )


