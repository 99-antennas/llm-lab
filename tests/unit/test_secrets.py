import subprocess

import pytest

from apps.api.core.config import Settings
from apps.api.core.secrets import SecretResolutionError, SecretStore, resolve_required_secrets


def test_secret_store_requires_op_reference():
    store = SecretStore()
    with pytest.raises(SecretResolutionError):
        store.read("plain-text-secret")


def test_resolve_required_secrets_with_env_override(monkeypatch):
    monkeypatch.setenv("EXTERNAL_API_KEY", "from-env")
    settings = Settings(EXTERNAL_API_KEY_REF="op://vault/item/field")
    resolved = resolve_required_secrets(settings)
    assert resolved.external_api_key == "from-env"


def test_secret_store_reads_via_op(monkeypatch):
    def fake_run(*args, **kwargs):
        class Result:
            stdout = "secret-value\n"

        return Result()

    monkeypatch.setattr(subprocess, "run", fake_run)
    store = SecretStore()
    assert store.read("op://Vault/Item/field") == "secret-value"
