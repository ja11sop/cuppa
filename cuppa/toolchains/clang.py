
#          Copyright Jamie Allsop 2014-2020
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   CLANG Toolchain
#-------------------------------------------------------------------------------

import SCons.Script

from subprocess import Popen, PIPE
import re
import shlex
import collections
import platform
import six

import cuppa.build_platform

from cuppa.cpp.create_version_file_cpp import CreateVersionHeaderCpp, CreateVersionFileCpp
from cuppa.cpp.run_boost_test import RunBoostTestEmitter, RunBoostTest
from cuppa.cpp.run_patched_boost_test import RunPatchedBoostTestEmitter, RunPatchedBoostTest
from cuppa.cpp.run_process_test import RunProcessTestEmitter, RunProcessTest
#from cuppa.cpp.run_gcov_coverage import RunGcovCoverageEmitter, RunGcovCoverage, CollateCoverageFilesEmitter, CollateCoverageFilesAction, CollateCoverageIndexEmitter, CollateCoverageIndexAction
from cuppa.output_processor import command_available
from cuppa.colourise import as_info, as_notice
from cuppa.log import logger
from cuppa.utility.python2to3 import as_str, Exception



class ClangException(Exception):
    def __init__(self, value):
        self.parameter = value
    def __str__(self):
        return repr(self.parameter)


