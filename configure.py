
#          Copyright Jamie Allsop 2013-2014
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   Construct
#-------------------------------------------------------------------------------

# standard library Imports
import os

# Scons Imports
import SCons.Script


class Configure(object):

    def __init__( self, env, conf_path="configure.conf", callback=None ):
        self._env = env
        self._conf_path = conf_path
        self._callback = callback
        env['configured_options'] = {}
        self._colouriser = env['colouriser']
        self._configured_options = {}


    def load( self ):
        self._configure   = self._env.get_option( 'configure' )
        self._clean       = self._env.get_option( 'clean' )
        self._unconfigure = self._configure and self._clean

        if self._unconfigure:
            self._configure = False
            print "configure: {}".format( self._colouriser.colour( 'notice', "unconfigure requested..." ) )
            if os.path.exists( self._conf_path ):
                print "configure: removing configure file [{}]".format(
                        self._colouriser.colour( 'warning', self._conf_path ) )
                os.remove( self._conf_path )
            else:
                print "configure: configure file [{}] does not exist. Unconfigure not needed".format(
                        self._colouriser.colour( 'warning', self._conf_path ) )
            return
        elif self._configure:
            print "configure: {}".format( self._colouriser.colour( 'notice', "configure requested..." ) )

        if not self._configure:
            configured_options = self._load_conf()
            self._env['configured_options'] = configured_options
            self._env['default_options'].update( configured_options )


    def save( self ):
        if self._configure and not self._clean:
            self._save_conf()


    def configure( self, env ):
        if self._configure and self._callback:
            configure = SCons.Script.Configure( env )
            self._callback( configure )
            env = configure.Finish()


    def _load_conf( self ):
        settings = {}
        if os.path.exists(self._conf_path):
            with open(self._conf_path) as config_file:
                print "configure: configure file [{}] exists. Load stored settings...".format(
                        self._colouriser.colour( 'warning', self._conf_path ) )
                for line in config_file.readlines():
                    setting = tuple( l.strip() for l in line.split('=', 1) )
                    print "configure: loading [{}] = [{}]".format(
                            self._colouriser.colour( 'warning', setting[0] ),
                            self._colouriser.colour( 'warning', str(setting[1]) ) )
                    settings[setting[0]] = setting[1]
        if settings:
            print "configure: load complete"
        else:
            print "configure: no settings to load, skipping configure"
        return settings


    def _save_conf( self ):
        print "configure: {}".format( self._colouriser.colour( 'notice', "save current settings..." ) )
        with open(self._conf_path, "w") as config_file:
            for key, value in SCons.Script.Main.OptionsParser.values.__dict__.items():
                if not key.startswith("__") and not key =='configure':
                    print "configure: saving [{}] = [{}]".format(
                            self._colouriser.colour( 'notice', key ),
                            self._colouriser.colour( 'notice', str(value) ) )
                    config_file.write( "{} = {}\n".format( key, value ) )
        print "configure: {}".format( self._colouriser.colour( 'notice', "save complete" ) )
