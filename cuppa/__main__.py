
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
                self.secrets[as_str(val)] = key

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


def run_scons( args_list ):

    masker = MaskSecrets()
    #print "The following tokens will be masked in output {}".format( str( sorted( six.itervalues(masker.secrets) ) ) )

    process = None
    stderr_thread = None

    try:
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
        stdout_consumer();
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
        if process:
            process.terminate()
            process.wait()
        if stderr_thread:
            stderr_thread.join()
        return process.returncode

    return 1


def main():
    sys.exit( run_scons( sys.argv[1:] ) )


if __name__ == "__main__":
    main()
