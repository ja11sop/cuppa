
#          Copyright Jamie Allsop 2011-2014
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   Boost
#-------------------------------------------------------------------------------
import shlex
import subprocess
import os
import shutil
import re
import sys
from exceptions   import Exception
from re           import search
from string       import strip, replace
from SCons.Script import AddOption, Environment, File, AlwaysBuild
from output_processor import IncrementalSubProcess
import build_platform


class BoostException(Exception):
    def __init__(self, value):
        self.parameter = value
    def __str__(self):
        return repr(self.parameter)


class Boost:

    @classmethod
    def add_options( cls ):
        AddOption( '--boost-version', dest='boost-version', type='string', nargs=1, action='store',
               help='Boost Version to build against' )

        AddOption( '--boost-home', dest='boost-home', type='string', nargs=1, action='store',
               help='The location of the boost source code' )

        AddOption( '--boost-build-once', dest='boost-build-once', action='store_true',
               help="Pass this if you know the source won't change and you only need the libraries built the first time" )


    @classmethod
    def add_to_env( cls, args ):
        env = args['env']
        build_once = env.get_option( 'boost-build-once' )
        try:
            if env.get_option( 'boost-home' ):
                obj = cls( env[ 'platform' ],
                           env[ 'scm' ],
                           env.get_option( 'boost-home' ) )
            else:
                obj = cls( env[ 'platform' ],
                           env[ 'scm' ],
                           env[ 'thirdparty' ],
                           version = env.get_option( 'boost-version' ) )

            env['dependencies']['boost'] = obj
        except BoostException, (e):
            print "Could not create boost dependency: {}".format(e)
            env['dependencies']['boost'] = None

        env.AddMethod( BoostStaticLibraryMethod( build_once=build_once ), "BoostStaticLibrary" )
        env.AddMethod( BoostSharedLibraryMethod( build_once=build_once ), "BoostSharedLibrary" )



    def get_boost_version( self, location ):
        version_hpp_path = os.path.join( location, 'boost', 'version.hpp' )
        if not os.path.exists( version_hpp_path ):
            raise BoostException("Boost version.hpp file not found")
        with open( version_hpp_path ) as version_hpp:
            for line in version_hpp:
                match = search( r'BOOST_VERSION\s+(?P<version>\d+)', line )
                if match:
                    int_version = int(match.group('version'))
                    major = int_version/100000
                    minor = int_version/100%1000
                    patch = int_version%100
                    full_version = "{}.{}.{}".format( major, minor, patch )
                    short_version = "{}_{}".format( major, minor )
                    numeric_version = float(major) + float(minor)/100
                    return full_version, short_version, numeric_version
        raise BoostException("Could not determine BoostVersion")


    def set_home_if_exists( self, path ):
        if os.path.exists( path ) and os.path.isdir( path ):
            self.values['home'] = path
            return True
        return False


    def __init__( self, platform, scm_system, base, version=None ):
        if not base and not version:
            raise BoostException("Cannot construct Boost Object. Invalid parameters")

        if not base:
            base = SCons.Script.GetLaunchDir()
        if not os.path.isabs( base ):
            base = os.path.abspath( base )

        self.__scm_system = scm_system
        self.values = {}
        self.values['name'] = 'boost'

        if not version:
            self.values['home'] = base
        elif version:
            if(     not self.set_home_if_exists( os.path.join( base, 'boost', version, 'source' ) )
                and not self.set_home_if_exists( os.path.join( base, 'boost', 'boost_' + version ) )
                and not self.set_home_if_exists( os.path.join( base, 'boost', version ) )
                and not self.set_home_if_exists( os.path.join( base, 'boost_' + version ) ) ):

                raise BoostException("Cannot construct Boost Object. Home for Version [{}] cannot be found".format(version))
        else:
            raise BoostException("Cannot construct Boost Object. No Home or Version specified")

        self.values['full_version'], self.values['version'], self.values['numeric_version'] = self.get_boost_version( self.values['home'] )

        self.values['include']  = [ self.values['home'] ]
        self.values['lib_base'] = os.path.join( self.values['home'], 'build' )
        self.values['location'] = self.values['home']
        if self.values['numeric_version'] > 1.39:
            self.values['library_mt_tag'] = ''
        else:
            self.values['library_mt_tag'] = '-' + platform['toolchain_tag'] + '-mt'

        self.values['defines'] = [
            'BOOST_PARAMETER_MAX_ARITY=20',
            'BOOST_DATE_TIME_POSIX_TIME_STD_CONFIG'
        ]


    def name( self ):
        return self.values['name']

    def location( self ):
        return self.values['location']

    def version( self ):
        return self.values['version']

    def revisions( self, scm = None ):
        scm_system = scm and scm or self.__scm_system
        return [ scm_system.revision( self.values['home'] ) ]

    def __call__( self, env, toolchain, variant ):
        env.AppendUnique( SYSINCPATH = self.values['include'] )
        env.AppendUnique( CPPDEFINES = self.values['defines'] )


    def numeric_version( self ):
        return self.values['numeric_version']


    def full_version( self ):
        return self.values['full_version']


    def lib( self, library ):
        return 'boost_' + library + self.values['library_mt_tag']



class BoostStaticLibraryMethod:

    def __init__( self, build_once=False ):
        self._build_once = build_once

    def __call__( self, env, library ):
        if not 'boost' in env['BUILD_WITH']:
            env.BuildWith( 'boost' )
        Boost = env['dependencies']['boost']
        library = BoostLibraryBuilder( Boost )( env, None, None, library, 'static' )
        if self._build_once:
            return library
        else:
            return AlwaysBuild( library )


