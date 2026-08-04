
#          Copyright Jamie Allsop 2011-2018
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   Library Naming
#-------------------------------------------------------------------------------

import os
import os.path
import re

import cuppa.build_platform



def extract_library_name_from_path( path ):
    # Extract the library name from the library path.
    # Possibly use regex instead?
    name = os.path.split( str(path) )[1]
    name = name.split( "." )[0]
    name = name.split( "-" )[0]
    name = "_".join( name.split( "_" )[1:] )
    return name



def toolset_name_from_toolchain( toolchain ):
    toolset_name = toolchain.toolset_name()
    if cuppa.build_platform.name() == "Darwin":
        if toolset_name == "gcc":
            toolset_name = "darwin"
        elif toolset_name == "clang":
            toolset_name = "clang-darwin"
    return toolset_name



def toolset_from_toolchain( toolchain ):
    toolset_name = toolset_name_from_toolchain( toolchain )
    if toolset_name == "clang-darwin":
        return toolset_name
    elif toolset_name == "msvc":
        return toolset_name

    toolset = toolchain.cxx_version() and toolset_name + "-" + toolchain.cxx_version() or toolset_name
    return toolset


def variant_name( variant ):
    if variant == 'dbg':
        return 'debug'
    else:
        return 'release'


def link_type( linktype ):
    if linktype == 'shared':
        return 'link-shared'
    return 'link-static'


def thread_model( threading ):
    if threading:
        return 'threading-multi'
    return 'threading-single'


def directory_from_abi_flag( abi_flag ):
    if abi_flag:
        flag, value = abi_flag.split('=')
        if value:
            return value
    return abi_flag


def stage_directory( toolchain, variant, target_arch, abi_flag ):
    build_base = "build"
    abi_dir = directory_from_abi_flag( abi_flag )
    if abi_dir:
        build_base += "." + abi_dir
    return os.path.join( build_base, toolchain.name(), variant, target_arch )


def b2_build_dir_toolset_base( toolchain ):
    """Boost.Build toolset folder prefix under ``bin.v2`` (e.g. ``clang-linux``, ``gcc``)."""
    toolset_name = toolchain.toolset_name()
    platform = cuppa.build_platform.name()
    if platform == "Darwin":
        if toolset_name == "gcc":
            return "darwin"
        if toolset_name == "clang":
            return "clang-darwin"
    elif platform == "Linux":
        if toolset_name == "clang":
            return "clang-linux"
    return toolset_name


def b2_build_dir_toolset_token( toolchain ):
    """Directory basename Boost.Build uses under ``bin.v2`` (e.g. ``clang-linux-21``)."""
    base = b2_build_dir_toolset_base( toolchain )
    if base in ( "clang-darwin", "msvc" ):
        # Often unversioned on disk; still prefer a versioned token when we know one.
        major = _toolchain_major_version( toolchain )
        return "{}-{}".format( base, major ) if major else base
    major = _toolchain_major_version( toolchain )
    if major:
        return "{}-{}".format( base, major )
    return base


_B2_TOOLSET_FAMILY_RE = re.compile(
        r'^((?:clang-linux|clang-darwin|clang|darwin|gcc|msvc|mingw|borland)'
        r'(?:-\d+)?)(?:\..*)?$'
)


def b2_toolset_family_token( token ):
    """Strip Boost.Build patch suffixes: ``gcc-15.3`` → ``gcc-15``."""
    if not token:
        return token
    match = _B2_TOOLSET_FAMILY_RE.match( token )
    return match.group( 1 ) if match else token


def b2_toolset_family_label( token, boost_variant=None ):
    """Honest bin-toolset tag: ``gcc-15*`` or ``gcc-15*/debug``.

    Cuppa toolchains encode minors (``gcc153``), but Boost.Build product dirs only
    distinguish the major toolset family (``gcc-15`` / ``gcc-15.*``). The trailing
    ``*`` makes that family match visible. Optional ``boost_variant`` names the
    ``debug`` / ``release`` leaf actually selected for clean.
    """
    family = b2_toolset_family_token( token )
    if not family:
        return boost_variant or ''
    label = family + '*'
    if boost_variant:
        return '{}/{}'.format( label, boost_variant )
    return label


def _toolchain_major_version( toolchain ):
    reported = getattr( toolchain, '_reported_version', None )
    if isinstance( reported, dict ) and reported.get( 'major' ) is not None:
        return str( reported['major'] )
    version = None
    if hasattr( toolchain, 'version' ) and callable( toolchain.version ):
        try:
            version = toolchain.version()
        except Exception:
            version = None
    if version:
        return str( version ).split( '.' )[0]
    cxx = None
    if hasattr( toolchain, 'cxx_version' ) and callable( toolchain.cxx_version ):
        try:
            cxx = toolchain.cxx_version()
        except Exception:
            cxx = None
    if cxx:
        return str( cxx ).lstrip( '-' ).split( '.' )[0]
    return ''


def selection_tool_variant_tag( toolchain, variant_key, target_arch ):
    """Cuppa-facing selection tag, e.g. ``clang211_dbg_x86_64``."""
    parts = [
            toolchain.name() if toolchain is not None else 'toolchain',
            str( variant_key or 'variant' ),
            str( target_arch or 'arch' ),
    ]
    return '_'.join( parts )