class Clang(object):

    @classmethod
    def add_options( cls, add_option ):

        std_lib_choices = ("libstdc++", "libc++")

        add_option( '--clang-stdlib', dest='clang-stdlib', choices=std_lib_choices, nargs=1, action='store',
                    help="!Experimental! Specify the standard library Version to build against. Value may be one of {}".format( str(std_lib_choices) ) )


        add_option( '--clang-disable-debug-for-auto', dest='clang-disable-debug-for-auto', action='store_true',
                    help="For clang versions before 3.6 this disables the -g flag so auto can compile" )


    @classmethod
    def version_from_command( cls, cxx ):
        command = "{} --version".format( cxx )
        if command_available( command ):
            reported_version = None
            version_string = as_str( Popen( shlex.split( command ), stdout=PIPE).communicate()[0] )
            matches = re.search( r'based on LLVM (?P<major>\d+)\.(?P<minor>\d)', version_string )
            if not matches:
                matches = re.search( r'Apple LLVM version (?P<major>\d+)\.(?P<minor>\d)', version_string )
                if not matches:
                    matches = re.search( r'clang version (?P<major>\d+)\.(?P<minor>\d)', version_string )
            if matches:
                major = matches.group('major')
                minor = matches.group('minor')
                reported_version = {}
                reported_version['toolchain'] = 'clang'
                reported_version['name'] = 'clang' + major + minor
                reported_version['major'] = int(major)
                reported_version['minor'] = int(minor)
                reported_version['version'] = major + "." + minor
                reported_version['short_version'] = major + minor
            return reported_version
        return None


    @classmethod
    def default_version( cls ):
        if not hasattr( cls, '_default_version' ):
            cxx = "clang++"
            command = "{} --version".format( cxx )
            reported_version = cls.version_from_command( command )
            cxx_version = ""
            if reported_version:
                major = reported_version['major']
                minor = reported_version['minor']
                version = "-{}.{}".format( major, minor )
                exists = cls.version_from_command( "clang++{} --version".format( version ) )
                if exists:
                    cxx_version = version
                else:
                    version = "-{}".format( major )
                    exists = cls.version_from_command( "clang++{} --version".format( version ) )
                    if exists:
                        cxx_version = version
            cls._default_version = ( reported_version, cxx_version )
        return cls._default_version


    @classmethod
    def supported_versions( cls ):
        return [
            "clang",
            "clang16",
            "clang15",
            "clang14",
            "clang13",
            "clang12",
            "clang11",
            "clang10",
            "clang9",
            "clang8",
            "clang7",
            "clang60",
            "clang50",
            "clang40",
            "clang39", "clang38", "clang37", "clang36", "clang35", "clang34", "clang33", "clang32"
        ]


    @classmethod
    def available_versions( cls ):
        if not hasattr( cls, '_available_versions' ):
            cls._available_versions = collections.OrderedDict()
            for version in cls.supported_versions():

                matches = re.match( r'clang(?P<version>(\d+)?)?', version )

                if not matches:
                    raise ClangException("Clang toolchain [{}] is not recognised as supported!".format( version ) )

                major = None
                minor = None

                version_string = matches.group('version')

                if len(version_string):
                    if int(version_string) <= 30:
                        major = int(version_string)
                    elif len(version_string) == 2:
                        major = int(version_string[0])
                        minor = int(version_string[1])
                    else:
                        major = int(version_string)

                if not major and not minor:
                    default_ver, default_cxx = cls.default_version()
                    if default_ver:
                        path = cuppa.build_platform.where_is( "clang++" )
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
                    cxx = "clang++{}".format( cxx_version )
                    reported_version = cls.version_from_command( cxx )
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
                    cxx = "clang++{}".format( cxx_version )
                    reported_version = cls.version_from_command( cxx )
                    if reported_version:
                        if version == reported_version['name']:
                            cxx_path = cuppa.build_platform.where_is( cxx )
                            cls._available_versions[reported_version['name']] = {
                                    'cxx_version': cxx_version,
                                    'version': reported_version,
                                    'path': cxx_path
                            }
                        else:
                            raise ClangException("Clang toolchain [{}] reporting version as [{}].".format( version, reported_version['name'] ) )
        return cls._available_versions


    @classmethod
    def llvm_version_from( cls, llvm_tool ):
        command = "{} --version".format( llvm_tool )
        if command_available( command ):
            reported_version = as_str( Popen( shlex.split( command ), stdout=PIPE).communicate()[0] )
            version = re.search( r'LLVM version (\d)\.(\d)\.(\d)', reported_version )
            reported_version = version.expand(r'\1')
            return reported_version
        return None


    @classmethod
    def coverage_tool( cls, cxx_version ):
        llvm_cov = "llvm-cov"
        versioned_llvm_cov = None
        if cxx_version:
            versioned_llvm_cov = "{llvm_cov}-{version}".format( llvm_cov=llvm_cov, version=cxx_version[0] )
            if cuppa.build_platform.where_is( versioned_llvm_cov ):
                return versioned_llvm_cov + " gcov"
        if cuppa.build_platform.where_is( llvm_cov ):
            version = cls.llvm_version_from( llvm_cov )
            if version == cxx_version:
                return llvm_cov + " gcov"
        logger.warn( "Coverage requested for current toolchain but none is available" )
        return None


    @classmethod
    def add_to_env( cls, env, add_toolchain, add_to_supported ):
        stdlib = None
        try:
            stdlib = env.get_option( 'clang-stdlib' )
            suppress_debug_for_auto = env.get_option( 'clang-disable-debug-for-auto' )
        except:
            pass

        for version in cls.supported_versions():
            add_to_supported( version )

        for version, clang in six.iteritems(cls.available_versions()):
            logger.debug(
                    "Adding toolchain [{}] reported as [{}] with cxx_version [clang++{}] at [{}]".format(
                    as_info(version),
                    as_info(clang['version']['name']),
                    as_info(clang['cxx_version']),
                    as_notice(clang['path'])
            ) )
            add_toolchain(
                    version,
                    cls( version, clang['cxx_version'], clang['version'], clang['path'], stdlib, suppress_debug_for_auto )
            )


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


    def __init__( self, version, cxx_version, reported_version, cxx_path, stdlib, suppress_debug_for_auto ):

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

        self._suppress_debug_for_auto = suppress_debug_for_auto

        self.values = {}

        self._gcov_format = self._gcov_format_version()
        self._initialise_toolchain( self._reported_version, stdlib )

        self.values['CXX'] = "clang++{}".format( self._cxx_version and "-" +  self._cxx_version or "" )
        self.values['CC']  = "clang{}".format( self._cxx_version and "-" +  self._cxx_version or "" )

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
        return "clang"


    def toolset_name( self ):
        return "clang"


    def toolset_tag( self ):
        return "clang"


    def version( self ):
        return self._version


    def short_version( self ):
        return self._short_version


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
        #return 'coverage_cxx_flags' in self.values
        return False


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
        #coverage_tool = self.coverage_tool( self._cxx_version )
        #return RunGcovCoverageEmitter( program, final_dir, coverage_tool ), RunGcovCoverage( program, final_dir, coverage_tool, include_patterns, exclude_patterns )
        return None, None

    def coverage_collate_files( self, destination=None ):
        #return CollateCoverageFilesEmitter( destination ), CollateCoverageFilesAction( destination )
        return None, None


    def coverage_collate_index( self, destination=None ):
        #return CollateCoverageIndexEmitter( destination ), CollateCoverageIndexAction( destination )
        return None, None


    def update_variant( self, env, variant ):
        if variant == 'dbg':
            env.MergeFlags( self.values['debug_cxx_flags'] + self.values['debug_c_flags'] )
            env.AppendUnique( LINKFLAGS = self.values['debug_link_cxx_flags'] )
        elif variant == 'rel':
            env.MergeFlags( self.values['release_cxx_flags'] + self.values['release_c_flags'] )
            env.AppendUnique( LINKFLAGS = self.values['release_link_cxx_flags'] )
        elif variant == 'cov':
            env.MergeFlags( self.values['coverage_flags'] )
            env.Append( CXXFLAGS = self.values['coverage_cxx_flags'] )
            env.AppendUnique( LINKFLAGS = self.values['coverage_link_flags'] )
        if env['stdcpp']:
            env.ReplaceFlags( "-std={}".format(env['stdcpp']) )


    def _gcov_format_version( self ):
        try:
            gcov_version = Popen(["gcov", "--version"], stdout=PIPE).communicate()[0]
            gcov_version = re.search( r'(\d)\.(\d)\.(\d)', gcov_version ).expand(r'\g<1>0\g<2>')
            return gcov_version + '*'
        except:
            return None


    def _initialise_toolchain( self, version, stdlib ):

        self.values['sys_inc_prefix']  = '-isystem'

        self.values['sys_inc_suffix']  = ''
        self.values['static_link']     = '-Xlinker -Bstatic'
        self.values['dynamic_link']    = '-Xlinker -Bdynamic'

        CommonCxxFlags = [ '-Wall', '-fexceptions' ]
        CommonCFlags   = [ '-Wall' ]

        if not re.match( 'clang3[2-5]', version['name'] ) or not self._suppress_debug_for_auto:
            CommonCxxFlags += [ "-g" ]
            CommonCFlags += [ "-g" ]

        if stdlib:
            CommonCxxFlags += [ "-stdlib={}".format(stdlib) ]

        CommonCxxFlags += self.__default_dialect_flags()

        self.values['debug_cxx_flags']     = CommonCxxFlags + []
        self.values['release_cxx_flags']   = CommonCxxFlags + [ '-O3', '-DNDEBUG' ]

        coverage_options = "--coverage -Xclang -coverage-cfg-checksum -Xclang -coverage-no-function-names-in-data -Xclang -coverage-version={}".format( self._gcov_format )

        self.values['coverage_flags']      = CommonCxxFlags
        self.values['coverage_cxx_flags']  = coverage_options.split()

        self.values['debug_c_flags']      = CommonCFlags + []
        self.values['release_c_flags']    = CommonCFlags + [ '-O3', '-DNDEBUG' ]

        CommonLinkCxxFlags = []
        if cuppa.build_platform.name() == "Linux":
            CommonLinkCxxFlags = ['-rdynamic', '-Wl,-rpath=.' ]

        self.values['debug_link_cxx_flags']   = CommonLinkCxxFlags
        self.values['release_link_cxx_flags'] = CommonLinkCxxFlags
        self.values['coverage_link_flags']    = CommonLinkCxxFlags + [ '--coverage' ]

        DynamicLibraries = []
        if cuppa.build_platform.name() == "Linux":
            DynamicLibraries = [ 'pthread', 'rt' ]
            if stdlib == "libc++":
                DynamicLibraries += [ 'c++abi', 'c++', 'c++abi', 'm', 'c', 'gcc_s', 'gcc' ]
        self.values['dynamic_libraries'] = DynamicLibraries


    def __get_clang_coverage( self, object_dir, source ):
        # -l = --long-file-names
        # -p = --preserve-paths
        # -b = --branch-probabilities
        return 'gcov -o ' + object_dir \
               + ' -l -p -b ' \
               + source + ' > ' + source + '_summary.gcov'


    def __default_dialect_flags( self ):
        major_ver = self._reported_version['major']
        minor_ver = self._reported_version['minor']
        if major_ver == 3:
            if minor_ver >= 2 and minor_ver <= 3:
                return ['-std=c++11']
            elif minor_ver >= 4 and minor_ver <= 8:
                return ['-std=c++1y']
            elif minor_ver >= 9:
                return ['-std=c++1z']
        elif major_ver >= 4 and major_ver <= 5:
            return ['-std=c++1z']
        elif major_ver >= 6 and major_ver <= 12:
            return ['-std=c++2a']
        elif major_ver >= 13 and major_ver <= 16:
            return ['-std=c++2b']
        elif major_ver >= 17:
            return ['-std=c++2c']
        return ['-std=c++03']


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
            'title'     : "Compiler Error",
            'regex'     : r"([][{}() \t#%@$~\w&_:+/\.-]+)(:([0-9]+):([0-9]+))(:[ \t](error:[ \t].*))",
            'meaning'   : 'error',
            'highlight' : set( [ 1, 2 ] ),
            'display'   : [ 1, 2, 5 ],
            'file'      : 1,
            'line'      : None,
            'column'    : None,
        },
        {
            'title'     : "Compiler Warning",
            'regex'     : r"([][{}() \t#%@$~\w&_:+/\.-]+)(:([0-9]+):([0-9]+))(:[ \t](warning:[ \t].*))",
            'meaning'   : 'warning',
            'highlight' : set( [ 1, 2 ] ),
            'display'   : [ 1, 2, 5 ],
            'file'      : 1,
            'line'      : None,
            'column'    : None,
        },
        {
            'title'     : "Compiler Note",
            'regex'     : r"([][{}() \t#%@$~\w&_:+/\.-]+)(:([0-9]+):([0-9]+))(:[ \t](note:[ \t].*))",
            'meaning'   : 'message',
            'highlight' : set( [ 1, 2 ] ),
            'display'   : [ 1, 2, 5 ],
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
            'title'     : "Compiler Error",
            'regex'     : r"(error:)([ \t].*)",
            'meaning'   : 'error',
            'highlight' : set( [ 1 ] ),
            'display'   : [ 1, 2 ],
            'file'      : None,
            'line'      : None,
            'column'    : None,
        },
    ]