class BoostSharedLibraryMethod:

    def __init__( self, build_once=False ):
        self._build_once = build_once

    def __call__( self, env, library ):
        if not 'boost' in env['BUILD_WITH']:
            env.BuildWith( 'boost' )
        Boost = env['dependencies']['boost']
        library = BoostLibraryBuilder( Boost )( env, None, None, library, 'shared' )
        if self._build_once:
            return library
        else:
            return AlwaysBuild( library )


class ProcessBjamBuild:

    def __call__( self, line ):
        match = re.search( r'\[COMPILE\] ([\S]+)', line )
        if match:
            self.bjam_exe_path = match.expand( r'\1' )
        return line

    def exe_path( self ):
        return self.bjam_exe_path


class BoostLibraryAction:

    def __init__( self, env, boost, library, linktype ):
        self.__env = env
        self.__location     = boost.location()
        self.__version      = boost.numeric_version()
        self.__full_version = boost.full_version()
        self.__library      = library
        self.__linktype     = linktype
        self.__variant      = self.__env['variant'].name()

        if self.__variant == 'dbg':
            self.__variant = 'debug'
        else:
            self.__variant = 'release'


    @classmethod
    def process_bjam_output( cls, line ):
        if line[0] != ' ' and line[0] != '.' and line[0] != 'C' and line[0] != 'P' and line[0] != 'w':
            return line


    def __build_bjam( self ):
        build_script_path = self.__location + '/tools/build/v2/engine'

        if self.__version < 1.47:
            build_script_path += '/src'

        ## TODO: change build script depending on platform
        bjam_build_script = './build.sh'

        print 'Execute ' + bjam_build_script + ' from ' + build_script_path

        process_bjam_build = ProcessBjamBuild()

        try:
            IncrementalSubProcess.Popen(
                process_bjam_build,
                [ bjam_build_script ],
                cwd=build_script_path
            )

            bjam_exe_path = process_bjam_build.exe_path()

            if not bjam_exe_path:
                print "Could not determine bjam exe path"
                return 1

            bjam_binary_path = build_script_path + '/' + bjam_exe_path

            shutil.copy( bjam_binary_path, self.__location + '/bjam' )

        except OSError as error:
            print 'Error building bjam [' + str( error.args ) + ']'
            return 1


    def _toolset_from_toolchain( self, toolchain ):
        toolset_name = toolchain.family()
        toolset_version = toolchain.version()
        if build_platform.name() == "Darwin":
            if toolset_name == "gcc":
                toolset_name = "darwin"
            elif toolset_name == "clang":
                toolset_name = "clang-darwin"
        return toolset_name + '-' + toolset_version


    def __build_command( self, toolchain, library, variant, linktype, stage_dir ):
        toolset = self._toolset_from_toolchain( toolchain )
        command_line = './bjam --with-' + library + ' toolset=' + toolset + ' variant=' + variant + ' ' + toolchain.build_flags_for('boost') + ' link=' + linktype + ' stage --stagedir=./' + stage_dir
        return shlex.split( command_line )


    def __call__( self, target, source, env ):

        if not os.path.exists( self.__location + '/bjam' ):
            self.__build_bjam()

        library   = self.__library == 'log_setup' and 'log' or self.__library
        toolchain = self.__env['toolchain'].name()
        stage_dir = 'build/' + toolchain + '/' + self.__variant
        args      = self.__build_command( self.__env['toolchain'], library, self.__variant, self.__linktype, stage_dir )

        try:
            IncrementalSubProcess.Popen(
                self.process_bjam_output,
                args,
                cwd=self.__location
            )

            target_path        = str( target[0] )
            filename           = os.path.split( target_path )[1]
            built_library_path = self.__location + '/' + stage_dir + '/lib/' + filename

            shutil.copy( built_library_path, target_path )
            return None

        except OSError as error:
            print 'Error building ' + self.__library + '[' + str( error.args ) + ']'
            return 1


class BoostLibraryEmitter:

    def __init__( self, env, library, linktype, boost ):
        self.__env = env
        self.__library      = library
        self.__linktype     = linktype
        self.__version      = boost.numeric_version()
        self.__full_version = boost.full_version()


    def _shared_library_name( self, env, library ):
        if build_platform.name() == "Darwin":
            return env.subst('$SHLIBPREFIX') + 'boost_' + library + env.subst('$SHLIBSUFFIX')
        else:
            return env.subst('$SHLIBPREFIX') + 'boost_' + library + env.subst('$SHLIBSUFFIX') + '.' + self.__full_version


    def __call__( self, target, source, env ):
        if self.__linktype == 'static':
            node = File( env.subst('$LIBPREFIX') + 'boost_' + self.__library + env.subst('$LIBSUFFIX') )
        else:
            shared_library_name = self._shared_library_name( env, self.__library )
            node = File( os.path.join( env['final_dir'], shared_library_name ) )
        target.append( node )
        return target, source


class BoostLibraryBuilder:

    def __init__( self, boost ):
        self.__boost = boost


    def __call__( self, env, target, source, library, linktype ):
        library_action  = BoostLibraryAction ( env, self.__boost, library, linktype )
        library_emitter = BoostLibraryEmitter( env, library, linktype, self.__boost )

        env.AppendUnique( BUILDERS = {
            'BoostLibraryBuilder' : env.Builder( action=library_action, emitter=library_emitter )
        } )

        return env.BoostLibraryBuilder( target, source )


