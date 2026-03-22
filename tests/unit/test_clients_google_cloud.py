from __future__ import annotations

from pathlib import Path

import pytest

from clients.config_manager import ConfigManager
from clients.google_cloud import GoogleCloudClientError, get_google_cloud
from clients.secret_manager import GoogleSecretManager, SecretManagerError


def test_get_google_cloud_loads_config_from_master_file(tmp_path: Path):
    (tmp_path / "master_config.yaml").write_text(
        """
google_cloud:
  - name: project_id
    type: value
    value: project-123
  - name: credentials_file
    type: value
    value: /tmp/service-account.json
""",
        encoding="utf-8",
    )

    client = get_google_cloud(str(tmp_path / "master_config.yaml"))
    assert client.config.project_id == "project-123"
    assert client.config.credentials_file == "/tmp/service-account.json"


def test_get_google_cloud_fails_if_section_missing(tmp_path: Path):
    (tmp_path / "master_config.yaml").write_text("global: []\n", encoding="utf-8")
    with pytest.raises(GoogleCloudClientError):
        get_google_cloud(str(tmp_path / "master_config.yaml"))


def test_config_manager_secret_entries_resolve_from_gsm(tmp_path: Path):
    class FakeSecretManager:
        def get_secret(self, _: str) -> str:
            return "smtp-pass"

    (tmp_path / "master_config.yaml").write_text(
        """
notification:
  - name: smtp_password
    type: secret
    secret_ref: gsm://project-1/smtp-password/latest
""",
        encoding="utf-8",
    )

    manager = ConfigManager(
        config_path=tmp_path / "master_config.yaml",
        secret_manager=FakeSecretManager(),  # type: ignore[arg-type]
    )
    cfg = manager.load_service("notification")
    assert cfg["smtp_password"] == "smtp-pass"


def test_google_secret_manager_requires_gsm_uri():
    manager = GoogleSecretManager()
    with pytest.raises(SecretManagerError):
        manager.get_secret("not-gsm-ref")


def test_google_secret_manager_parses_ref_formats():
    manager = GoogleSecretManager()
    assert (
        manager._parse_ref("gsm://project-1/secret-name/latest")
        == "projects/project-1/secrets/secret-name/versions/latest"
    )
    assert (
        manager._parse_ref("gsm://projects/project-1/secrets/secret-name/versions/latest")
        == "projects/project-1/secrets/secret-name/versions/latest"
    )


def test_google_secret_manager_fetches_secret(monkeypatch):
    class FakePayload:
        data = b"secret-value"

    class FakeResponse:
        payload = FakePayload()

    class FakeSMClient:
        def access_secret_version(self, name: str):
            assert name == "projects/project-1/secrets/secret-name/versions/latest"
            return FakeResponse()

    class FakeSecretManagerServiceClient:
        def __init__(self, **kwargs):
            assert "credentials" in kwargs

        def access_secret_version(self, name: str):
            assert name == "projects/project-1/secrets/secret-name/versions/latest"
            return FakeResponse()

    class FakeCredentials:
        pass

    monkeypatch.setenv("GOOGLE_CLOUD_SM_KEYFILE", "/tmp/fake-sm-sa.json")
    monkeypatch.setattr(
        "google.oauth2.service_account.Credentials.from_service_account_file",
        lambda _: FakeCredentials(),
    )
    monkeypatch.setattr(
        "google.cloud.secretmanager.SecretManagerServiceClient",
        FakeSecretManagerServiceClient,
    )

    manager = GoogleSecretManager()
    value = manager.get_secret("gsm://project-1/secret-name/latest")
    assert value == "secret-value"


def test_google_secret_manager_requires_sm_keyfile(monkeypatch):
    monkeypatch.delenv("GOOGLE_CLOUD_SM_KEYFILE", raising=False)
    manager = GoogleSecretManager()
    with pytest.raises(SecretManagerError):
        manager.get_secret("gsm://project-1/secret-name/latest")
