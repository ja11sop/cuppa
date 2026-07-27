import pytest

from cuppa import log
from cuppa.__main__ import MaskSecrets


pytestmark = pytest.mark.unit


def test_register_and_mask_secrets():
    log.register_secret("super-secret-token", "XXXX")
    assert log.mask_secrets("using super-secret-token here") == "using XXXX here"
    log.unregister_secret("super-secret-token")
    assert log.mask_secrets("using super-secret-token here") == "using super-secret-token here"


def test_mask_secrets_wrapper_masks_token_env(monkeypatch):
    monkeypatch.setenv("MY_CI_TOKEN", "abc123xyz")
    masker = MaskSecrets()
    assert "abc123xyz" not in masker.mask("token=abc123xyz")
    assert "MY_CI_TOKEN" in masker.mask("token=abc123xyz")
