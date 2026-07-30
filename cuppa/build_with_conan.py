#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   build_with_conan — Conan 2 consumer via SConsDeps
#-------------------------------------------------------------------------------

"""Optional Conan 2 consumer support for Cuppa.

Primary generator is Conan 2 ``SConsDeps`` (``SConscript_conandeps`` +
``env.MergeFlags``). See ``CONAN_CONSUMER_PLAN.md``.
"""

from __future__ import annotations

import hashlib
import os
import re
import shutil
import subprocess
import sys
from contextlib import contextmanager

from cuppa.colourise import as_error, as_notice
from cuppa.log import logger


_MERGE_SKIP_KEYS = frozenset( {'BINPATH'} )
_DONE_MARKER = '.cuppa_conan_ok'
_LOCK_NAME = '.cuppa_conan.lock'


class ConanDependencyException( Exception ):
    def __init__( self, value ):
        self.parameter = value

    def __str__( self ):
        return repr( self.parameter )


def _sha256_file( path ):
    digest = hashlib.sha256()
    with open( path, 'rb' ) as handle:
        for chunk in iter( lambda: handle.read( 65536 ), b'' ):
            digest.update( chunk )
    return digest.hexdigest()


def _sha256_text( text ):
    return hashlib.sha256( text.encode( 'utf-8' ) ).hexdigest()


@contextmanager
def _exclusive_file_lock( lock_path ):
    """Process-safe lock so parallel SCons workers do not race ``conan install``."""
    parent = os.path.dirname( lock_path )
    if parent:
        os.makedirs( parent, exist_ok=True )
    # Binary mode keeps Windows happier; flock is POSIX-only.
    handle = open( lock_path, 'a+b' )
    try:
        if os.name == 'nt':
            import msvcrt
            handle.seek( 0 )
            if handle.read( 1 ) == b'':
                handle.write( b'0' )
                handle.flush()
            handle.seek( 0 )
            msvcrt.locking( handle.fileno(), msvcrt.LK_LOCK, 1 )
        else:
            import fcntl
            fcntl.flock( handle.fileno(), fcntl.LOCK_EX )
        yield
    finally:
        try:
            if os.name == 'nt':
                import msvcrt
                handle.seek( 0 )
                msvcrt.locking( handle.fileno(), msvcrt.LK_UNLCK, 1 )
            else:
                import fcntl
                fcntl.flock( handle.fileno(), fcntl.LOCK_UN )
        finally:
            handle.close()


def _find_conan_executable():
    return shutil.which( 'conan' )


def _platform_os_name():
    import cuppa.build_platform
    name = cuppa.build_platform.name()
    if name == 'Windows':
        return 'Windows'
    if name == 'Darwin':
        return 'Macos'
    return 'Linux'


def _map_cppstd( std_flag_or_abi ):
    """Map Cuppa ``-std=…`` / abi / ``stdcpp`` values to Conan ``compiler.cppstd``."""
    if not std_flag_or_abi:
        return None
    value = str( std_flag_or_abi ).strip()
    value = value.replace( '-std=', '' )
    # Cuppa abi folder uses cxx2c etc.
    if value.startswith( 'cxx' ):
        value = 'c++' + value[3:]
    mapping = {
        'c++98': '98', 'c++03': '03',
        'c++0x': '11', 'c++11': '11',
        'c++1y': '14', 'c++14': '14',
        'c++1z': '17', 'c++17': '17',
        'c++2a': '20', 'c++20': '20',
        'c++2b': '23', 'c++23': '23',
        'c++2c': '26', 'c++26': '26',
        'c++latest': '26',
        'gnu++98': 'gnu98', 'gnu++03': 'gnu03',
        'gnu++11': 'gnu11', 'gnu++14': 'gnu14',
        'gnu++17': 'gnu17', 'gnu++20': 'gnu20',
        'gnu++23': 'gnu23', 'gnu++26': 'gnu26',
    }
    if value in mapping:
        return mapping[value]
    if re.fullmatch( r'(gnu)?\d+', value ):
        return value
    return value.replace( 'c++', '' ).replace( 'gnu++', 'gnu' )


