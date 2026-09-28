#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

"""Local pre-push gate: venv preflight, then flake8 / pylint / pytest.

    python -m scripts.local_gate
    python -m scripts.local_gate --unit
    python -m scripts.local_gate --preflight-only

Exit codes: 0 success, 1 a gate step failed, 2 environment broken (preflight).
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


REPO_ROOT = Path( __file__ ).resolve().parents[1]
EXIT_OK = 0
EXIT_STEP_FAILED = 1
EXIT_ENV_BROKEN = 2


def repo_venv_python() -> Path:
    if os.name == 'nt':
        return REPO_ROOT / 'venv' / 'Scripts' / 'python.exe'
    return REPO_ROOT / 'venv' / 'bin' / 'python'


def running_under_repo_venv( executable: str | None = None ) -> bool:
    """True when ``executable`` is the checkout ``venv`` interpreter."""
    venv_python = repo_venv_python()
    if not venv_python.is_file():
        return False
    exe = Path( executable or sys.executable ).resolve()
    try:
        if exe == venv_python.resolve():
            return True
    except OSError:
        return False
    virtual_env = os.environ.get( 'VIRTUAL_ENV' )
    if virtual_env:
        try:
            return Path( virtual_env ).resolve() == ( REPO_ROOT / 'venv' ).resolve()
        except OSError:
            return False
    return False


def maybe_reexec_into_venv( argv: list[str] ) -> None:
    """Replace this process with ``venv/bin/python -m scripts.local_gate …`` if needed."""
    venv_python = repo_venv_python()
    if not venv_python.is_file():
        return
    if running_under_repo_venv():
        return
    os.execv(
            str( venv_python ),
            [ str( venv_python ), '-m', 'scripts.local_gate', *argv[1:] ],
    )


def _fail_env( message: str ) -> int:
    print( 'local_gate: env broken — {}'.format( message ), file=sys.stderr )
    return EXIT_ENV_BROKEN


def preflight( *, need_cxx: bool ) -> int:
    """Return EXIT_OK or EXIT_ENV_BROKEN."""
    venv_python = repo_venv_python()
    if not venv_python.is_file():
        return _fail_env(
                'checkout venv missing at {} — create with:\n'
                '  python3 -m venv venv && source venv/bin/activate && '
                'pip install -r requirements.txt && pip install -e .'
                .format( venv_python )
        )
    if not running_under_repo_venv():
        return _fail_env(
                'not running under {} (got {})'
                .format( venv_python, sys.executable )
        )

    for module in ( 'six', 'SCons', 'cuppa', 'pytest', 'flake8', 'pylint' ):
        try:
            __import__( module )
        except ImportError as error:
            return _fail_env(
                    'in-process import failed for {!r}: {} '
                    '(activate venv and pip install -r requirements.txt && pip install -e .)'
                    .format( module, error )
            )

    smoke = _subprocess_cuppa_smoke()
    if smoke != EXIT_OK:
        return smoke

    if need_cxx:
        cxx = None
        for name in ( 'g++', 'clang++', 'c++', 'cl' ):
            if shutil.which( name ):
                cxx = name
                break
        if cxx is None and os.name == 'nt':
            try:
                from SCons.Tool.MSCommon.vc import get_installed_vcs
                if get_installed_vcs():
                    cxx = 'cl'
            except Exception:
                pass
        if cxx is None:
            return _fail_env(
                    'no C++ compiler (g++/clang++/c++/cl) on PATH; '
                    'needed for integration'
            )

    forced = os.environ.get( 'CUPPA_TEST_TOOLCHAIN', '' ).strip()
    args = os.environ.get( 'CUPPA_TEST_ARGS', '' ).strip()
    if forced or args:
        print(
                'local_gate: note — CUPPA_TEST_TOOLCHAIN={!r} '
                'CUPPA_TEST_ARGS={!r} (CI cell overrides; intentional?)'
                .format( forced, args )
        )

    print( 'local_gate: preflight ok ({})'.format( sys.executable ) )
    return EXIT_OK


def _subprocess_cuppa_smoke() -> int:
    """Catch 'import works in-process but nested ``python -m cuppa`` does not'."""
    with tempfile.TemporaryDirectory( prefix='cuppa-local-gate-' ) as tmp:
        root = Path( tmp )
        ( root / 'sconstruct' ).write_text(
                'import cuppa\n'
                'cuppa.run()\n',
                encoding='utf-8',
        )
        env = os.environ.copy()
        # Prefer the checkout so editable / PYTHONPATH installs stay coherent.
        root_str = str( REPO_ROOT )
        parts = [ root_str ]
        existing = env.get( 'PYTHONPATH' )
        if existing:
            parts.extend(
                    part for part in existing.split( os.pathsep )
                    if part and part != root_str
            )
        env['PYTHONPATH'] = os.pathsep.join( parts )
        cmd = [
                sys.executable, '-m', 'cuppa', '-D', '--offline', '--dump',
                '--toolchains=gcc',
        ]
        try:
            result = subprocess.run(
                    cmd,
                    cwd=str( root ),
                    env=env,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    timeout=120,
                    text=True,
            )
        except subprocess.TimeoutExpired:
            return _fail_env( 'subprocess cuppa smoke timed out' )
        except OSError as error:
            return _fail_env( 'subprocess cuppa smoke failed to start: {}'.format( error ) )

        output = result.stdout or ''
        if result.returncode == 0:
            return EXIT_OK
        # Dump-only may still exit non-zero on some hosts; treat missing modules as env.
        for needle in (
                'No module named',
                'ModuleNotFoundError',
                'ImportError',
        ):
            if needle in output:
                print( output, file=sys.stderr )
                return _fail_env(
                        'subprocess ``python -m cuppa`` failed imports '
                        '(exit {})'.format( result.returncode )
                )
        # Other StopError / configure issues are not "env broken" for preflight —
        # the dump project is intentionally minimal. Log and continue.
        if 'cuppa' in output.lower() or result.returncode != 0:
            # Prefer success path: a configure exception that is not ImportError
            # still proves the nested interpreter loaded cuppa.
            if 'import cuppa' in output or 'cuppa:' in output or 'Cuppa' in output:
                return EXIT_OK
        print( output, file=sys.stderr )
        return _fail_env(
                'subprocess ``python -m cuppa`` smoke failed '
                '(exit {})'.format( result.returncode )
        )


def _run_step( label: str, cmd: list[str] ) -> int:
    print( 'local_gate: {}'.format( label ) )
    result = subprocess.run( cmd, cwd=str( REPO_ROOT ) )
    if result.returncode != 0:
        print(
                'local_gate: {} failed (exit {})'.format( label, result.returncode ),
                file=sys.stderr,
        )
        return EXIT_STEP_FAILED
    return EXIT_OK


def integration_worker_count() -> int:
    """Modest xdist width: enough for ~2–3 min, not ``-n auto``."""
    cpus = os.cpu_count() or 1
    return min( 4, max( 1, cpus // 2 ) )


def xdist_available() -> bool:
    try:
        import xdist  # noqa: F401
    except ImportError:
        return False
    return True


def integration_pytest_cmd( *, serial: bool ) -> list[str]:
    """Build the ``pytest -m integration`` command (parallel by default)."""
    cmd = [ sys.executable, '-m', 'pytest', '-m', 'integration' ]
    if serial or not xdist_available():
        return cmd
    workers = integration_worker_count()
    cmd.extend( [ '-n', str( workers ), '--dist=loadfile' ] )
    return cmd


def run_gate(
        *,
        unit: bool,
        integration: bool,
        lint: bool,
        serial_integration: bool = False,
) -> int:
    if lint:
        code = _run_step( 'flake8 cuppa', [ sys.executable, '-m', 'flake8', 'cuppa' ] )
        if code != EXIT_OK:
            return code
        code = _run_step(
                'pylint -E cuppa',
                [ sys.executable, '-m', 'pylint', '-E', 'cuppa' ],
        )
        if code != EXIT_OK:
            return code
    if unit:
        code = _run_step(
                'pytest -m unit',
                [ sys.executable, '-m', 'pytest', '-m', 'unit' ],
        )
        if code != EXIT_OK:
            return code
    if integration:
        cmd = integration_pytest_cmd( serial=serial_integration )
        label = 'pytest -m integration'
        if '-n' in cmd:
            label = '{} -n {} --dist=loadfile'.format(
                    label, cmd[ cmd.index( '-n' ) + 1 ]
            )
        elif serial_integration:
            label = '{} (serial)'.format( label )
        code = _run_step( label, cmd )
        if code != EXIT_OK:
            return code
    print( 'local_gate: ok' )
    return EXIT_OK


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
            prog='python -m scripts.local_gate',
            description=(
                    'Run the cuppa local pre-push gate (venv preflight, then '
                    'flake8 / pylint / pytest).'
            ),
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
            '--unit',
            action='store_true',
            help='Preflight → lint → unit only',
    )
    mode.add_argument(
            '--integration',
            action='store_true',
            help='Preflight (incl. C++) → integration only',
    )
    mode.add_argument(
            '--preflight-only',
            action='store_true',
            help='Environment checks only',
    )
    mode.add_argument(
            '--skip-integration',
            action='store_true',
            help='Preflight → lint → unit (skip integration)',
    )
    parser.add_argument(
            '--serial-integration',
            action='store_true',
            help=(
                    'Run pytest -m integration without xdist '
                    '(bisect / debug; default is modest -n --dist=loadfile)'
            ),
    )
    parser.add_argument(
            '--no-reexec',
            action='store_true',
            help=argparse.SUPPRESS,
    )
    return parser


def main( argv: list[str] | None = None ) -> int:
    argv = list( sys.argv if argv is None else argv )
    parser = build_parser()
    args = parser.parse_args( argv[1:] )

    if not args.no_reexec:
        maybe_reexec_into_venv( argv )

    need_cxx = bool( args.integration ) or (
            not args.unit
            and not args.preflight_only
            and not args.skip_integration
    )
    # --unit / --skip-integration still lint+unit; default runs integration too.
    if args.integration:
        need_cxx = True

    code = preflight( need_cxx=need_cxx )
    if code != EXIT_OK:
        return code
    if args.preflight_only:
        return EXIT_OK

    serial = bool( args.serial_integration )
    if args.integration:
        return run_gate(
                unit=False,
                integration=True,
                lint=False,
                serial_integration=serial,
        )
    if args.unit or args.skip_integration:
        return run_gate( unit=True, integration=False, lint=True )
    return run_gate(
            unit=True,
            integration=True,
            lint=True,
            serial_integration=serial,
    )


if __name__ == '__main__':
    sys.exit( main() )
