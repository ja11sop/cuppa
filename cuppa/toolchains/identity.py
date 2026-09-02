#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   Toolchain identity — full vs major layout / package tokens
#-------------------------------------------------------------------------------

"""Policy for ``toolchain.name()`` / ``package_name()`` and consume-side pairing.

``full`` keeps today's encoded major.minor token (``gcc153``, ``clang211``, ``vc145``).
``major`` drops the point-release digits (``gcc15``, ``clang21``, ``vc14``) while leaving
stdlib tags and registered archive qualifiers (``gcc17_gcc_snapshot_…``) intact.

Selection aliases (``--toolchains=gcc153``) and ``--list-toolchains`` version fields are
unchanged. Layout identity lives here; GitLab lookup overrides live on
``PackageConsumeIdentity`` and in ``cuppa.package_managers.gitlab``.
"""

import os
import re

from cuppa.log import logger
from cuppa.colourise import as_info, as_notice


IDENTITY_FULL = 'full'
IDENTITY_MAJOR = 'major'
IDENTITY_CHOICES = ( IDENTITY_FULL, IDENTITY_MAJOR )

TOOLCHAIN_IDENTITY_KEY = 'toolchain_identity'
PACKAGE_OS_OVERRIDE_KEY = 'package_gitlab_os_override'
PACKAGE_IDENTITY_FALLBACK_KEY = 'package_gitlab_identity_fallback'
PACKAGE_IDENTITY_FALLBACK_CHOICES = ( 'on', 'off' )
PACKAGE_OS_IDENTITY_KEY = 'package_gitlab_os_identity'
OS_IDENTITY_INCLUDE = 'include'
OS_IDENTITY_OMIT = 'omit'
PACKAGE_OS_IDENTITY_CHOICES = ( OS_IDENTITY_INCLUDE, OS_IDENTITY_OMIT )

_GNU_PACKAGE_TOKEN = re.compile( r'^(gcc|clang)(\d+)(?:-(.+))?$' )
_MSVC_PACKAGE_TOKEN = re.compile( r'^vc(\d+)(e)?$', re.I )


class ToolchainIdentity( object ):
    """Registers ``--toolchain-identity=``; not itself a compiler toolchain."""

    @classmethod
    def add_options( cls, add_option ):
        add_option(
            '--toolchain-identity',
            dest='toolchain_identity',
            choices=list( IDENTITY_CHOICES ),
            nargs=1,
            action='store',
            help="How toolchain tokens are encoded in _build paths and package stems: "
                 "'full' (gcc153) or 'major' (gcc15). Does not change --list-toolchains "
                 "reported compiler versions. New installs persist major in ~/.cuppaconfig; "
                 "existing global files without the key are grandfathered to full.",
        )

    @classmethod
    def add_to_env( cls, env, add_toolchain, add_to_supported ):
        # Option-only helper; do not register a compiler.
        pass


class PackageConsumeIdentity( object ):
    """Registers GitLab package OS/toolchain lookup and OS-identity options."""

    @classmethod
    def add_options( cls, add_option ):
        add_option(
            '--package-gitlab-os-override',
            dest=PACKAGE_OS_OVERRIDE_KEY,
            type='string',
            nargs=1,
            action='store',
            help="Force the OS segment used when looking up GitLab package archives "
                 "(for example debian while the host is ubuntu). Does not change "
                 "published stems. Per-dependency "
                 "--package-gitlab-os-override-<name>= takes precedence.",
        )
        add_option(
            '--package-gitlab-identity-fallback',
            dest=PACKAGE_IDENTITY_FALLBACK_KEY,
            choices=list( PACKAGE_IDENTITY_FALLBACK_CHOICES ),
            nargs=1,
            action='store',
            help="When a GitLab archive 404s, try the other toolchain identity "
                 "(full vs major) with the same OS shape, then the other OS encoding "
                 "(include vs omit). Default on. Dual-try is consume-only; "
                 "a successful fallback is an ABI bet the project owns.",
        )
        add_option(
            '--package-gitlab-os-identity',
            dest=PACKAGE_OS_IDENTITY_KEY,
            choices=list( PACKAGE_OS_IDENTITY_CHOICES ),
            nargs=1,
            action='store',
            help="Whether GitLab package archive stems include the OS id "
                 "({package}_{os}_{tool}) or omit it ({package}_{tool}). "
                 "Default include. Omit is a publish-time ABI bet; consume "
                 "uses the same flag for the preferred lookup stem.",
        )

    @classmethod
    def add_to_env( cls, env, add_toolchain, add_to_supported ):
        pass


