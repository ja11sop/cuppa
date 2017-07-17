
#          Copyright Jamie Allsop 2014-2017
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   Git Source Control Management System
#-------------------------------------------------------------------------------

import subprocess
import shlex
import os
import re
from exceptions import Exception

from cuppa.log import logger
from cuppa.colourise import as_notice, as_info, colour_items


class Git:

    class Error(Exception):
        def __init__(self, value):
            self.parameter = value
        def __str__(self):
            return repr(self.parameter)


    @classmethod
    def vc_type( cls ):
        return "git"


    @classmethod
    def binary( cls ):
        return "git"


    @classmethod
    def execute_command( cls, command, path ):
        try:
            return subprocess.check_output( shlex.split( command ), stderr=subprocess.STDOUT, cwd=path )
        except subprocess.CalledProcessError:
            raise cls.Error("Command [{command}] failed".format( command=str(command) ) )
        except OSError:
            raise cls.Error("Binary [{git}] is not available".format(
                    git=cls.binary()
            ) )


    @classmethod
    def get_branch( cls, path ):
        branch = None
        try:
            result = cls.execute_command( "{git} symbolic-ref HEAD".format( git=cls.binary() ), path )
            branch = result.replace( "refs/heads/", "" ).strip()
            logger.trace( "Branch (using symbolic-ref) for [{}] is [{}]".format( as_notice(path), as_info(branch) ) )
            return branch
        except cls.Error:
            pass

        # In case we have a detached head we can fallback to this
        result = cls.execute_command( "{git} show -s --pretty=\%d HEAD".format( git=cls.binary() ), path )
        match = re.search( r'[(]HEAD[^,]*[,] (?P<branches>[^)]+)[)]', result )
        if match:
            branches = [ b.strip() for b in match.group("branches").split(',') ]
            logger.trace( "Branches (using show) for [{}] are [{}]".format( as_notice(path), colour_items(branches) ) )
            if len(branches) == 1:
                branch = branches[0].split('/')[1]
            else:
                branch = branches[-2].split('/')[1]
            logger.trace( "Branch (using show) for [{}] is [{}]".format( as_notice(path), as_info(branch) ) )
        else:
            logger.warn( "No branch found from [{}]".format( result ) )

        return branch



    @classmethod
    def info( cls, path ):
        if not path:
            raise cls.Error("No working copy path specified for calling git commands with.")

        url        = None
        repository = None
        branch     = None
        revision   = None

        if not os.path.exists( os.path.join( path, ".git" ) ):
            raise cls.Error("Not a Git working copy")

        command = None
        try:
            command = "{git} describe --always".format( git=cls.binary() )
            revision = subprocess.check_output( shlex.split( command ), stderr=subprocess.STDOUT, cwd=path ).strip()

            branch = cls.get_branch( path )

            command = "{git} config --get remote.origin.url".format( git=cls.binary() )
            repository = subprocess.check_output( shlex.split( command ), stderr=subprocess.STDOUT, cwd=path ).strip()
            url = repository

        except subprocess.CalledProcessError:
            raise cls.Error("Git command [{command}] failed".format(
                    command=str(command)
            ) )

        except OSError:
            raise cls.Error("Git binary [{git}] is not available".format(
                    git=cls.binary()
            ) )

        return url, repository, branch, revision

