import pytest

from tests.helpers.cuppa_runner import assert_success, find_final_binaries, run_cuppa
from tests.helpers.project import copy_dummy_project, write_sconstruct, write_sconscript


pytestmark = pytest.mark.integration


def test_build_profile_custom(tmp_path):
    project = copy_dummy_project(tmp_path)
    write_sconstruct(
        project,
        body=(
            "import cuppa\n"
            "\n"
            "class define_profile(object):\n"
            "    @classmethod\n"
            "    def add_options(cls, add_option):\n"
            "        pass\n"
            "\n"
            "    @classmethod\n"
            "    def add_to_env(cls, env, add_profile):\n"
            "        add_profile('define_profile', cls.create)\n"
            "\n"
            "    @classmethod\n"
            "    def create(cls, env):\n"
            "        return cls()\n"
            "\n"
            "    def name(self):\n"
            "        return 'define_profile'\n"
            "\n"
            "    def __call__(self, env, toolchain, variant):\n"
            "        env.AppendUnique(CCFLAGS=['-DCUPPA_PROFILE_ON=1'])\n"
            "\n"
            "cuppa.run(\n"
            "    default_variants=['dbg'],\n"
            "    profiles=[define_profile],\n"
            ")\n"
        ),
    )
    write_sconscript(
        project,
        "Import('env')\n"
        "env.BuildProfile('define_profile')\n"
        "env.AppendUnique(CPPPATH=['#/include'])\n"
        "env.Build('main', 'apps/main.cpp')\n",
    )
    result = run_cuppa(project, "--dbg")
    assert_success(result)
    assert find_final_binaries(project, "main")
