
#          Copyright Jamie Allsop 2019-2019
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

import sys
import threading
import platform
import subprocess
import re
import os


class AutoFlushFile(object):

    def __init__( self, f ):
        self.f = f

    def flush( self ):
        self.f.flush()

    def write( self, x ):
        self.f.write(x)
        self.f.flush()


class LineConsumer(object):

    def __init__( self, call_readline, processor=None ):
        self.call_readline = call_readline
        self.processor = processor

    def __call__( self ):
        for line in iter( self.call_readline, "" ):
            line = line.rstrip()
            if line:
                if self.processor:
                    line = self.processor( line )
                    if line:
                        print line
                else:
                    print line


class MaskSecrets(object):

    def __init__( self ):
        secret_regex = re.compile( r'.*TOKEN.*' )
        self.secrets = {}
        for key, val in os.environ.iteritems():
            if re.match( secret_regex, key ):
                self.secrets[val] = key

    def mask( self, message ):
        for secret, mask in self.secrets.iteritems():
            message = message.replace( secret, mask )
        return message


def run_scons( args_list ):

    masker = MaskSecrets()
    #print "The following tokens will be masked in output {}".format( str( sorted( masker.secrets.itervalues() ) ) )

    process = None
    stderr_thread = None

    try:
        args_list = ['scons'] + args_list + ['--cuppa-mode']

        stdout_processor = masker.mask
        stderr_processor = masker.mask

        sys.stdout = AutoFlushFile( sys.stdout )
        sys.stderr = AutoFlushFile( sys.stderr )

        kwargs = {}
        kwargs['stdout']    = subprocess.PIPE
        kwargs['stderr']    = subprocess.PIPE
        kwargs['close_fds'] = platform.system() == "Windows" and False or True

        use_shell = False

        process = subprocess.Popen(
            use_shell and " ".join(args_list) or args_list,
            **dict( kwargs, shell=use_shell )
        )

        stderr_consumer = LineConsumer( process.stderr.readline, stderr_processor )
        stdout_consumer = LineConsumer( process.stdout.readline, stdout_processor )

        stderr_thread = threading.Thread( target=stderr_consumer )
        stderr_thread.start()
        stdout_consumer();
        stderr_thread.join()

        process.wait()
        return process.returncode

    except Exception as e:
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
