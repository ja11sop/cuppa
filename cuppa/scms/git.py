
#          Copyright Jamie Allsop 2014-2015
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   Git Source Control Management System
#-------------------------------------------------------------------------------

import subprocess
import shlex
import os
from exceptions import Exception


class GitException(Exception):
    def __init__(self, value):
        self.parameter = value
    def __str__(self):
        return repr(self.parameter)


def info( path ):
    if not path:
        raise GitException("No working copy path specified for calling git commands with.")

    url        = None
    repository = None
    branch     = None
    revision   = None

    if not os.path.exists( os.path.join( path, ".git" ) ):
        raise GitException("Not a Git working copy")

    try:
        command = "git describe --always"
        revision = subprocess.check_output( shlex.split( command ), stderr=subprocess.STDOUT, cwd=path ).strip()

        command = "git symbolic-ref HEAD"
        branch = subprocess.check_output( shlex.split( command ), stderr=subprocess.STDOUT, cwd=path )
        branch = branch.replace( "refs/heads/", "" ).strip()

        command = "git config --get remote.origin.url"
        repository = subprocess.check_output( shlex.split( command ), stderr=subprocess.STDOUT, cwd=path ).strip()
        url = repository

    except subprocess.CalledProcessError:
        raise GitException("Not a Git working copy")

    return url, repository, branch, revision

