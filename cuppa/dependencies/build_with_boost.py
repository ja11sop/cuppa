
#          Copyright Jamie Allsop 2011-2015
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   Boost
#-------------------------------------------------------------------------------
import shlex
import os
import shutil
import re

from exceptions   import Exception
from re           import search

from SCons.Script import File, AlwaysBuild

from cuppa.output_processor import IncrementalSubProcess, ToolchainProcessor

import cuppa.build_platform
import cuppa.location


class BoostException(Exception):
    def __init__(self, value):
        self.parameter = value
    def __str__(self):
        return repr(self.parameter)


class Boost(object):

    @classmethod
    def add_options( cls, add_option ):
        add_option( '--boost-version', dest='boost-version', type='string', nargs=1, action='store',
                    help='Boost Version to build against' )

        add_option( '--boost-home', dest='boost-home', type='string', nargs=1, action='store',
                    help='The location of the boost source code' )

        add_option( '--boost-build-always', dest='boost-build-always', action='store_true',
                    help="Pass this if your boost source may change (for example you are patching it) and you want boost build to be executed each time the library is asked for" )

        add_option( '--boost-verbose-build', dest='boost-verbose-build', action='store_true',
                    help="Pass this option if you wish to see the command-line output of boost build" )

        add_option( '--boost-verbose-config', dest='boost-verbose-config', action='store_true',
                    help="Pass this option if you wish to see the configuration output of boost build" )


    @classmethod
    def add_to_env( cls, env, add_dependency ):
        build_always = env.get_option( 'boost-build-always' )
        verbose_build = env.get_option( 'boost-verbose-build' )
        verbose_config = env.get_option( 'boost-verbose-config' )
        boost = None
        try:
            if env.get_option( 'boost-home' ):
                boost = cls( env, env[ 'platform' ],
                           env.get_option( 'boost-home' ) )
            else:
                boost = cls( env, env[ 'platform' ],
                           env[ 'thirdparty' ],
                           version = env.get_option( 'boost-version' ) )
        except BoostException, (e):
            print "Could not create boost dependency: {}".format(e)

        add_dependency( 'boost', boost )

        env.AddMethod(
                BoostStaticLibraryMethod(
                        build_always=build_always,
                        verbose_build=verbose_build,
                        verbose_config=verbose_config ),
                "BoostStaticLibrary" )
        env.AddMethod(
                BoostSharedLibraryMethod(
                        build_always=build_always,
                        verbose_build=verbose_build,
                        verbose_config=verbose_config ),
                "BoostSharedLibrary" )


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


    def __init__( self, env, platform, base, version=None ):
        if not base and not version:
            raise BoostException("Cannot construct Boost Object. Invalid parameters")

        if not base:
            base = env['working_dir']
        if not os.path.isabs( base ):
            base = os.path.abspath( base )

        self.values = {}
        self.values['name'] = 'boost'

        if not version:
            self.values['home'] = base
        elif version:
            search_list = [
                os.path.join( base, 'boost', version, 'source' ),
                os.path.join( base, 'boost', 'boost_' + version ),
                os.path.join( base, 'boost', version ),
                os.path.join( base, 'boost_' + version ),
            ]

            def exists_in( locations ):
                for location in locations:
                    if self.set_home_if_exists( location ):
                        return True
                return False

            if not exists_in( search_list ):
                raise BoostException("Cannot construct Boost Object. Home for Version [{}] cannot be found. Seached in [{}]".format(version, str([l for l in search_list])))
        else:
            raise BoostException("Cannot construct Boost Object. No Home or Version specified")

        self.values['full_version'], self.values['version'], self.values['numeric_version'] = self.get_boost_version( self.values['home'] )

        self._location = cuppa.location.Location( env, self.values['home'] )

        self.values['revisions'] = self._location.revisions()

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

    def version( self ):
        return self.values['version']

    def repository( self ):
        return self._location.repository()

    def branch( self ):
        return self._location.branch()

    def revisions( self ):
        return self._location.revisions()

    def local( self ):
        return self._location.local()


    def __call__( self, env, toolchain, variant ):
        env.AppendUnique( SYSINCPATH = self.values['include'] )
        env.AppendUnique( CPPDEFINES = self.values['defines'] )


    def numeric_version( self ):
        return self.values['numeric_version']


    def full_version( self ):
        return self.values['full_version']


    def lib( self, library ):
        return 'boost_' + library + self.values['library_mt_tag']



class BoostStaticLibraryMethod(object):

    def __init__( self, build_always=False, verbose_build=False, verbose_config=False ):
        self._build_always = build_always
        self._verbose_build = verbose_build
        self._verbose_config = verbose_config

    def __call__( self, env, library ):
        if not 'boost' in env['BUILD_WITH']:
            env.BuildWith( 'boost' )
        Boost = env['dependencies']['boost']
        library = BoostLibraryBuilder(
                Boost,
                verbose_build=self._verbose_build,
                verbose_config=self._verbose_config )( env, None, None, library, 'static' )
        if self._build_always:
            return AlwaysBuild( library )
        else:
            return library



