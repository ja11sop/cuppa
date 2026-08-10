
#          Copyright Jamie Allsop 2011-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   GCC Toolchain
#-------------------------------------------------------------------------------

import SCons.Script

from subprocess import Popen, PIPE
import os
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
            "gcc16", "gcc161",
            "gcc15", "gcc151", "gcc152", "gcc153",
            "gcc14", "gcc141", "gcc142", "gcc143",
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

        from cuppa.toolchains import toolchain_archive
        toolchain_archive.register_prepared_gcc( env, add_toolchain, add_to_supported, cls )


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

        cxx_name = "g++{}".format( self._cxx_version and "-" +  self._cxx_version or "" )
        cc_name  = "gcc{}".format( self._cxx_version and "-" +  self._cxx_version or "" )
        # Prefer absolute drivers for registered prefixes (snapshot / --gcc-root) so PATH
        # cannot silently pick up the distro g++ after configure saw the snapshot tree.
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
        return self._name


    def package_name( self ):
        return self.name()


    def family( self ):
        return "gcc"


    def describe( self ):
        from cuppa.toolchains.describe import describe_toolchain
        return describe_toolchain( self )


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


    def _resolve_driver( self, name ):
        """Return an absolute path to a gcc driver when its install dir is known."""
        if self._cxx_path:
            candidate = os.path.join( self._cxx_path, name )
            if os.path.exists( candidate ):
                return candidate
            # Unversioned g++ / gcc in a snapshot bin dir.
            bare = 'g++' if name.startswith( 'g++' ) else 'gcc'
            if bare != name:
                candidate = os.path.join( self._cxx_path, bare )
                if os.path.exists( candidate ):
                    return candidate
        return name


    def make_env( self, cuppa_env, variant, target_arch ):

        env = None

        if not target_arch:
            target_arch = self._host_arch

        if platform.system() == "Windows":
            env = cuppa_env.create_env( tools = ['mingw'] )
            env['ENV']['PATH'] = ";".join( [ env['ENV']['PATH'], self._cxx_path ] )
        else:
            env = cuppa_env.create_env( tools = ['g++'] )
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
        lto_flags      = self.__lto_flags()

        self.values['debug_cxx_flags']    = CommonCxxFlags + []
        # LTO is release-only: it raises link-time memory and slows dbg/cov builds;
        # the runtime benefit belongs on --rel.
        self.values['release_cxx_flags']  = CommonCxxFlags + [ '-O3', '-DNDEBUG' ] + lto_flags
        self.values['coverage_cxx_flags'] = CommonCxxFlags + [ '--coverage' ]

        self.values['debug_c_flags']      = CommonCFlags + []
        self.values['release_c_flags']    = CommonCFlags + [ '-O3', '-DNDEBUG' ]
        self.values['coverage_c_flags']   = CommonCFlags + [ '--coverage' ]

        CommonLinkCxxFlags = []
        if cuppa.build_platform.name() == "Linux":
            CommonLinkCxxFlags = ['-rdynamic', '-Wl,-rpath=.' ]

        self.values['debug_link_cxx_flags']    = CommonLinkCxxFlags
        self.values['release_link_cxx_flags']  = CommonLinkCxxFlags + lto_flags
        self.values['coverage_link_cxx_flags'] = CommonLinkCxxFlags + [ '--coverage' ]

        # Linux DYNAMICLIBS defaults (see toolchain-gcc.adoc § Default Linux libraries).
        # pthread: C++ threads / many libraries historically needed an explicit -lpthread
        # (glibc < 2.34). rt: clock_gettime and related APIs historically lived in librt
        # (integrated into libc on modern glibc). Both remain for older targets and are
        # harmless stubs/filters on current glibc; Cuppa's STATICLIBS/DYNAMICLIBS sandwich
        # places them in the dynamic half of the link line.
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


    def default_dialect( self ):
        """Cuppa default ``-std=`` token for this reported GCC version."""
        major_ver = self._reported_version['major']
        minor_ver = self._reported_version['minor']
        if major_ver == 4:
            if 3 <= minor_ver <= 6:
                return 'c++0x'
            if minor_ver == 7:
                return 'c++11'
            return 'c++1y'
        if major_ver == 5 and minor_ver <= 1:
            return 'c++1y'
        if 5 <= major_ver < 8:
            return 'c++1z'
        if 8 <= major_ver < 11:
            return 'c++2a'
        if 11 <= major_ver < 14:
            return 'c++2b'
        if major_ver >= 14:
            return 'c++2c'
        return 'c++03'


    def usable_features( self ):
        """Display items for verbose ``usable features:`` (see ``describe``)."""
        from cuppa.toolchains.describe import format_usable_feature_items

        major_ver = self._reported_version['major']
        dialect = self.default_dialect()
        gated = []
        dialect_inclusive = True
        if major_ver in ( 8, 9 ):
            # Concepts TS via -fconcepts — not ISO "all c++2a".
            gated.append( 'concepts' )
            dialect_inclusive = False
        elif major_ver == 10:
            gated.append( 'coroutines' )
        experimental = []
        try:
            if self.supports_modules( None ):
                experimental.append( 'modules (experimental)' )
        except Exception:
            pass
        return format_usable_feature_items(
                dialect,
                gated=gated,
                experimental=experimental,
                dialect_inclusive=dialect_inclusive,
        )


    def __default_dialect_flags( self ):
        """Default dialect ``-std=`` plus feature flags only when the dialect lacks them.

        Policy: latest dialect Cuppa selects for this GCC, with every language
        feature that dialect already enables — do **not** pass ``-fconcepts`` /
        ``-fcoroutines`` once they are part of the chosen ``-std=``. Extras are
        only for older GCC where the default dialect still needs a gate:

        * GCC 8–9 (``c++2a``): Concepts TS via ``-fconcepts`` (ISO C++20 concepts
          arrive in GCC 10).
        * GCC 10 (``c++2a``): coroutines still require ``-fcoroutines`` even with
          ``-std=c++2a`` / ``c++20`` (libstdc++ ``<coroutine>`` asserts this).
        * GCC 11+: concepts and coroutines come with the C++20+ dialects — ``-std=``
          alone.

        Modules stay opt-in via ``--modules`` (see ``modules_enable_flags``).
        """
        flags = [ '-std={}'.format( self.default_dialect() ) ]
        major_ver = self._reported_version['major']
        if major_ver in ( 8, 9 ):
            flags.append( '-fconcepts' )
        elif major_ver == 10:
            flags.append( '-fcoroutines' )
        return flags


    def __lto_flags( self ):
        """Release-only LTO flags (compile and link). Empty before GCC 8."""
        major_ver = self._reported_version['major']
        if major_ver >= 12:
            return ['-flto=auto']
        if major_ver >= 8:
            return ['-flto']
        return []


    def abi_flag( self, env ):
        if env['stdcpp']:
            return '-std={}'.format(env['stdcpp'])
        else:
            return self.__default_dialect_flags()[0]


    def stdlib_flag( self, env ):
        return None


    def supports_modules( self, env ):
        import cuppa.build_platform
        if cuppa.build_platform.name() not in ( "Linux", "Darwin" ):
            return False
        return self._reported_version['major'] >= 14


    def modules_enable_flags( self, env ):
        from cuppa.toolchains.cxx_modules_support import mapper_path, write_gcc_module_mapper
        write_gcc_module_mapper( env )
        return [ '-fmodules', '-fmodule-mapper={}'.format( mapper_path( env ) ) ]


    def profiles_supported( self, env ):
        return False


    def profiles_enable_flags( self, env ):
        return []


    def profiles_enforce_flags( self, env, names ):
        return []


    def module_bmi_path( self, env, module_name ):
        from cuppa.toolchains.cxx_modules_support import named_bmi_path
        return named_bmi_path( env, module_name, '.gcm' )


    def header_unit_bmi_path( self, env, header_path ):
        from cuppa.toolchains.cxx_modules_support import header_bmi_path
        return header_bmi_path( env, header_path, '.gcm' )


    def write_module_mapper( self, env ):
        from cuppa.toolchains.cxx_modules_support import write_gcc_module_mapper
        return write_gcc_module_mapper( env )


    def _modules_mapper_flags( self, env ):
        """Refresh the module mapper and return the flags a compile still needs.

        Both interface and consuming compiles need `-fmodules` and the mapper,
        but `modules_enable_flags` has usually already put them on the env, so
        return nothing rather than repeating them on the command line.
        """
        from cuppa.toolchains.cxx_modules_support import mapper_path, write_gcc_module_mapper
        write_gcc_module_mapper( env )
        flags = [ '-fmodules', '-fmodule-mapper={}'.format( mapper_path( env ) ) ]
        existing = list( env.get( 'CXXFLAGS', [] ) )
        if all( flag in existing for flag in flags ):
            return []
        return flags


    def interface_module_flags( self, env, module_name, bmi_path, exported=True ):
        return self._modules_mapper_flags( env )


    def consume_module_flags( self, env, scan ):
        return self._modules_mapper_flags( env )


    def build_header_unit( self, env, header, bmi_path, **kwargs ):
        from cuppa.toolchains.cxx_modules_support import mapper_path, write_gcc_module_mapper
        from cuppa.cpp.cxx_modules import register_header_unit
        declared = kwargs.pop( 'declared', None )
        system_header = kwargs.pop( 'system_header', None )
        bmi_node = env.File( bmi_path )

        if system_header:
            # Resolve absolute path so the mapper can key the compile-line spelling.
            header_abs = self._find_system_header_path( env, system_header )
            register_header_unit( env, system_header, bmi_path, bmi_node )
            register_header_unit( env, '<' + system_header + '>', bmi_path, bmi_node )
            if declared:
                register_header_unit( env, declared, bmi_path, bmi_node )
            if header_abs:
                register_header_unit( env, header_abs, bmi_path, bmi_node )
            write_gcc_module_mapper( env )
            source_arg = header_abs or system_header
            action = (
                '$CXX -o $TARGET -c -fmodule-header -fmodules '
                '-fmodule-mapper={mapper} $CXXFLAGS $_CPPINCFLAGS '
                '-x c++-header {source}'
                .format( mapper=mapper_path( env ), source=source_arg )
            )
            return env.Command( bmi_path, [], action, **kwargs )[0]

        header_path = header.get_abspath() if hasattr( header, 'get_abspath' ) else str( header )
        register_header_unit( env, header_path, bmi_path, bmi_node )
        if declared:
            register_header_unit( env, declared, bmi_path, bmi_node )
            register_header_unit(
                env,
                './' + declared.replace( '\\', '/' ).lstrip( './' ),
                bmi_path,
                bmi_node,
            )
        else:
            register_header_unit( env, str( header ), bmi_path, bmi_node )
            try:
                rel = os.path.relpath( header_path, env.get( 'sconscript_dir', os.getcwd() ) )
                build_dir = env.get( 'build_dir', '' )
                if build_dir and rel.replace( '\\', '/' ).startswith( build_dir.replace( '\\', '/' ).rstrip( '/' ) + '/' ):
                    rel = os.path.relpath( rel, build_dir )
                register_header_unit( env, rel, bmi_path, bmi_node )
                register_header_unit( env, './' + rel.replace( '\\', '/' ).lstrip( './' ), bmi_path, bmi_node )
            except ValueError:
                pass
        write_gcc_module_mapper( env )
        action = (
            '$CXX -o $TARGET -c -fmodule-header -fmodules '
            '-fmodule-mapper={mapper} $CXXFLAGS $_CPPINCFLAGS $SOURCES'
            .format( mapper=mapper_path( env ) )
        )
        return env.Command( bmi_path, header, action, **kwargs )[0]


    def _find_system_header_path( self, env, name ):
        import subprocess
        try:
            probe = '#include <{}>\n'.format( name )
            result = subprocess.run(
                [ self.binary(), '-std=c++20', '-M', '-x', 'c++', '-' ],
                input=probe,
                capture_output=True,
                text=True,
                timeout=30,
            )
            for token in result.stdout.replace( '\\', ' ' ).split():
                if token.endswith( '/' + name ) or token.endswith( os.sep + name ) or token == name:
                    if os.path.isfile( token ):
                        return os.path.abspath( token )
        except Exception:
            pass
        # Fall back to common libstdc++ include roots from -print-search-dirs / known paths
        for major in (
            str( self._reported_version.get( 'major', '' ) ),
            '',
        ):
            candidates = [
                '/usr/include/c++/{}/{}'.format( major, name ) if major else None,
            ]
            for path in candidates:
                if path and os.path.isfile( path ):
                    return path
        return None


    def supports_import_std( self, env ):
        import cuppa.build_platform
        if cuppa.build_platform.name() not in ( "Linux", "Darwin" ):
            return False
        return self._reported_version['major'] >= 15


    def std_module_sources( self, env ):
        sources = {}
        for name, relative in (
            ( 'std', 'bits/std.cc' ),
            ( 'std.compat', 'bits/std.compat.cc' ),
        ):
            path = self._find_gcc_include_file( relative )
            if path:
                sources[name] = path
        return sources


    def _find_gcc_include_file( self, relative ):
        import subprocess
        # Prefer include-tree lookup over -print-file-name (often returns relative stubs).
        try:
            result = subprocess.run(
                [ self.binary(), '-E', '-Wp,-v', '-xc++', '/dev/null' ],
                capture_output=True,
                text=True,
                timeout=30,
            )
            in_search = False
            for line in ( result.stderr or '' ).splitlines():
                text = line.strip()
                if 'search starts here' in text:
                    in_search = True
                    continue
                if text.startswith( 'End of search' ):
                    break
                if in_search and text.startswith( '/' ):
                    candidate = os.path.join( text, relative )
                    if os.path.isfile( candidate ):
                        return candidate
        except Exception:
            pass
        major = self._reported_version.get( 'major' )
        if major:
            candidate = '/usr/include/c++/{}/{}'.format( major, relative )
            if os.path.isfile( candidate ):
                return candidate
        return None


    def build_std_module( self, env, name ):
        import os
        from cuppa.toolchains.cxx_modules_support import (
            mapper_path,
            modules_build_dir,
            named_bmi_path,
            write_gcc_module_mapper,
        )
        from cuppa.cpp.cxx_modules import register_named_module, get_registry

        sources = self.std_module_sources( env )
        source = sources.get( name )
        if not source:
            return None
        if name in get_registry( env )['named']:
            return get_registry( env )['named'][name]['bmi']

        modules_build_dir( env )
        bmi_path = named_bmi_path( env, name, '.gcm' )
        bmi_node = env.File( bmi_path )
        register_named_module(
            env,
            name,
            bmi_path,
            bmi_node,
            imports=[ 'std' ] if name == 'std.compat' else [],
        )
        write_gcc_module_mapper( env )
        # Object is discarded; BMI is written via the module mapper.
        obj_path = os.path.join( modules_build_dir( env ), name.replace( '.', '--' ) + '.std.o' )
        action = (
            '$CXX -o $TARGET -c -fmodules -fsearch-include-path '
            '-fmodule-mapper={mapper} $CXXFLAGS $_CPPINCFLAGS {source}'
            .format( mapper=mapper_path( env ), source=source )
        )
        sources_nodes = []
        if name == 'std.compat' and 'std' in get_registry( env )['named']:
            sources_nodes = [ get_registry( env )['named']['std']['bmi'] ]
        env.Command( obj_path, sources_nodes, action )
        env.SideEffect( bmi_path, obj_path )
        env.Depends( bmi_node, obj_path )
        return bmi_node


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
