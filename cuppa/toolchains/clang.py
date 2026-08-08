
#          Copyright Jamie Allsop 2014-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   CLANG Toolchain
#-------------------------------------------------------------------------------

import SCons.Script

from subprocess import Popen, PIPE
import os
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
from cuppa.cpp.run_gcov_coverage import RunGcovCoverageEmitter, RunGcovCoverage, CollateCoverageFilesEmitter, CollateCoverageFilesAction, CollateCoverageIndexEmitter, CollateCoverageIndexAction
from cuppa.output_processor import command_available
from cuppa.colourise import as_info, as_notice, as_warning
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
                    help="Specify the C++ standard library to build against ({}). "
                         "On Linux defaults to libstdc++.".format( str(std_lib_choices) ) )


        add_option( '--clang-disable-debug-for-auto', dest='clang-disable-debug-for-auto', action='store_true',
                    help="For clang versions before 3.6 this disables the -g flag so auto can compile" )


    @classmethod
    def version_from_command( cls, cxx ):
        command = "{} --version".format( cxx )
        if command_available( command ):
            reported_version = None
            version_string = as_str( Popen( shlex.split( command ), stdout=PIPE).communicate()[0] )
            is_apple = bool( re.search( r'Apple (?:clang|LLVM) version', version_string ) )
            matches = re.search( r'based on LLVM (?P<major>\d+)\.(?P<minor>\d)', version_string )
            if not matches:
                matches = re.search( r'Apple (?:clang|LLVM) version (?P<major>\d+)\.(?P<minor>\d)', version_string )
                if not matches:
                    matches = re.search( r'(?<!Apple )clang version (?P<major>\d+)\.(?P<minor>\d)', version_string )
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
                reported_version['apple'] = is_apple
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
            "clang22", "clang221",
            "clang21", "clang211",
            "clang20",
            "clang19",
            "clang18",
            "clang17",
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
            version = re.search( r'(?:LLVM version|clang version)\s+(\d+)(?:\.(\d+)\.(\d+))?', reported_version )
            if version:
                return version.group(1)
        return None


    @classmethod
    def coverage_tool( cls, reported_version ):
        """Return an llvm-cov/gcov command suitable for RunGcovCoverage / gcovr."""
        major = None
        if isinstance( reported_version, dict ):
            major = str( reported_version.get( 'major', '' ) or '' )
        elif reported_version:
            match = re.match( r'(\d+)', str( reported_version ).lstrip( '-' ) )
            if match:
                major = match.group( 1 )

        llvm_cov = "llvm-cov"
        if major:
            versioned_llvm_cov = "{llvm_cov}-{version}".format( llvm_cov=llvm_cov, version=major )
            if cuppa.build_platform.where_is( versioned_llvm_cov ):
                return versioned_llvm_cov + " gcov"

        if cuppa.build_platform.where_is( llvm_cov ):
            if major:
                tool_major = cls.llvm_version_from( llvm_cov )
                if tool_major and tool_major != major:
                    logger.warn(
                        "Using [{}] (LLVM {}) for clang{} coverage; prefer llvm-cov-{} if available".format(
                            as_warning( llvm_cov ),
                            as_info( tool_major or "?" ),
                            as_info( major ),
                            as_info( major ),
                        )
                    )
            return llvm_cov + " gcov"

        if cuppa.build_platform.where_is( "gcov" ):
            logger.warn( "llvm-cov not found; falling back to gcov for clang coverage" )
            return "gcov"

        logger.warn( "Coverage requested for current toolchain but none is available" )
        return None


    @classmethod
    def default_stdlib( cls ):
        # Clang on Linux uses libstdc++ by default; make that explicit for Boost b2
        # and for consistent -stdlib= flags on compile/link lines.
        if cuppa.build_platform.name() == "Linux":
            return "libstdc++"
        return None


    @classmethod
    def add_to_env( cls, env, add_toolchain, add_to_supported ):
        stdlib = None
        suppress_debug_for_auto = False
        try:
            stdlib = env.get_option( 'clang-stdlib' )
            suppress_debug_for_auto = env.get_option( 'clang-disable-debug-for-auto' )
        except:
            pass

        if not stdlib:
            stdlib = cls.default_stdlib()

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

        from cuppa.toolchains import toolchain_archive
        toolchain_archive.register_prepared( env, add_toolchain, add_to_supported, cls )


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

        self._stdlib = stdlib

        self.values = {}

        self._gcov_format = self._gcov_format_version()
        self._initialise_toolchain( self._reported_version, stdlib )

        cxx_name = "clang++{}".format( self._cxx_version and "-" +  self._cxx_version or "" )
        cc_name  = "clang{}".format( self._cxx_version and "-" +  self._cxx_version or "" )
        # Prefer absolute drivers so SCons' default ENV PATH (often /usr/bin first)
        # cannot silently pick up Apple Clang after configure saw Homebrew LLVM.
        self.values['CXX'] = self._resolve_driver( cxx_name )
        self.values['CC']  = self._resolve_driver( cc_name )

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
        # Build/ABI identity: platform default stdlib (libstdc++ on Linux) keeps the
        # bare reported name so existing paths stay stable; only a non-default
        # choice is tagged (e.g. clang21-libc++). Compiler commands use binary()/CXX.
        if self._stdlib and self._stdlib != self.default_stdlib():
            return "{}-{}".format( self._name, self._stdlib )
        return self._name


    def package_name( self ):
        return self.name()


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


    def _resolve_driver( self, name ):
        """Return an absolute path to a clang driver when its install dir is known."""
        if self._cxx_path:
            candidate = os.path.join( self._cxx_path, name )
            if os.path.exists( candidate ):
                return candidate
        return name


    def _resolve_versioned_tool( self, base_name ):
        """Prefer a major-versioned sibling of this Clang (e.g. llvm-ar-21), else base_name.

        ``cuppa.build_platform.where_is`` returns the *directory* containing the
        program (SCons WhereIs + dirname). Join the tool name back on before use.
        """
        major = self._reported_version['major']
        names = [
            "{}-{}".format( base_name, major ),
            base_name,
        ]
        for name in names:
            resolved = self._resolve_driver( name )
            if os.path.isabs( resolved ) and os.path.isfile( resolved ):
                return resolved
            found_dir = cuppa.build_platform.where_is( name )
            if found_dir:
                candidate = os.path.join( found_dir, name )
                if os.path.isfile( candidate ):
                    return candidate
        return None


    def binary( self ):
        return self.values['CXX']


    def make_env( self, cuppa_env, variant, target_arch ):
        env = None

        if not target_arch:
            target_arch = self._host_arch

        if platform.system() == "Windows":
            env = cuppa_env.create_env( tools = ['mingw'] )
            env['ENV']['PATH'] = os.pathsep.join( [ env['ENV']['PATH'], self._cxx_path ] )
        else:
            env = cuppa_env.create_env( tools = ['g++'] )
            # Prepend the discovered toolchain bin dir so sibling tools (and a
            # non-absolute CXX fallback) resolve to the same Clang as configure.
            if self._cxx_path:
                default_path = env['ENV'].get( 'PATH', '' )
                parts = [ self._cxx_path ]
                if default_path:
                    parts.extend( default_path.split( os.pathsep ) )
                env['ENV']['PATH'] = os.pathsep.join( parts )

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

        # Clang LTO bitcode in static archives needs a matching llvm-ar/ranlib.
        # Binutils ar loads whatever LLVMgold.so is on the system plugin path
        # (often an older LLVM), which silently drops symbols from .a files.
        if self.__lto_flags():
            llvm_ar = self._resolve_versioned_tool( 'llvm-ar' )
            if llvm_ar:
                env['AR'] = llvm_ar
            llvm_ranlib = self._resolve_versioned_tool( 'llvm-ranlib' )
            if llvm_ranlib:
                env['RANLIB'] = llvm_ranlib

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
        if not coverage_tool:
            return None, None
        return (
            RunGcovCoverageEmitter( program, final_dir, coverage_tool ),
            RunGcovCoverage( program, final_dir, coverage_tool, include_patterns, exclude_patterns ),
        )


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
            env.MergeFlags( self.values['coverage_flags'] )
            env.Append( CXXFLAGS = self.values['coverage_cxx_flags'] )
            env.AppendUnique( LINKFLAGS = self.values['coverage_link_flags'] )
        if env['stdcpp']:
            env.ReplaceFlags( "-std={}".format(env['stdcpp']) )


    def _gcov_format_version( self ):
        try:
            gcov_version = as_str( Popen(["gcov", "--version"], stdout=PIPE).communicate()[0] )
            match = re.search( r'(\d+)\.(\d+)\.(\d+)', gcov_version )
            if not match:
                return None
            # Clang's -coverage-version expects a 4-char magic like "A89*" for older gcov.
            # Prefer major/minor packed form when available; otherwise skip the override.
            major = int( match.group(1) )
            minor = int( match.group(2) )
            if major < 10:
                return "{major}0{minor}*".format( major=major, minor=minor )
            return None
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
        lto_flags       = self.__lto_flags()

        self.values['debug_cxx_flags']     = CommonCxxFlags + []
        # LTO is release-only (same policy as GCC): slower/heavier for dbg/cov;
        # runtime wins belong on --rel.
        self.values['release_cxx_flags']   = CommonCxxFlags + [ '-O3', '-DNDEBUG' ] + lto_flags

        if self._gcov_format:
            coverage_options = (
                "--coverage -Xclang -coverage-cfg-checksum "
                "-Xclang -coverage-no-function-names-in-data "
                "-Xclang -coverage-version={}".format( self._gcov_format )
            )
        else:
            # Modern clang + llvm-cov gcov: plain --coverage is sufficient
            coverage_options = "--coverage"

        self.values['coverage_flags']      = CommonCxxFlags
        self.values['coverage_cxx_flags']  = coverage_options.split()

        self.values['debug_c_flags']      = CommonCFlags + []
        self.values['release_c_flags']    = CommonCFlags + [ '-O3', '-DNDEBUG' ]

        CommonLinkCxxFlags = []
        if cuppa.build_platform.name() == "Linux":
            CommonLinkCxxFlags = ['-rdynamic', '-Wl,-rpath=.' ]

        if stdlib:
            CommonLinkCxxFlags += [ "-stdlib={}".format(stdlib) ]

        release_link_flags = list( CommonLinkCxxFlags )
        if lto_flags:
            release_link_flags += lto_flags
            # Prefer lld for Clang LTO so linking does not depend on binutils'
            # LLVMgold plugin matching this Clang's bitcode version.
            if self._resolve_versioned_tool( 'ld.lld' ) or self._resolve_versioned_tool( 'lld' ):
                release_link_flags.append( '-fuse-ld=lld' )

        self.values['debug_link_cxx_flags']   = CommonLinkCxxFlags
        self.values['release_link_cxx_flags'] = release_link_flags
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


    def __lto_flags( self ):
        """Release-only LTO flags (compile and link). Empty before Clang 8.

        Include `-ffat-lto-objects` so static archives remain usable when the
        archiver is binutils `ar` (system LLVMgold is often an older LLVM than
        the active clang++, which otherwise drops bitcode members).
        """
        major_ver = self._reported_version['major']
        if major_ver >= 17:
            return ['-flto=auto', '-ffat-lto-objects']
        if major_ver >= 8:
            return ['-flto', '-ffat-lto-objects']
        return []


    def abi_flag( self, env ):
        if env['stdcpp']:
            return '-std={}'.format(env['stdcpp'])
        else:
            return self.__default_dialect_flags()[0]


    def stdlib_flag( self, env ):
        if not self._stdlib:
            return None
        return '-stdlib={}'.format(self._stdlib)


    def supports_modules( self, env ):
        import cuppa.build_platform
        if cuppa.build_platform.name() not in ( "Linux", "Darwin" ):
            return False
        # Apple Clang reports high majors but does not support C++20 named modules.
        if self._reported_version.get( 'apple' ):
            return False
        return self._reported_version['major'] >= 16


    def supports_import_std( self, env ):
        import cuppa.build_platform
        if cuppa.build_platform.name() not in ( "Linux", "Darwin" ):
            return False
        # Apple Clang does not provide C++20 modules / import std.
        if self._reported_version.get( 'apple' ):
            return False
        if self._reported_version['major'] < 18:
            return False
        return getattr( self, '_stdlib', None ) == 'libc++'


    def modules_enable_flags( self, env ):
        # Avoid -fmodules here: that enables Clang *header* modules and breaks
        # C++20 header-unit imports (import <span>;) and libc++ std.cppm.
        return []


    def module_bmi_path( self, env, module_name ):
        from cuppa.toolchains.cxx_modules_support import named_bmi_path
        return named_bmi_path( env, module_name, '.pcm' )


    def header_unit_bmi_path( self, env, header_path ):
        from cuppa.toolchains.cxx_modules_support import header_bmi_path
        return header_bmi_path( env, header_path, '.pcm' )


    def write_module_mapper( self, env ):
        return None


    def interface_module_flags( self, env, module_name, bmi_path, exported=True ):
        return [
            '-x', 'c++-module',
            '-fmodule-output={}'.format( bmi_path ),
        ]


    def consume_module_flags( self, env, scan ):
        from cuppa.cpp.cxx_modules import get_registry, lookup_header_entry
        from cuppa.cpp.module_scanner import owning_module_name, qualify_relative_import
        flags = []
        registry = get_registry( env )
        if not scan:
            return flags

        def add_named( name, seen ):
            if not name or name in seen:
                return
            entry = registry['named'].get( name )
            if not entry:
                return
            seen.add( name )
            flag = '-fmodule-file={}={}'.format( name, entry['path'] )
            if flag not in flags:
                flags.append( flag )
            for dep in entry.get( 'imports', [] ):
                add_named( dep, seen )

        owner = owning_module_name( scan )
        seen = set()
        for item in scan.imports:
            if item.kind == 'named':
                name = qualify_relative_import( item.name, owner )
                add_named( name, seen )
            else:
                entry = lookup_header_entry( registry, item.name )
                if entry:
                    flag = '-fmodule-file={}'.format( entry['path'] )
                    if flag not in flags:
                        flags.append( flag )
        if scan.module_declaration:
            decl = scan.module_declaration
            if ':' in decl:
                # Partition BMI unit: reference primary, never self-reference.
                primary = decl.split( ':', 1 )[0]
                add_named( primary, seen )
            else:
                add_named( decl, seen )
        return flags


    def build_header_unit( self, env, header, bmi_path, **kwargs ):
        kwargs.pop( 'declared', None )
        system_header = kwargs.pop( 'system_header', None )
        if system_header:
            header_abs = self._find_system_header_path( env, system_header )
            source = header_abs or system_header
            action = (
                '$CXX -o $TARGET --precompile -fmodule-header -x c++-header '
                '$CXXFLAGS $_CPPINCFLAGS {source}'
                .format( source=source )
            )
            return env.Command( bmi_path, [], action, **kwargs )[0]
        action = (
            '$CXX -o $TARGET --precompile -fmodule-header $CXXFLAGS $_CPPINCFLAGS $SOURCES'
        )
        return env.Command( bmi_path, header, action, **kwargs )[0]


    def _find_system_header_path( self, env, name ):
        import os
        import subprocess
        try:
            probe = '#include <{}>\n'.format( name )
            cmd = [ self.binary(), '-std=c++20', '-M', '-x', 'c++', '-' ]
            stdlib = self.stdlib_flag( env )
            if stdlib:
                cmd.insert( 1, stdlib )
            result = subprocess.run(
                cmd,
                input=probe,
                capture_output=True,
                text=True,
                timeout=30,
            )
            for token in result.stdout.replace( '\\', ' ' ).split():
                if token.endswith( '/' + name ) or os.path.basename( token ) == name:
                    if os.path.isfile( token ):
                        return os.path.abspath( token )
        except Exception:
            pass
        # Common libc++ / system locations
        for candidate in (
            '/usr/include/c++/v1/{}'.format( name ),
            '/usr/include/{}'.format( name ),
        ):
            if os.path.isfile( candidate ):
                return candidate
        return None


    def std_module_sources( self, env ):
        sources = {}
        for name, filename in (
            ( 'std', 'std.cppm' ),
            ( 'std.compat', 'std.compat.cppm' ),
        ):
            path = self._find_libcxx_module_interface( filename )
            if path:
                sources[name] = path
        return sources


    def _find_libcxx_module_interface( self, filename ):
        import os
        import subprocess
        candidates = []
        try:
            result = subprocess.run(
                [ self.binary(), '-print-resource-dir' ],
                capture_output=True,
                text=True,
                timeout=15,
            )
            resource = ( result.stdout or '' ).strip()
            if resource:
                # resource-dir is typically .../lib/clang/N — modules live under the llvm root.
                root = os.path.abspath( os.path.join( resource, '..', '..', '..' ) )
                candidates.append( os.path.join( root, 'share', 'libc++', 'v1', filename ) )
        except Exception:
            pass
        # Only probe the matching major — cross-version std.cppm is not ABI-safe.
        major = self._reported_version.get( 'major' )
        if major:
            candidates.append(
                '/usr/lib/llvm-{}/share/libc++/v1/{}'.format( major, filename )
            )
        candidates.append( '/usr/share/libc++/v1/{}'.format( filename ) )
        # Homebrew / macOS SDK layouts
        candidates.append( '/opt/homebrew/opt/llvm/share/libc++/v1/{}'.format( filename ) )
        candidates.append( '/usr/local/opt/llvm/share/libc++/v1/{}'.format( filename ) )
        for path in candidates:
            if path and os.path.isfile( path ):
                return path
        return None


    def build_std_module( self, env, name ):
        from cuppa.toolchains.cxx_modules_support import modules_build_dir, named_bmi_path
        from cuppa.cpp.cxx_modules import register_named_module, get_registry

        sources = self.std_module_sources( env )
        source = sources.get( name )
        if not source:
            return None
        if name in get_registry( env )['named']:
            return get_registry( env )['named'][name]['bmi']

        modules_build_dir( env )
        bmi_path = named_bmi_path( env, name, '.pcm' )
        bmi_node = env.File( bmi_path )
        register_named_module(
            env,
            name,
            bmi_path,
            bmi_node,
            imports=[ 'std' ] if name == 'std.compat' else [],
        )
        # Do not pass $CXXFLAGS: env modules flags include -fmodules, which enables
        # Clang header modules and conflicts with libc++'s C++20 std.cppm
        # ("redefinition of module 'std'" via module.modulemap).
        dialect = env.get( 'stdcpp' ) or 'c++23'
        stdlib = self.stdlib_flag( env ) or '-stdlib=libc++'
        extra = ''
        sources_nodes = []
        if name == 'std.compat' and 'std' in get_registry( env )['named']:
            std_bmi = get_registry( env )['named']['std']['path']
            extra = '-fmodule-file=std={} '.format( std_bmi )
            sources_nodes = [ get_registry( env )['named']['std']['bmi'] ]
        action = (
            '$CXX -o $TARGET --precompile -fmodule-output={bmi} '
            '{extra}-std={dialect} {stdlib} {source}'
            .format(
                bmi=bmi_path,
                extra=extra,
                dialect=dialect,
                stdlib=stdlib,
                source=source,
            )
        )
        return env.Command( bmi_path, sources_nodes, action )[0]


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
