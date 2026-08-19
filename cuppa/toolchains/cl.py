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

# import std ships with VS 2022 17.5+ STL (toolset 14.3 family); still gate on std.ixx.
IMPORT_STD_MIN_MSVC_TOOLSET = ( 14, 3 )


def find_msvc_modules_dir( env=None ):
    """
    Locate the MSVC STL ``modules`` directory that holds ``std.ixx``.

    Search order: ``VCToolsInstallDir`` (env / process), walk up from ``cl.exe``,
    then common Visual Studio install layouts.
    """
    candidates = []

    def _add( path ):
        if path and path not in candidates:
            candidates.append( path )

    def _from_vctools( root ):
        if not root:
            return
        root = os.path.expandvars( str( root ) ).strip( '"%' )
        _add( os.path.join( root, 'modules' ) )

    if env is not None:
        _from_vctools( env.get( 'VCToolsInstallDir' ) )
        nested = env.get( 'ENV' ) or {}
        if isinstance( nested, dict ):
            _from_vctools( nested.get( 'VCToolsInstallDir' ) )
        cxx = env.get( 'CXX' )
        if cxx:
            _add( _modules_dir_from_cl_path( str( cxx ) ) )

    _from_vctools( os.environ.get( 'VCToolsInstallDir' ) )

    try:
        import shutil
        cl_path = shutil.which( 'cl' ) or shutil.which( 'cl.exe' )
        if cl_path:
            _add( _modules_dir_from_cl_path( cl_path ) )
    except Exception:
        pass

    for base in (
        r'C:\Program Files\Microsoft Visual Studio',
        r'C:\Program Files (x86)\Microsoft Visual Studio',
    ):
        if not os.path.isdir( base ):
            continue
        for year in ( '18', '2025', '2022', '2019' ):
            year_root = os.path.join( base, year )
            if not os.path.isdir( year_root ):
                continue
            for edition in ( 'Enterprise', 'Professional', 'Community', 'BuildTools' ):
                msvc_root = os.path.join(
                    year_root, edition, 'VC', 'Tools', 'MSVC'
                )
                if not os.path.isdir( msvc_root ):
                    continue
                try:
                    versions = sorted( os.listdir( msvc_root ), reverse=True )
                except OSError:
                    continue
                for ver in versions:
                    _add( os.path.join( msvc_root, ver, 'modules' ) )

    for path in candidates:
        if path and os.path.isfile( os.path.join( path, 'std.ixx' ) ):
            return path
    return None


def _modules_dir_from_cl_path( cl_path ):
    """
    ``.../MSVC/<ver>/bin/Hostx64/x64/cl.exe`` → ``.../MSVC/<ver>/modules``.
    """
    path = os.path.abspath( os.path.normpath( cl_path ) )
    # bin/Host*/arch/cl.exe → four parents up to MSVC/<ver>
    ver_root = path
    for _ in range( 4 ):
        ver_root = os.path.dirname( ver_root )
    modules = os.path.join( ver_root, 'modules' )
    if os.path.isdir( modules ):
        return modules
    # Fallback: walk parents looking for modules/std.ixx
    cur = os.path.dirname( path )
    for _ in range( 8 ):
        candidate = os.path.join( cur, 'modules' )
        if os.path.isfile( os.path.join( candidate, 'std.ixx' ) ):
            return candidate
        parent = os.path.dirname( cur )
        if parent == cur:
            break
        cur = parent
    return None


