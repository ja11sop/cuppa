
#          Copyright Jamie Allsop 2014-2014
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   CLANG Toolchain
#-------------------------------------------------------------------------------

import SCons.Script

from subprocess import Popen, PIPE
from string import strip, replace
import re
import os.path
import shlex
from exceptions import Exception

import modules.registration
import build_platform

from cpp.create_version_file_cpp import CreateVersionHeaderCpp, CreateVersionFileCpp
from cpp.run_boost_test import RunBoostTestEmitter, RunBoostTest
from cpp.run_process_test import RunProcessTestEmitter, RunProcessTest
from cpp.run_gcov_coverage import RunGcovCoverageEmitter, RunGcovCoverage
from output_processor import command_available



class ClangException(Exception):
    def __init__(self, value):
        self.parameter = value
    def __str__(self):
        return repr(self.parameter)


class Clang(object):


    @classmethod
    def default_version( cls ):
        if not hasattr( cls, '_default_version' ):
            command = "clang++ --version"
            if command_available( command ):
                version = Popen( shlex.split( command ), stdout=PIPE).communicate()[0]
                cls._default_version = 'clang' + re.search( r'(\d)\.(\d)', version ).expand(r'\1\2')
            else:
                cls._default_version = None
        return cls._default_version


    @classmethod
    def supported_versions( cls ):
        return [
            "clang",
            "clang35",
            "clang34",
            "clang33",
            "clang32"
        ]


    @classmethod
    def available_versions( cls ):
        if not hasattr( cls, '_available_versions' ):
            cls._available_versions = []
            for version in cls.supported_versions():
                if version == "clang":
                    continue
                command = "clang++-{} --version".format( re.search( r'(\d)(\d)', version ).expand(r'\1.\2') )
                if command_available( command ):
                    reported_version = Popen( shlex.split( command ), stdout=PIPE).communicate()[0]
                    reported_version = 'clang' + re.search( r'(\d)\.(\d)', reported_version ).expand(r'\1\2')
                    if version == reported_version:
                        cls._available_versions.append( version )
                    else:
                        raise ClangException("CLANG toolchain [{}] reporting version as [{}].".format( version, reported_version ) )
            if cls._available_versions:
                cls._available_versions.append( "clang" )
        return cls._available_versions


    @classmethod
    def add_options( cls ):
        pass


    @classmethod
    def add_to_env( cls, args ):
        for version in cls.supported_versions():
            args['env']['supported_toolchains'].append( version )

        for version in cls.available_versions():
            args['env']['toolchains'][version] = cls( version )


    @classmethod
    def default_variants( cls ):
        return [ 'dbg', 'rel' ]


    def __init__( self, version ):

        if version == "clang":
            version = self.default_version()

        self.values = {}
        self._version = re.search( r'(\d)(\d)', version ).expand(r'\1.\2')
        self.values['name'] = version
        self._gcov_format = self._gcov_format_version()

        self._initialise_toolchain( version )

        self.values['CXX'] = "clang++-{}".format( self._version )
        self.values['CC']  = "clang-{}".format( self._version )

        env = SCons.Script.DefaultEnvironment()

        SYSINCPATHS = '${_concat(\"' + self.values['sys_inc_prefix'] + '\", SYSINCPATH, \"'+ self.values['sys_inc_suffix'] + '\", __env__, RDirs, TARGET, SOURCE)}'
#
        self.values['_CPPINCFLAGS'] = '$( ' + SYSINCPATHS + ' ${_concat(INCPREFIX, INCPATH, INCSUFFIX, __env__, RDirs, TARGET, SOURCE)} $)'
