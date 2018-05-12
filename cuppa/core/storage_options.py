#          Copyright Jamie Allsop 2018-2018
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   Storage Options
#-------------------------------------------------------------------------------

# Python Standard
import os

# Cuppa
from cuppa.colourise import as_error
from cuppa.log import logger



class default(object):

    build_root    = '_build'
    download_root = '_cuppa'
    cache_root    = '~/_cuppa/_cache'



def add_storage_options( add_option ):

    add_option( '--build-root', type='string', nargs=1, action='store',
                            dest='build_root',
                            help="The root directory for build output. If not specified"
                                 " then " +  default.build_root + " is used" )

    add_option( '--download-root', type='string', nargs=1, action='store',
                            dest='download_root',
                            help="The root directory for downloading external libraries to."
                                 " If not specified then " +  default.download_root + " is used" )

    add_option( '--cache-root', type='string', nargs=1, action='store',
                            dest='cache_root',
                            help="The root directory for caching downloaded external archived libraries."
                                 " If not specified then " +  default.cache_root + " is used" )



def process_storage_options( cuppa_env ):

        def get_normal_path( option, defaults_to ):
            path = cuppa_env.get_option( option, default=defaults_to )
            return os.path.normpath( os.path.expanduser( path ) )

        cuppa_env['build_root']     = get_normal_path( 'build_root', default.build_root )
        cuppa_env['abs_build_root'] = os.path.abspath( cuppa_env['build_root'] )
        cuppa_env['download_root']  = get_normal_path( 'download_root', default.download_root )
        cuppa_env['cache_root']     = get_normal_path( 'cache_root', default.cache_root )

        if not os.path.exists( cuppa_env['cache_root'] ):
            try:
                os.makedirs( cuppa_env['cache_root'] )
            except os.error as e:
                logger.error( "Creating cache_root directory [{}] failed with error: {}"
                             .format( cuppa_env['cache_root'], as_error(str(e)) ) )
                raise
