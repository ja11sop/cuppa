
#          Copyright Jamie Allsop 2011-2016
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


class SubversionException(Exception):
    def __init__(self, value):
        self.parameter = value
    def __str__(self):
        return repr(self.parameter)


def info( path ):
    if not path:
        raise SubversionException("No working copy path specified for calling svnversion with.")

    url        = None
    repository = None
    branch     = None
    revision   = None

    try:
        command = "svn info {}".format( path )
        svn_info = subprocess.check_output( shlex.split( command ), stderr=subprocess.STDOUT )
        url        = re.search( r'URL: ([^\s]+)', svn_info ).expand(r'\1')
        repository = re.search( r'Repository Root: ([^\s]+)', svn_info ).expand(r'\1')
        branch     = re.search( r'Relative URL: \^/([^\s]+)', svn_info ).expand(r'\1')
        revision   = re.search( r'Revision: (\d+)', svn_info ).expand(r'\1')
    except subprocess.CalledProcessError:
        raise SubversionException("Not a Subversion working copy")

    try:
        command = "svnversion -n {}".format( path )
        revision = subprocess.check_output( shlex.split( command ), stderr=subprocess.STDOUT )
    except subprocess.CalledProcessError:
        pass
    except OSError:
        logger.warn( "The {} binary is not available. Consider installing it.".format( as_warning("svnversion") ) )

    return url, repository, branch, revision

