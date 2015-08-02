
#          Copyright Jamie Allsop 2014-2015
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
from exceptions import Exception

import cuppa.build_platform

from cuppa.cpp.create_version_file_cpp import CreateVersionHeaderCpp, CreateVersionFileCpp
from cuppa.cpp.run_boost_test import RunBoostTestEmitter, RunBoostTest
from cuppa.cpp.run_patched_boost_test import RunPatchedBoostTestEmitter, RunPatchedBoostTest
from cuppa.cpp.run_process_test import RunProcessTestEmitter, RunProcessTest
from cuppa.cpp.run_gcov_coverage import RunGcovCoverageEmitter, RunGcovCoverage
from cuppa.output_processor import command_available



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
    def default_version( cls ):
        if not hasattr( cls, '_default_version' ):
            command = "clang++ --version"
            if command_available( command ):
                version = Popen( shlex.split( command ), stdout=PIPE).communicate()[0]
                cls._default_version = 'clang' + re.search( r'based on LLVM (\d)\.(\d)', version ).expand(r'\1\2')
            else:
                cls._default_version = None
        return cls._default_version


    @classmethod
    def supported_versions( cls ):
        return [
            "clang",
            "clang37",
            "clang36",
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
                    reported_version = 'clang' + re.search( r'based on LLVM (\d)\.(\d)', reported_version ).expand(r'\1\2')
                    if version == reported_version:
                        cls._available_versions.append( version )
                    else:
                        raise ClangException("CLANG toolchain [{}] reporting version as [{}].".format( version, reported_version ) )
            if cls._available_versions or cls.default_version():
                cls._available_versions.append( "clang" )
        return cls._available_versions



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

        for version in cls.available_versions():
            add_toolchain( version, cls( version, stdlib, suppress_debug_for_auto ) )


    @classmethod
    def default_variants( cls ):
        return [ 'dbg', 'rel' ]


    def _linux_lib_flags( self, env ):
        self.values['static_link']     = '-Xlinker -Bstatic'
        self.values['dynamic_link']    = '-Xlinker -Bdynamic'

        STATICLIBFLAGS  = self.values['static_link']   + ' ' + re.search( r'(.*)(,\s*LIBS\s*,)(.*)', env['_LIBFLAGS'] ).expand( r'\1, STATICLIBS,\3' )
        DYNAMICLIBFLAGS = self.values['dynamic_link']  + ' ' + re.search( r'(.*)(,\s*LIBS\s*,)(.*)', env['_LIBFLAGS'] ).expand( r'\1, DYNAMICLIBS,\3' )
        return STATICLIBFLAGS + ' ' + DYNAMICLIBFLAGS


    def __init__( self, version, stdlib, suppress_debug_for_auto ):

        if version == "clang":
            if self.default_version():
                version = self.default_version()
            else:
                version = self.available_versions()[0]

        self._suppress_debug_for_auto = suppress_debug_for_auto

        self.values = {}
        self._version = re.search( r'(\d)(\d)', version ).expand(r'\1.\2')
        self.values['name'] = version
        self._gcov_format = self._gcov_format_version()

        self._initialise_toolchain( version, stdlib )

        if version == self.default_version():
            self.values['CXX'] = "clang++"
            self.values['CC']  = "clang"
        else:
            self.values['CXX'] = "clang++-{}".format( self._version )
            self.values['CC']  = "clang-{}".format( self._version )

        env = SCons.Script.DefaultEnvironment()

        SYSINCPATHS = '${_concat(\"' + self.values['sys_inc_prefix'] + '\", SYSINCPATH, \"'+ self.values['sys_inc_suffix'] + '\", __env__, RDirs, TARGET, SOURCE)}'

        self.values['_CPPINCFLAGS'] = '$( ' + SYSINCPATHS + ' ${_concat(INCPREFIX, INCPATH, INCSUFFIX, __env__, RDirs, TARGET, SOURCE)} $)'

        if cuppa.build_platform.name() == "Linux":
            self.values['_LIBFLAGS'] = self._linux_lib_flags( env )
        else:
            self.values['_LIBFLAGS'] = env['_LIBFLAGS']


    def __getitem__( self, key ):
        return self.values.get( key )


    def name( self ):
        return self.values['name']


    def family( self ):
        return "clang"


    def version( self ):
        return self._version


    def cxx_version( self ):
        return self._version


    def binary( self ):
        return self.values['CXX']


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
        elif tester=='patched_boost':
            return RunPatchedBoostTest( expected ), RunPatchedBoostTestEmitter( final_dir )


    def test_runners( self ):
        return [ 'process', 'boost', 'patched_boost' ]


    def coverage_runner( self, program, final_dir ):
        return RunGcovCoverageEmitter( program, final_dir ), RunGcovCoverage( program, final_dir )


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
        gcov_version = Popen(["gcov", "--version"], stdout=PIPE).communicate()[0]
        gcov_version = re.search( r'(\d)\.(\d)\.(\d)', gcov_version ).expand(r'\g<1>0\g<2>')
        return gcov_version + '*'


    def _initialise_toolchain( self, toolchain, stdlib ):

        self.values['sys_inc_prefix']  = '-isystem'

        self.values['sys_inc_suffix']  = ''
        self.values['static_link']     = '-Xlinker -Bstatic'
        self.values['dynamic_link']    = '-Xlinker -Bdynamic'

        CommonCxxFlags = [ '-Wall', '-fexceptions' ]
        CommonCFlags   = [ '-Wall' ]

        if not re.match( 'clang3[2-5]', toolchain ) or not self._suppress_debug_for_auto:
            CommonCxxFlags += [ "-g" ]
            CommonCFlags += [ "-g" ]

        if stdlib:
            CommonCxxFlags += [ "-stdlib={}".format(stdlib) ]

        if re.match( 'clang3[2-3]', toolchain ):
            CommonCxxFlags += [ '-std=c++11' ]
        elif re.match( 'clang3[4-7]', toolchain ):
            CommonCxxFlags += [ '-std=c++1y' ]

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


    def abi_flag( self, env ):
        if env['stdcpp']:
            return '-std={}'.format(env['stdcpp'])
        elif re.match( 'clang3[2-3]', self.values['name'] ):
            return '-std=c++11'
        elif re.match( 'clang3[4-7]', self.values['name'] ):
            return '-std=c++1y'


    def stdcpp_flag_for( self, standard ):
        return "-std={}".format( standard )


    def error_format( self ):
        return "{}:{}: {}"


    @classmethod
    def output_interpretors( cls ):
        return [
        {
            'title'     : "Compiler Error",
            'regex'     : r"([][{}() \t#%$~\w&_:+/\.-]+)(:([0-9]+):([0-9]+))(:[ \t](error:[ \t].*))",
            'meaning'   : 'error',
            'highlight' : set( [ 1, 2 ] ),
            'display'   : [ 1, 2, 5 ],
            'file'      : 1,
            'line'      : None,
            'column'    : None,
        },
        {
            'title'     : "Compiler Warning",
            'regex'     : r"([][{}() \t#%$~\w&_:+/\.-]+)(:([0-9]+):([0-9]+))(:[ \t](warning:[ \t].*))",
            'meaning'   : 'warning',
            'highlight' : set( [ 1, 2 ] ),
            'display'   : [ 1, 2, 5 ],
            'file'      : 1,
            'line'      : None,
            'column'    : None,
        },
        {
            'title'     : "Compiler Note",
            'regex'     : r"([][{}() \t#%$~\w&_:+/\.-]+)(:([0-9]+):([0-9]+))(:[ \t](note:[ \t].*))",
            'meaning'   : 'message',
            'highlight' : set( [ 1, 2 ] ),
            'display'   : [ 1, 2, 5 ],
            'file'      : 1,
            'line'      : None,
            'column'    : None,
        },
        {
            'title'     : "Linker Warning",
            'regex'     : r"([][{}() \t#%$~\w&_:+/\.-]+)(:\(\.text\+[0-9a-fA-FxX]+\))(:[ \t]([Ww]arning:[ \t].*))",
            'meaning'   : 'warning',
            'highlight' : set( [ 1, 2 ] ),
            'display'   : [ 1, 2, 4 ],
            'file'      : 1,
            'line'      : None,
            'column'    : None,
        },
        {
            'title'     : "Linker Error",
            'regex'     : r"([][{}() \t#%$~\w&_:+/\.-]+)(:([0-9]+):[0-9]+)(:[ \t](.*))",
            'meaning'   : 'error',
            'highlight' : set( [ 1, 2 ] ),
            'display'   : [ 1, 2, 4 ],
            'file'      : 1,
            'line'      : None,
            'column'    : None,
        },
        {
            'title'     : "Linker Error 2",
            'regex'     : r"([][{}() \t#%$~\w&_:+/\.-]+\(.text\+[0-9A-Za-z]+\):([ \tA-Za-z0-9_:+/\.-]+))(:[ \t](.*))",
            'meaning'   : 'error',
            'highlight' : set( [ 1 ] ),
            'display'   : [ 1, 4 ],
            'file'      : 1,
            'line'      : None,
            'column'    : None,
        },
        {
            'title'     : "Linker Error 3",
            'regex'     : r"(([][{}() \t#%$~\w&_:+/\.-]+):\(\.text\+[0-9a-fA-FxX]+\))(:(.*))",
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
            'regex'     : r"([][{}() \t#%$~\w&_:+/\.-]+)(:[ \t](undefined reference.*))",
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
