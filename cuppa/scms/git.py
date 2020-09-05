
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
from cuppa.colourise import as_notice, as_info, colour_items, as_warning
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
            logger.trace( "Executing command [{command}]...".format(
                    command=as_info(command)
            ) )
            result = as_str( subprocess.check_output( shlex.split( command ), stderr=subprocess.STDOUT, cwd=path ) ).strip()
            logger.trace( "Result of calling [{command}] was [{result}]".format(
                    command=as_info(command),
                    result=as_notice(result)
            ) )
            return result
        except subprocess.CalledProcessError as error:
            logger.trace( "Command [{command}] failed with exit code [{exit_code}]".format(
                    command=as_warning(str(command)),
                    exit_code=as_warning(str(error.returncode))
            ) )
            raise cls.Error("Command [{command}] failed".format( command=str(command) ) )
        except OSError:
            logger.trace( "Binary [{git}] is not available".format(
                    git=as_warning(cls.binary())
            ) )
            raise cls.Error("Binary [{git}] is not available".format(  git=cls.binary() ) )


    @classmethod
    def remote_branch_exists( cls, repository, branch ):
        command = "{git} ls-remote --heads {repository} {branch}".format( git=cls.binary(), repository=repository, branch=branch )
        result = cls.execute_command( command )
        if result:
            for line in result.splitlines():
                if line.startswith( "warning: redirecting"):
                    logger.trace( "Ignoring redirection warning and proceeding" )
                elif branch in line:
                    logger.trace( "Branch {branch} found in {line}".format( branch=as_info(branch), line=as_notice(line) ) )
                    return True
        return False


    @classmethod
    def remote_default_branch( cls, repository ):
        command = "{git} ls-remote --symref {repository} HEAD".format( git=cls.binary(), repository=repository )
        result = cls.execute_command( command )

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
        result = cls.execute_command(
                "{git} show -s --pretty=\%d --decorate=full HEAD".format( git=cls.binary() ),
                path
        )

        match = re.search( r'HEAD(?:(?:[^ ]* -> |[^,]*, )(?P<refs>[^)]+))?', result )

        if match:
            refs = [ { "ref":r.strip(), "type": "" } for r in match.group("refs").split(',') ]
            logger.trace( "Refs (using show) for [{}] are [{}]".format(
                    as_notice(path),
                    colour_items( (r["ref"] for r in refs) )
            ) )
            if refs:
                for ref in refs:
                    if ref["ref"].startswith("refs/heads/"):
                        ref["ref"] = ref["ref"][len("refs/heads/"):]
                        ref["type"] = "L"
                    elif ref["ref"].startswith("refs/tags/"):
                        ref["ref"] = ref["ref"][len("refs/tags/"):]
                        ref["type"] = "T"
                    elif ref["ref"].startswith("refs/remotes/"):
                        ref["ref"] = ref["ref"][len("refs/remotes/"):]
                        ref["type"] = "R"
                    else:
                        ref["type"] = "U"

                logger.trace( "Refs (after classification) for [{}] are [{}]".format(
                        as_notice(path),
                        colour_items( (":".join([r["type"], r["ref"]]) for r in refs) )
                ) )

                if refs[0]["type"] == "L":
                    branch = refs[0]["ref"]
                elif refs[0]["type"] == "T":
                    branch = refs[0]["ref"]
                elif refs[0]["type"] == "R":
                    branch = refs[0]["ref"].split('/')[1]

                remote = next( ( ref["ref"] for ref in refs if ref["type"]=="R" ), None )

            logger.trace( "Branch (using show) for [{}] is [{}]".format( as_notice(path), as_info(str(branch)) ) )
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

        command = "{git} describe --always".format( git=cls.binary() )
        revision = cls.execute_command( command, path )

        branch, remote = cls.get_branch( path )

        if remote:
            command = "{git} config --get remote.origin.url".format( git=cls.binary() )
            repository = cls.execute_command( command, path )
            url = repository

        return url, repository, branch, remote, revision

