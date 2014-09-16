# -*- coding: utf-8 -*-
#-------------------------------------------------------------------------------
#   ebl
#-------------------------------------------------------------------------------

from exceptions   import Exception
from SCons.Script import AddOption


class EblException(Exception):
    def __init__(self, value):
        self.parameter = value
    def __str__(self):
        return repr(self.parameter)


class Ebl:


    @classmethod
    def add_options( cls ):
        AddOption( '--ebl-branch', dest='ebl-branch', type='string', nargs=1, action='store',
                   help='xstd version to build against' )


    @classmethod
    def add_to_env( cls, args ):
        env = args['env']
        try:
            obj = cls( env.get_option('ebl-branch'),
                       env[ 'branch_root' ],
                       env[ 'platform' ],
                       env[ 'scm' ] )

            env['dependencies']['ebl'] = obj
        except EblException, (e):
            env['dependencies']['ebl'] = None


    def __init__( self, branch, base, platform, scm_system ):
        if branch == None or base == None:
            raise EblException("Cannot construct Ebl Object. Invalid parameters")

        ## TODO: Check the directories below exist
        self.__scm_system = scm_system
        self.values = {}
        self.values['name']         = 'ebl'
        self.values['branch']       = branch
        self.values['version']      = branch
        self.values['home']         = base + '/ebl/' + branch
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

