
#          Copyright Jamie Allsop 2017-2020
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   Bazaar Source Control Management System
#-------------------------------------------------------------------------------

import subprocess
import shlex
import os
import re
from cuppa.utility.python2to3 import as_str, Exception


class Bazaar:

    class Error(Exception):
        def __init__(self, value):
            self.parameter = value
        def __str__(self):
            return repr(self.parameter)


    @classmethod
    def vc_type( cls ):
        return "bzr"


    @classmethod
    def binary( cls ):
        return "bzr"


    @classmethod
    def remote_branch_exists( cls, repository, branch ):
        #TODO
        return False


    @classmethod
    def remote_default_branch( cls, repository ):
        #TODO
        return None


    @classmethod
    def info( cls, path ):
        if not path:
            raise cls.Error("No working copy path specified for calling bzr commands with.")

        url        = None
        repository = None
        branch     = None
        remote     = None
        revision   = None

        if not os.path.exists( os.path.join( path, ".bzr" ) ):
            raise cls.Error("Not a Bazaar working copy")

        try:
            command = "{bzr} nick".format( bzr=cls.binary() )
            branch = as_str( subprocess.check_output( shlex.split( command ), stderr=subprocess.STDOUT, cwd=path ).strip() )

            command = "{bzr} revno".format( bzr=cls.binary() )
            revision = as_str( subprocess.check_output( shlex.split( command ), stderr=subprocess.STDOUT, cwd=path ).strip() )

            command = "{bzr} info".format( bzr=cls.binary() )
            bzr_info = as_str( subprocess.check_output( shlex.split( command ), stderr=subprocess.STDOUT, cwd=path ).strip() )
            repository_match = re.search( r'shared repository: (?P<repository>.*)\n', bzr_info )
            if repository_match:
                repository = repository_match.group('repository')

            url_match = re.search( r'checkout of branch: (?P<url>.*)\n', bzr_info )
            if url_match:
                url = url_match.group('url')

        except subprocess.CalledProcessError:
            raise cls.Error("Not a Bazaar working copy")

        except OSError:
            raise cls.Error("Bazaar binary [{bzr}] is not available".format(
                    bzr=cls.binary()
            ) )

        return url, repository, branch, remote, revision

