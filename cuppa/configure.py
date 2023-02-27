
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


import cuppa.core.options
from cuppa.colourise import as_info, as_notice
from cuppa.log import logger


cuppa.core.options.add_option( '--show-conf', dest='show_conf', action='store_true',
                               help='Show the current values in the configuration file if one exists' )

cuppa.core.options.add_option( '--save-conf', dest='save_conf', action='store_true',
                               help='Save the current command-line as a configuration file' )

cuppa.core.options.add_option( '--save-global-conf', dest='save_global_conf', action='store_true',
                               help='Save the current command-line as a global configuration file' )

cuppa.core.options.add_option( '--update-conf', dest='update_conf', action='store_true',
                               help='Update the configuration file with the current command-line' )

cuppa.core.options.add_option( '--update-global-conf', dest='update_global_conf', action='store_true',
                               help='Update the global configuration file with the current command-line' )

cuppa.core.options.add_option( '--remove-settings', type='string', nargs=1,
                               action='callback', callback=cuppa.core.options.list_parser( 'remove_settings' ),
                               help='Remove the listed settings from the configuration file' )

cuppa.core.options.add_option( '--remove-global-settings', type='string', nargs=1,
                               action='callback', callback=cuppa.core.options.list_parser( 'remove_global_settings' ),
                               help='Remove the listed settings from the global configuration file' )

cuppa.core.options.add_option( '--clear-conf', dest='clear_conf', action='store_true',
                               help='Clear the configuration file' )

cuppa.core.options.add_option( '--clear-global-conf', dest='clear_global_conf', action='store_true',
                               help='Clear the global configuration file' )

