
#          Copyright Jamie Allsop 2011-2024
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

import logging
import traceback
from inspect import getframeinfo, stack


def log_exception( error, stack_trace, suppress=None ):

    from cuppa.log import logger
    from cuppa.colourise import as_error, as_info
    from cuppa.utility.storage import highlight_values

    if not suppress:
        name = error.__class__.__name__
        message = str( error )
        # Operator refusals (StopError / UserError): plain prose with error-coloured
        # ``[values]`` and bare ``--flags``. Other exceptions stay info-coloured.
        if name in ( "StopError", "UserError" ):
            shown_name = as_error( name )
            shown_message = highlight_values( message, as_error )
        else:
            shown_name = as_info( name )
            shown_message = as_info( message )
        logger.fatal( "Cuppa terminated by exception [{}: {}]".format(
                    shown_name,
                    shown_message,
        ) )
        if not logger.isEnabledFor( logging.EXCEPTION ):
            logger.warn( "Use {} (or above) to see the stack".format( as_info( "--verbosity=exception" ) ) )

    logger.exception( stack_trace )


def _mask_and_colour_operator_error( error ):
    """Mask secrets and highlight ``[values]`` / ``--flags`` for SCons' re-raise line."""
    from cuppa.colourise import as_error
    from cuppa.log import mask_secrets
    from cuppa.utility.storage import highlight_values

    if len( error.args ) < 1:
        return
    text = mask_secrets( str( error.args[0] ) )
    error.args = ( highlight_values( text, as_error ), ) + error.args[1:]


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
        _mask_and_colour_operator_error( error )
        raise
    except SCons.Errors.UserError as error:
        stack_trace = traceback.format_exc()
        log_exception( error, stack_trace )
        _mask_and_colour_operator_error( error )
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

from cuppa.build_with_conan import conan_deps
from cuppa.build_with_conan import conan_dependency

import cuppa.packages.boost_package

import cuppa.build_with_profile

from cuppa.build_with_profile import profile