class BoostSharedLibraryMethod(object):

    def __init__( self, build_always=False, verbose_build=False, verbose_config=False ):
        self._build_always = build_always
        self._verbose_build = verbose_build
        self._verbose_config = verbose_config

    def __call__( self, env, library ):
        if not 'boost' in env['BUILD_WITH']:
            env.BuildWith( 'boost' )
        Boost = env['dependencies']['boost']

        if library.startswith('log'):
            env.AppendUnique( CPPDEFINES = 'BOOST_LOG_DYN_LINK' )
        elif library == 'chrono':
            env.AppendUnique( CPPDEFINES = 'BOOST_CHRONO_DYN_LINK' )
        elif library == 'filesystem':
            env.AppendUnique( CPPDEFINES = 'BOOST_FILESYSTEM_DYN_LINK' )
        elif library == 'date_time':
            env.AppendUnique( CPPDEFINES = 'BOOST_DATE_TIME_DYN_LINK' )
        elif library == 'system':
            env.AppendUnique( CPPDEFINES = 'BOOST_SYSTEM_DYN_LINK' )

        library = BoostLibraryBuilder(
                Boost,
                verbose_build=self._verbose_build,
                verbose_config=self._verbose_config )( env, None, None, library, 'shared' )
        if self._build_always:
            return AlwaysBuild( library )
        else:
            return library



class ProcessBjamBuild(object):

    def __call__( self, line ):
        match = re.search( r'\[COMPILE\] ([\S]+)', line )
        if match:
            self.bjam_exe_path = match.expand( r'\1' )
        return line

    def exe_path( self ):
        return self.bjam_exe_path



class BuildBjam(object):

    def __init__( self, boost ):
        self._location = boost.local()
        self._version  = boost.numeric_version()

    def __call__( self, target, source, env ):
        print "_build_bjam"

        build_script_path = self._location + '/tools/build'

        if self._version < 1.47:
            build_script_path += '/src/v2/engine'

        elif self._version > 1.55:
            build_script_path += '/src/engine'

        else:
            build_script_path += '/v2/engine'

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

            shutil.copy( bjam_binary_path, target[0].path )

        except OSError as error:
            print 'Error building bjam [' + str( error.args ) + ']'
            return 1

        return None



def toolset_name_from_toolchain( toolchain ):
    toolset_name = toolchain.family()
    if cuppa.build_platform.name() == "Darwin":
        if toolset_name == "gcc":
            toolset_name = "darwin"
        elif toolset_name == "clang":
            toolset_name = "clang-darwin"
    return toolset_name



def toolset_from_toolchain( toolchain ):
    toolset_name = toolset_name_from_toolchain( toolchain )
    if toolset_name == "clang-darwin":
        return toolset_name
    return toolset_name + '-' + toolchain.version()



class UpdateProjectConfigJam(object):

    def __init__( self, project_config_path ):
        self._project_config_path = project_config_path


    def __call__( self, target, source, env ):

        toolchain = env['toolchain']

        current_toolset = "using {} : {} :".format( toolset_name_from_toolchain( toolchain ), toolchain.version() )
        toolset_config_line = "{} {} ;\n".format( current_toolset, toolchain.binary() )
        print "boost: adding toolset config [{}]".format( toolset_config_line )
        config_added = False
        changed = False

        project_config_path = self._project_config_path

        temp_path = os.path.splitext( project_config_path )[0] + ".new_jam"
        if not os.path.exists( project_config_path ):
            with open( project_config_path, 'w' ) as project_config_jam:
                project_config_jam.write( "# File created by cuppa:boost\n" )
        with open( project_config_path ) as project_config_jam:
            with open( temp_path, 'w' ) as temp_file:
                for line in project_config_jam.readlines():
                    if line.startswith( current_toolset ):
                        if line != toolset_config_line:
                            temp_file.write( toolset_config_line )
                            changed = True
                        config_added = True
                    else:
                        temp_file.write( line )
                if not config_added:
                    temp_file.write( toolset_config_line )
                    changed = True
        if changed:
            os.remove( project_config_path )
            shutil.move( temp_path, project_config_path )



