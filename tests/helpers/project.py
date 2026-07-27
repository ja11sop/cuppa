import logging
import os
import shutil
from pathlib import Path

import pytest

logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[2]
DUMMY_PROJECT = REPO_ROOT / "tests" / "fixtures" / "dummy_project"


def copy_dummy_project(tmp_path):
    dest = tmp_path / "dummy_project"
    shutil.copytree(DUMMY_PROJECT, dest)
    return dest


def write_sconstruct(project_dir, body=None, **run_kwargs):
    if body is None:
        options = ""
        if run_kwargs:
            parts = []
            for key, value in run_kwargs.items():
                parts.append("{}={!r}".format(key, value))
            options = ",\n    ".join(parts)
            body = "import cuppa\n\ncuppa.run(\n    {}\n)\n".format(options)
        else:
            body = "import cuppa\n\ncuppa.run(default_variants=['dbg'])\n"
    path = Path(project_dir) / "sconstruct"
    path.write_text(body)
    return path


def write_sconscript(project_dir, body):
    path = Path(project_dir) / "sconscript"
    path.write_text(body)
    return path
