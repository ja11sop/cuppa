#          Copyright Jamie Allsop 2014-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   version.py
#-------------------------------------------------------------------------------

from __future__ import print_function

import json
import sys

try:
    import xmlrpclib
except ImportError:
    import xmlrpc.client as xmlrpclib

try:
    from packaging.version import parse as parse_version
except ImportError:  # pragma: no cover
    from pkg_resources import parse_version

from cuppa.colourise import as_info, as_warning, as_emphasised
from cuppa.log import logger
from cuppa.utility.version import get_version


def probe_pypi_latest():
    """Return the latest PyPI cuppa version string, or None on any failure."""
    try:
        pypi = xmlrpclib.ServerProxy( 'http://pypi.python.org/pypi' )
        releases = pypi.package_releases( 'cuppa' )
        if releases:
            return releases[0]
    except Exception:
        pass
    return None


def check_current_version( offline ):

    installed_version = get_version()
    logger.info( "cuppa: version {}".format( as_info( installed_version ) ) )
    if not offline:
        latest_available = probe_pypi_latest()
        if latest_available is not None:
            if parse_version( installed_version ) < parse_version( latest_available ):
                logger.warn( "Newer version [{}] available. Upgrade using \"{}\"\n".format(
                        as_warning( latest_available ),
                        as_emphasised( "pip install -U cuppa" )
                ) )


def argv_wants_info( argv ):
    return '--info' in argv


def argv_offline( argv ):
    return '--offline' in argv


def argv_list_format( argv, default='text' ):
    for index, arg in enumerate( argv ):
        if arg.startswith( '--list-format=' ):
            return arg.split( '=', 1 )[1] or default
        if arg == '--list-format' and index + 1 < len( argv ):
            return argv[index + 1]
    return default


def report_info( offline=False, list_format='text', out=None ):
    """Print cuppa version for ``--info`` (no project / toolchain side effects).

    Text mode writes ``cuppa <version>`` only. JSON includes ``cuppa_version``,
    ``offline``, and ``pypi_latest`` when a probe succeeds and offline is false.
    """
    if out is None:
        out = sys.stdout
    installed_version = get_version()
    offline = bool( offline )
    list_format = list_format or 'text'

    pypi_latest = None
    if not offline:
        pypi_latest = probe_pypi_latest()

    if list_format == 'json':
        payload = {
            'cuppa_version': installed_version,
            'offline': offline,
        }
        if pypi_latest is not None:
            payload['pypi_latest'] = pypi_latest
        print( json.dumps( payload, indent=4, sort_keys=True ), file=out )
        return

    print( "cuppa {}".format( installed_version ), file=out )
