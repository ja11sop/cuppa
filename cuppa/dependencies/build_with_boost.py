
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
import string
import lxml.html

from exceptions import Exception

from SCons.Script import File, AlwaysBuild, Flatten

import cuppa.build_platform
import cuppa.location

from cuppa.output_processor import IncrementalSubProcess, ToolchainProcessor
from cuppa.colourise        import as_warning, as_info



class BoostException(Exception):
    def __init__(self, value):
        self.parameter = value
    def __str__(self):
        return repr(self.parameter)


def determine_latest_boost_verion( env ):
    current_release = "1.58.0"
    try:
        html = lxml.html.parse('http://www.boost.org/users/download/')

        current_release = html.xpath("/html/body/div[2]/div/div[1]/div/div/div[2]/h3[1]/span")[0].text
        current_release = str( re.search( r'(\d[.]\d+([.]\d+)?)', current_release ).group(1) )

        print "cuppa: boost: latest boost release detected as [{}]".format( as_info( env, current_release ) )

    except Exception as e:
        print as_warning( env, "cuppa: boost: warning: cannot determine latest version of boost - [{}]. Assuming [{}].".format( str(e), current_release ) )

    return current_release


class Boost(object):

    @classmethod
    def add_options( cls, add_option ):
        add_option( '--boost-latest', dest='boost-latest', action='store_true',
                    help='Specify that you want to use boost. The latest version will be downloaded and used.' )

        add_option( '--boost-version', dest='boost-version', type='string', nargs=1, action='store',
                    help='Boost Version to build against' )

        add_option( '--boost-home', dest='boost-home', type='string', nargs=1, action='store',
                    help='The location of the boost source code' )

        add_option( '--boost-location', dest='boost-location', type='string', nargs=1, action='store',
                    help='The location of the boost source code' )

        add_option( '--boost-build-always', dest='boost-build-always', action='store_true',
                    help="Pass this if your boost source may change (for example you are patching it) and you want boost build to be executed each time the library is asked for" )

        add_option( '--boost-verbose-build', dest='boost-verbose-build', action='store_true',
                    help="Pass this option if you wish to see the command-line output of boost build" )

        add_option( '--boost-verbose-config', dest='boost-verbose-config', action='store_true',
                    help="Pass this option if you wish to see the configuration output of boost build" )


    @classmethod
    def add_to_env( cls, env, add_dependency ):
        build_always   = env.get_option( 'boost-build-always' )
        verbose_build  = env.get_option( 'boost-verbose-build' )
        verbose_config = env.get_option( 'boost-verbose-config' )

        boost_location = env.get_option( 'boost-location' )
        boost_home     = env.get_option( 'boost-home' )
        boost_version  = env.get_option( 'boost-version' )
        boost_latest   = env.get_option( 'boost-latest' )
        thirdparty     = env[ 'thirdparty' ]

        boost = None
        try:
            if boost_location:
                boost = cls( env, env[ 'platform' ],
                           location = boost_location,
                           version  = boost_version )
            elif boost_home:
                boost = cls( env, env[ 'platform' ],
                           base = boost_home )
            elif thirdparty and boost_version:
                boost = cls( env, env[ 'platform' ],
                           base = thirdparty,
                           version = boost_version )
            elif boost_version:
                boost = cls( env, env[ 'platform' ],
                           version = boost_version )
            elif boost_latest:
                boost = cls( env, env[ 'platform' ],
                           version = 'latest' )

        except BoostException as e:
            print as_warning( env, "cuppa: boost: warning: Could not create boost dependency - {}".format(e) )

        add_dependency( 'boost', boost )

        env.AddMethod(
                BoostStaticLibraryMethod(
                        add_dependents=False,
                        build_always=build_always,
                        verbose_build=verbose_build,
                        verbose_config=verbose_config ),
                "BoostStaticLibrary" )
        env.AddMethod(
                BoostSharedLibraryMethod(
                        add_dependents=False,
                        build_always=build_always,
                        verbose_build=verbose_build,
                        verbose_config=verbose_config ),
                "BoostSharedLibrary" )
        env.AddMethod(
                BoostStaticLibraryMethod(
                        add_dependents=False,
                        build_always=build_always,
                        verbose_build=verbose_build,
                        verbose_config=verbose_config ),
                "BoostStaticLib" )
        env.AddMethod(
                BoostSharedLibraryMethod(
                        add_dependents=False,
                        build_always=build_always,
                        verbose_build=verbose_build,
                        verbose_config=verbose_config ),
                "BoostSharedLib" )
        env.AddMethod(
                BoostStaticLibraryMethod(
                        add_dependents=True,
                        build_always=build_always,
                        verbose_build=verbose_build,
                        verbose_config=verbose_config ),
                "BoostStaticLibs" )
        env.AddMethod(
                BoostSharedLibraryMethod(
                        add_dependents=True,
                        build_always=build_always,
                        verbose_build=verbose_build,
                        verbose_config=verbose_config ),
                "BoostSharedLibs" )


    def get_boost_version( self, location ):
        version_hpp_path = os.path.join( location, 'boost', 'version.hpp' )
        if not os.path.exists( version_hpp_path ):
            raise BoostException("Boost version.hpp file not found")
        with open( version_hpp_path ) as version_hpp:
            for line in version_hpp:
                match = re.search( r'BOOST_VERSION\s+(?P<version>\d+)', line )
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


    def location_from_boost_version( self, location ):
        if location == "latest" or location == "current":
            location = determine_latest_boost_verion( self._env )
        if location:
            match = re.match( r'(boost_)?(?P<version>\d[._]\d\d(?P<minor>[._]\d)?)', location )
            if match:
                version = match.group('version')
                if not match.group('minor'):
                    version += "_0"
                print "cuppa: boost version specified as a location, attempt to download it"
                return "http://sourceforge.net/projects/boost/files/boost/{numeric_version}/boost_{string_version}.tar.gz/download".format(
                            numeric_version = version.translate( string.maketrans( '._', '..' ) ),
                            string_version = version.translate( string.maketrans( '._', '__' ) )
                        )
        return location


    def __init__( self, env, platform, base=None, location=None, version=None ):
        print "cuppa: boost: identify boost using base = [{}], location = [{}] and version = [{}]".format(
                as_info( env, str(base) ),
                as_info( env, str(location) ),
                as_info( env, str(version) )
            )

        if not base and not version and not location:
            raise BoostException("Cannot construct Boost Object. Invalid parameters")

        self._env = env
        self.values = {}
        self.values['name'] = 'boost'

        if location:
            location = self.location_from_boost_version( location )
            if not location: # use version as a fallback in case both at specified
                location = self.location_from_boost_version( version )
            self._location = cuppa.location.Location( env, location )

        elif base: # Find boost locally
            if not os.path.isabs( base ):
                base = os.path.abspath( base )

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

            print "cuppa: boost: using boost found at [{}]".format( as_info( env, self.values['home'] ) )
            self._location = cuppa.location.Location( env, self.values['home'] )
        else:
            location = self.location_from_boost_version( version )
            self._location = cuppa.location.Location( env, location )

        self.values['home'] = self._location.local()

        self.values['full_version'], self.values['version'], self.values['numeric_version'] = self.get_boost_version( self.values['home'] )

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

    def __init__( self, add_dependents=False, build_always=False, verbose_build=False, verbose_config=False ):
        self._add_dependents = add_dependents
        self._build_always   = build_always
        self._verbose_build  = verbose_build
        self._verbose_config = verbose_config

    def __call__( self, env, libraries ):
        if not self._add_dependents:
            print as_warning( env, "cuppa: boost: warning: BoostStaticLibrary() is deprecated, use BoostStaticLibs() or BoostStaticLib() instead" )
        libraries = Flatten( [ libraries ] )
        if not 'boost' in env['BUILD_WITH']:
            env.BuildWith( 'boost' )
        Boost = env['dependencies']['boost']
        library = BoostLibraryBuilder(
                Boost,
                add_dependents = self._add_dependents,
                verbose_build  = self._verbose_build,
                verbose_config = self._verbose_config )( env, None, None, libraries, 'static' )
        if self._build_always:
            return AlwaysBuild( library )
        else:
            return library



