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
import re
import six
from collections import namedtuple

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


# SCons MSVC ids look like "14.5", "14.3", "14.2Exp" — the Visual Studio
# *platform toolset* major.minor (v145 / v143 / v142), NOT the compiler update
# string people sometimes write as "14.29" / "19.29".
MsvcToolsetVersion = namedtuple(
    'MsvcToolsetVersion',
    ( 'scons', 'major', 'minor', 'experimental', 'alias' ),
)

# C++20 named modules: VS 2019 toolset family onward (SCons "14.2"+).
MODULES_MIN_MSVC_TOOLSET = ( 14, 2 )


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
    def parse_toolset_version( cls, long_version ):
        """
        Parse a SCons MSVC version id into structured toolset fields.

        Examples::

            "14.5"    → alias vc145,  key (14, 5)
            "14.3"    → alias vc143,  key (14, 3)
            "14.2Exp" → alias vc142e, key (14, 2)
            "14.51"   → alias vc1451, key (14, 51)   # if SCons ever reports it

        Cuppa CLI names drop the dot so they stay short and match the VS
        platform toolset label (`v145` ↔ `--toolchains=vc145`), same digit
        style as `gcc15` / `clang21`.
        """
        text = str( long_version ).strip()
        match = re.match(
            r'^(?P<major>\d+)\.(?P<minor>\d+)(?P<exp>Exp)?$',
            text,
            flags=re.IGNORECASE,
        )
        if not match:
            # Fallback: preserve legacy strip-dots behaviour for odd ids.
            compact = text.replace( '.', '' ).replace( 'Exp', 'e' ).replace( 'exp', 'e' )
            digits = re.match( r'^(?P<body>\d+)(?P<e>e?)$', compact )
            if not digits:
                raise ValueError( "Unrecognised MSVC toolset version {!r}".format( long_version ) )
            body = digits.group( 'body' )
            # Best-effort: treat first two digits as major when length >= 3 (e.g. 145 → 14,5).
            if len( body ) >= 3:
                major = int( body[:2] )
                minor = int( body[2:] )
            else:
                major = int( body )
                minor = 0
            experimental = bool( digits.group( 'e' ) )
            alias = 'vc' + body + ( 'e' if experimental else '' )
            return MsvcToolsetVersion( text, major, minor, experimental, alias )

        major = int( match.group( 'major' ) )
        minor = int( match.group( 'minor' ) )
        experimental = bool( match.group( 'exp' ) )
        alias = 'vc{}{}{}'.format( major, minor, 'e' if experimental else '' )
        return MsvcToolsetVersion( text, major, minor, experimental, alias )


    @classmethod
    def vc_version( cls, long_version ):
        """Cuppa toolchain alias for a SCons MSVC version (e.g. ``14.5`` → ``vc145``)."""
        return cls.parse_toolset_version( long_version ).alias


    @classmethod
    def toolset_key( cls, long_version ):
        """Comparable ``(major, minor)`` tuple for a SCons MSVC version id."""
        parsed = cls.parse_toolset_version( long_version )
        return ( parsed.major, parsed.minor )


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
                parsed = cls.parse_toolset_version( default )
                cls._available_versions['vc'] = {
                        'vc_version': parsed.alias,
                        'version': parsed.scons,
                        'toolset': parsed,
                }

            for version in installed_versions:
                parsed = cls.parse_toolset_version( version )
                cls._available_versions[parsed.alias] = {
                        'vc_version': parsed.alias,
                        'version': parsed.scons,
                        'toolset': parsed,
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
            toolset = vc.get( 'toolset' ) or cls.parse_toolset_version( vc['version'] )
            logger.debug(
                "Adding toolchain [{}] reported as [{}] (MSVC toolset {}, alias {})"
                .format(
                    as_info( name ),
                    as_info( vc['vc_version'] ),
                    as_notice( toolset.scons ),
                    as_info( toolset.alias ),
                )
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

        self._toolset = self.parse_toolset_version( version )
        # Prefer the structured alias so name()/package ids stay consistent even
        # if a caller passes a slightly different vc_version string.
        self._name    = self._toolset.alias
        self._version = self._toolset.alias
        self._long_version = self._toolset.scons
        self._short_version = "{}{}".format(
            self._toolset.major,
            self._toolset.minor,
        ) + ( "e" if self._toolset.experimental else "" )
        # Keep the registration key (e.g. "vc") when it differs from the alias.
        self._requested_name = name

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


    def toolset_version( self ):
        """SCons MSVC toolset id (e.g. ``14.5``)."""
        return self._long_version


    def toolset( self ):
        """Structured MSVC toolset fields (``MsvcToolsetVersion``)."""
        return self._toolset


    def supports_modules( self, env ):
        import cuppa.build_platform
        if cuppa.build_platform.name() != "Windows":
            return False
        # Compare SCons toolset major.minor (14.2, 14.3, 14.5, …) — not compiler
        # update numbers such as 14.29 / 19.29.
        return self.toolset_key( self._long_version ) >= MODULES_MIN_MSVC_TOOLSET


    def supports_import_std( self, env ):
        # STL named modules require a recent MSVC + std.ixx install; opt-in later.
        return False


    def modules_enable_flags( self, env ):
        return []


    def module_bmi_path( self, env, module_name ):
        from cuppa.toolchains.cxx_modules_support import named_bmi_path
        return named_bmi_path( env, module_name, '.ifc' )


    def header_unit_bmi_path( self, env, header_path ):
        from cuppa.toolchains.cxx_modules_support import header_bmi_path
        return header_bmi_path( env, header_path, '.ifc' )


    def interface_module_flags( self, env, module_name, bmi_path ):
        # Hyphen forms avoid SCons treating /flags as paths on Windows.
        # Use space-separated -ifcOutput PATH: the colon form (-ifcOutput:PATH)
        # breaks on absolute Windows paths because MSVC treats the drive letter
        # colon as part of the filename (error C3474 on ':C:\...').
        return [
            '-interface',
            '-TP',
            '-ifcOutput',
            bmi_path,
        ]


    def consume_module_flags( self, env, scan ):
        from cuppa.cpp.cxx_modules import get_registry, lookup_header_entry
        from cuppa.cpp.module_scanner import owning_module_name, qualify_relative_import
        flags = []
        registry = get_registry( env )
        if not scan:
            return flags

        def append_reference( payload ):
            # Space-separated -reference avoids drive-letter colon issues on Windows.
            for i in range( 0, len( flags ) - 1 ):
                if flags[i] == '-reference' and flags[i + 1] == payload:
                    return
            flags.extend( [ '-reference', payload ] )

        def add_named( name, seen ):
            if not name or name in seen:
                return
            entry = registry['named'].get( name )
            if not entry:
                return
            seen.add( name )
            append_reference( '{}={}'.format( name, entry['path'] ) )
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
                    append_reference( entry['path'] )
        if scan.module_declaration:
            decl = scan.module_declaration
            primary = decl.split( ':', 1 )[0]
            for candidate in ( decl, primary ):
                if candidate in registry['named']:
                    add_named( candidate, seen )
                    break
        return flags


    def build_header_unit( self, env, header, bmi_path, **kwargs ):
        raise NotImplementedError(
            "MSVC header units are not supported in this cuppa release "
            "(named modules via --modules are supported)"
        )


    def build_std_module( self, env, name ):
        raise NotImplementedError(
            "import std is not supported for MSVC in this cuppa release"
        )


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