def normalised_identity( value ):
    """Return ``full`` or ``major``, or ``None`` when unset."""
    if value is None or value == '':
        return None
    if isinstance( value, ( list, tuple ) ):
        if not value:
            return None
        value = value[0]
    text = str( value ).strip().lower()
    if text not in IDENTITY_CHOICES:
        raise ValueError(
            "toolchain_identity must be 'full' or 'major', not {!r}".format( value )
        )
    return text


def current_identity():
    """Effective policy for this process, defaulting to ``full`` when unset."""
    try:
        from cuppa.core.environment import CuppaEnvironment
        raw = CuppaEnvironment.get_option( TOOLCHAIN_IDENTITY_KEY )
    except Exception:
        raw = None
    try:
        parsed = normalised_identity( raw )
    except ValueError:
        parsed = None
    return parsed or IDENTITY_FULL


def gnu_numeric_token( prefix, major, minor, policy ):
    """``gcc`` / ``clang`` + digits for the requested policy."""
    prefix = str( prefix )
    major = int( major )
    minor = int( minor )
    if policy == IDENTITY_MAJOR:
        return '{}{}'.format( prefix, major )
    return '{}{}{}'.format( prefix, major, minor )


def is_plain_gnu_token( encoded, prefix, major, minor ):
    """True when ``encoded`` is prefix+major or prefix+major+minor (optional ``-tag``)."""
    if not encoded:
        return True
    major_token = gnu_numeric_token( prefix, major, minor, IDENTITY_MAJOR )
    full_token = gnu_numeric_token( prefix, major, minor, IDENTITY_FULL )
    base = encoded.split( '-', 1 )[0]
    return base in ( major_token, full_token )


def gnu_layout_name( prefix, major, minor, policy=None, encoded_name=None, tag=None ):
    """Layout / package token for GCC or Clang.

    Registered archive names (``gcc17_qualifier``) already use the major line plus a
    unique qualifier; they are returned unchanged so two snapshots cannot collide.
    """
    policy = policy or IDENTITY_FULL
    if encoded_name and not is_plain_gnu_token( encoded_name, prefix, major, minor ):
        token = encoded_name
    else:
        token = gnu_numeric_token( prefix, major, minor, policy )
    if tag:
        suffix = '-{}'.format( tag )
        if not token.endswith( suffix ):
            return token + suffix
    return token


def msvc_layout_name( toolset, policy=None ):
    """Layout / package token for MSVC.

    ``full`` is the usual alias (``vc145``). ``major`` keeps the toolset major only
    (``vc14``, plus ``e`` when the toolset is experimental).
    """
    policy = policy or IDENTITY_FULL
    if policy == IDENTITY_MAJOR:
        suffix = 'e' if getattr( toolset, 'experimental', False ) else ''
        return 'vc{}{}'.format( int( toolset.major ), suffix )
    return toolset.alias


def should_migrate_global_identity():
    """Skip rewriting the developer's ``~/.cuppaconfig`` during pytest unless opted in."""
    if os.environ.get( 'CUPPA_TEST_IDENTITY_MIGRATE' ) == '1':
        return True
    if os.environ.get( 'PYTEST_CURRENT_TEST' ):
        return False
    return True


def migrate_global_toolchain_identity( conf_path ):
    """Persist identity into the global conf file.

    Missing file → create ``toolchain_identity=major``. Existing file without the key →
    write ``full``. Existing key is left unchanged.
    """
    from cuppa.configure import load_settings_file, upsert_setting

    existed = bool( conf_path ) and os.path.exists( conf_path )
    settings = load_settings_file( conf_path )
    if TOOLCHAIN_IDENTITY_KEY in settings:
        return normalised_identity( settings[TOOLCHAIN_IDENTITY_KEY] )

    value = IDENTITY_FULL if existed else IDENTITY_MAJOR
    upsert_setting( conf_path, TOOLCHAIN_IDENTITY_KEY, value )
    logger.info( "Persisted [{}] = [{}] in [{}]".format(
            as_notice( TOOLCHAIN_IDENTITY_KEY ),
            as_info( value ),
            as_notice( conf_path ),
    ) )
    return value


def option_text( value ):
    """Flatten SCons ``nargs=1`` lists to a stripped string, or ``None``."""
    if value is None or value == '':
        return None
    if isinstance( value, ( list, tuple ) ):
        if not value:
            return None
        return option_text( value[0] )
    text = str( value ).strip()
    return text or None


def _option_from_env( env, key ):
    if env is not None:
        getter = getattr( env, 'get_option', None )
        if callable( getter ):
            try:
                return option_text( getter( key ) )
            except Exception:
                pass
        if isinstance( env, dict ) and key in env:
            return option_text( env.get( key ) )
    try:
        from cuppa.core.environment import CuppaEnvironment
        return option_text( CuppaEnvironment.get_option( key ) )
    except Exception:
        return None