class BoostSharedLibraryMethod(object):

    def __init__( self, add_dependents=False, build_always=False, verbose_build=False, verbose_config=False ):
        self._add_dependents = add_dependents
        self._build_always   = build_always
        self._verbose_build  = verbose_build
        self._verbose_config = verbose_config

    def __call__( self, env, libraries ):
        if not self._add_dependents:
            print as_warning( env, "cuppa: boost: warning: BoostSharedLibrary() is deprecated, use BoostSharedLibs() or BoostSharedLib() instead" )
        libraries = Flatten( [ libraries ] )

        if not 'boost' in env['BUILD_WITH']:
            env.BuildWith( 'boost' )
        Boost = env['dependencies']['boost']

        for library in libraries:
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
                add_dependents = self._add_dependents,
                verbose_build  = self._verbose_build,
                verbose_config = self._verbose_config )( env, None, None, libraries, 'shared' )
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
    return toolset_name + '-' + toolchain.cxx_version()



class UpdateProjectConfigJam(object):

    def __init__( self, project_config_path ):
        self._project_config_path = project_config_path


    def __call__( self, target, source, env ):

        toolchain = env['toolchain']

        current_toolset = "using {} : {} :".format( toolset_name_from_toolchain( toolchain ), toolchain.cxx_version() )
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


