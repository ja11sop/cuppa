#          Copyright Jamie Allsop 2014-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   CL Toolchain
#-------------------------------------------------------------------------------

import os
import collections
import platform
import six

import SCons.Script
from SCons.Tool.MSCommon.vc import _VCVER, get_default_version

try:
    from SCons.Tool.MSCommon.vc import cached_get_installed_vcs as get_installed_vcs
except (ImportError, AttributeError):  # scons version >= 4.1
    from SCons.Tool.MSCommon.vc import get_installed_vcs as get_installed_vcs

from cuppa.cpp.create_version_file_cpp import CreateVersionHeaderCpp, CreateVersionFileCpp
from cuppa.cpp.run_boost_test import RunBoostTestEmitter, RunBoostTest
from cuppa.cpp.run_patched_boost_test import RunPatchedBoostTestEmitter, RunPatchedBoostTest
from cuppa.cpp.run_process_test import RunProcessTestEmitter, RunProcessTest
from cuppa.colourise import as_info, as_notice, as_warning
from cuppa.log import logger


class Cl(object):

    _default_dialect_flag = '-std:c++20'

    # Map cuppa --stdcpp / StdCpp names onto MSVC -std: flags.
    # Use '-' not '/' so SCons/Windows do not treat the flag as a filesystem path
    # (e.g. "/std:c++14" → "C:\\std:c++14").
    # Pre-C++14 aliases have no MSVC -std: equivalent; map to -std:c++14 with a warning.
    _stdcpp_flag_map = {
        'c++98': '-std:c++14',
        'c++03': '-std:c++14',
        'c++0x': '-std:c++14',
        'c++11': '-std:c++14',
        'c++1y': '-std:c++14',
        'c++14': '-std:c++14',
        'c++1z': '-std:c++17',
        'c++17': '-std:c++17',
        'c++2a': '-std:c++20',
        'c++20': '-std:c++20',
        'c++2b': '-std:c++23',
        'c++23': '-std:c++23',
        'c++2c': '-std:c++latest',
        'c++26': '-std:c++latest',
        'c++latest': '-std:c++latest',
    }

    _pre_cxx14_standards = frozenset( [ 'c++98', 'c++03', 'c++0x', 'c++11' ] )

    _supported_architectures = {
        "amd64"     : "amd64",
        "emt64"     : "amd64",
        "i386"      : "x86",
        "i486"      : "x86",
        "i586"      : "x86",
        "i686"      : "x86",
        "ia64"      : "ia64",
        "itanium"   : "ia64",
        "x86"       : "x86",
        "x86_64"    : "amd64",
        "x86_amd64" : "x86_amd64",
        "arm"       : "arm",
        "arm64"     : "arm64",
        "aarch64"   : "arm64",
    }

    _target_architectures = {
        ("x86", "x86")         : "x86",
        ("x86", "amd64")       : "x86_amd64",
        ("x86", "x86_amd64")   : "x86_amd64",
        ("amd64", "x86_amd64") : "x86_amd64",
        ("amd64", "amd64")     : "amd64",
        ("amd64", "x86")       : "x86",
        ("x86", "ia64")        : "x86_ia64",
        ("x86", "arm")         : "x86_arm",
        ("amd64", "arm")       : "amd64_arm",
        ("arm", "arm")         : "arm",
        ("amd64", "arm64")     : "amd64_arm64",
        ("arm64", "arm64")     : "arm64",
        ("arm64", "x86")       : "arm64_x86",
        ("arm64", "amd64")     : "arm64_amd64",
        ("x86", "arm64")       : "x86_arm64",
    }

    @classmethod
    def default_version( cls, env ):
        if not hasattr( cls, '_default_version' ):
            cls._default_version = get_default_version( env )
        return cls._default_version


    @classmethod
    def vc_version( cls, long_version ):
        version = long_version.replace( ".", "" )
        version = version.replace( "Exp", "e" )
        return 'vc' + version


    @classmethod
    def supported_versions( cls ):
        supported = [ "vc" ]
        for version in reversed(_VCVER):
            supported.append( cls.vc_version( version ) )
        return supported


    @classmethod
    def available_versions( cls, env ):
        if not hasattr( cls, '_available_versions' ):
            cls._available_versions = collections.OrderedDict()
            installed_versions = get_installed_vcs()
            if installed_versions:
                default = cls.default_version( env )
                cls._available_versions['vc'] = {
                        'vc_version': cls.vc_version( default ),
                        'version': default,
                }

            for version in installed_versions:
                vc_version = cls.vc_version( version )
                cls._available_versions[vc_version] = {
                        'vc_version': vc_version,
                        'version': version,
                }

        return cls._available_versions


    @classmethod
    def add_options( cls, add_option ):
        pass


    @classmethod
    def add_to_env( cls, env, add_toolchain, add_to_supported ):
        for version in cls.supported_versions():
            add_to_supported( version )

        for name, vc in six.iteritems( cls.available_versions( env ) ):
            logger.debug(
                "Adding toolchain [{}] reported as [{}] (MSVC {})"
                .format( as_info( name ), as_info( vc['vc_version'] ), as_notice( vc['version'] ) )
            )
            add_toolchain( name, cls( name, vc['vc_version'], vc['version'] ) )


    @classmethod
    def default_variants( cls ):
        return [ 'dbg', 'rel' ]


    @classmethod
    def host_architecture( cls, env ):
        arch = env.get('HOST_ARCH')
        if not arch:
            arch = platform.machine()
            if not arch:
                arch = os.environ.get( 'PROCESSOR_ARCHITECTURE', '' )
        try:
            arch = cls._supported_architectures[ arch.lower() ]
        except KeyError:
            pass
        return arch



    def __init__( self, name, vc_version, version ):

        self.values = {}
        env = SCons.Script.DefaultEnvironment()
        SCons.Script.Tool( 'msvc' )( env )

        self._host_arch = self.host_architecture( env )

        self._name    = vc_version
        self._version = vc_version
        self._long_version = version
        self._short_version = vc_version[2:].replace( "e", "" )

        self._target_store = "desktop"

        self.values['sys_inc_prefix'] = env['INCPREFIX']
        self.values['sys_inc_suffix'] = env['INCSUFFIX']

        SYSINCPATHS = '${_concat(\"' + self.values['sys_inc_prefix'] + '\", SYSINCPATH, \"'+ self.values['sys_inc_suffix'] + '\", __env__, RDirs, TARGET, SOURCE)}'

        self.values['_CPPINCFLAGS'] = '$( ' + SYSINCPATHS + ' ${_concat(INCPREFIX, INCPATH, INCSUFFIX, __env__, RDirs, TARGET, SOURCE)} $)'

        self._initialise_toolchain()


    def __getitem__( self, key ):
        return self.values.get( key )


    def name( self ):
        return self._name


    def package_name( self ):
        return self.name()


    def family( self ):
        return "cl"


    def toolset_name( self ):
        return "msvc"


    def toolset_tag( self ):
        return "vc"


    def version( self ):
        return self._version


    def short_version( self ):
        return self._short_version


    def cxx_version( self ):
        return self._version


    def binary( self ):
        return self.values['CXX']


    def target_store( self ):
        return self._target_store


    def make_env( self, cuppa_env, variant, target_arch ):

        if not target_arch:
            target_arch = self._host_arch
        else:
            target_arch = target_arch.lower()
            if target_arch not in self._supported_architectures:
                return None, target_arch
            else:
                target_arch = self._supported_architectures[ target_arch ]

        target_arch = self._target_architectures[ ( self._host_arch, target_arch ) ]

        env = cuppa_env.create_env(
                tools = ['msvc'],
                MSVC_VERSION = self._long_version,
                TARGET_ARCH = target_arch,
        )

        env['_CPPINCFLAGS'] = self.values['_CPPINCFLAGS']
        env['SYSINCPATH']   = []
        env['INCPATH']      = [ '#.', '.' ]
        env['CPPDEFINES']   = []
        env['LIBS']         = []
        env['STATICLIBS']   = []

        self.update_variant( env, variant.name() )

        return env, target_arch


    def variants( self ):
        pass


    def supports_coverage( self ):
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
        if not benchmarker or benchmarker =='process':
            return RunProcessTest( expected, final_dir, **kwargs ), RunProcessTestEmitter( final_dir, **kwargs )
        elif benchmarker == 'boost':
            return RunBoostTest( expected, final_dir, **kwargs ), RunBoostTestEmitter( final_dir, **kwargs )
        elif benchmarker == 'patched_boost':
            return RunPatchedBoostTest( expected, final_dir, **kwargs ), RunPatchedBoostTestEmitter( final_dir, **kwargs )


    def benchmark_runners( self ):
        return [ 'process', 'boost', 'patched_boost' ]


    def coverage_runner( self, program, final_dir, include_patterns=[], exclude_patterns=[] ):
        return None, None


    def coverage_collate_files( self, destination=None ):
        return None, None


    def coverage_collate_index( self, destination=None ):
        return None, None


    def update_variant( self, env, variant ):
        if variant == 'dbg':
            env.AppendUnique( CXXFLAGS = self.values['dbg_cxx_flags'] )
            env.AppendUnique( LINKFLAGS = self.values['dbg_link_flags'] )
        elif variant == 'rel':
            env.AppendUnique( CXXFLAGS = self.values['rel_cxx_flags'] )
            env.AppendUnique( LINKFLAGS = self.values['rel_link_flags'] )
        elif variant == 'cov':
            # MSVC coverage instrumentation is not supported.
            pass
        env.AppendUnique( CXXFLAGS = [ self.abi_flag( env ) ] )


    def _initialise_toolchain( self ):

        CommonCxxFlags = [
            '-W4',
            '-EHsc',
            '-nologo',
            '-GR',
            '-permissive-',
            '-Zc:__cplusplus',
            '-utf-8',
        ]

        self.values['dbg_cxx_flags'] = CommonCxxFlags + [ '-Zi', '-MDd' ]
        self.values['rel_cxx_flags'] = CommonCxxFlags + [ '-Ox', '-MD' ]

        CommonLinkFlags = [ '-OPT:REF']

        self.values['dbg_link_flags'] = CommonLinkFlags + []
        self.values['rel_link_flags'] = CommonLinkFlags + []


    def abi_flag( self, env ):
        if env.get( 'stdcpp' ):
            return self.stdcpp_flag_for( env['stdcpp'] )
        return self._default_dialect_flag


    def stdlib_flag( self, env ):
        return None


    def supports_modules( self, env ):
        return False


    def supports_import_std( self, env ):
        return False


    def modules_enable_flags( self, env ):
        return []


    def module_bmi_path( self, env, module_name ):
        raise NotImplementedError( "C++ modules are not supported for MSVC in this cuppa release" )


    def header_unit_bmi_path( self, env, header_path ):
        raise NotImplementedError( "C++ modules are not supported for MSVC in this cuppa release" )


    def interface_module_flags( self, env, module_name, bmi_path ):
        raise NotImplementedError( "C++ modules are not supported for MSVC in this cuppa release" )


    def consume_module_flags( self, env, scan ):
        raise NotImplementedError( "C++ modules are not supported for MSVC in this cuppa release" )


    def build_header_unit( self, env, header, bmi_path, **kwargs ):
        raise NotImplementedError( "C++ modules are not supported for MSVC in this cuppa release" )


    def build_std_module( self, env, name ):
        raise NotImplementedError( "C++ modules are not supported for MSVC in this cuppa release" )


    def abi( self, env ):
        flag = self.abi_flag( env )
        if ':' in flag:
            return flag.split( ':', 1 )[1]
        if env.get( 'stdcpp' ):
            return env['stdcpp']
        return 'c++20'


    def stdcpp_flag_for( self, standard ):
        flag = self._stdcpp_flag_map.get( standard )
        if flag is None:
            logger.warn(
                "Unknown C++ standard [{}] for MSVC; using {}"
                .format( as_warning( standard ), as_info( self._default_dialect_flag ) )
            )
            return self._default_dialect_flag
        if standard in self._pre_cxx14_standards:
            logger.warn(
                "MSVC has no -std: for [{}]; using {}"
                .format( as_warning( standard ), as_info( flag ) )
            )
        return flag


    def error_format( self ):
        return "{}({}): error: {}"


    @classmethod
    def output_interpretors( cls ):
        return [
        {
            'title'     : "Compiler Error",
            'regex'     : r"([][{}() \t#%@$~\w&_:+\\/\.-]+)([(]([0-9]+)[)])([ ]?:[ ]error [A-Z0-9]+:.*)",
            'meaning'   : 'error',
            'highlight' : set( [ 1, 2 ] ),
            'display'   : [ 1, 2, 4 ],
            'file'      : 1,
            'line'      : None,
            'column'    : None,
        },
        {
            'title'     : "Compiler Warning",
            'regex'     : r"([][{}() \t#%@$~\w&_:+\\/\.-]+)([(]([0-9]+)[)])([ ]?:[ ]warning [A-Z0-9]+:.*)",
            'meaning'   : 'warning',
            'highlight' : set( [ 1, 2 ] ),
            'display'   : [ 1, 2, 4 ],
            'file'      : 1,
            'line'      : None,
            'column'    : None,
        },
        {
            'title'     : "Compiler Note",
            'regex'     : r"([][{}() \t#%@$~\w&_:+\\/\.-]+)([(]([0-9]+)[)])([ ]?:[ ]note:.*)",
            'meaning'   : 'message',
            'highlight' : set( [ 1, 2 ] ),
            'display'   : [ 1, 2, 4 ],
            'file'      : 1,
            'line'      : None,
            'column'    : None,
        },
        {
            'title'     : "Linker Fatal Error",
            'regex'     : r"([][{}() \t#%@$~\w&_:+\\/\.-]+)([ ]?:[ ]fatal error LNK[0-9]+:)(.*)",
            'meaning'   : 'error',
            'highlight' : set( [ 1, 2 ] ),
            'display'   : [ 1, 2, 3 ],
            'file'      : 1,
            'line'      : None,
            'column'    : None,
        },
        {
            'title'     : "Linker Error",
            'regex'     : r"([][{}() \t#%@$~\w&_:+\\/\.-]+)([ ]?:[ ]error LNK[0-9]+:)(.*)",
            'meaning'   : 'error',
            'highlight' : set( [ 1, 2 ] ),
            'display'   : [ 1, 2, 3 ],
            'file'      : 1,
            'line'      : None,
            'column'    : None,
        },
        {
            'title'     : "Linker Warning",
            'regex'     : r"([][{}() \t#%@$~\w&_:+\\/\.-]+)([ ]?:[ ]warning LNK[0-9]+:)(.*)",
            'meaning'   : 'warning',
            'highlight' : set( [ 1, 2 ] ),
            'display'   : [ 1, 2, 3 ],
            'file'      : 1,
            'line'      : None,
            'column'    : None,
        },
    ]