def _compiler_family( toolchain ):
    family = toolchain.family() if hasattr( toolchain, 'family' ) else 'gcc'
    if family in ( 'cl', 'vc', 'msvc' ):
        return 'msvc'
    if family == 'clang':
        # Apple Clang is a distinct Conan compiler; detect when possible.
        binary = toolchain.binary() if hasattr( toolchain, 'binary' ) else ''
        if sys.platform == 'darwin' and binary and 'Xcode' in str( binary ):
            return 'apple-clang'
        return 'clang'
    return family


def _compiler_version( toolchain ):
    family = _compiler_family( toolchain )
    if family == 'msvc':
        return _msvc_conan_version( toolchain )

    reported = getattr( toolchain, '_reported_version', None )
    if isinstance( reported, dict ) and reported.get( 'major' ) is not None:
        return str( reported['major'] )
    if hasattr( toolchain, 'short_version' ):
        short = str( toolchain.short_version() )
        match = re.match( r'(\d+)', short )
        if match:
            # gcc153 -> 15 for Conan major; if short is already "15", keep it.
            digits = match.group( 1 )
            if len( digits ) >= 3 and family == 'gcc':
                return digits[:2] if int( digits[:2] ) >= 10 else digits[0]
            return digits
    if hasattr( toolchain, 'version' ):
        match = re.search( r'(\d+)', str( toolchain.version() ) )
        if match:
            return match.group( 1 )
    return None


def _msvc_conan_version( toolchain ):
    """Map Cuppa MSVC toolset (e.g. vc145 / 14.5) to Conan ``compiler.version``."""
    toolset = getattr( toolchain, '_toolset', None )
    major = minor = None
    if toolset is not None:
        try:
            major = int( toolset.major )
            minor = int( toolset.minor )
        except ( TypeError, ValueError, AttributeError ):
            major = minor = None
    if major is None and hasattr( toolchain, 'short_version' ):
        short = re.sub( r'\D', '', str( toolchain.short_version() ) )
        if len( short ) >= 2:
            major = int( short[:2] )
            minor = int( short[2] ) if len( short ) >= 3 and short[2].isdigit() else 0
    if major == 14:
        if minor >= 4:
            return '194'
        if minor >= 3:
            return '193'
        if minor >= 2:
            return '192'
        if minor >= 1:
            return '191'
        return '190'
    if major is not None:
        return str( major )
    return None


def _compiler_libcxx( env, toolchain ):
    family = _compiler_family( toolchain )
    if family not in ( 'clang', 'apple-clang' ):
        if family == 'gcc':
            return 'libstdc++11'
        return None
    if hasattr( toolchain, 'stdlib_flag' ):
        flag = toolchain.stdlib_flag( env )
        if flag and 'libc++' in flag:
            return 'libc++'
        if flag and 'libstdc++' in flag:
            return 'libstdc++11'
    stdlib = getattr( toolchain, '_stdlib', None )
    if stdlib == 'libc++':
        return 'libc++'
    if stdlib in ( 'libstdc++', 'libstdc++11' ):
        return 'libstdc++11'
    option = env.get_option( 'clang-stdlib' ) if hasattr( env, 'get_option' ) else env.get( 'clang-stdlib' )
    if option == 'libc++':
        return 'libc++'
    if family == 'apple-clang':
        return 'libc++'
    return 'libstdc++11'


def _msvc_runtime( env, variant ):
    """Cuppa defaults to the dynamic CRT; map variant to Conan runtime settings."""
    # Prefer dynamic (/MD, /MDd). Static CRT can be added later via options.
    runtime = 'dynamic'
    build_type = _build_type_for_variant( variant )
    # Conan 2: compiler.runtime_type distinguishes Debug vs Release CRT when set.
    runtime_type = 'Debug' if build_type == 'Debug' else 'Release'
    return runtime, runtime_type