def build_with_library_name( library ):
    return library == 'log_setup' and 'log' or library


def variant_name( variant ):
    if variant == 'dbg':
        return 'debug'
    else:
        return 'release'


def directory_from_abi_flag( abi_flag ):
    flag, value = abi_flag.split('=')
    if value:
        return value
    return abi_flag


def stage_directory( toolchain, variant, abi_flag ):
    build_base = "build"
    abi_dir = directory_from_abi_flag( abi_flag )
    if abi_dir:
        build_base += "." + abi_dir
    return os.path.join( build_base, toolchain.name(), variant )


def boost_dependency_order():
    return [ 'graph', 'regex', 'coroutine', 'context', 'log_setup', 'log', 'date_time', 'filesystem', 'timer', 'chrono', 'system', 'thread' ]


def boost_dependency_set():
    return set( boost_dependency_order() )


def boost_libraries_with_no_dependencies():
    return set( [
        'context',
        'date_time',
        'exception',
        'graph_parallel',
        'iostreams',
        'locale',
        'math',
        'mpi',
        'program_options',
        'python',
        'random',
        'regex',
        'serialization',
        'signals',
        'system',
        'test',
        'thread',
        'wave'
    ] )


def add_dependent_libraries( version, linktype, libraries ):
    required_libraries = set( libraries )
    for library in libraries:
        if library in boost_libraries_with_no_dependencies():
            continue
        elif library == 'chrono':
            required_libraries.update( ['system'] )
        elif library == 'coroutine':
            required_libraries.update( ['context', 'system'] )
            if version > 1.55:
                required_libraries.update( ['thread'] )
            if linktype == 'shared':
                required_libraries.update( ['chrono'] )
        elif library == 'filesystem':
            required_libraries.update( ['system'] )
        elif library == 'graph':
            required_libraries.update( ['regex'] )
        elif library == 'log':
            required_libraries.update( ['date_time', 'filesystem', 'system', 'thread'] )
        elif library == 'log_setup':
            required_libraries.update( ['log', 'date_time', 'filesystem', 'system', 'thread'] )
        elif library == 'timer':
            required_libraries.update( ['chrono'] )

    libraries = []

    for library in boost_dependency_order():
        if library in required_libraries:
            libraries.append( library )

    for library in required_libraries:
        if library not in boost_dependency_set():
            libraries.append( library )

    return libraries


