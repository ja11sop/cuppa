
#          Copyright Jamie Allsop 2019-2024
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

import sys
import threading
import platform
import subprocess
import re
import os
import six
import psutil
from cuppa.core.profiles_inventory_cli import inject_inventory_ignore_errors
from cuppa.utility.python2to3 import as_str, as_byte_str, Exception


class LineConsumer(object):

    _empty_str = as_byte_str("")

    def __init__( self, call_readline, processor=None ):
        self.call_readline = call_readline
        self.processor = processor

    def __call__( self ):
        for line in iter( self.call_readline, self._empty_str ):
            line = as_str( line )
            if line:
                if self.processor:
                    line = self.processor( line )
                    if line:
                        sys.stdout.write( line )
                else:
                    sys.stdout.write( line )


class MaskSecrets(object):

    def __init__( self ):
        secret_regex = re.compile( r'.*TOKEN.*' )
        self.secrets = {}
        for key, val in six.iteritems(os.environ):
            if re.match( secret_regex, key ):
                value = as_str( val )
                # An empty value would make str.replace insert the key between every
                # character of the line. Unset variables are simply absent from os.environ.
                if value:
                    self.secrets[value] = key

    def mask( self, message ):
        for secret, mask in six.iteritems(self.secrets):
            message = message.replace( secret, mask )
        return message


def restrict_cpus():
    process = psutil.Process()
    core_count = psutil.cpu_count()
    with process.oneshot():
        if core_count <= 2:
            process.cpu_affinity( list(range(core_count)) )
        elif core_count <=4:
            process.cpu_affinity( list(range(core_count-1)) )
        elif core_count <=16:
            process.cpu_affinity( list(range(core_count-2)) )
        elif core_count <=32:
            process.cpu_affinity( list(range(core_count-3)) )
        else:
            process.cpu_affinity( list(range(core_count-4)) )


def _abort_scons( process ):
    """Stop the inner SCons process. Used when Ctrl-C is pressed again."""
    if not process:
        return
    try:
        if process.poll() is not None:
            return
    except Exception:
        pass
    try:
        process.kill()
    except Exception:
        pass


def run_scons( args_list ):

    masker = MaskSecrets()
    #print "The following tokens will be masked in output {}".format( str( sorted( six.itervalues(masker.secrets) ) ) )

    process = None
    stderr_thread = None

    try:
        args_list = inject_inventory_ignore_errors( args_list )
        # --cuppa-mode is a session marker for the inner SCons process (not persisted).
        # Token masking of this process's stdout/stderr is the pipe below, not that flag.
        args_list = ['scons'] + args_list + ['--cuppa-mode']

        if '--parallel' in args_list:
            restrict_cpus()

        stdout_processor = masker.mask
        stderr_processor = masker.mask

        kwargs = {}
        kwargs['stdout']    = subprocess.PIPE
        kwargs['stderr']    = subprocess.PIPE
        kwargs['close_fds'] = platform.system() == "Windows" and False or True

        use_shell = False
        propagated_env = os.environ

        process = subprocess.Popen(
            use_shell and " ".join(args_list) or args_list,
            **dict( kwargs, shell=use_shell, env=propagated_env )
        )

        stderr_consumer = LineConsumer( process.stderr.readline, stderr_processor )
        stdout_consumer = LineConsumer( process.stdout.readline, stdout_processor )

        stderr_thread = threading.Thread( target=stderr_consumer )
        stderr_thread.start()
        # The first Ctrl-C is delivered to this process and to SCons. SCons
        # stops scheduling new tasks; children are in their own session, so
        # they keep running. Keep reading so that drain is not stuck on a
        # full pipe. The inner process handles a second Ctrl-C by terminating
        # those children; a third stops SCons outright.
        interrupts = 0
        while True:
            try:
                stdout_consumer()
                break
            except KeyboardInterrupt:
                interrupts += 1
                if interrupts >= 3:
                    _abort_scons( process )
                    break
        stderr_thread.join()

        process.wait()
        return process.returncode

    except Exception:
        if process:
            process.kill()
        if stderr_thread:
            stderr_thread.join()
        return process.returncode

    except KeyboardInterrupt:
        _abort_scons( process )
        if process:
            try:
                process.wait()
            except Exception:
                pass
        if stderr_thread:
            stderr_thread.join()
        return process.returncode if process else 1

    return 1


def main():
    from cuppa.version import (
            argv_list_format,
            argv_offline,
            argv_wants_info,
            report_info,
    )
    args = sys.argv[1:]
    if argv_wants_info( args ):
        report_info(
                offline=argv_offline( args ),
                list_format=argv_list_format( args ),
        )
        sys.exit( 0 )
    sys.exit( run_scons( args ) )


if __name__ == "__main__":
    main()
