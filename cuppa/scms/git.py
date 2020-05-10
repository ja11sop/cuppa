
#          Copyright Jamie Allsop 2014-2020
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

from cuppa.log import logger
from cuppa.colourise import as_notice, as_info, colour_items
from cuppa.utility.python2to3 import as_str, Exception


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
    def execute_command( cls, command, path=None ):
        try:
            return subprocess.check_output( shlex.split( command ), stderr=subprocess.STDOUT, cwd=path )
        except subprocess.CalledProcessError:
            raise cls.Error("Command [{command}] failed".format( command=str(command) ) )
        except OSError:
            raise cls.Error("Binary [{git}] is not available".format(
                    git=cls.binary()
            ) )


    @classmethod
    def remote_branch_exists( cls, repository, branch ):
        command = "{git} ls-remote --heads {repository} {branch}".format( git=cls.binary(), repository=repository, branch=branch )
        result = as_str( cls.execute_command( command ) ).strip()
        logger.trace( "Result of calling [{command}] was [{result}]".format( command=as_info(command), result=as_notice(result) ) )
        if result:
            return True
        return False


    @classmethod
    def remote_default_branch( cls, repository ):
        command = "{git} ls-remote --symref {repository} HEAD".format( git=cls.binary(), repository=repository )
        result = as_str( cls.execute_command( command ) ).strip()
        logger.trace( "Result of calling [{command}] was [{result}]".format( command=as_info(command), result=as_notice(result) ) )

        if result:
            branch_pattern = r'ref[:]\s+refs/heads/(?P<default_branch>[^\s]+)\s+HEAD'
            match = re.search( branch_pattern, result )
            logger.trace(
                    "When searching for default branch name for repoistory [{}] using regex [{}] the following match [{}] was returned".format(
                    as_info(repository), as_notice(branch_pattern), as_info(str(match))
            ) )
            if match:
                return match.group('default_branch')
        return None


    @classmethod
    def get_branch( cls, path ):
        branch = None
        remote = None

        # In case we have a detached head we use this
        result = as_str( cls.execute_command( "{git} show -s --pretty=\%d HEAD".format( git=cls.binary() ), path ) )
        match = re.search( r'[(]HEAD[^,]*[,] (?P<branches>[^)]+)[)]', result )
        if match:
            branches = [ b.strip() for b in match.group("branches").split(',') ]
            logger.trace( "Branches (using show) for [{}] are [{}]".format( as_notice(path), colour_items(branches) ) )
            if len(branches) == 1:
                # If this returns a tag: tag_name replace the ": " with "/" and then extract the tag_name
                # otherwise this will simply extract the branch_name as expected
                if not branches[0].startswith('tag:'):
                    remote = branches[0]
                branch = branches[0].replace(': ','/').split('/')[1]
            else:
                remote = branches[-2]
                branch = remote.split('/')[1]
            logger.trace( "Branch (using show) for [{}] is [{}]".format( as_notice(path), as_info(branch) ) )
        else:
            logger.warn( "No branch found from [{}]".format( result ) )

        return branch, remote



    @classmethod
    def info( cls, path ):
        if not path:
            raise cls.Error("No working copy path specified for calling git commands with.")

        url        = None
        repository = None
        branch     = None
        remote     = None
        revision   = None

        if not os.path.exists( os.path.join( path, ".git" ) ):
            raise cls.Error("Not a Git working copy")

        command = None
        try:
            command = "{git} describe --always".format( git=cls.binary() )
            revision = as_str( subprocess.check_output( shlex.split( command ), stderr=subprocess.STDOUT, cwd=path ).strip() )

            branch, remote = cls.get_branch( path )

            command = "{git} config --get remote.origin.url".format( git=cls.binary() )
            repository = as_str( subprocess.check_output( shlex.split( command ), stderr=subprocess.STDOUT, cwd=path ).strip() )
            url = repository

        except subprocess.CalledProcessError:
            raise cls.Error("Git command [{command}] failed".format(
                    command=str(command)
            ) )

        except OSError:
            raise cls.Error("Git binary [{git}] is not available".format(
                    git=cls.binary()
            ) )

        return url, repository, branch, remote, revision

