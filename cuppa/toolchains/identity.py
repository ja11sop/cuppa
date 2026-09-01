#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   Toolchain identity — full vs major layout / package tokens
#-------------------------------------------------------------------------------

"""Policy for ``toolchain.name()`` / ``package_name()``.

``full`` keeps today's encoded major.minor token (``gcc153``, ``clang211``, ``vc145``).
``major`` drops the point-release digits (``gcc15``, ``clang21``, ``vc14``) while leaving
stdlib tags and registered archive qualifiers (``gcc17_gcc_snapshot_…``) intact.

Selection aliases (``--toolchains=gcc153``) and ``--list-toolchains`` version fields are
unchanged. This module only names *layout and package* identity.
"""

import os

from cuppa.log import logger
from cuppa.colourise import as_info, as_notice


IDENTITY_FULL = 'full'
IDENTITY_MAJOR = 'major'
IDENTITY_CHOICES = ( IDENTITY_FULL, IDENTITY_MAJOR )

TOOLCHAIN_IDENTITY_KEY = 'toolchain_identity'


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