def _build_type_for_variant( variant ):
    name = variant if isinstance( variant, str ) else getattr( variant, 'name', lambda: str( variant ) )()
    if callable( name ):
        name = name()
    name = str( name )
    # Coverage instrumentation builds as Debug-compatible for Conan packages.
    if name in ( 'dbg', 'cov', 'Debug' ):
        return 'Debug'
    return 'Release'


def conan_settings_for( env, toolchain, variant ):
    """Build Conan settings dict from Cuppa env / toolchain / variant."""
    settings = {
        'os': _platform_os_name(),
        'arch': env.get( 'target_arch' ) or 'x86_64',
        'build_type': _build_type_for_variant( variant ),
        'compiler': _compiler_family( toolchain ),
    }
    version = _compiler_version( toolchain )
    if version:
        settings['compiler.version'] = version

    stdcpp = env.get( 'stdcpp' )
    if not stdcpp and hasattr( toolchain, 'abi' ):
        try:
            stdcpp = toolchain.abi( env )
        except Exception:
            stdcpp = None
    if not stdcpp and hasattr( toolchain, 'abi_flag' ):
        try:
            stdcpp = toolchain.abi_flag( env )
        except Exception:
            stdcpp = None
    cppstd = _map_cppstd( stdcpp )
    if cppstd:
        settings['compiler.cppstd'] = cppstd

    family = settings['compiler']
    if family == 'msvc':
        runtime, runtime_type = _msvc_runtime( env, variant )
        settings['compiler.runtime'] = runtime
        settings['compiler.runtime_type'] = runtime_type
    else:
        libcxx = _compiler_libcxx( env, toolchain )
        if libcxx:
            settings['compiler.libcxx'] = libcxx

    return settings


def settings_to_cli( settings ):
    args = []
    for key, value in sorted( settings.items() ):
        if value is None:
            continue
        args.extend( [ '-s', '{}={}'.format( key, value ) ] )
    return args


def write_transient_conanfile( path, requires ):
    lines = [ '[requires]' ]
    for req in requires:
        lines.append( str( req ) )
    lines.extend( [ '', '[generators]', 'SConsDeps', 'VirtualRunEnv', '' ] )
    parent = os.path.dirname( path )
    if parent:
        os.makedirs( parent, exist_ok=True )
    with open( path, 'w', encoding='utf-8' ) as handle:
        handle.write( '\n'.join( lines ) )
    return path


def load_sconsdeps( install_dir ):
    """Load ``SConscript_conandeps`` and return the conandeps mapping.

    Uses a small ``exec`` loader with a ``Return`` shim so the file can be read
    during unit tests and during SConscript evaluation without requiring a fully
    initialised SCons ``SConstruct_dir`` (``SConscript()`` needs that context).
    """
    import SCons.Errors

    script = os.path.join( install_dir, 'SConscript_conandeps' )
    if not os.path.isfile( script ):
        raise SCons.Errors.StopError(
            "Conan SConsDeps output missing: [{}]".format( script )
        )
    try:
        namespace = { 'Return': None }
        returned = {}

        def _return( name ):
            returned['name'] = name

        namespace['Return'] = _return
        with open( script, encoding='utf-8' ) as handle:
            code = compile( handle.read(), script, 'exec' )
        exec( code, namespace, namespace )
        key = returned.get( 'name', 'conandeps' )
        info = namespace.get( key )
    except SCons.Errors.StopError:
        raise
    except Exception as exc:
        raise SCons.Errors.StopError(
            "Failed to load Conan SConsDeps script [{}]: {}".format( script, exc )
        ) from exc
    if not isinstance( info, dict ) or 'conandeps' not in info:
        raise SCons.Errors.StopError(
            "Conan SConsDeps script [{}] did not return a conandeps mapping".format( script )
        )
    return info


def merge_conan_flags( env, flags ):
    """Apply SConsDeps flag dict via MergeFlags; route BINPATH/LIBPATH into ENV."""
    if not flags:
        return
    merge = {}
    for key, value in flags.items():
        if key in _MERGE_SKIP_KEYS:
            continue
        if value:
            merge[key] = value
    if merge:
        env.MergeFlags( merge )

    binpaths = list( flags.get( 'BINPATH' ) or [] )
    libpaths = list( flags.get( 'LIBPATH' ) or [] )
    _apply_runtime_paths( env, binpaths, libpaths )


