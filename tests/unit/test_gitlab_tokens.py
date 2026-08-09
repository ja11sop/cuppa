#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

import pytest

from cuppa.package_managers.gitlab import get_header_token, registry_auth_headers


pytestmark = pytest.mark.unit


def test_get_header_token_custom_env(monkeypatch):
    monkeypatch.delenv("GITLAB_REGISTRY_TOKEN", raising=False)
    monkeypatch.delenv("CI_JOB_TOKEN", raising=False)
    monkeypatch.setenv("MY_TOKEN", "custom-secret")
    assert get_header_token("MY_TOKEN") == "PRIVATE-TOKEN: custom-secret"


def test_get_header_token_registry_before_ci(monkeypatch):
    monkeypatch.setenv("GITLAB_REGISTRY_TOKEN", "reg")
    monkeypatch.setenv("CI_JOB_TOKEN", "ci")
    assert get_header_token() == "PRIVATE-TOKEN: reg"


def test_get_header_token_ci_job_fallback(monkeypatch):
    monkeypatch.delenv("GITLAB_REGISTRY_TOKEN", raising=False)
    monkeypatch.setenv("CI_JOB_TOKEN", "ci-job")
    assert get_header_token() == "JOB-TOKEN: ci-job"


def test_get_header_token_missing(monkeypatch):
    monkeypatch.delenv("GITLAB_REGISTRY_TOKEN", raising=False)
    monkeypatch.delenv("CI_JOB_TOKEN", raising=False)
    assert get_header_token() == "None"


def test_registry_auth_headers_maps_private_token(monkeypatch):
    monkeypatch.delenv("CI_JOB_TOKEN", raising=False)
    monkeypatch.setenv("GITLAB_REGISTRY_TOKEN", "reg-secret")
    assert registry_auth_headers() == { "PRIVATE-TOKEN": "reg-secret" }


def test_registry_auth_headers_missing(monkeypatch):
    monkeypatch.delenv("GITLAB_REGISTRY_TOKEN", raising=False)
    monkeypatch.delenv("CI_JOB_TOKEN", raising=False)
    assert registry_auth_headers() == {}
