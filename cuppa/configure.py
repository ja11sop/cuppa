
#          Copyright Jamie Allsop 2013-2015
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   Configure
#-------------------------------------------------------------------------------

# standard library Imports
import os
import ast

# Scons Imports
import SCons.Script


import cuppa.options
from cuppa.colourise import as_info, as_notice
from cuppa.log import logger



SCons.Script.AddOption( '--show-conf', dest='show_conf', action='store_true',
                        help='Show the current values in the configuration file if one exists' )

SCons.Script.AddOption( '--save-conf', dest='save_conf', action='store_true',
                        help='Save the current command-line a configuration file' )

SCons.Script.AddOption( '--update-conf', dest='update_conf', action='store_true',
                        help='Update the configuration file with the current command-line' )

SCons.Script.AddOption( '--remove-settings', type='string', nargs=1,
                        action='callback', callback=cuppa.options.list_parser( 'remove_settings' ),
                        help='Remove the listed settings from the configuration file' )

SCons.Script.AddOption( '--clear-conf', dest='clear_conf', action='store_true',
                        help='Clear the configuration file' )


class never_save(object):
    pass


default_scons_options = {
    'debug_explain': False,
    'debug_includes': False,
    'climb_up': never_save
}


class Configure(object):

    def __init__( self, env, conf_path="configure.conf", callback=None ):
        self._env = env
        self._conf_path = conf_path
        self._callback = callback
        env['configured_options'] = {}
        self._configured_options = {}


    def load( self ):
        self._show   = self._env.get_option( 'show_conf' )
        self._save   = self._env.get_option( 'save_conf' )
        self._remove = self._env.get_option( 'remove_settings' )
        self._update = self._env.get_option( 'update_conf' )
        self._clear  = self._env.get_option( 'clear_conf' )

        self._configure   = self._save or self._remove or self._update

        self._clean       = self._env.get_option( 'clean' )

        self._unconfigure =  ( self._save and self._clean ) or self._clear

        if self._unconfigure:
            self._configure = False
            logger.info( "{}".format( as_notice( "Clear configuration requested..." ) ) )
            if os.path.exists( self._conf_path ):
                logger.info( "Removing configure file [{}]".format(
                        as_info( self._conf_path ) ) )
                os.remove( self._conf_path )
            else:
                logger.info( "Configure file [{}] does not exist. Unconfigure not needed".format(
                        as_info( self._conf_path ) ) )
            return
        elif self._configure:
            print logger.info( "{}".format( as_notice( "Update configuration requested..." ) ) )

        if not self._save:
            self._loaded_options = self._load_conf()
        else:
            self._loaded_options = {}
        self._env['configured_options'] = self._loaded_options
        self._env['default_options'].update( self._loaded_options )


    def save( self ):
        if self._configure and not self._clean:
            if self._save:
                self._save_conf()
            else:
                if self._update:
                    self._update_conf()
                if self._remove:
                    self._remove_settings()


    def handle_conf_only( self ):
        return self._save or self._update or self._remove or self._clear or self._show


    def action( self ):
        if self._save:
            return "save"
        elif self._update:
            return "update"
        elif self._remove:
            return "remove"
        elif self._clear:
            return "clear"
        elif self._show:
            return "show"


    def configure( self, env ):
        configure = SCons.Script.Configure( env )
        if self._callback:
            self._callback( configure )
        env = configure.Finish()


    def _load_conf( self ):
        settings = {}
        if os.path.exists(self._conf_path):
            with open(self._conf_path) as config_file:
                logger.info( "Configure file [{}] exists. Load stored settings...".format(
                        as_info( self._conf_path ) ) )
                for line in config_file.readlines():
                    name, value = tuple( l.strip() for l in line.split('=', 1) )
                    try:
                        value = ast.literal_eval( str(value) )
                    except:
                        pass
                    self._print_setting( 'loading', name, value )
                    settings[name] = value
        if settings:
            logger.info( "Load complete" )
        else:
            logger.info( "No settings to load, skipping configure" )
        return settings


    def _is_defaulted_scons_option( self, key, value ):
        if key in default_scons_options:
            if default_scons_options[key] == value:
                return True
            elif default_scons_options[key] == never_save:
                return True
        return False


    def _is_saveable( self, key, value ):
        return(     not key.startswith("__")
                and not self._is_defaulted_scons_option( key, value )
                and not key =='save_conf'
                and not key =='update_conf'
                and not key =='remove_settings'
                and not key =='show_conf'
                and not key =='clear_conf' )


    def _print_setting( self, action, key, value ):
        logger.info( "{} [{}] = [{}]".format(
                action,
                as_notice( key ),
                as_notice( str(value) )
        ) )


    def _save_settings( self ):
        options = self._loaded_options
        for key, value in SCons.Script.Main.OptionsParser.values.__dict__.items():
            if self._is_saveable( key, value ):
                try:
                    value = ast.literal_eval( str(value) )
                except:
                    pass
                options[key] = value

        with open(self._conf_path, "w") as config_file:
            for key, value in options.items():
                self._print_setting( 'saving', key, value )
                config_file.write( "{} = {}\n".format( key, value ) )


    def _remove_settings( self ):
        initial_option_count = len(self._loaded_options)
        logger.info( "Remove settings requested for the following options {}".format( self._remove ) )
        for setting in self._remove:
            if setting in self._loaded_options:
                del self._loaded_options[setting]
                logger.info( "Removing option [{}] as requested".format( as_notice( "--" + setting ) ) )
        if initial_option_count != len(self._loaded_options):
            self._update_conf()


    def _save_conf( self ):
        logger.info( "{}".format( as_notice( "Save current settings..." ) ) )
        self._save_settings()
        logger.info( "{}".format( as_notice( "Save complete" ) ) )


    def _update_conf( self ):
        logger.info( "{}".format( as_notice( "Updating current settings..." ) ) )
        self._save_settings()
        logger.info( "{}".format( as_notice( "Update complete" ) ) )



