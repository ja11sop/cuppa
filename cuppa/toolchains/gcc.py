
#          Copyright Jamie Allsop 2011-2020
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   GCC Toolchain
#-------------------------------------------------------------------------------

import SCons.Script

from subprocess import Popen, PIPE
import re
import shlex
import collections
import platform
import six

from cuppa.cpp.create_version_file_cpp import CreateVersionHeaderCpp, CreateVersionFileCpp
from cuppa.cpp.run_boost_test import RunBoostTestEmitter, RunBoostTest
from cuppa.cpp.run_patched_boost_test import RunPatchedBoostTestEmitter, RunPatchedBoostTest
from cuppa.cpp.run_process_test import RunProcessTestEmitter, RunProcessTest
from cuppa.cpp.run_gcov_coverage import RunGcovCoverageEmitter, RunGcovCoverage, CollateCoverageFilesEmitter, CollateCoverageFilesAction, CollateCoverageIndexEmitter, CollateCoverageIndexAction
from cuppa.output_processor import command_available
from cuppa.log import logger
from cuppa.colourise import as_notice, as_info
import cuppa.build_platform
from cuppa.utility.python2to3 import as_str, Exception


class GccException(Exception):
    def __init__(self, value):
        self.parameter = value
    def __str__(self):
        return repr(self.parameter)


