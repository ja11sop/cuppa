#!/usr/bin/env python3
#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

"""Capture Alliance Clang std::init diagnostics from the example fixture."""

from __future__ import print_function

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path


_PROFILE_LINE = re.compile(
    r"^(?P<path>.+):(?P<line>\d+):(?P<column>\d+): error: "
    r"(?P<message>.+ under profile 'std::init'(?:$|;).*)$"
)

_ANSI_ESCAPE = re.compile( r'\x1b\[[0-9;]*m' )


def _strip_ansi( text ):
    return _ANSI_ESCAPE.sub( '', text )


def _run_build( example_dir, toolchain, cuppa_module_path ):
    command = [
        sys.executable,
        '-m',
        'cuppa',
        '-D',
        '--dbg',
        '--offline',
        '--cxx-profiles',
        '--cxx-profiles-enforce=std::init',
        '--cxx-disable-error-limit',
        '--toolchains={}'.format( toolchain ),
        '-i',
    ]
    environment = dict( **dict( subprocess.os.environ ) )
    if cuppa_module_path:
        environment[ 'PYTHONPATH' ] = cuppa_module_path
    completed = subprocess.run(
        command,
        cwd=str( example_dir ),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        universal_newlines=True,
        env=environment,
        check=False,
    )
    return completed.stdout


def _collect_lines( build_output ):
    lines = []
    for raw_line in build_output.splitlines():
        line = _strip_ansi( raw_line ).strip()
        match = _PROFILE_LINE.match( line )
        if match is not None:
            lines.append( line )
    return lines


def main():
    parser = argparse.ArgumentParser(
        description='Capture std::init profile diagnostics from the cuppa example.',
    )
    parser.add_argument(
        '--toolchain',
        default='clang24_profiles_2026_08_07_27',
        help='Profiles-capable Clang toolchain name registered in ~/.cuppaconfig',
    )
    parser.add_argument(
        '--example-dir',
        type=Path,
        default=Path( __file__ ).resolve().parents[ 1 ]
        / 'examples'
        / 'profiles'
        / 'std-init-violations',
    )
    parser.add_argument(
        '--cuppa-root',
        type=Path,
        default=Path( __file__ ).resolve().parents[ 1 ],
        help='Cuppa repository root (added to PYTHONPATH)',
    )
    parser.add_argument(
        '--output',
        type=Path,
        help='Optional path to write the raw capture (one diagnostic per line)',
    )
    parser.add_argument(
        '--json',
        type=Path,
        help='Optional path to write deduped message lines as JSON array',
    )
    args = parser.parse_args()

    build_output = _run_build(
        args.example_dir,
        args.toolchain,
        str( args.cuppa_root ),
    )
    profile_lines = _collect_lines( build_output )

    if args.output:
        args.output.write_text( '\n'.join( profile_lines ) + '\n', encoding='utf-8' )
    if args.json:
        args.json.write_text(
            json.dumps( profile_lines, indent=2, sort_keys=True ) + '\n',
            encoding='utf-8',
        )

    print( 'Captured {} std::init diagnostic line(s)'.format( len( profile_lines ) ) )
    for line in profile_lines:
        print( line )

    return 0 if profile_lines else 1


if __name__ == '__main__':
    sys.exit( main() )
