
#          Copyright Jamie Allsop 2011-2014
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   Subversion Source Control Management System
#-------------------------------------------------------------------------------

from subprocess import Popen, PIPE
from string import strip, replace
from exceptions import Exception
from SCons.Script import AddOption



class SubversionException(Exception):
    def __init__(self, value):
        self.parameter = value
    def __str__(self):
        return repr(self.parameter)


class Subversion:


    @classmethod
    def add_to_env( cls, env, add_scm ):
        scm = cls( env['platform'] )
        add_scm( 'subversion', scm )
        add_scm( 'svn',        scm )


    def __init__( self, platform ):
        ## TODO: Check for svnversion
        self.__platform = platform


    def revision( self, location ):
        if location == '' or location == None:
            raise SubversionException("No working copy path specified for calling svnversion with.")

        revision = Popen(["svnversion", location], stdout=PIPE).communicate()[0].strip()
        return revision