def package_os_override( env=None ):
    """Project-level OS segment for GitLab lookup, or ``None``."""
    return _option_from_env( env, PACKAGE_OS_OVERRIDE_KEY )


def package_identity_fallback_enabled( env=None ):
    """True unless ``--package-gitlab-identity-fallback=off`` (default on)."""
    raw = _option_from_env( env, PACKAGE_IDENTITY_FALLBACK_KEY )
    if raw is None:
        return True
    text = raw.lower()
    if text in ( 'off', 'false', '0', 'no' ):
        return False
    if text in ( 'on', 'true', '1', 'yes' ):
        return True
    return True


def package_os_identity( env=None ):
    """``include`` (default) or ``omit`` for GitLab archive OS segments."""
    raw = _option_from_env( env, PACKAGE_OS_IDENTITY_KEY )
    if raw is None:
        return OS_IDENTITY_INCLUDE
    text = raw.lower()
    if text in PACKAGE_OS_IDENTITY_CHOICES:
        return text
    return OS_IDENTITY_INCLUDE


def host_package_identity_tokens( toolchain ):
    """``(full, major)`` layout tokens for ``toolchain``, or ``(name, None)``."""
    if toolchain is None:
        return None, None
    family = None
    try:
        family = toolchain.family()
    except Exception:
        family = None
    reported = getattr( toolchain, '_reported_version', None )
    if family in ( 'gcc', 'clang' ) and reported:
        tag = None
        if family == 'clang':
            stdlib = getattr( toolchain, '_stdlib', None )
            default = None
            default_fn = getattr( toolchain, 'default_stdlib', None )
            if callable( default_fn ):
                try:
                    default = default_fn()
                except Exception:
                    default = None
            if stdlib and stdlib != default:
                tag = stdlib
        encoded = getattr( toolchain, '_name', None )
        full = gnu_layout_name(
                family,
                reported['major'],
                reported['minor'],
                policy=IDENTITY_FULL,
                encoded_name=encoded,
                tag=tag,
        )
        major = gnu_layout_name(
                family,
                reported['major'],
                reported['minor'],
                policy=IDENTITY_MAJOR,
                encoded_name=encoded,
                tag=tag,
        )
        return full, major
    if family == 'cl':
        toolset = getattr( toolchain, '_toolset', None )
        if toolset is not None:
            return (
                msvc_layout_name( toolset, policy=IDENTITY_FULL ),
                msvc_layout_name( toolset, policy=IDENTITY_MAJOR ),
            )
    try:
        name = toolchain.package_name()
    except Exception:
        name = None
    return name, None


def coarsen_package_token( token ):
    """Syntactic full → major for plain gcc/clang/vc tokens; else ``None``.

    Three-or-more GNU version digits drop the last (``gcc153`` → ``gcc15``).
    Two-digit GNU tokens are left alone so ``gcc15`` is not treated as ``gcc1``.
    MSVC ``vc145`` → ``vc14``. Archive qualifiers are not rewritten.
    """
    text = option_text( token )
    if not text:
        return None
    match = _GNU_PACKAGE_TOKEN.match( text )
    if match:
        prefix, digits, tag = match.group( 1 ), match.group( 2 ), match.group( 3 )
        if len( digits ) < 3:
            return None
        out = '{}{}'.format( prefix, digits[:-1] )
        if tag:
            out = '{}-{}'.format( out, tag )
        return out if out != text else None
    match = _MSVC_PACKAGE_TOKEN.match( text )
    if match:
        digits = match.group( 1 )
        experimental = match.group( 2 ) or ''
        if len( digits ) < 3:
            return None
        out = 'vc{}{}'.format( digits[:2], experimental )
        return out if out != text else None
    return None


def alternate_package_token( token, toolchain=None ):
    """The other of full ↔ major for ``token``, or ``None``."""
    text = option_text( token )
    if not text:
        return None
    full, major = host_package_identity_tokens( toolchain )
    if full and major and full != major:
        if text == full:
            return major
        if text == major:
            return full
    coarsened = coarsen_package_token( text )
    if coarsened and coarsened != text:
        return coarsened
    return None


def paired_package_tokens( token, toolchain=None ):
    """Preferred token then the full↔major alternate when one exists."""
    preferred = option_text( token )
    if not preferred:
        return []
    tokens = [ preferred ]
    alternate = alternate_package_token( preferred, toolchain )
    if alternate and alternate not in tokens:
        tokens.append( alternate )
    return tokens
