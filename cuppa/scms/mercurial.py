
#          Copyright Jamie Allsop 2015-2019
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   Mercurial Source Control Management System
#-------------------------------------------------------------------------------

import subprocess
import shlex
import os
import sys

from cuppa.utility.python2to3 import Exception


class Mercurial:

    class Error(Exception):
        def __init__(self, value):
            self.parameter = value
        def __str__(self):
            return repr(self.parameter)


    @classmethod
    def vc_type( cls ):
        return "hg"


    @classmethod
    def binary( cls ):
        return "hg"


    @classmethod
    def info( cls, path ):
        if not path:
            raise cls.Error("No working copy path specified for calling hg commands with.")

        url        = None
        repository = None
        branch     = None
        remote     = None
        revision   = None

        if not os.path.exists( os.path.join( path, ".hg" ) ):
            raise cls.Error("Not a Mercurial working copy")

        try:
            command = "{hg} summary".format( hg=cls.binary() )
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

            command = "{hg} path".format( hg=cls.binary() )
            repository = subprocess.check_output( shlex.split( command ), stderr=subprocess.STDOUT, cwd=path ).strip().split('=')[1]
            url = repository

        except subprocess.CalledProcessError:
            raise cls.Error("Not a Mercurial working copy")

        except OSError:
            raise cls.Error("Mercurial binary [{hg}] is not available".format(
                    hg=cls.binary()
            ) )

        return url, repository, branch, remote, revision

