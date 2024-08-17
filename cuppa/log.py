
#          Copyright Jamie Allsop 2015-2024
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   Log
#-------------------------------------------------------------------------------

import logging
import six

from cuppa.colourise import as_error_label, as_warning_label, as_emphasised

logging.TRACE = 5

def trace( self, message, *args, **kwargs ):
    if self.isEnabledFor( logging.TRACE ):
        self._log( logging.TRACE, message, args, **kwargs )

logging.Logger.trace = trace

logging.EXCEPTION = 15

def exception( self, message, *args, **kwargs ):
    if self.isEnabledFor( logging.EXCEPTION ):
        self._log( logging.EXCEPTION, message, args, **kwargs )

logging.Logger.exception = exception

root_logger = logging.getLogger()

logger = logging.getLogger('cuppa')
root_logger.setLevel( logging.INFO )


_secrets = {}


class _formatter(logging.Formatter):

    _default_preamble = '%(name)s: %(module)s: [%(levelname)s]'
    _debug_preamble   = '%(name)s: %(module)s: %(funcName)s:%(lineno)d [%(levelname)s]'
    _trace_preamble   = '%(name)s: %(module)s: %(funcName)s: {path_and_line} [%(levelname)s]'.format( path_and_line='%(pathname)s:%(lineno)d' )

    _warn_fmt = None
    _error_fmt = None
    _critical_fmt = None

    @classmethod
    def fmt_with_preamble( cls, preamble ):
        return "{} %(message)s".format( preamble )


    @classmethod
    def preamble_from_level( cls ):
        if root_logger.isEnabledFor( logging.TRACE ):
            return cls._trace_preamble
        elif root_logger.isEnabledFor( logging.DEBUG ):
            return cls._debug_preamble
        else:
            return cls._default_preamble


    def __init__( self, fmt=None ):

        if not fmt:
            preamble = self.preamble_from_level()
            fmt      = self.fmt_with_preamble( preamble )

            self._warn_fmt     = self.fmt_with_preamble( as_warning_label( preamble ) )
            self._error_fmt    = self.fmt_with_preamble( as_error_label( preamble ) )
            self._critical_fmt = self.fmt_with_preamble( as_error_label( as_emphasised( preamble ) ) )

        logging.Formatter.__init__( self, fmt )


    def format( self, record ):

        orig_fmt = self._fmt
        if record.levelno == logging.WARN:
            self._fmt = self._warn_fmt
        elif record.levelno == logging.ERROR:
            self._fmt = self._error_fmt
        elif record.levelno == logging.CRITICAL:
            self._fmt = self._critical_fmt
        result = logging.Formatter.format( self, record )
        self._fmt = orig_fmt

        return mask_secrets( result )


def mask_secrets( message ):
    for secret, mask in six.iteritems(_secrets):
        message = message.replace( secret, mask )
    return message


def register_secret( secret, replacement="xxxxxxxx" ):
    _secrets[secret] = replacement


def unregister_secret( secret ):
    try:
        del _secrets[secret]
    except:
        pass


_log_handler = logging.StreamHandler()


def initialise_logging():

    logging.addLevelName( logging.TRACE,    'trace' )
    logging.addLevelName( logging.DEBUG,    'debug' )
    logging.addLevelName( logging.EXCEPTION,'exception' )
    logging.addLevelName( logging.INFO,     'info' )
    logging.addLevelName( logging.WARN,     'warn' )
    logging.addLevelName( logging.ERROR,    'error' )
    logging.addLevelName( logging.CRITICAL, 'critical' )

    _log_handler.setFormatter( _formatter() )

    logger.addHandler( _log_handler )
    logger.propagate = False
    root_logger.addHandler( logging.NullHandler() )


def enable_thirdparty_logging( enable ):
    if enable:
        root_logger.addHandler( _log_handler )


def reset_logging_format():
    _log_handler.setFormatter( _formatter() )


def set_logging_level( level ):

    if level == "trace":
        root_logger.setLevel( logging.TRACE )
    elif level == "debug":
        root_logger.setLevel( logging.DEBUG )
    elif level == "exception":
        root_logger.setLevel( logging.EXCEPTION )
    elif level == "warn":
        root_logger.setLevel( logging.WARN )
    elif level == "error":
        root_logger.setLevel( logging.ERROR )
    else:
        root_logger.setLevel( logging.INFO )

