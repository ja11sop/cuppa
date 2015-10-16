
#          Copyright Jamie Allsop 2015-2015
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   Log
#-------------------------------------------------------------------------------

import logging

from cuppa.colourise import as_error_label, as_warning_label, as_emphasised

logging.TRACE = 5

def trace( self, message, *args, **kwargs ):
    if self.isEnabledFor( logging.TRACE ):
        self._log( logging.TRACE, message, args, **kwargs )

logging.Logger.trace = trace

logger = logging.getLogger('cuppa')
logger.setLevel( logging.INFO )


class _formatter(logging.Formatter):

    @classmethod
    def warn_fmt( cls ):
        return "{} %(message)s".format( as_warning_label("%(name)s: %(module)s: [%(levelname)s]") )

    @classmethod
    def error_fmt( cls ):
        return "{} %(message)s".format( as_error_label("%(name)s: %(module)s: [%(levelname)s]") )

    @classmethod
    def critical_fmt( cls ):
        return "{} %(message)s".format( as_error_label( as_emphasised( "%(name)s: %(module)s: [%(levelname)s]") ) )

    def __init__( self, fmt="%(name)s: %(module)s: [%(levelname)s] %(message)s" ):
        logging.Formatter.__init__( self, fmt )
        self._warn_fmt = self.warn_fmt()
        self._error_fmt = self.error_fmt()
        self._critical_fmt = self.critical_fmt()

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
    elif level == "warn":
        logger.setLevel( logging.WARN )
    elif level == "error":
        logger.setLevel( logging.ERROR )
    else:
        logger.setLevel( logging.INFO )

