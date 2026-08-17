import textwrap

import pytest

from tests.helpers.cuppa_runner import assert_success, run_cuppa
from tests.helpers.project import copy_dummy_project, write_sconstruct, write_sconscript


pytestmark = pytest.mark.integration


def _write_env_check_test(project, env_var, expected):
    tests_dir = project / "tests"
    tests_dir.mkdir(exist_ok=True)
    (tests_dir / "env_check_test.cpp").write_text(
        textwrap.dedent(
            """
            #include <cstdlib>
            #include <cstring>

            int main()
            {{
                const char* Value = std::getenv("{env_var}");
                if( !Value ) return 1;
                return std::strcmp( Value, "{expected}" ) == 0 ? 0 : 2;
            }}
            """
        ).format(env_var=env_var, expected=expected),
        encoding="utf-8",
    )


def test_run_callable_export_dict_reaches_test(tmp_path):
    project = copy_dummy_project(tmp_path)
    _write_env_check_test(project, "CUPPA_EXPORT_DICT", "dict-value")
    write_sconstruct(project)
    write_sconscript(
        project,
        textwrap.dedent(
            """
            import os
            Import('env')

            def export_test_var(target, source, env):
                return {'CUPPA_EXPORT_DICT': 'dict-value'}

            env.Run([], command=export_test_var)
            env.BuildTest('env_check_test', 'tests/env_check_test.cpp')
            """
        ),
    )
    result = run_cuppa(project, "--dbg", "--test")
    assert_success(result)


def test_inherit_process_env_per_run(tmp_path, monkeypatch):
    project = copy_dummy_project(tmp_path)
    _write_env_check_test(project, "CUPPA_INHERIT_ONLY", "inherit-value")
    write_sconstruct(project)
    write_sconscript(
        project,
        textwrap.dedent(
            """
            import os
            Import('env')

            def set_os_environ_only(target, source, env):
                os.environ['CUPPA_INHERIT_ONLY'] = 'inherit-value'

            env.Run([], command=set_os_environ_only)
            env.BuildTest(
                'env_check_test',
                'tests/env_check_test.cpp',
                inherit_process_env=True,
            )
            """
        ),
    )
    monkeypatch.delenv("CUPPA_INHERIT_ONLY", raising=False)
    result = run_cuppa(project, "--dbg", "--test")
    assert_success(result)


def test_inherit_process_env_cli_flag(tmp_path, monkeypatch):
    project = copy_dummy_project(tmp_path)
    _write_env_check_test(project, "CUPPA_INHERIT_CLI", "cli-value")
    write_sconstruct(project)
    write_sconscript(
        project,
        textwrap.dedent(
            """
            import os
            Import('env')

            def set_os_environ_only(target, source, env):
                os.environ['CUPPA_INHERIT_CLI'] = 'cli-value'

            env.Run([], command=set_os_environ_only)
            env.BuildTest('env_check_test', 'tests/env_check_test.cpp')
            """
        ),
    )
    monkeypatch.delenv("CUPPA_INHERIT_CLI", raising=False)
    result = run_cuppa(project, "--dbg", "--test", "--inherit-process-env")
    assert_success(result)