class BoostLibraryAction(object):

    def __init__( self, env, libraries, add_dependents, linktype, boost, verbose_build, verbose_config ):
        self._env = env

        if add_dependents:
            self._libraries = set( build_with_library_name(l) for l in add_dependent_libraries( boost.numeric_version(), linktype, libraries ) )
        else:
            self._libraries = libraries

        self._location       = boost.local()
        self._version        = boost.numeric_version()
        self._full_version   = boost.full_version()
        self._verbose_build  = verbose_build
        self._verbose_config = verbose_config
        self._linktype       = linktype
        self._variant        = variant_name( self._env['variant'].name() )
        self._toolchain      = env['toolchain']
        self._job_count      = env['job_count']
        self._parallel       = env['parallel']


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


    def _build_command( self, env, toolchain, libraries, variant, linktype, stage_dir ):

        verbose = ""
        if self._verbose_build:
            verbose += " -d+2"
        if self._verbose_config:
            verbose += " --debug-configuration"

        jobs = "1"
        if self._job_count >= 2 and self._parallel:
            if len(libraries)>4:
                jobs = str( self._job_count - 1 )
            else:
                jobs = str( self._job_count/4 + 1 )

        with_libraries = ""
        for library in libraries:
            with_libraries += " --with-" + library

        build_flags = ""
        abi_flag = toolchain.abi_flag(env)
        if abi_flag:
            build_flags = 'cxxflags="' + abi_flag + '"'
        build_flags += ' define="BOOST_DATE_TIME_POSIX_TIME_STD_CONFIG"'

        if linktype == 'shared':
            build_flags += ' define="BOOST_ALL_DYN_LINK"'

        build_dir = "bin." + directory_from_abi_flag( abi_flag )

        command_line = "./bjam{verbose} -j {jobs}{with_libraries} toolset={toolset} variant={variant} {build_flags} link={linktype} --build-dir=./{build_dir} stage --stagedir=./{stage_dir}".format(
                verbose         = verbose,
                jobs            = jobs,
                with_libraries  = with_libraries,
                toolset         = toolset_from_toolchain( toolchain ),
                variant         = variant,
                build_flags     = build_flags,
                linktype        = linktype,
                build_dir       = build_dir,
                stage_dir       = stage_dir )

        print command_line
        return shlex.split( command_line )


    def __call__( self, target, source, env ):

        stage_dir = stage_directory( self._toolchain, self._variant, self._toolchain.abi_flag(env) )
        args      = self._build_command( env, self._toolchain, self._libraries, self._variant, self._linktype, stage_dir )

        processor = BjamOutputProcessor( env, self._verbose_build, self._verbose_config, self._toolset_name_from_toolchain( self._toolchain ) )

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


def static_library_name( env, library ):
    return env.subst('$LIBPREFIX') + 'boost_' + library + env.subst('$LIBSUFFIX')


def shared_library_name( env, library, full_version ):
    if cuppa.build_platform.name() == "Darwin":
        return env.subst('$SHLIBPREFIX') + 'boost_' + library + env.subst('$SHLIBSUFFIX')
    else:
        return env.subst('$SHLIBPREFIX') + 'boost_' + library + env.subst('$SHLIBSUFFIX') + '.' + full_version


class BoostLibraryEmitter(object):

    def __init__( self, env, libraries, add_dependents, linktype, boost ):
        self._env = env

        if add_dependents:
            self._libraries = add_dependent_libraries( boost.numeric_version(), linktype, libraries )
        else:
            self._libraries = libraries

        self._location     = boost.local()
        self._linktype     = linktype
        self._version      = boost.numeric_version()
        self._full_version = boost.full_version()
        self._variant      = variant_name( self._env['variant'].name() )
        self._toolchain    = env['toolchain']


    def __call__( self, target, source, env ):
        stage_dir = stage_directory( self._toolchain, self._variant, self._toolchain.abi_flag(env) )

        for library in self._libraries:
            filename = None
            if self._linktype == 'static':
                filename = static_library_name( env, library )
            else:
                filename = shared_library_name( env, library, self._full_version )

            built_library_path = os.path.join( self._location, stage_dir, 'lib', filename )
            node = File( built_library_path )
            target.append( node )
        return target, source



class BoostLibraryBuilder(object):

    def __init__( self, boost, add_dependents, verbose_build, verbose_config ):
        self._boost = boost
        self._add_dependents = add_dependents
        self._verbose_build  = verbose_build
        self._verbose_config = verbose_config


    def __call__( self, env, target, source, libraries, linktype ):
        library_action  = BoostLibraryAction ( env, libraries, self._add_dependents, linktype, self._boost, self._verbose_build, self._verbose_config )
        library_emitter = BoostLibraryEmitter( env, libraries, self._add_dependents, linktype, self._boost )

        env.AppendUnique( BUILDERS = {
            'BoostLibraryBuilder' : env.Builder( action=library_action, emitter=library_emitter )
        } )

        bjam_target = os.path.join( self._boost.local(), 'bjam' )
        bjam    = env.Command( bjam_target, [], BuildBjam( self._boost ) )
        env.NoClean( bjam )
        library = env.BoostLibraryBuilder( target, source )

        env.Requires( library, bjam )

        if cuppa.build_platform.name() == "Linux":
            project_config_target = os.path.join( self._boost.local(), "project-config.jam" )
            project_config_jam = env.Command( project_config_target, [], UpdateProjectConfigJam( project_config_target ) )
            env.Requires( library, project_config_jam )

        install_dir = ''
        library_name = os.path.split( library[0].path )[1]
        if linktype == 'shared':
            install_dir = os.path.split( os.path.join( env['abs_final_dir'], library_name ) )[0]

        installed_library = env.Install( install_dir, library )

        return installed_library


