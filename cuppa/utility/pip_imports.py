#          Copyright Jamie Allsop 2020-2022
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   pip_imports
#-------------------------------------------------------------------------------

from cuppa.colourise import as_notice, as_info
from cuppa.log import logger


def pip_version_gte_25_1_0():
    try:
        import pip
        major_version = int(pip.__version__.split('.')[0])
        minor_version = int(pip.__version__.split('.')[1])
        return major_version >= 25 and minor_version >=1
    except ImportError:
        return False


def pip_version_gte_22_0_0():
    try:
        import pip
        major_version = int(pip.__version__.split('.')[0])
        return major_version >= 22
    except ImportError:
        return False


def pip_version_gt_20_0_0():
    if pip_version_gte_22_0_0():
        return True
    try:
        import pip._internal.network.download
        #print( "PIP Version > 20" )
        return True
    except ImportError:
        return False


def pip_version_gt_19_3_1():
    if pip_version_gt_20_0_0():
        return True
    try:
        from pip._internal.vcs import is_url
        #print( "PIP Version > 19" )
        return True
    except ImportError:
        return False


def pip_version_gt_10_0_0():
    if pip_version_gt_19_3_1():
        return True
    try:
        from pip._internal.download import is_url
        #print( "PIP Version > 10" )
        return True
    except ImportError:
        return False


def verbosity_level():
    import logging
    log_level = logger.getEffectiveLevel()
    if log_level == logging.TRACE:
        return 2
    elif log_level == logging.DEBUG:
        return 1
    elif log_level == logging.EXCEPTION:
        return 0
    elif log_level == logging.INFO:
        return 0
    elif log_level == logging.WARN:
        return -1
    elif log_level == logging.ERROR:
        return -2
    elif log_level == logging.CRITICAL:
        return -3
    return 0


if pip_version_gt_10_0_0():

    import pip._internal.vcs as pip_vcs
    import pip._internal.exceptions as pip_exceptions

    if pip_version_gte_25_1_0():
        import pip._internal.req.req_install as pip_req_install
    if pip_version_gt_20_0_0():
        import pip._internal.network.download as pip_download
    else:
        import pip._internal.download as pip_download

    if pip_version_gt_19_3_1():
        from pip._internal.req.constructors import is_archive_file as pip_is_archive_file
        from pip._internal.vcs import is_url as pip_is_url
        from pip._internal.utils.misc import hide_url as pip_hide_url

        def obtain( vcs_backend, dest, url ):
            if pip_version_gte_22_0_0():
                return vcs_backend.obtain( dest, pip_hide_url( url ), verbosity_level() )
            else:
                return vcs_backend.obtain( dest, pip_hide_url( url ) )

    else:
        from pip._internal.download import is_archive_file as pip_is_archive_file
        from pip._internal.download import is_url as pip_is_url

        def pip_hide_url( ignored ):
            pass

        def obtain( vcs_backend, dest, url ):
            return vcs_backend.obtain( dest )


    def get_url_rev( vcs_backend ):
        url_rev_auth = vcs_backend.get_url_rev_and_auth( vcs_backend.url )
        return url_rev_auth[0], url_rev_auth[1]


    def update( vcs_backend, dest, rev_options ):
        return vcs_backend.update( dest, vcs_backend.url, rev_options )


    def make_rev_options( vc_type, vcs_backend, url, rev, local_remote ):
        logger.debug( "vc_type={vc_type}, url={url}, rev={rev}, local_remote={local_remote}".format(
            vc_type = as_info( str(vc_type) ),
            url = as_notice( str(url) ),
            rev = as_notice( str(rev) ),
            local_remote = as_notice( str(local_remote) )
        ) )
        if vc_type == 'git':
            if rev:
                return vcs_backend.make_rev_options( rev=rev )
            #elif local_remote:
                #return vcs_backend.make_rev_options( rev=local_remote )
        elif vc_type == 'hg' and rev:
            return vcs_backend.make_rev_options( rev=rev )
        elif vc_type == 'bzr' and rev:
            return vcs_backend.make_rev_options( rev=rev )
        return vcs_backend.make_rev_options()

else:
    try:
        import pip.vcs as pip_vcs
        import pip.download as pip_download
        import pip.exceptions as pip_exceptions
        from pip.download import is_url as pip_is_url
        from pip.download import is_archive_file as pip_is_archive_file
    except ImportError as error:
        logger.error( "Cuppa requires Python pip. Please make sure it is installed" )
        raise error


    def pip_hide_url( ignored ):
        pass


    def obtain( vcs_backend, dest, url ):
        return vcs_backend.obtain( dest, pip_hide_url( url ) )


    def get_url_rev( vcs_backend ):
        return vcs_backend.get_url_rev()


    def update( vcs_backend, dest, rev_options ):
        return vcs_backend.update( dest, rev_options )


    def make_rev_options( vc_type, vcs_backend, url, rev, local_remote ):
        if vc_type == 'git':
            if rev:
                return [rev]
            elif local_remote:
                return [local_remote]
        elif vc_type == 'hg' and rev:
            return vcs_backend.get_rev_options( url, rev )
        elif vc_type == 'bzr' and rev:
            return ['-r', rev]
        return []
