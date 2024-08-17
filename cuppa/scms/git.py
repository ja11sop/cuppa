
#          Copyright Jamie Allsop 2014-2024
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
        # Branch doesn't exist but a tag of the same name might
        command = "{git} ls-remote --tags {repository} {branch}".format( git=cls.binary(), repository=repository, branch=branch )
        result = cls.execute_command( command )
        if result:
            for line in result.splitlines():
                if line.startswith( "warning: redirecting"):
                    logger.trace( "Ignoring redirection warning and proceeding" )
                elif branch in line:
                    logger.trace( "Tag {branch} found in {line}".format( branch=as_info(branch), line=as_notice(line) ) )
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


    ## Example outputs:
    #
    ## 1. rebasing branch "rebase_test"
    #
    #    $ git branch
    #    * (no branch, rebasing rebase_test)
    #        master
    #        rebase_test
    #
    #    $ git status -sb
    #    ## HEAD (no branch)
    #
    #    $ git show -s --pretty=\%d --decorate=full HEAD
    #     (HEAD, tag: refs/tags/product_beta_r1.13, refs/remotes/origin/master, refs/remotes/origin/HEAD, refs/heads/master)
    #
    ## 2. Detached HEAD
    #
    #    $ git branch
    #    * (HEAD detached at product_beta_r1.13)
    #      master
    #
    #    $ git status
    #    HEAD detached at product_beta_r1.13
    #    nothing to commit, working tree clean
    #
    #    $ git show -s --pretty=\%d --decorate=full HEAD
    #     (HEAD, tag: refs/tags/product_beta_r1.9, tag: refs/tags/product_beta_r1.13, refs/remotes/origin/master, refs/remotes/origin/HEAD, refs/heads/master)
    #
    ## 3. normal
    #


    @classmethod
    def get_branch( cls, path ):
        branch = None
        remote = None

        head_detached = False
        command = "{git} branch".format( git=cls.binary() )
        branch_info = cls.execute_command( command, path )
        if branch_info:
            match = re.search( r'^[*] [(]HEAD detached ', branch_info )
            if match:
                head_detached = True

        if not head_detached:
            result = cls.execute_command( "{git} status -sb".format( git=cls.binary() ), path )
            if result:
                match = re.search( r'## (?P<branch>(?:(?!\.\.)[^\^~:\s\\\n])+)(?:\.\.\.(?P<remote>[^\^~:\s\\\n]+))?', result )
                if match:
                    branch = match.group("branch")
                    remote = match.group("remote")
                match = re.search( r'## HEAD (no branch)', result )
                # Check if we are rebasing
                if match:
                    command = "{git} branch".format( git=cls.binary() )
                    branch_info = cls.execute_command( command, path )
                    if branch_info:
                        match = re.search( r'(no branch, rebasing (?P<branch>[^)]+))', branch_info )
                        if match:
                            branch = match.group("branch")
                            logger.warn( as_warning( "Currently rebasing branch [{}]".format( branch ) ) )

            return branch, remote

        else:
            result = cls.execute_command(
                    r"{git} show -s --pretty=\%d --decorate=full HEAD".format( git=cls.binary() ),
                    path
            )

            match = re.search( r'HEAD(?:(?:[^ ]* -> |[^,]*, )(?P<refs>[^)]+))?', result )

            if match and match.group("refs"):
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
                        elif ref["ref"].startswith("tag: refs/tags/"):
                            ref["ref"] = ref["ref"][len("tag: refs/tags/"):]
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
                    #elif refs[0]["type"] == "T":
                        #branch = refs[0]["ref"]
                    elif refs[0]["type"] == "R":
                        branch = refs[0]["ref"].split('/')[1]

                    remote = next( ( ref["ref"] for ref in refs if ref["type"]=="R" ), None )

                logger.trace( "Branch (using show) for [{}] is [{}]".format( as_notice(path), as_info(str(branch)) ) )
            else:
                if result == "(HEAD)":
                    command = "{git} branch".format( git=cls.binary() )
                    branch_info = cls.execute_command( command )
                    if branch_info:
                        match = re.search( r'(no branch, rebasing (?P<branch>[^)]+))', branch_info )
                        if match:
                            branch = match.group("branch")
                            logger.warn( as_warning( "Currently rebasing branch [{}]".format( branch ) ) )

        return branch, remote


    @classmethod
    def get_revision( cls, path ):
        guessed_revision = None
        revision = None

        command = "{git} describe --always".format( git=cls.binary() )
        revision = cls.execute_command( command, path )
        if revision.strip():
            guessed_revision = revision

        command = "{git} rev-parse HEAD".format( git=cls.binary() )
        commit_sha = cls.execute_command( command, path )

        command = "{git} name-rev --tags --name-only {commit_sha}".format( git=cls.binary(), commit_sha=commit_sha.strip() )
        revision = cls.execute_command( command, path )
        if revision.strip() != "undefined":
            guessed_revision = revision
        return guessed_revision


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

        revision = cls.get_revision( path )

        branch, remote = cls.get_branch( path )

        command = "{git} config --get remote.origin.url".format( git=cls.binary() )
        repository = cls.execute_command( command, path )
        repository = repository.strip()
        url = repository

        return url, repository, branch, remote, revision

