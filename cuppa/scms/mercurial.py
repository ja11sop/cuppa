
#          Copyright Jamie Allsop 2015-2015
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   Mercurial Source Control Management System
#-------------------------------------------------------------------------------

import subprocess
import shlex
import os
from exceptions import Exception


class MercurialException(Exception):
    def __init__(self, value):
        self.parameter = value
    def __str__(self):
        return repr(self.parameter)


def info( path ):
    if not path:
        raise MercurialException("No working copy path specified for calling hg commands with.")

    url        = None
    repository = None
    branch     = None
    revision   = None

    if not os.path.exists( os.path.join( path, ".hg" ) ):
        raise MercurialException("Not a Mercurial working copy")

    try:
        command = "hg summary"
        summary = subprocess.check_output( shlex.split( command ), stderr=subprocess.STDOUT, cwd=path ).strip().split('\n')

        revision = ""
        branch   = ""
        for line in summary:
            if not revision and line.startswith( 'parent: ' ):
                revision = line.replace( 'parent: ', '' )
                if branch:
                    break
            elif not branch and line.startswith( 'branch: ' ):
                branch = line.replace( 'branch: ', '' )
                if revision:
                    break

        command = "hg path"
        repository = subprocess.check_output( shlex.split( command ), stderr=subprocess.STDOUT, cwd=path ).strip().split('=')[1]
        url = repository

    except subprocess.CalledProcessError:
        raise MercurialException("Not a Mercurial working copy")

    return url, repository, branch, revision

