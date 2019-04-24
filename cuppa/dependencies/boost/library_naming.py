
#          Copyright Jamie Allsop 2011-2018
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   Library Naming
#-------------------------------------------------------------------------------

import os.path

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