class Cl(object):

    # Cuppa default dialect token; flag is derived so the two cannot drift.
    _default_dialect = 'c++20'
    _default_dialect_flag = '-std:{}'.format( _default_dialect )

    # Real MSVC ``-std:`` dialects Cuppa lists (newest first). Distinct from the
    # ``--stdcpp`` alias map below, which may collapse several names onto one flag.
    _available_dialects = (
        'c++latest',
        'c++20',
        'c++17',
        'c++14',
    )

    # Map cuppa --stdcpp / StdCpp names onto MSVC -std: flags.
    # Use '-' not '/' so SCons/Windows do not treat the flag as a filesystem path
    # (e.g. "/std:c++14" → "C:\\std:c++14").
    # Pre-C++14 aliases have no MSVC -std: equivalent; map to -std:c++14 with a warning.
    # c++23 / c++2b → -std:c++latest: many MSVC toolsets (including 19.51 / VS 18)
    # ignore unknown `-std:c++23` (D9002), which then breaks `import std` / std.ixx
    # ("Standard Library Modules are available only with C++20 or later").
    # Microsoft’s own import-std tutorial uses /std:c++latest.
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
        'c++2b': '-std:c++latest',
        'c++23': '-std:c++latest',
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


    def describe( self ):
        from cuppa.toolchains.describe import describe_toolchain
        return describe_toolchain( self )


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


    def default_dialect( self ):
        """Cuppa default MSVC dialect token (without the ``-std:`` prefix)."""
        return self._default_dialect


    @classmethod
    def available_dialects( cls ):
        """MSVC ``-std:`` dialects Cuppa lists for verbose describe (newest first)."""
        return cls._available_dialects


    def usable_features( self ):
        """Display items for verbose ``usable features:`` (see ``describe``)."""
        from cuppa.toolchains.describe import format_usable_feature_items

        experimental = []
        try:
            if self.supports_modules( None ):
                experimental.append( 'modules (experimental)' )
        except Exception:
            pass
        return format_usable_feature_items(
                self.default_dialect(), experimental=experimental,
        )


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
        if not self.supports_modules( env ):
            return False
        if self.toolset_key( self._long_version ) < IMPORT_STD_MIN_MSVC_TOOLSET:
            return False
        return 'std' in self.std_module_sources( env )


    def modules_enable_flags( self, env ):
        return []


    def profiles_supported( self, env ):
        return False


    def profiles_enable_flags( self, env ):
        return []


    def profiles_enforce_flags( self, env, names ):
        return []


    def error_limit_flags( self, env, limit ):
        # MSVC cl.exe stops with fatal C1003 after an internal cap (~100 errors).
        # There is no documented /errorlimit switch on cl (that spelling is lld-link).
        return []


    def disable_error_limit_flags( self, env ):
        return self.error_limit_flags( env, 0 )


    def module_bmi_path( self, env, module_name ):
        from cuppa.toolchains.cxx_modules_support import named_bmi_path
        return named_bmi_path( env, module_name, '.ifc' )


    def header_unit_bmi_path( self, env, header_path ):
        from cuppa.toolchains.cxx_modules_support import header_bmi_path
        return header_bmi_path( env, header_path, '.ifc' )


    def interface_module_flags( self, env, module_name, bmi_path, exported=True ):
        # Hyphen forms avoid SCons treating /flags as paths on Windows.
        # Use space-separated -ifcOutput PATH: the colon form (-ifcOutput:PATH)
        # breaks on absolute Windows paths because MSVC treats the drive letter
        # colon as part of the filename (error C3474 on ':C:\...').
        # Non-exported partitions (module M:part;) need -internalPartition, not
        # -interface (otherwise MSVC C7621).
        kind = '-interface' if exported else '-internalPartition'
        return [
            kind,
            '-TP',
            '-ifcOutput',
            bmi_path,
        ]


    @staticmethod
    def _append_flag_pair( flags, flag, payload ):
        for i in range( 0, len( flags ) - 1 ):
            if flags[i] == flag and flags[i + 1] == payload:
                return
        flags.extend( [ flag, payload ] )


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
            # Space-separated -reference avoids drive-letter colon issues on Windows.
            self._append_flag_pair(
                flags, '-reference', '{}={}'.format( name, entry['path'] )
            )
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
                if not entry:
                    continue
                # Header units need -headerUnit, not -reference (MSVC).
                # Keep header=ifc as one argv payload so C:\ paths stay intact.
                payload = '{}={}'.format( item.name, entry['path'] )
                if item.kind == 'header_angle':
                    self._append_flag_pair( flags, '-headerUnit:angle', payload )
                else:
                    self._append_flag_pair( flags, '-headerUnit', payload )
        if scan.module_declaration:
            decl = scan.module_declaration
            if ':' in decl:
                # Internal / interface partition unit: never self-reference the
                # partition BMI being produced; pull in the primary module IFC.
                primary = decl.split( ':', 1 )[0]
                add_named( primary, seen )
            else:
                # Implementation unit `module M;`: reference primary BMI.
                add_named( decl, seen )
        return flags


    def build_header_unit( self, env, header, bmi_path, **kwargs ):
        kwargs.pop( 'declared', None )
        system_header = kwargs.pop( 'system_header', None )
        # -exportHeader creates the IFC; -ifcOutput PATH places it (space form).
        if system_header:
            action = (
                '$CXX $CXXFLAGS $_CPPINCFLAGS -exportHeader -headerName:angle '
                '{name} -ifcOutput $TARGET'
                .format( name=system_header )
            )
            return env.Command( bmi_path, [], action, **kwargs )[0]
        action = (
            '$CXX $CXXFLAGS $_CPPINCFLAGS -exportHeader -ifcOutput $TARGET $SOURCES'
        )
        return env.Command( bmi_path, header, action, **kwargs )[0]


    def _msvc_modules_dir( self, env=None ):
        """Directory containing STL ``std.ixx`` / ``std.compat.ixx``, if present."""
        return find_msvc_modules_dir( env )


    def std_module_sources( self, env ):
        sources = {}
        modules_dir = self._msvc_modules_dir( env )
        if not modules_dir:
            return sources
        for name, filename in (
            ( 'std', 'std.ixx' ),
            ( 'std.compat', 'std.compat.ixx' ),
        ):
            path = os.path.join( modules_dir, filename )
            if os.path.isfile( path ):
                sources[name] = path
        return sources


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
        bmi_path = named_bmi_path( env, name, '.ifc' )
        obj_path = os.path.splitext( bmi_path )[0] + '.obj'
        bmi_node = env.File( bmi_path )
        register_named_module(
            env,
            name,
            bmi_path,
            bmi_node,
            imports=[ 'std' ] if name == 'std.compat' else [],
        )

        # Compile STL .ixx to IFC (+ obj).
        # -ifcOutput PATH: space-separated (colon form breaks on C:\ drive letters).
        # -FoPATH: must be glued — "-Fo PATH" makes MSVC treat PATH as a source file.
        extra = ''
        sources_nodes = []
        if name == 'std.compat' and 'std' in get_registry( env )['named']:
            std_bmi = get_registry( env )['named']['std']['path']
            extra = '-reference std={} '.format( std_bmi )
            sources_nodes = [ get_registry( env )['named']['std']['bmi'] ]

        # Prefer c++latest for STL modules: matches Microsoft’s tutorial and
        # avoids toolchains that ignore -std:c++23 (D9002).
        dialect = self.stdcpp_flag_for( 'c++latest' )
        action = (
            '$CXX $CXXFLAGS {dialect} -c -TP -interface '
            '-ifcOutput {bmi} -Fo"{obj}" '
            '{extra}"{source}"'
            .format(
                dialect=dialect,
                bmi=bmi_path,
                obj=obj_path,
                extra=extra,
                source=source,
            )
        )
        return env.Command( bmi_path, sources_nodes, action )[0]


    def abi( self, env ):
        # Prefer the cuppa dialect name so --stdcpp=c++23 stays "c++23" in paths
        # even when the MSVC flag is -std:c++latest.
        if env.get( 'stdcpp' ):
            return env['stdcpp']
        flag = self.abi_flag( env )
        if ':' in flag:
            return flag.split( ':', 1 )[1]
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
