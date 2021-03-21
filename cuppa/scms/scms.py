
#          Copyright Jamie Allsop 2020-2020
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   Source Control Management Systems
#-------------------------------------------------------------------------------

from . import subversion, git, mercurial, bazaar

from cuppa.log import logger
from cuppa.colourise import as_notice, as_info


scms_systems = {
    'git': git.Git,
    'hg' : mercurial.Mercurial,
    'bzr': bazaar.Bazaar,
    'svn': subversion.Subversion,
}


def get_scms( vc_type ):
    if vc_type in scms_systems:
        return scms_systems[vc_type]
    return None


def get_current_rev_info( path ):
    logger.debug( "Checking current revision info for [{}]...".format( as_info(path) ) )
    rev_info = None
    for scm_system in scms_systems.values():
        try:
            rev_info = scm_system.info( path )
            break;
        except:
            continue
    if rev_info:
        url, repo, branch, remote, rev = rev_info[0], rev_info[1], rev_info[2], rev_info[3], rev_info[4]
        logger.debug( "Path [{path}] is under version control as"
                      " URL [{url}], Repository [{repo}], Branch [{branch}],"
                      " Remote [{remote}], Revision [{rev}]".format(
                    path   = as_notice(path),
                    url    = url and as_info(url) or "<None>",
                    repo   = repo and as_info(repo) or "<None>",
                    branch = branch and as_info(branch) or "<None>",
                    remote = remote and as_info(remote) or "<None>",
                    rev    = rev and as_info(rev) or "<None>"
        ) )
        return url, repo, branch, remote, rev
    return None, None, None, None, None