cuppa.core.options.add_option( '--use-conf', dest='use_conf', action='store',
                               type='string', nargs=1,
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
        self._conf_path = self._env.get_option( 'use_conf' )
        if not self._conf_path:
            self._conf_path = conf_path
        self._global_conf_path = self.global_config_path()
        self._callback = callback
        env['configured_options'] = {}
        self._configured_options = {}


    def global_config_path( self ):
        return os.path.join( os.path.expanduser("~"), ".cuppaconfig" )


    def load( self ):
        self._show          = self._env.get_option( 'show_conf' )
        self._save          = self._env.get_option( 'save_conf' )
        self._save_global   = self._env.get_option( 'save_global_conf' )
        self._remove        = self._env.get_option( 'remove_settings' )
        self._remove_global = self._env.get_option( 'remove_global_settings' )
        self._update        = self._env.get_option( 'update_conf' )
        self._update_global = self._env.get_option( 'update_global_conf' )
        self._clear         = self._env.get_option( 'clear_conf' )
        self._clear_global  = self._env.get_option( 'clear_global_conf' )

        self._configure = (
                self._save
            or  self._save_global
            or  self._remove
            or  self._remove_global
            or  self._update
            or  self._update_global
        )

        self._clean = self._env.get_option( 'clean' )

        self._unconfigure = (
                ( ( self._save or self._save_global ) and self._clean )
            or  self._clear
            or  self._clear_global
        )

        if self._unconfigure:
            self._configure = False
            logger.info( "{}".format( as_notice( "Clear configuration requested..." ) ) )

            if self._save or self._clear:
                self._clear_config( self._conf_path )

            if self._save_global or self._clear_global:
                self._clear_config( self._global_conf_path )

        elif self._configure:
            logger.info( "{}".format( as_notice( "Update configuration requested..." ) ) )

        if not self._save and not self._save_global:
            self._loaded_options = self._load_conf()
        else:
            self._loaded_options = {}
        self._env['configured_options'] = self._loaded_options
        self._env['default_options'].update( self._loaded_options )


    def save( self ):
        if self._configure and not self._clean:
            if self._save or self._save_global:
                if self._save:
                    self._save_conf( self._conf_path )
                if self._save_global:
                    self._save_conf( self._global_conf_path )
            else:
                if self._update:
                    self._update_conf( self._conf_path )
                if self._update_global:
                    self._update_conf( self._global_conf_path )
                if self._remove:
                    self._remove_settings( self._conf_path, self._remove )
                if self._remove_global:
                    self._remove_settings( self._global_conf_path, self._remove_global )


    def handle_conf_only( self ):
        return (
                self._save
            or  self._save_global
            or  self._remove
            or  self._remove_global
            or  self._update
            or  self._update_global
            or  self._clear
            or  self._clear_global
            or  self._show
        )


    def action( self ):
        if self._save:
            return "save"
        elif self._save_global:
            return "save_global"
        elif self._update:
            return "update"
        elif self._update_global:
            return "update_global"
        elif self._remove:
            return "remove"
        elif self._remove_global:
            return "remove_global"
        elif self._clear:
            return "clear"
        elif self._clear_global:
            return "clear_global"
        elif self._show:
            return "show"


    def configure( self, env ):
        configure = SCons.Script.Configure( env )
        if self._callback:
            self._callback( configure )
        env = configure.Finish()


    def _clear_config( self, conf_path ):
        if os.path.exists( conf_path ):
            logger.info( "Removing configure file [{}]".format(
                    as_info( conf_path ) ) )
            os.remove( conf_path )
        else:
            logger.info( "Configure file [{}] does not exist. Unconfigure not needed".format(
                    as_info( conf_path ) ) )


    def _load_settings_from_file( self, conf_path, conf_file, settings ):
        logger.info( "Configure file [{}] exists. Load stored settings...".format( as_info( conf_path ) ) )
        for line in conf_file.readlines():
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            name, value = tuple( word.strip() for word in line.split('=', 1) )
            try:
                value = ast.literal_eval( str(value) )
            except:
                pass
            self._print_setting( 'loading', name, value )
            settings[name] = value


    def _load_conf( self ):
        settings = {}

        if os.path.exists( self._global_conf_path ):
            with open( self._global_conf_path ) as conf_file:
                self._load_settings_from_file( self._global_conf_path, conf_file, settings )

        if os.path.exists( self._conf_path ):
            with open(self._conf_path) as conf_file:
                self._load_settings_from_file( self._conf_path, conf_file, settings )

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
                and not key == 'cuppa-mode'
                and not key == 'save_global_conf'
                and not key == 'update_global_conf'
                and not key == 'clear_global_conf'
                and not key == 'remove_global_settings'
                and not key == 'save_conf'
                and not key == 'update_conf'
                and not key == 'clear_conf'
                and not key == 'remove_settings'
                and not key == 'show_conf'
                and not key == 'use_conf' )


    def _print_setting( self, action, key, value ):
        logger.info( "{} [{}] = [{}]".format(
                action,
                as_notice( key ),
                as_notice( str(value) )
        ) )


    def _save_settings( self, conf_path ):
        options = self._loaded_options
        for key, value in SCons.Script.Main.OptionsParser.values.__dict__.items():
            if self._is_saveable( key, value ):
                try:
                    value = ast.literal_eval( str(value) )
                except:
                    pass
                options[key] = value

        with open(conf_path, "w") as config_file:
            for key, value in options.items():
                self._print_setting( 'saving', key, value )
                config_file.write( "{} = {}\n".format( key, value ) )


    def _remove_settings( self, conf_path, remove_options ):
        initial_option_count = len(self._loaded_options)
        logger.info( "Remove settings requested for the following options {}".format( remove_options ) )
        for setting in remove_options:
            if setting in self._loaded_options:
                del self._loaded_options[setting]
                logger.info( "Removing option [{}] as requested".format( as_notice( "--" + setting ) ) )
        if initial_option_count != len(self._loaded_options):
            self._update_conf( conf_path )


    def _save_conf( self, conf_path ):
        logger.info( "{}".format( as_notice( "Save current settings..." ) ) )
        self._save_settings( conf_path )
        logger.info( "{}".format( as_notice( "Save complete" ) ) )


    def _update_conf( self, conf_path ):
        logger.info( "{}".format( as_notice( "Updating current settings..." ) ) )
        self._save_settings( conf_path )
        logger.info( "{}".format( as_notice( "Update complete" ) ) )



