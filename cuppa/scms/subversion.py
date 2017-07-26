
#          Copyright Jamie Allsop 2011-2017
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   Subversion Source Control Management System
#-------------------------------------------------------------------------------

import subprocess
import shlex
import re
from exceptions import Exception

from cuppa.log import logger
from cuppa.colourise import as_warning


class Subversion:


    class Error(Exception):
        def __init__(self, value):
            self.parameter = value
        def __str__(self):
            return repr(self.parameter)


    @classmethod
    def vc_type( cls ):
        return "svn"


    @classmethod
    def binary( cls ):
        return "svn"


    @classmethod
    def info( cls, path ):
        if not path:
            raise cls.Error("No working copy path specified for calling svnversion with.")

        url        = None
        repository = None
        branch     = None
        revision   = None

        try:
            command = "{svn} info {path}".format( svn=cls.binary(), path=path )
            svn_info = subprocess.check_output( shlex.split( command ), stderr=subprocess.STDOUT )
            url        = re.search( r'URL: ([^\s]+)', svn_info ).expand(r'\1')
            repository = re.search( r'Repository Root: ([^\s]+)', svn_info ).expand(r'\1')
            branch     = re.search( r'Relative URL: \^/([^\s]+)', svn_info ).expand(r'\1')
            revision   = re.search( r'Revision: (\d+)', svn_info ).expand(r'\1')
        except subprocess.CalledProcessError:
            raise cls.Error("Not a Subversion working copy")
        except OSError:
            raise cls.Error("Subversion binary [{svn}] is not available".format(
                    svn=as_warning( cls.binary() )
            ) )

        try:
            command = "svnversion -n {path}".format( path=path )
            revision = subprocess.check_output( shlex.split( command ), stderr=subprocess.STDOUT )
        except subprocess.CalledProcessError:
            pass
        except OSError:
            logger.warn( "The {svnversion} binary is not available. Consider installing it.".format( svnversion=as_warning("svnversion") ) )

        return url, repository, branch, revision