#
        STATICLIBFLAGS  = self.values['static_link']   + ' ' + re.search( r'(.*)(,\s*LIBS\s*,)(.*)', env['_LIBFLAGS'] ).expand( r'\1, STATICLIBS,\3' )
        DYNAMICLIBFLAGS = self.values['dynamic_link']  + ' ' + re.search( r'(.*)(,\s*LIBS\s*,)(.*)', env['_LIBFLAGS'] ).expand( r'\1, DYNAMICLIBS,\3' )

        self.values['_LIBFLAGS'] = STATICLIBFLAGS + ' ' + DYNAMICLIBFLAGS


    def __getitem__( self, key ):
        return self.values.get( key )


    def name( self ):
        return self.values['name']


    def family( self ):
        return "clang"


    def version( self ):
        return self._version


    def initialise_env( self, env ):

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


    def variants( self ):
        pass


    def supports_coverage( self ):
        return 'coverage_cxx_flags' in self.values


    def version_file_builder( self, env, namespace, version, location ):
        return CreateVersionFileCpp( env, namespace, version, location )


    def version_file_emitter( self, env, namespace, version, location ):
        return CreateVersionHeaderCpp( env, namespace, version, location )


    def test_runner( self, tester, final_dir, expected ):
        if not tester or tester =='process':
            return RunProcessTest( expected ), RunProcessTestEmitter( final_dir )
        elif tester=='boost':
            return RunBoostTest( expected ), RunBoostTestEmitter( final_dir )


    def test_runners( self ):
        return [ 'process', 'boost' ]


    def coverage_runner( self, program, final_dir ):
        return RunGcovCoverageEmitter( program, final_dir ), RunGcovCoverage( program, final_dir )


    def _gcov_format_version( self ):
        gcov_version = Popen(["gcov", "--version"], stdout=PIPE).communicate()[0]
        gcov_version = re.search( r'(\d)\.(\d)\.(\d)', gcov_version ).expand(r'\g<1>0\g<2>')
        return gcov_version + '*'


    def _initialise_toolchain( self, toolchain ):

        self.values['sys_inc_prefix']  = '-isystem'

        self.values['sys_inc_suffix']  = ''
        self.values['static_link']     = '-Xlinker -Bstatic'
        self.values['dynamic_link']    = '-Xlinker -Bdynamic'

        CommonCxxFlags = [ '-Wall', '-Wextra', '-fexceptions', '-g' ]
        CommonCFlags   = [ '-Wall', '-Wextra', '-g' ]

        if re.match( 'clang3[2-3]', toolchain ):
            CommonCxxFlags += [ '-std=c++11' ]
        elif re.match( 'clang3[4-5]', toolchain ):
            CommonCxxFlags += [ '-std=c++1y' ]

        self.values['debug_cxx_flags']     = CommonCxxFlags + []
        self.values['release_cxx_flags']   = CommonCxxFlags + [ '-O3', '-DNDEBUG' ]

        coverage_options = "--coverage -Xclang -coverage-cfg-checksum -Xclang -coverage-no-function-names-in-data -Xclang -coverage-version={}".format( self._gcov_format )

        self.values['coverage_cxx_flags']  = CommonCxxFlags + coverage_options.split()
        self.values['coverage_libs']       = []

        self.values['debug_c_flags']      = CommonCFlags + []
        self.values['release_c_flags']    = CommonCFlags + [ '-O3', '-DNDEBUG' ]
        self.values['coverage_c_flags']   = CommonCFlags + coverage_options.split()

        CommonLinkCxxFlags = ['-rdynamic', '-Wl,-rpath=.' ]
        self.values['debug_link_cxx_flags'] = CommonLinkCxxFlags
        self.values['release_link_cxx_flags'] = CommonLinkCxxFlags
        self.values['coverage_link_cxx_flags'] = CommonLinkCxxFlags + [ '--coverage' ]

        if build_platform.name() == "Darwin":
            self.values['dynamic_libraries'] = []
        else:
            self.values['dynamic_libraries'] = [ 'pthread', 'rt' ]


    def __get_clang_coverage( self, object_dir, source ):
        # -l = --long-file-names
        # -p = --preserve-paths
        # -b = --branch-probabilities
        return 'gcov -o ' + object_dir \
               + ' -l -p -b ' \
               + source + ' > ' + source + '_summary.gcov'


    def build_flags_for( self, library ):
        if library == 'boost':
            if re.match( 'clang3[2-3]', self.values['name'] ):
                return 'cxxflags="-std=c++11"'
            elif re.match( 'clang3[4-5]', self.values['name'] ):
                return 'cxxflags="-std=c++1y"'

    @classmethod
    def output_interpretors( cls ):
        return []
