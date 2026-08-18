#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

import importlib
import os

import pytest

pytestmark = pytest.mark.unit


def _repo_root():
    return os.path.abspath( os.path.join( os.path.dirname( __file__ ), '..', '..' ) )


def _read_setup_packages():
    setup_path = os.path.join( _repo_root(), 'setup.py' )
    packages = []
    in_packages = False
    with open( setup_path, encoding='utf-8' ) as handle:
        for line in handle:
            stripped = line.strip()
            if stripped.startswith( 'packages' ) and '=' in stripped:
                in_packages = True
                continue
            if not in_packages:
                continue
            if stripped.startswith( ']' ):
                break
            if stripped.startswith( "'" ):
                packages.append( stripped.strip( "',\"" ) )
    return packages


def _discover_package_dirs():
    cuppa_root = os.path.join( _repo_root(), 'cuppa' )
    discovered = { 'cuppa' }
    for dirpath, dirnames, filenames in os.walk( cuppa_root ):
        if '__init__.py' not in filenames:
            continue
        rel = os.path.relpath( dirpath, cuppa_root ).replace( os.sep, '.' )
        name = 'cuppa' if rel == '.' else 'cuppa.{}'.format( rel )
        discovered.add( name )
    return discovered


def test_setup_lists_nested_python_packages():
    listed = set( _read_setup_packages() )
    discovered = _discover_package_dirs()
    missing = sorted( discovered - listed )
    assert not missing, 'setup.py packages missing: {}'.format( ', '.join( missing ) )


def test_import_cuppa_entrypoint_modules():
    importlib.import_module( 'cuppa' )
    importlib.import_module( 'cuppa.cpp.profiles_report.profiles.std_init' )
    importlib.import_module( 'cuppa.reports.link_style' )