def _apply_runtime_paths( env, binpaths, libpaths ):
    import cuppa.build_platform
    platform_name = cuppa.build_platform.name()
    for path in binpaths:
        if path:
            env.PrependENVPath( 'PATH', path )
    if platform_name == 'Windows':
        for path in libpaths:
            if path:
                env.PrependENVPath( 'PATH', path )
    elif platform_name == 'Darwin':
        for path in libpaths:
            if path:
                env.PrependENVPath( 'DYLD_LIBRARY_PATH', path )
    else:
        for path in libpaths:
            if path:
                env.PrependENVPath( 'LD_LIBRARY_PATH', path )


def version_summary_from_info( info ):
    versions = []
    for key, value in sorted( info.items() ):
        if key.endswith( '_version' ) and value:
            pkg = key[:-len( '_version' )]
            versions.append( '{}={}'.format( pkg, value ) )
    return ', '.join( versions ) if versions else 'conan'


class base( object ):
    """Conan consumer dependency applied through ``env.BuildWith``."""

    _name = None
    _conanfile = None
    _requires = None
    _generators_folder = None
    _remote = None
    _package_key = None  # optional per-require MergeFlags key; default whole graph
    _install_cache = {}

    @classmethod
    def add_options( cls, add_option ):
        pass

    @classmethod
    def add_to_env( cls, env, add_dependency ):
        add_dependency( cls._name, cls.create )

    @classmethod
    def create( cls, env ):
        return cls( env )

    @classmethod
    def name( cls ):
        return cls._name

    def __init__( self, env ):
        self._env_ref = env
        self._install_dir = None
        self._info = None
        self._version_string = 'conan'
        self._resolved_conanfile = None

    def version( self ):
        return self._version_string

    def repository( self ):
        return 'conan'

    def branch( self ):
        return None

    def revisions( self ):
        return None

    def install_dir( self ):
        return self._install_dir

    def __call__( self, env, toolchain, variant ):
        import SCons.Errors

        try:
            install_dir = self._ensure_installed( env, toolchain, variant )
            info = load_sconsdeps( install_dir )
        except SCons.Errors.StopError:
            raise
        except Exception as exc:
            logger.error( "Conan dependency [{}] failed: {}".format(
                    as_error( self._name ), as_error( str( exc ) )
            ) )
            raise SCons.Errors.StopError(
                "Conan dependency [{}] failed: {}".format( self._name, exc )
            ) from exc

        self._install_dir = install_dir
        self._info = info
        self._version_string = version_summary_from_info( info )

        # SConsDeps per-require keys may omit LIBS; always prefer aggregated
        # ``conandeps`` for correct link lines (whole graph or single-require sugar).
        flags = info.get( 'conandeps' ) or {}
        merge_conan_flags( env, flags )
        logger.debug( "Applied Conan SConsDeps [conandeps] from [{}]".format(
                as_notice( install_dir )
        ) )

    def _resolve_conanfile_path( self, env ):
        if self._generators_folder:
            return None
        if self._conanfile:
            path = os.path.expanduser( self._conanfile )
            if not os.path.isabs( path ):
                root = env.get( 'sconstruct_dir' ) or os.getcwd()
                path = os.path.join( root, path )
            return os.path.normpath( path )
        if self._requires:
            return None
        import SCons.Errors
        raise SCons.Errors.StopError(
            "Conan dependency [{}] needs conanfile=, requires=, or generators_folder=".format(
                    self._name
            )
        )

    def _fingerprint( self, env, toolchain, variant, conanfile_path ):
        settings = conan_settings_for( env, toolchain, variant )
        parts = [
            'name=' + str( self._name ),
            'settings=' + ','.join( '{}={}'.format( k, settings[k] ) for k in sorted( settings ) ),
        ]
        if conanfile_path and os.path.isfile( conanfile_path ):
            parts.append( 'conanfile=' + _sha256_file( conanfile_path ) )
            lockfile = os.path.join( os.path.dirname( conanfile_path ), 'conan.lock' )
            if os.path.isfile( lockfile ):
                parts.append( 'lock=' + _sha256_file( lockfile ) )
            else:
                parts.append( 'lock=none' )
        elif self._requires:
            reqs = tuple( sorted( str( r ) for r in self._requires ) )
            parts.append( 'requires=' + _sha256_text( '|'.join( reqs ) ) )
            parts.append( 'lock=none' )
        if self._remote:
            parts.append( 'remote=' + str( self._remote ) )
        digest = hashlib.sha256( '\n'.join( parts ).encode( 'utf-8' ) ).hexdigest()
        return digest, settings

    def _install_root( self, env ):
        download_root = env.get( 'download_root' ) or os.path.join( os.getcwd(), '_cuppa' )
        return os.path.join( os.path.expanduser( download_root ), 'conan', self._name )

    def _ensure_installed( self, env, toolchain, variant ):
        import SCons.Errors

        if self._generators_folder:
            folder = os.path.expanduser( self._generators_folder )
            if not os.path.isabs( folder ):
                root = env.get( 'sconstruct_dir' ) or os.getcwd()
                folder = os.path.join( root, folder )
            folder = os.path.normpath( folder )
            if not os.path.isfile( os.path.join( folder, 'SConscript_conandeps' ) ):
                raise SCons.Errors.StopError(
                    "generators_folder [{}] has no SConscript_conandeps".format( folder )
                )
            return folder

        conanfile_path = self._resolve_conanfile_path( env )
        fingerprint, settings = self._fingerprint( env, toolchain, variant, conanfile_path )
        cache_key = ( self._name, fingerprint )

        if cache_key in self._install_cache:
            return self._install_cache[cache_key]

        install_dir = os.path.join( self._install_root( env ), fingerprint[:16] )
        done_path = os.path.join( install_dir, _DONE_MARKER )
        script_path = os.path.join( install_dir, 'SConscript_conandeps' )
        lock_path = os.path.join( self._install_root( env ), _LOCK_NAME )

        with _exclusive_file_lock( lock_path ):
            if os.path.isfile( done_path ) and os.path.isfile( script_path ):
                try:
                    with open( done_path, encoding='utf-8' ) as handle:
                        if handle.read().strip() == fingerprint:
                            self._install_cache[cache_key] = install_dir
                            return install_dir
                except OSError:
                    pass

            self._run_conan_install(
                    env, install_dir, conanfile_path, settings, fingerprint
            )
            self._install_cache[cache_key] = install_dir
            return install_dir

    def _run_conan_install( self, env, install_dir, conanfile_path, settings, fingerprint ):
        import SCons.Errors

        conan = _find_conan_executable()
        if not conan:
            raise SCons.Errors.StopError(
                "Conan CLI not found on PATH; install Conan 2 to use dependency [{}]".format(
                        self._name
                )
            )

        os.makedirs( install_dir, exist_ok=True )

        path_for_install = conanfile_path
        if not path_for_install and self._requires:
            path_for_install = write_transient_conanfile(
                    os.path.join( install_dir, 'conanfile.txt' ),
                    self._requires,
            )
        if not path_for_install or not os.path.isfile( path_for_install ):
            raise SCons.Errors.StopError(
                "Conanfile not found for dependency [{}]: {}".format(
                        self._name, path_for_install
                )
            )

        # Prefer installing against the directory containing the conanfile so
        # adjacent conan.lock is discovered; still pass -g explicitly.
        install_src = path_for_install
        cmd = [
            conan, 'install', install_src,
            '-of', install_dir,
            '-g', 'SConsDeps',
            '-g', 'VirtualRunEnv',
            '--build=missing',
        ]
        cmd.extend( settings_to_cli( settings ) )

        lockfile = os.path.join( os.path.dirname( path_for_install ), 'conan.lock' )
        if os.path.isfile( lockfile ):
            cmd.extend( [ '-l', lockfile ] )
        else:
            logger.warn(
                "Conan dependency [{}]: no conan.lock beside [{}]; builds are not pinned".format(
                        as_notice( self._name ), as_notice( path_for_install )
                )
            )

        if self._remote:
            cmd.extend( [ '-r', str( self._remote ) ] )

        offline = bool( env.get( 'offline' ) )
        if offline:
            # Cuppa --offline: do not contact remotes; fail if cache miss.
            cmd.append( '--no-remote' )

        logger.info( "Running [{}]".format( as_notice( ' '.join( cmd ) ) ) )
        try:
            completed = subprocess.run(
                    cmd,
                    check=False,
                    capture_output=True,
                    text=True,
            )
        except OSError as exc:
            raise SCons.Errors.StopError(
                "Failed to execute conan for [{}]: {}".format( self._name, exc )
            ) from exc

        if completed.returncode != 0:
            detail = ( completed.stderr or completed.stdout or '' ).strip()
            if offline:
                raise SCons.Errors.StopError(
                    "Conan install for [{}] failed in offline mode (no remotes). "
                    "Ensure packages are in the local Conan cache. Detail:\n{}".format(
                            self._name, detail
                    )
                )
            raise SCons.Errors.StopError(
                "Conan install for [{}] failed (exit {}):\n{}".format(
                        self._name, completed.returncode, detail
                )
            )

        if not os.path.isfile( os.path.join( install_dir, 'SConscript_conandeps' ) ):
            raise SCons.Errors.StopError(
                "Conan install for [{}] did not produce SConscript_conandeps under [{}]".format(
                        self._name, install_dir
                )
            )

        with open( os.path.join( install_dir, _DONE_MARKER ), 'w', encoding='utf-8' ) as handle:
            handle.write( fingerprint )


