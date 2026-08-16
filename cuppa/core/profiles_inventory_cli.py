#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   Profiles inventory CLI — implied SCons keep-going (-i)
#-------------------------------------------------------------------------------

import os
import re

_PROFILES_REPORT_FLAG = '--cxx-profiles-report'
_COLLATE_INDEX_RE = re.compile( r'\bCollateCxxProfilesIndex\s*\(' )


def user_passed_ignore_errors( args_list ):
    for Arg in args_list:
        if Arg in ( '-i', '--ignore-errors' ):
            return True
    return False


def has_profiles_report_flag( args_list ):
    for Arg in args_list:
        if Arg == _PROFILES_REPORT_FLAG or Arg.startswith( _PROFILES_REPORT_FLAG + '=' ):
            return True
    return False


def _collect_sconscript_paths( args_list, launch_dir=None ):
    launch_dir = launch_dir or os.getcwd()
    paths = []

    for Index, Arg in enumerate( args_list ):
        if Arg == '--scripts' and Index + 1 < len( args_list ):
            Spec = args_list[ Index + 1 ]
        elif Arg.startswith( '--scripts=' ):
            Spec = Arg.split( '=', 1 )[ 1 ]
        else:
            continue
        for Entry in Spec.split( ',' ):
            Entry = Entry.strip()
            if Entry:
                paths.append( Entry )

    Sconstruct = os.path.join( launch_dir, 'sconstruct' )
    if os.path.isfile( Sconstruct ):
        paths.append( 'sconstruct' )
    for Name in ( 'sconscript', 'SConscript', 'Sconstruct' ):
        Path = os.path.join( launch_dir, Name )
        if os.path.isfile( Path ) and Name.lower() not in { p.lower() for p in paths }:
            paths.append( Name )

    Normalised = []
    for Path in paths:
        if not os.path.isabs( Path ):
            Path = os.path.join( launch_dir, Path )
        Normalised.append( os.path.normpath( Path ) )
    return Normalised


def sconscripts_declare_collate_index( args_list, launch_dir=None ):
    for Path in _collect_sconscript_paths( args_list, launch_dir=launch_dir ):
        try:
            with open( Path, encoding='utf-8' ) as Handle:
                if _COLLATE_INDEX_RE.search( Handle.read() ):
                    return True
        except OSError:
            continue
    return False


def args_imply_profiles_inventory( args_list, launch_dir=None ):
    if has_profiles_report_flag( args_list ):
        return True
    return sconscripts_declare_collate_index( args_list, launch_dir=launch_dir )


def inject_inventory_ignore_errors( args_list, launch_dir=None ):
    """Prepend SCons ``-i`` when a Profiles inventory run did not pass it explicitly."""
    if user_passed_ignore_errors( args_list ):
        return list( args_list )
    if not args_imply_profiles_inventory( args_list, launch_dir=launch_dir ):
        return list( args_list )
    return [ '-i' ] + list( args_list )
