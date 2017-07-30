
#          Copyright Jamie Allsop 2015-2017
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   Log
#-------------------------------------------------------------------------------

import logging

from cuppa.colourise import as_error_label, as_warning_label, as_notice, as_emphasised

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

logger = logging.getLogger('cuppa')
logger.setLevel( logging.INFO )


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
        if logger.isEnabledFor( logging.TRACE ):
            return cls._trace_preamble
        elif logger.isEnabledFor( logging.DEBUG ):
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
        return result



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


def reset_logging_format():

    _log_handler.setFormatter( _formatter() )



def set_logging_level( level ):

    if level == "trace":
        logger.setLevel( logging.TRACE )
    elif level == "debug":
        logger.setLevel( logging.DEBUG )
    elif level == "exception":
        logger.setLevel( logging.EXCEPTION )
    elif level == "warn":
        logger.setLevel( logging.WARN )
    elif level == "error":
        logger.setLevel( logging.ERROR )
    else:
        logger.setLevel( logging.INFO )