def conan_deps(
        name='conan',
        conanfile=None,
        requires=None,
        generators_folder=None,
        remote=None,
):
    """Factory for a Conan 2 consumer dependency (whole graph via SConsDeps).

    Prefer ``conanfile=`` pointing at ``conanfile.txt`` / ``conanfile.py``.
    ``requires=`` writes a transient conanfile. ``generators_folder=`` reuses a
    pre-run ``conan install`` output (Approach C).
    """
    import SCons.Errors

    if not conanfile and not requires and not generators_folder:
        raise SCons.Errors.StopError(
            "conan_deps({!r}) requires conanfile=, requires=, or generators_folder=".format( name )
        )

    type_name = 'BuildWithConan' + str( name ).title().replace( '_', '' ).replace( '-', '' )
    return type(
            type_name,
            ( base, ),
            {
                '_name': name,
                '_conanfile': conanfile,
                '_requires': list( requires ) if requires else None,
                '_generators_folder': generators_folder,
                '_remote': remote,
                '_package_key': None,
                '_install_cache': {},
            }
    )


def conan_dependency(
        name,
        requires=None,
        conanfile=None,
        generators_folder=None,
        remote=None,
):
    """Sugar for a named Conan require sharing the same install machinery.

    When ``requires`` is a string package name without a version, uses ``name/[*]``.
    Applies the whole-graph ``conandeps`` flags (SConsDeps per-package keys may omit LIBS).
    """
    import SCons.Errors

    req_list = None
    if requires is None and conanfile is None and generators_folder is None:
        req_list = [ '{}/[*]'.format( name ) ]
    elif isinstance( requires, str ):
        req_list = [ requires ]
    elif requires is not None:
        req_list = list( requires )

    if not req_list and not conanfile and not generators_folder:
        raise SCons.Errors.StopError(
            "conan_dependency({!r}) needs requires=, conanfile=, or generators_folder=".format( name )
        )

    type_name = 'BuildWithConanDep' + str( name ).title().replace( '_', '' ).replace( '-', '' )
    return type(
            type_name,
            ( base, ),
            {
                '_name': name,
                '_conanfile': conanfile,
                '_requires': req_list,
                '_generators_folder': generators_folder,
                '_remote': remote,
                '_package_key': name,
                '_install_cache': {},
            }
    )
