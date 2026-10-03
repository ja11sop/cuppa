#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

"""Build-transcript options and their interactions.

Normal and terse are one boolean choice. Diagnostic filtering, colour, and
the spawn backend are separate controls. Registration, precedence,
validation, and the resolved environment values live here so callers do not
reconstruct that matrix.
"""

import SCons.Errors

import cuppa.core.options
from cuppa.log import logger, reset_logging_format


def add_output_options( add_option ):
    add_option( '--raw-output', dest='raw_output', action='store_true',
                            help="Disable Cuppa colour and do not install the spawn processor. "
                                 "Use --scons-output to skip only the processor and keep colour" )

    add_option( '--scons-output', dest='scons_output', action='store_true',
                            help="Do not install Cuppa's spawn processor, so SCons launches "
                                 "child processes itself. Cuppa colour on logs and reports stays. "
                                 "Progress nodes and the cuppa token mask still apply. "
                                 "Do not combine with --minimal-output or --terse-output" )

    add_option( '--standard-output', dest='standard_output', action='store_true',
                            help="Perform standard output processing but not colourisation of output" )

    add_option( '--minimal-output', dest='minimal_output', action='store_true',
                            help="Show only errors and warnings in the output. Requires Cuppa's "
                                 "spawn processor; refused with --raw-output or --scons-output. "
                                 "Ignored with a warning when --native-output is set" )

    add_option( '--native-output', dest='native_output', action='store_true',
                            help="Pass toolchain diagnostic lines through with the tool's own "
                                 "colour. Not a third transcript: works with --normal-output or "
                                 "--terse-output. Enables toolchain colour flags and skips Cuppa "
                                 "re-colouring. Refused with --raw-output or --scons-output" )

    add_option( '--normal-output', dest='normal_output', action='store_true',
                            help="Print the normal transcript. Overrides --terse-output, including "
                                 "a choice saved in a configuration file. Do not combine the two" )

    add_option( '--terse-output', dest='terse_output', action='store_true', default=None,
                            help="On a clean tool run, print one success line and hide the command. "
                                 "On a warning or failure, print the command and the processed output. "
                                 "Does not imply --minimal-output. Refused with "
                                 "--raw-output or --scons-output. [progress] checkpoints stay under -Q. "
                                 "Do not combine with --normal-output" )

    add_option( '--terse-output-show-actions', dest='terse_output_show_actions', action='store_true',
                            help="With --terse-output, also print the raw SCons action after each "
                                 "status line. For refining the action names. Requires --terse-output" )

    add_option( '--show-test-cases', dest='show_test_cases', action='store_true',
                            help="With --terse-output, print a line for every test case, "
                                 "including those that passed. Requires --terse-output. "
                                 "Failing cases are shown either way" )

    add_option( '--ignore-duplicates', dest='ignore_duplicates', action='store_true',
                            help="Do not show repeated errors or warnings" )

    add_option( '--show-test-output', dest='show-test-output', action='store_true',
                            help="When executing tests display all output to stdout and stderr as appropriate" )

    add_option( '--suppress-process-output', dest='suppress-process-output', action='store_true',
                            help="When executing processes suppress all output to stdout and stderr" )


def skips_spawn_processor( env ):
    """True when SCons' own SPAWN must stay in place."""
    return bool( env.get( 'raw_output' ) or env.get( 'scons_output' ) )


def _terse_only_flag( env, name, message ):
    """Resolve a modifier that only applies to the terse transcript."""
    if not env.get_option( name ):
        return False
    if env.get( 'terse_output' ):
        return True
    if cuppa.core.options.command_line_option( name ) is True:
        raise SCons.Errors.StopError( message )
    return False


def process_output_options( env ):
    """Resolve output options onto ``env`` and validate their combination."""
    env['raw_output']      = bool( env.get_option( 'raw_output' ) )
    env['scons_output']    = bool( env.get_option( 'scons_output' ) )
    env['standard_output'] = bool( env.get_option( 'standard_output' ) )
    env['minimal_output']  = bool( env.get_option( 'minimal_output' ) )
    env['native_output']   = bool( env.get_option( 'native_output' ) )
    env['ignore_duplicates'] = bool( env.get_option( 'ignore_duplicates' ) )
    env['show_test_output'] = bool( env.get_option( 'show-test-output' ) )
    env['suppress_process_output'] = bool(
            env.get_option( 'suppress-process-output' )
    )
    normal_requested = cuppa.core.options.command_line_option( 'normal_output' ) is True
    terse_requested = cuppa.core.options.command_line_option( 'terse_output' ) is True
    if normal_requested and terse_requested:
        raise SCons.Errors.StopError(
                "Invalid option combination (--normal-output and --terse-output)"
        )
    env['terse_output'] = (
            False if normal_requested else bool( env.get_option( 'terse_output' ) )
    )

    env['show_test_cases'] = _terse_only_flag(
            env,
            'show_test_cases',
            "--show-test-cases requires --terse-output",
    )
    env['terse_output_show_actions'] = _terse_only_flag(
            env,
            'terse_output_show_actions',
            "--terse-output-show-actions requires --terse-output",
    )

    # Native passthrough cannot classify lines the way --minimal-output needs.
    if env['native_output'] and env['minimal_output']:
        logger.warn(
                "--minimal-output is ignored with --native-output "
                "(passthrough has no Cuppa error/warning filter)"
        )
        env['minimal_output'] = False

    processor_flags = []
    if env['minimal_output']:
        processor_flags.append( '--minimal-output' )
    if env['terse_output']:
        processor_flags.append( '--terse-output' )
    if env['native_output']:
        processor_flags.append( '--native-output' )
    if processor_flags and skips_spawn_processor( env ):
        blockers = []
        if env['raw_output']:
            blockers.append( '--raw-output' )
        if env['scons_output']:
            blockers.append( '--scons-output' )
        raise SCons.Errors.StopError(
                "Invalid option combination ({} and {})".format(
                        " and ".join( processor_flags ),
                        " and ".join( blockers ),
                )
        )

    if not env['raw_output'] and not env['standard_output']:
        env.colouriser().enable()
        reset_logging_format()


def is_saveable( key, value ):
    """Whether an output option value carries an explicit choice."""
    if key == 'normal_output':
        return False
    return not ( key == 'terse_output' and value is None )


def update_saved_options( options ):
    """Persist the normal alias as the canonical false terse choice."""
    if cuppa.core.options.command_line_option( 'normal_output' ) is True:
        options['terse_output'] = False
    options.pop( 'normal_output', None )
    return options
