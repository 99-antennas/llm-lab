import pytest

from apps.api.core.config import Settings
from apps.api.core.secrets import SecretResolutionError, SecretStore, resolve_required_secrets
from clients.secret_manager import SecretManagerError


def test_secret_store_requires_gsm_reference():
    store = SecretStore()
    with pytest.raises(SecretResolutionError):
        store.read("plain-text-secret")


def test_resolve_required_secrets_with_env_override(monkeypatch):
    monkeypatch.setenv("EXTERNAL_API_KEY", "from-env")
    settings = Settings(EXTERNAL_API_KEY_REF="gsm://project-1/external-api-key/latest")
    resolved = resolve_required_secrets(settings)
    assert resolved.external_api_key == "from-env"


def test_secret_store_reads_via_gsm(monkeypatch):
    def fake_get_secret(self, _: str):
        return "secret-value"

    monkeypatch.setattr("clients.secret_manager.GoogleSecretManager.get_secret", fake_get_secret)
    store = SecretStore()
    assert store.read("gsm://project-1/external-api-key/latest") == "secret-value"


def test_secret_store_raises_when_secret_missing(monkeypatch):
    def fake_get_secret(self, _: str):
        raise SecretManagerError("missing")

    monkeypatch.setattr("clients.secret_manager.GoogleSecretManager.get_secret", fake_get_secret)
    store = SecretStore()
    with pytest.raises(SecretResolutionError):
        store.read("gsm://project-1/external-api-key/latest")
