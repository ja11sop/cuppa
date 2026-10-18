
#          Copyright Jamie Allsop 2014-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   Options
#-------------------------------------------------------------------------------

# Scons
import SCons.Script


# Tip ``cuppa.add_option`` registrations (project-only). Nested cascade sessions
# drop these — the child sconstruct never registered them.
_tip_local_flags: dict[str, bool] = {}


def reset_tip_local_options() -> None:
    """Clear tip-local option tracking (tests / process boundaries)."""
    _tip_local_flags.clear()


def _option_strings( args ) -> list[str]:
    return [
            arg for arg in args
            if isinstance( arg, str ) and arg.startswith( "-" )
    ]


def _option_takes_separate_value( kwargs: dict ) -> bool:
    """True when the following argv token is this option's value."""
    action = kwargs.get( "action" )
    if action in ( "store_true", "store_false", "help", "count" ):
        return False
    nargs = kwargs.get( "nargs" )
    if nargs in ( 0, ):
        return False
    # ``store`` / typed options / nargs>=1 / callback with a value.
    if action in ( None, "store", "append", "callback" ) or kwargs.get( "type" ):
        if nargs == "?" or nargs == "*":
            # Optional value — still skip a following non-flag token when present;
            # tip_forward_args only skips when the flag is in takes_value and the
            # exact form (no ``=``) is used, matching dependency-scoped drops.
            return True
        return True
    return False


def _register_option( args, kwargs, *, tip_local: bool ) -> None:
    SCons.Script.AddOption( *args, **kwargs )
    takes_value = _option_takes_separate_value( kwargs )
    for flag in _option_strings( args ):
        # Normalise short forms out of tip-local tracking (tips use long opts).
        if not flag.startswith( "--" ):
            continue
        if tip_local:
            _tip_local_flags[ flag ] = takes_value
        else:
            # Cuppa-owned registration via this wrapper must not linger as tip-local
            # if a prior tip registration reused the same string (tests).
            _tip_local_flags.pop( flag, None )


def add_option( *args, **kwargs ):
    """Register a Cuppa-owned CLI option (not dropped from nest argv)."""
    _register_option( args, kwargs, tip_local=False )


def add_tip_option( *args, **kwargs ):
    """Register a tip/project ``cuppa.add_option`` flag (dropped from nest argv)."""
    _register_option( args, kwargs, tip_local=True )


def tip_local_option_flags() -> frozenset[str]:
    """Long-option strings the tip registered via ``cuppa.add_option``."""
    return frozenset( _tip_local_flags.keys() )


def tip_local_option_takes_value() -> frozenset[str]:
    """Tip-local flags whose following argv token is the option value."""
    return frozenset(
            flag for flag, takes_value in _tip_local_flags.items() if takes_value
    )


def command_line_option( option ):
    """Return only an explicitly parsed command-line value, or ``None``."""
    try:
        value = SCons.Script.GetOption( option )
    except AttributeError:
        return None
    if value is None or value == '':
        return None
    return value


class list_parser(object):

    def __init__( self, attribute ):
        self._attribute = attribute

    def __call__( self, option, opt, value, parser):
        setattr( parser.values, self._attribute, value.split(',') )