class BoostLibraryAction(object):

    def __init__( self, env, boost, verbose_build, verbose_config, library, linktype ):
        self._env = env
        self._location       = boost.local()
        self._version        = boost.numeric_version()
        self._full_version   = boost.full_version()
        self._verbose_build  = verbose_build
        self._verbose_config = verbose_config
        self._library        = library
        self._linktype       = linktype
        self._variant        = self._env['variant'].name()

        if self._variant == 'dbg':
            self._variant = 'debug'
        else:
            self._variant = 'release'


    def _toolset_name_from_toolchain( self, toolchain ):
        toolset_name = toolchain.family()
        if cuppa.build_platform.name() == "Darwin":
            if toolset_name == "gcc":
                toolset_name = "darwin"
            elif toolset_name == "clang":
                toolset_name = "clang-darwin"
        return toolset_name


    def _toolset_from_toolchain( self, toolchain ):
        toolset_name = toolset_name_from_toolchain( toolchain )
        if toolset_name == "clang-darwin":
            return toolset_name
        return toolset_name + '-' + toolchain.version()


    def _build_command( self, toolchain, library, variant, linktype, stage_dir ):

        verbose = ""
        if self._verbose_build:
            verbose += " -d+2"
        if self._verbose_config:
            verbose += " --debug-configuration"

        build_flags = toolchain.build_flags_for('boost')
        build_flags += ' define="BOOST_DATE_TIME_POSIX_TIME_STD_CONFIG"'

        if linktype == 'shared':
            build_flags += ' define="BOOST_ALL_DYN_LINK"'

        command_line = "./bjam{verbose} --with-{library} toolset={toolset} variant={variant} {build_flags} link={linktype} stage --stagedir=./{stage_dir}".format(
                verbose     = verbose,
                library     = library,
                toolset     = toolset_from_toolchain( toolchain ),
                variant     = variant,
                build_flags = build_flags,
                linktype    = linktype,
                stage_dir   = stage_dir )

        print command_line
        return shlex.split( command_line )


    def __call__( self, target, source, env ):

        library   = self._library == 'log_setup' and 'log' or self._library
        toolchain = self._env['toolchain']
        stage_dir = os.path.join( 'build', toolchain.name(), self._variant )
        args      = self._build_command( toolchain, library, self._variant, self._linktype, stage_dir )

        processor = BjamOutputProcessor( env, self._verbose_build, self._verbose_config, self._toolset_name_from_toolchain( toolchain ) )

        returncode = IncrementalSubProcess.Popen(
            processor,
            args,
            cwd=self._location
        )

        summary = processor.summary( returncode )

        if summary:
            print summary

        if returncode:
            return returncode

        target_path        = str( target[0] )
        filename           = os.path.split( target_path )[1]
        built_library_path = os.path.join( self._location, stage_dir, 'lib', filename )

        shutil.copy( built_library_path, target_path )
        return None



class BjamOutputProcessor(object):

    def __init__( self, env, verbose_build, verbose_config, toolset_name ):
        self._verbose_build = verbose_build
        self._verbose_config = verbose_config
        self._toolset_filter = toolset_name + '.'

        self._colouriser = env['colouriser']
        self._minimal_output = not self._verbose_build
        ignore_duplicates = not self._verbose_build
        self._toolchain_processor = ToolchainProcessor( self._colouriser, env['toolchain'], self._minimal_output, ignore_duplicates )


    def __call__( self, line ):
        if line.startswith( self._toolset_filter ):
            return line
        elif not self._verbose_config:
            if(     line.startswith( "Performing configuration" )
                or  line.startswith( "Component configuration" )
                or  line.startswith( "    - " ) ):
                return None
        return self._toolchain_processor( line )


    def summary( self, returncode ):
        summary = self._toolchain_processor.summary( returncode )
        if returncode and not self._verbose_build:
            summary += "\nTry running with {} for more details".format( self._colouriser.emphasise( '--boost-verbose-build' ) )
        return summary



class BoostLibraryEmitter(object):

    def __init__( self, env, library, linktype, boost ):
        self._env = env
        self._library      = library
        self._linktype     = linktype
        self._version      = boost.numeric_version()
        self._full_version = boost.full_version()


    def _shared_library_name( self, env, library ):
        if cuppa.build_platform.name() == "Darwin":
            return env.subst('$SHLIBPREFIX') + 'boost_' + library + env.subst('$SHLIBSUFFIX')
        else:
            return env.subst('$SHLIBPREFIX') + 'boost_' + library + env.subst('$SHLIBSUFFIX') + '.' + self._full_version


    def __call__( self, target, source, env ):
        if self._linktype == 'static':
            node = File( env.subst('$LIBPREFIX') + 'boost_' + self._library + env.subst('$LIBSUFFIX') )
        else:
            shared_library_name = self._shared_library_name( env, self._library )
            node = File( os.path.join( env['abs_final_dir'], shared_library_name ) )
        target.append( node )
        return target, source



class BoostLibraryBuilder(object):

    def __init__( self, boost, verbose_build, verbose_config ):
        self._boost = boost
        self._verbose_build = verbose_build
        self._verbose_config = verbose_config


    def __call__( self, env, target, source, library, linktype ):
        library_action  = BoostLibraryAction ( env, self._boost, self._verbose_build, self._verbose_config, library, linktype )
        library_emitter = BoostLibraryEmitter( env, library, linktype, self._boost )

        env.AppendUnique( BUILDERS = {
            'BoostLibraryBuilder' : env.Builder( action=library_action, emitter=library_emitter )
        } )

        bjam_target = os.path.join( self._boost.local(), 'bjam' )
        bjam    = env.Command( bjam_target, [], BuildBjam( self._boost ) )
        library = env.BoostLibraryBuilder( target, source )
        env.Requires( library, bjam )

        if cuppa.build_platform.name() == "Linux":
            project_config_target = os.path.join( self._boost.local(), "project-config.jam" )
            project_config_jam = env.Command( project_config_target, [], UpdateProjectConfigJam( project_config_target ) )
            env.Requires( library, project_config_jam )

        return library