_B2_TOOLSET_DIR_RE = re.compile(
        r'^(?:clang-linux|clang-darwin|clang|darwin|gcc|msvc|mingw|borland)'
        r'(?:-\d+(?:\.\d+)*)?$'
)


def is_b2_toolset_dir_name( name ):
    return bool( name and _B2_TOOLSET_DIR_RE.match( name ) )


def find_b2_build_dir_products( bin_root, toolset_token, boost_variant=None ):
    """Absolute product dirs under a Boost ``bin.<abi>`` tree for one toolset(/variant).

    Walks for directories named ``toolset_token`` (or ``toolset_token.<patch>``). When
    ``boost_variant`` is set (``debug`` / ``release``), only that child directory is
    returned — the bare toolset directory is never chosen as a fallback (it may contain
    products for other variants). When ``boost_variant`` is omitted, the toolset
    directory itself is returned.

    Nested paths are pruned (a parent is dropped when a child path is also selected) so
    sizes are not double-counted.
    """
    products = []
    if not bin_root or not os.path.isdir( bin_root ) or not toolset_token:
        return products
    seen = set()
    token_prefix = toolset_token + '.'
    for dirpath, dirnames, _filenames in os.walk( bin_root ):
        matched = []
        for name in list( dirnames ):
            if name != toolset_token and not name.startswith( token_prefix ):
                continue
            toolset_path = os.path.join( dirpath, name )
            if boost_variant:
                variant_path = os.path.join( toolset_path, boost_variant )
                if not os.path.isdir( variant_path ):
                    matched.append( name )
                    continue
                chosen = variant_path
            else:
                chosen = toolset_path
            abs_chosen = os.path.abspath( chosen )
            if abs_chosen not in seen:
                seen.add( abs_chosen )
                products.append( abs_chosen )
            matched.append( name )
        # Do not walk into matched toolset trees; we clean them as units.
        for name in matched:
            dirnames.remove( name )
    return _prune_nested_paths( products )


def _prune_nested_paths( paths ):
    """Drop any path that is an ancestor of another path in the list."""
    if len( paths ) < 2:
        return list( paths )
    ordered = sorted( { os.path.abspath( p ) for p in paths } )
    kept = []
    for path in ordered:
        # If a later path is under this one, skip this ancestor.
        if any(
                other != path and other.startswith( path + os.sep )
                for other in ordered
        ):
            continue
        kept.append( path )
    return kept


def enumerate_b2_build_dir_toolset_products( bin_root ):
    """All toolset (or toolset/variant) product dirs under ``bin.<abi>`` for leftover listing."""
    products = []
    if not bin_root or not os.path.isdir( bin_root ):
        return products
    seen = set()
    for dirpath, dirnames, _filenames in os.walk( bin_root ):
        matched = []
        for name in list( dirnames ):
            if not is_b2_toolset_dir_name( name ):
                continue
            toolset_path = os.path.join( dirpath, name )
            abs_toolset = os.path.abspath( toolset_path )
            # Prefer variant children when present so leftovers mirror clean targets.
            variant_children = [
                    os.path.join( toolset_path, variant )
                    for variant in ( 'debug', 'release' )
                    if os.path.isdir( os.path.join( toolset_path, variant ) )
            ]
            if variant_children:
                for child in variant_children:
                    abs_child = os.path.abspath( child )
                    if abs_child not in seen:
                        seen.add( abs_child )
                        products.append( abs_child )
            elif abs_toolset not in seen:
                seen.add( abs_toolset )
                products.append( abs_toolset )
            matched.append( name )
        for name in matched:
            dirnames.remove( name )
    return products


def library_tag( toolchain, boost_version, variant, threading ):
    tag = "-{toolset_tag}{toolset_version}{threading}{abi_flag}-{boost_version}"

    toolset_tag = toolchain.toolset_tag()
    abi_flag = variant == "debug" and "-d" or ""

    if cuppa.build_platform.name() == "Windows":
        if toolset_tag == "gcc":
            toolset_tag = "mgw"
        elif toolset_tag == "vc":
            abi_flag = variant == "debug" and "-gd" or ""

    return tag.format(
            toolset_tag     = toolset_tag,
            toolset_version = toolchain.short_version(),
            threading       = threading and "-mt" or "",
            abi_flag        = abi_flag,
            boost_version   = boost_version
    )


def static_library_name( env, library, toolchain, boost_version, variant, threading ):
    name    = "{prefix}boost_{library}{tag}{suffix}"
    tag     = ""
    prefix  = env.subst('$LIBPREFIX')

    if cuppa.build_platform.name() == "Windows":
        tag = library_tag( toolchain, boost_version, variant, threading )
        prefix = "lib"

    return name.format(
            prefix  = prefix,
            library = library,
            tag     = tag,
            suffix  = env.subst('$LIBSUFFIX')
    )


def shared_library_name( env, library, toolchain, boost_version, variant, threading ):
    name    = "{prefix}boost_{library}{tag}{suffix}{version}"
    tag     = ""
    version = ""

    if cuppa.build_platform.name() == "Windows":
        tag = library_tag( toolchain, boost_version, variant, threading )
    elif cuppa.build_platform.name() == "Linux":
        version = "." + boost_version

    return name.format(
            prefix  = env.subst('$SHLIBPREFIX'),
            library = library,
            tag     = tag,
            suffix  = env.subst('$SHLIBSUFFIX'),
            version = version
     )
