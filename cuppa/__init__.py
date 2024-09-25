
#          Copyright Jamie Allsop 2011-2024
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

import logging
import traceback
from inspect import getframeinfo, stack


def log_exception( error, stack_trace, suppress=None ):

    from cuppa.log import logger
    from cuppa.colourise import as_info

    if not suppress:
        logger.fatal( "Cuppa terminated by exception [{}: {}]".format(
                    as_info( error.__class__.__name__ ),
                    as_info( str(error) )
        ) )
        if not logger.isEnabledFor( logging.EXCEPTION ):
            logger.warn( "Use {} (or above) to see the stack".format( as_info( "--verbosity=exception" ) ) )

    logger.exception( stack_trace )


def run( *args, **kwargs ):

    from cuppa.log import initialise_logging
    from cuppa.log import mask_secrets
    import SCons.Errors
    import cuppa.output

    caller = getframeinfo(stack()[1][0])
    sconstruct_path = caller.filename
    initialise_logging()
    try:
        import cuppa.construct
        cuppa.construct.run( sconstruct_path, *args, **kwargs )
    except SCons.Errors.BuildError as error:
        stack_trace = traceback.format_exc()
        log_exception( error, stack_trace )
        if len(error.args) >= 1:
            error.args = (mask_secrets(str(error.args[0])),) + error.args[1:]
        raise
    except SCons.Errors.StopError as error:
        stack_trace = traceback.format_exc()
        log_exception( error, stack_trace )
        if len(error.args) >= 1:
            error.args = (mask_secrets(str(error.args[0])),) + error.args[1:]
        raise
    except SCons.Errors.UserError as error:
        stack_trace = traceback.format_exc()
        log_exception( error, stack_trace )
        if len(error.args) >= 1:
            error.args = (mask_secrets(str(error.args[0])),) + error.args[1:]
        raise
    except Exception as error:
        stack_trace = traceback.format_exc()
        log_exception( error, stack_trace )
        if len(error.args) >= 1:
            error.args = (mask_secrets(str(error.args[0])),) + error.args[1:]
        raise SCons.Errors.StopError( error )


def add_option( *args, **kwargs ):
    import cuppa.core.options
    cuppa.core.options.add_option( *args, **kwargs )


import cuppa.build_with_location

from cuppa.build_with_location import location_dependency
from cuppa.build_with_location import location_dependency as header_library_dependency

from cuppa.build_with_package import package_dependency

import cuppa.packages.boost_package

import cuppa.build_with_profile

from cuppa.build_with_profile import profile