class Gcc(object):

    @classmethod
    def supported_versions( cls ):
        return [
            "gcc",
            "gcc14", "gcc141", "gcc142",
            "gcc13", "gcc131", "gcc132",
            "gcc12", "gcc121", "gcc122",
            "gcc11", "gcc111", "gcc112", "gcc113",
            "gcc10", "gcc102", "gcc101",
            "gcc9", "gcc93", "gcc92", "gcc91",
            "gcc8", "gcc83", "gcc82", "gcc81",
            "gcc7", "gcc74", "gcc73", "gcc72", "gcc71",
            "gcc6", "gcc64", "gcc63", "gcc62", "gcc61",
            "gcc5", "gcc54", "gcc53", "gcc52", "gcc51",
            "gcc4", "gcc49", "gcc48", "gcc47", "gcc46", "gcc45", "gcc44", "gcc43", "gcc42", "gcc41", "gcc40",
            "gcc34"
        ]


    @classmethod
    def version_from_command( cls, cxx, prefix ):
        command = "{} --version".format( cxx )
        if command_available( command ):
            reported_version = None
            version_string = as_str( Popen( shlex.split( command ), stdout=PIPE).communicate()[0] )
            matches = re.search( r'(?P<major>\d+)\.(?P<minor>\d)', version_string )
            if matches:
                major = matches.group('major')
                minor = matches.group('minor')
                reported_version = {}
                reported_version['toolchain'] = prefix
                reported_version['name'] = prefix + major + minor
                reported_version['major'] = int(major)
                reported_version['minor'] = int(minor)
                reported_version['version'] = major + "." + minor
                reported_version['short_version'] = major + minor
            return reported_version
        return None


    @classmethod
    def default_version( cls ):
        if not hasattr( cls, '_default_version' ):
            cxx = "g++"
            command = "{} --version".format( cxx )
            reported_version = cls.version_from_command( command, 'gcc' )
            cxx_version = ""
            if reported_version:
                major = reported_version['major']
                minor = reported_version['minor']
                version = "-{}.{}".format( major, minor )
                exists = cls.version_from_command( "g++{} --version".format( version ), 'gcc' )
                if exists:
                    cxx_version = version
                else:
                    version = "-{}".format( major )
                    exists = cls.version_from_command( "g++{} --version".format( version ), 'gcc' )
                    if exists:
                        cxx_version = version
            cls._default_version = ( reported_version, cxx_version )
        return cls._default_version


    @classmethod
    def available_versions( cls ):
        if not hasattr( cls, '_available_versions' ):
            cls._available_versions = collections.OrderedDict()
            for version in cls.supported_versions():

                matches = re.match( r'gcc(?P<version>(\d+)?)?', version )

                if not matches:
                    raise GccException("GCC toolchain [{}] is not recognised as supported!".format( version ) )

                major = None
                minor = None

                version_string = matches.group('version')

                if len(version_string) and len(version_string) <= 2 and int(version_string[0]) >= 3:
                    matches = re.match( r'(?P<major>(\d))?(?P<minor>(\d))?', version_string )
                    if matches:
                        major = matches.group('major')
                        minor = matches.group('minor')
                elif len(version_string) >= 2:
                    matches = re.match( r'(?P<major>(\d\d))?(?P<minor>(\d))?', version_string )
                    if matches:
                        major = matches.group('major')
                        minor = matches.group('minor')

                if not major and not minor:
                    default_ver, default_cxx = cls.default_version()
                    if default_ver:
                        path = cuppa.build_platform.where_is( "g++" )
                        cls._available_versions[version] = {
                                'cxx_version': default_cxx,
                                'version': default_ver,
                                'path': path
                        }
                        cls._available_versions[default_ver['name']] = {
                                'cxx_version': default_cxx,
                                'version': default_ver,
                                'path': path
                        }
                elif not minor:
                    cxx_version = "-{}".format( major )
                    cxx = "g++{}".format( cxx_version )
                    reported_version = cls.version_from_command( cxx, 'gcc' )
                    if reported_version:
                        cxx_path = cuppa.build_platform.where_is( cxx )
                        cls._available_versions[version] = {
                                'cxx_version': cxx_version,
                                'version': reported_version,
                                'path': cxx_path
                        }
                        cls._available_versions[reported_version['name']] = {
                                'cxx_version': cxx_version,
                                'version': reported_version,
                                'path': cxx_path
                        }
                else:
                    cxx_version = "-{}.{}".format( major, minor )
                    cxx = "g++{}".format( cxx_version )
                    reported_version = cls.version_from_command( cxx, 'gcc' )
                    if reported_version:
                        if version == reported_version['name']:
                            cxx_path = cuppa.build_platform.where_is( cxx )
                            cls._available_versions[reported_version['name']] = {
                                    'cxx_version': cxx_version,
                                    'version': reported_version,
                                    'path': cxx_path
                            }
                        else:
                            raise GccException("GCC toolchain [{}] reporting version as [{}].".format( version, reported_version['name'] ) )
        return cls._available_versions


    @classmethod
    def coverage_tool( cls, reported_version ):
        gcov = "gcov"
        versioned_gcov = "{gcov}-{version}".format( gcov=gcov, version=str(reported_version['major']) )
        if cuppa.build_platform.where_is( versioned_gcov ):
            return versioned_gcov
        if cuppa.build_platform.where_is( gcov ):
            version = cls.version_from_command( gcov, "gcc" )
            if version == reported_version:
                return gcov
        logger.warn( "Coverage requested for current toolchain but none is available" )
        return None


    @classmethod
    def add_options( cls, add_option ):
        pass


    @classmethod
    def add_to_env( cls, env, add_toolchain, add_to_supported ):
        for version in cls.supported_versions():
            add_to_supported( version )

        for version, gcc in six.iteritems(cls.available_versions()):
            logger.debug(
                "Adding toolchain [{}] reported as [{}] with cxx_version [g++{}] at [{}]"
                .format( as_info(version), as_info(gcc['version']['name']), as_info(gcc['cxx_version']), as_notice(gcc['path']) )
            )
            add_toolchain( version, cls( version, gcc['cxx_version'], gcc['version'], gcc['path'] ) )


    @classmethod
    def default_variants( cls ):
        return [ 'dbg', 'rel' ]


    @classmethod
    def host_architecture( cls, env ):
        arch = env.get('HOST_ARCH')
        if not arch:
            arch = platform.machine()
        return arch


    def _linux_lib_flags( self, env ):
        self.values['static_link']     = '-Xlinker -Bstatic'
        self.values['dynamic_link']    = '-Xlinker -Bdynamic'

        STATICLIBFLAGS  = self.values['static_link']   + ' ' + re.search( r'(.*)(,\s*LIBS\s*,)(.*)', env['_LIBFLAGS'] ).expand( r'\1, STATICLIBS,\3' )
        DYNAMICLIBFLAGS = self.values['dynamic_link']  + ' ' + re.search( r'(.*)(,\s*LIBS\s*,)(.*)', env['_LIBFLAGS'] ).expand( r'\1, DYNAMICLIBS,\3' )
        return STATICLIBFLAGS + ' ' + DYNAMICLIBFLAGS


    def __init__( self, available_version, cxx_version, reported_version, cxx_path ):

        self.values = {}

        self._version          = reported_version['version']
        self._short_version    = reported_version['short_version']
        self._cxx_version      = cxx_version.lstrip('-')
        self._cxx_path         = cxx_path
        if self._cxx_version == cxx_version:
            self._cxx_version = ""
        else:
            self._cxx_version = self._cxx_version

        self._name             = reported_version['name']
        self._reported_version = reported_version

        self._initialise_toolchain( self._reported_version )

        self.values['CXX'] = "g++{}".format( self._cxx_version and "-" +  self._cxx_version or "" )
        self.values['CC']  = "gcc{}".format( self._cxx_version and "-" +  self._cxx_version or "" )

        env = SCons.Script.DefaultEnvironment()
        if platform.system() == "Windows":
            SCons.Script.Tool( 'mingw' )( env )
        else:
            SCons.Script.Tool( 'g++' )( env )

        self._host_arch = self.host_architecture( env )

        SYSINCPATHS = '${_concat(\"' + self.values['sys_inc_prefix'] + '\", SYSINCPATH, \"'+ self.values['sys_inc_suffix'] + '\", __env__, RDirs, TARGET, SOURCE)}'

        self.values['_CPPINCFLAGS'] = '$( ' + SYSINCPATHS + ' ${_concat(INCPREFIX, INCPATH, INCSUFFIX, __env__, RDirs, TARGET, SOURCE)} $)'

        if cuppa.build_platform.name() == "Linux":
            self.values['_LIBFLAGS'] = self._linux_lib_flags( env )
        else:
            self.values['_LIBFLAGS'] = env['_LIBFLAGS']


    def __getitem__( self, key ):
        return self.values.get( key )


    def name( self ):
        return self._name


    def family( self ):
        return "gcc"


    def toolset_name( self ):
        return "gcc"


    def toolset_tag( self ):
        return "gcc"


    def short_version( self ):
        return self._short_version


    def version( self ):
        return self._version


    def cxx_version( self ):
        return self._cxx_version


    def binary( self ):
        return self.values['CXX']


    def make_env( self, cuppa_env, variant, target_arch ):

        env = None

        if not target_arch:
            target_arch = self._host_arch

        if platform.system() == "Windows":
            env = cuppa_env.create_env( tools = ['mingw'] )
            env['ENV']['PATH'] = ";".join( [ env['ENV']['PATH'], self._cxx_path ] )
        else:
            env = cuppa_env.create_env( tools = ['g++'] )

        env['CXX']          = self.values['CXX']
        env['CC']           = self.values['CC']
        env['_CPPINCFLAGS'] = self.values['_CPPINCFLAGS']
        env['_LIBFLAGS']    = self.values['_LIBFLAGS']
        env['CCFLAGS']      = []
        env['SYSINCPATH']   = []
        env['INCPATH']      = [ '#.', '.' ]
        env['LIBPATH']      = []
        env['CPPDEFINES']   = []
        env['LIBS']         = []
        env['STATICLIBS']   = []
        env['DYNAMICLIBS']  = self.values['dynamic_libraries']

        self.update_variant( env, variant.name() )

        return env, target_arch


    def variants( self ):
        pass


    def supports_coverage( self ):
        return 'coverage_cxx_flags' in self.values


    def version_file_builder( self, env, namespace, version, location, build_id=None ):
        return CreateVersionFileCpp( env, namespace, version, location, build_id=build_id )


    def version_file_emitter( self, env, namespace, version, location, build_id=None ):
        return CreateVersionHeaderCpp( env, namespace, version, location, build_id=build_id )


    def test_runner( self, tester, final_dir, expected, **kwargs ):

        if not tester or tester =='process':
            return RunProcessTest( expected, final_dir, **kwargs ), RunProcessTestEmitter( final_dir, **kwargs )
        elif tester=='boost':
            return RunBoostTest( expected, final_dir, **kwargs ), RunBoostTestEmitter( final_dir, **kwargs )
        elif tester=='patched_boost':
            return RunPatchedBoostTest( expected, final_dir, **kwargs ), RunPatchedBoostTestEmitter( final_dir, **kwargs )


    def test_runners( self ):
        return [ 'process', 'boost', 'patched_boost' ]


    def benchmark_runner( self, benchmarker, final_dir, expected, **kwargs ):
        if not benchmarker or benchmarker == 'process':
            return RunProcessTest( expected, final_dir, **kwargs ), RunProcessTestEmitter( final_dir, **kwargs )
        elif benchmarker == 'boost':
            return RunBoostTest( expected, final_dir, **kwargs ), RunBoostTestEmitter( final_dir, **kwargs )
        elif benchmarker == 'patched_boost':
            return RunPatchedBoostTest( expected, final_dir, **kwargs ), RunPatchedBoostTestEmitter( final_dir, **kwargs )


    def benchmark_runners( self ):
        return [ 'process', 'boost', 'patched_boost' ]


    def coverage_runner( self, program, final_dir, include_patterns=[], exclude_patterns=[] ):
        coverage_tool = self.coverage_tool( self._reported_version )
        return RunGcovCoverageEmitter( program, final_dir, coverage_tool ), RunGcovCoverage( program, final_dir, coverage_tool, include_patterns, exclude_patterns )


    def coverage_collate_files( self, destination=None ):
        return CollateCoverageFilesEmitter( destination ), CollateCoverageFilesAction( destination )


    def coverage_collate_index( self, destination=None ):
        return CollateCoverageIndexEmitter( destination ), CollateCoverageIndexAction( destination )


    def update_variant( self, env, variant ):
        if variant == 'dbg':
            env.MergeFlags( self.values['debug_cxx_flags'] + self.values['debug_c_flags'] )
            env.AppendUnique( LINKFLAGS = self.values['debug_link_cxx_flags'] )
        elif variant == 'rel':
            env.MergeFlags( self.values['release_cxx_flags'] + self.values['release_c_flags'] )
            env.AppendUnique( LINKFLAGS = self.values['release_link_cxx_flags'] )
        elif variant == 'cov':
            env.MergeFlags( self.values['coverage_cxx_flags'] + self.values['coverage_c_flags'] )
            env.Append( CXXFLAGS = self.values['coverage_cxx_flags'] )
            env.AppendUnique( LINKFLAGS = self.values['coverage_link_cxx_flags'] )
        if env['stdcpp']:
            env.ReplaceFlags( "-std={}".format(env['stdcpp']) )


    def _initialise_toolchain( self, toolchain_version ):
        if toolchain_version['name'] == 'gcc34':
            self.values['sys_inc_prefix']  = '-I'
        else:
            self.values['sys_inc_prefix']  = '-isystem'

        self.values['sys_inc_suffix']  = ''

        CommonCxxFlags = [ '-Wall', '-fexceptions', '-g' ] + self.__default_dialect_flags()
        CommonCFlags   = [ '-Wall', '-g' ]

        self.values['debug_cxx_flags']    = CommonCxxFlags + []
        self.values['release_cxx_flags']  = CommonCxxFlags + [ '-O3', '-DNDEBUG' ]
        self.values['coverage_cxx_flags'] = CommonCxxFlags + [ '--coverage' ]

        self.values['debug_c_flags']      = CommonCFlags + []
        self.values['release_c_flags']    = CommonCFlags + [ '-O3', '-DNDEBUG' ]
        self.values['coverage_c_flags']   = CommonCFlags + [ '--coverage' ]

        CommonLinkCxxFlags = []
        if cuppa.build_platform.name() == "Linux":
            CommonLinkCxxFlags = self.__default_linker_flags() + ['-rdynamic', '-Wl,-rpath=.' ]

        self.values['debug_link_cxx_flags']    = CommonLinkCxxFlags
        self.values['release_link_cxx_flags']  = CommonLinkCxxFlags
        self.values['coverage_link_cxx_flags'] = CommonLinkCxxFlags + [ '--coverage' ]

        DynamicLibraries = []
        if cuppa.build_platform.name() == "Linux":
            DynamicLibraries = [ 'pthread', 'rt' ]
        self.values['dynamic_libraries'] = DynamicLibraries


    def __get_gcc_coverage( self, object_dir, source ):
        # -l = --long-file-names
        # -p = --preserve-paths
        # -b = --branch-probabilities
        return 'gcov -o ' + object_dir \
               + ' -l -p -b ' \
               + source + ' > ' + source + '_summary.gcov'


    def __default_dialect_flags( self ):
        major_ver = self._reported_version['major']
        minor_ver = self._reported_version['minor']
        if major_ver == 4:
            if minor_ver >= 3 and minor_ver <= 6:
                return ['-std=c++0x']
            elif minor_ver == 7:
                return ['-std=c++11']
            else:
                return ['-std=c++1y']
        elif major_ver == 5 and minor_ver <= 1:
            return ['-std=c++1y']
        elif major_ver >= 5 and major_ver < 8:
            return ['-std=c++1z']
        elif major_ver >= 8 and major_ver < 10:
            return ['-std=c++2a', '-fconcepts', '-flto']
        elif major_ver >= 10 and major_ver < 11:
            return ['-std=c++2a', '-fconcepts', '-fcoroutines', '-flto']
        elif major_ver >= 11 and major_ver < 12:
            return ['-std=c++2b', '-fconcepts', '-fcoroutines', '-flto']
        elif major_ver >= 12 and major_ver < 14:
            return ['-std=c++2b', '-fconcepts', '-fcoroutines', '-flto=auto']
        elif major_ver >= 14:
            return ['-std=c++2c', '-fconcepts', '-fcoroutines', '-flto=auto']
        return ['-std=c++03']


    def __default_linker_flags( self ):
        major_ver = self._reported_version['major']
        minor_ver = self._reported_version['minor']
        if major_ver == 4:
            if minor_ver >= 3 and minor_ver <= 6:
                return []
            elif minor_ver == 7:
                return []
            else:
                return []
        elif major_ver == 5 and minor_ver <= 1:
            return []
        elif major_ver >= 5 and major_ver < 8:
            return []
        elif major_ver >= 8 and major_ver < 10:
            return ['-flto']
        elif major_ver >= 10 and major_ver < 11:
            return ['-flto']
        elif major_ver >= 11 and major_ver < 12:
            return ['-flto']
        elif major_ver >= 12 and major_ver < 14:
            return ['-flto=auto']
        elif major_ver >= 14:
            return ['-flto=auto']
        return []


    def abi_flag( self, env ):
        if env['stdcpp']:
            return '-std={}'.format(env['stdcpp'])
        else:
            return self.__default_dialect_flags()[0]


    def abi( self, env ):
        return self.abi_flag( env ).split('=')[1]


    def stdcpp_flag_for( self, standard ):
        return "-std={}".format( standard )


    def error_format( self ):
        return "{}:{}: {}"


    @classmethod
    def output_interpretors( cls ):
        return [
        {
            'title'     : "Fatal Error",
            'regex'     : r"(FATAL:[ \t]*(.*))",
            'meaning'   : 'error',
            'highlight' : set( [ 1 ] ),
            'display'   : [ 1 ],
            'file'      : None,
            'line'      : None,
            'column'    : None,
        },
        {
            'title'     : "In File Included From",
            'regex'     : r"(In file included\s+|\s+)(from\s+)([][{}() \t#%@$~\w&_:+/\.-]+)(:([0-9]+)(:[0-9]+)?)([,:])",
            'meaning'   : 'message',
            'highlight' : set( [ 1, 3, 4 ] ),
            'display'   : [ 1, 2, 3, 4, 7 ],
            'file'      : 3,
            'line'      : None,
            'column'    : None,
        },
        {
            'title'     : "In Function Info",
            'regex'     : r"([][{}() \t#%@$~\w&_:+/\.-]+)(:[ \t]+([iI]n ([cC]lass|[cC]onstructor|[dD]estructor|[fF]unction|[mM]ember [fF]unction|[sS]tatic [fF]unction|[sS]tatic [mM]ember [fF]unction).*))",
            'meaning'   : 'message',
            'highlight' : set( [ 1 ] ),
            'display'   : [ 1, 2 ],
            'file'      : 1,
            'line'      : None,
            'column'    : None,
        },
        {
            'title'     : "Skipping Instantiation Contexts 2",
            'regex'     : r"([][{}() \t#%@$~\w&_:+/\.-]+)(:([0-9]+):[0-9]+)(:[ \t]+(\[[ \t]+[Ss]kipping [0-9]+ instantiation contexts[, \t]+.*\]))",
            'meaning'   : 'message',
            'highlight' : set( [ 1, 2 ] ),
            'display'   : [ 1, 2, 4 ],
            'file'      : 1,
            'line'      : None,
            'column'    : None,
        },
        {
            'title'     : "Skipping Instantiation Contexts",
            'regex'     : r"([][{}() \t#%@$~\w&_:+/\.-]+)(:([0-9]+))(:[ \t]+(\[[ \t]+[Ss]kipping [0-9]+ instantiation contexts[ \t]+\]))",
            'meaning'   : 'message',
            'highlight' : set( [ 1, 2 ] ),
            'display'   : [ 1, 2, 4 ],
            'file'      : 2,
            'line'      : None,
            'column'    : None,
        },
        {
            'title'     : "Instantiated From",
            'regex'     : r"([][{}() \t#%@$~\w&_:+/\.-]+)(:([0-9]+))(:[ \t]+([iI]nstantiated from .*))",
            'meaning'   : 'message',
            'highlight' : set( [ 1, 2] ),
            'display'   : [ 1, 2, 4 ],
            'file'      : 1,
            'line'      : None,
            'column'    : None,
        },
        {
            'title'     : "Instantiation of",
            'regex'     : r"([][{}() \t#%@$~\w&_:+/\.-]+)(:[ \t]+(In instantiation of .*))",
            'meaning'   : 'message',
            'highlight' : set( [ 1 ] ),
            'display'   : [ 1, 2 ],
            'file'      : 1,
            'line'      : None,
            'column'    : None,
        },
        {
            'title'     : "Required",
            'regex'     : r"([][{}() \t#%@$~\w&_:+/\.-]+)(:([0-9]+):[0-9]+)(:[ \t]+(?:[Rr]ecursively )?[Rr]equired (?:from|by) .*)",
            'meaning'   : 'message',
            'highlight' : set( [ 1, 2 ] ),
            'display'   : [ 1, 2, 4 ],
            'file'      : 1,
            'line'      : None,
            'column'    : None,
        },
        {
            'title'     : "In",
            'regex'     : r"([][{}() \t#%@$~\w&_:+/\.-]+)(:([0-9]+):[0-9]+)(:[ \t]+in .*)",
            'meaning'   : 'message',
            'highlight' : set( [ 1, 2 ] ),
            'display'   : [ 1, 2, 4 ],
            'file'      : 1,
            'line'      : None,
            'column'    : None,
        },
        {
            'title'     : "Compiler Warning 2",
            'regex'     : r"([][{}() \t#%@$~\w&_:+/\.-]+)(:([0-9]+):([0-9]+))(:[ \t]([Ww]arning:[ \t].*))",
            'meaning'   : 'warning',
            'highlight' : set( [ 1, 2 ] ),
            'display'   : [ 1, 2, 5 ],
            'file'      : 1,
            'line'      : None,
            'column'    : None,
        },
        {
            'title'     : "Compiler Note 2",
            'regex'     : r"([][{}() \t#%@$~\w&_:+/\.-]+)(:([0-9]+):[0-9]+)(:[ \t]([Nn]ote:[ \t].*))",
            'meaning'   : 'message',
            'highlight' : set( [ 1, 2 ] ),
            'display'   : [ 1, 2, 4 ],
            'file'      : 1,
            'line'      : None,
            'column'    : None,
        },
        {
            'title'     : "Compiler Note",
            'regex'     : r"([][{}() \t#%@$~\w&_:+/\.-]+)(:([0-9]+))(:[ \t]([Nn]ote:[ \t].*))",
            'meaning'   : 'message',
            'highlight' : set( [ 1, 2 ] ),
            'display'   : [ 1, 2, 4 ],
            'file'      : 1,
            'line'      : None,
            'column'    : None,
        },
        {
            'title'     : "General Note",
            'regex'     : r"([Nn]ote:[ \t].*)",
            'meaning'   : 'message',
            'highlight' : set( [ 1 ] ),
            'display'   : [ 1 ],
            'file'      : None,
            'line'      : None,
            'column'    : None,
        },
        {
            'title'     : "Compiler Error 2",
            'regex'     : r"([][{}() \t#%@$~\w&_:+/\.-]+)(:([0-9]+):[0-9]+)(:[ \t](.*))",
            'meaning'   : 'error',
            'highlight' : set( [ 1, 2 ] ),
            'display'   : [ 1, 2, 4 ],
            'file'      : 1,
            'line'      : None,
            'column'    : None,
        },
        {
            'title'     : "Compiler Warning",
            'regex'     : r"([][{}() \t#%@$~\w&_:+/\.-]+)(:([0-9]+))(:[ \t]([Ww]arning:[ \t].*))",
            'meaning'   : 'warning',
            'highlight' : set( [ 1 ] ),
            'display'   : [ 1, 2, 4 ],
            'file'      : 1,
            'line'      : None,
            'column'    : None,
        },
        {
            'title'     : "Undefined Reference 2",
            'regex'     : r"([][{}() \t#%@$~\w&_:+/\.-]+\.o:([][{}() \t#%@$~\w&_:+/\.-]+):([0-9]+))(:[ \t](undefined reference.*))",
            'meaning'   : 'warning',
            'highlight' : set( [ 1 ] ),
            'display'   : [ 1, 4 ],
            'file'      : 2,
            'line'      : None,
            'column'    : None,
        },
        {
            'title'     : "Compiler Error",
            'regex'     : r"([][{}() \t#%@$~\w&_:+/\.-]+)(:([0-9]+))(:[ \t](.*))",
            'meaning'   : 'error',
            'highlight' : set( [ 1, 2 ] ),
            'display'   : [ 1, 2, 4 ],
            'file'      : 1,
            'line'      : None,
            'column'    : None,
        },
        {
            'title'     : "Linker Warning",
            'regex'     : r"([][{}() \t#%@$~\w&_:+/\.-]+)(:\(\.text\+[0-9a-fA-FxX]+\))(:[ \t]([Ww]arning:[ \t].*))",
            'meaning'   : 'warning',
            'highlight' : set( [ 1, 2 ] ),
            'display'   : [ 1, 2, 4 ],
            'file'      : 1,
            'line'      : None,
            'column'    : None,
        },
        {
            'title'     : "Linker Error",
            'regex'     : r"([][{}() \t#%@$~\w&_:+/\.-]+)(:([0-9]+):[0-9]+)(:[ \t](.*))",
            'meaning'   : 'error',
            'highlight' : set( [ 1, 2 ] ),
            'display'   : [ 1, 2, 4 ],
            'file'      : 1,
            'line'      : None,
            'column'    : None,
        },
        {
            'title'     : "Linker Error 2",
            'regex'     : r"([][{}() \t#%@$~\w&_:+/\.-]+\(.text\+[0-9A-Za-z]+\):([ \tA-Za-z0-9_:+/\.-]+))(:[ \t](.*))",
            'meaning'   : 'error',
            'highlight' : set( [ 1 ] ),
            'display'   : [ 1, 4 ],
            'file'      : 1,
            'line'      : None,
            'column'    : None,
        },
        {
            'title'     : "Linker Error 3",
            'regex'     : r"(([][{}() \t#%@$~\w&_:+/\.-]+):\(\.text\+[0-9a-fA-FxX]+\))(:(.*))",
            'meaning'   : 'error',
            'highlight' : set( [ 1 ] ),
            'display'   : [ 1, 4 ],
            'file'      : 2,
            'line'      : None,
            'column'    : None,
        },
        {
            'title'     : "Linker Error - lib not found",
            'regex'     : r"(.*(ld.*):[ \t](cannot find.*))",
            'meaning'   : 'error',
            'highlight' : set( [ 1 ] ),
            'display'   : [ 1 ],
            'file'      : None,
            'line'      : None,
            'column'    : None,
        },
        {
            'title'     : "Linker Error - cannot open output file",
            'regex'     : r"(.*(ld.*):[ \t](cannot open output file.*))(:[ \t](.*))",
            'meaning'   : 'error',
            'highlight' : set( [ 1 ] ),
            'display'   : [ 1, 4 ],
            'file'      : None,
            'line'      : None,
            'column'    : None,
        },
        {
            'title'     : "Linker Error - unrecognized option",
            'regex'     : r"(.*(ld.*))(:[ \t](unrecognized option.*))",
            'meaning'   : 'error',
            'highlight' : set( [ 1 ] ),
            'display'   : [ 1, 3 ],
            'file'      : None,
            'line'      : None,
            'column'    : None,
        },
        {
            'title'     : "No such File or Directory",
            'regex'     : r"(.*:(.*))(:[ \t](No such file or directory.*))",
            'meaning'   : 'error',
            'highlight' : set( [ 1 ] ),
            'display'   : [ 1, 3 ],
            'file'      : None,
            'line'      : None,
            'column'    : None,
        },
        {
            'title'     : "Undefined Reference",
            'regex'     : r"([][{}() \t#%@$~\w&_:+/\.-]+)(:[ \t](undefined reference.*))",
            'meaning'   : 'error',
            'highlight' : set( [ 1 ] ),
            'display'   : [ 1, 2 ],
            'file'      : None,
            'line'      : None,
            'column'    : None,
        },
        {
            'title'     : "General Warning",
            'regex'     : r"([Ww]arning:[ \t].*)",
            'meaning'   : 'warning',
            'highlight' : set( [ 1 ] ),
            'display'   : [ 1 ],
            'file'      : None,
            'line'      : None,
            'column'    : None,
        },
        {
            'title'     : "Auto-Import Info",
            'regex'     : r"(([Ii]nfo:[ \t].*)\(auto-import\))",
            'meaning'   : 'message',
            'highlight' : set( [ 1 ] ),
            'display'   : [ 1 ],
            'file'      : None,
            'line'      : None,
            'column'    : None,
        },
    ]
