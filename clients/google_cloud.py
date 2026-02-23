from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from pydantic import BaseModel

from clients.config_manager import ConfigManager, ConfigManagerError


class GoogleCloudClientError(RuntimeError):
    pass


class GoogleCloudConfig(BaseModel):
    project_id: str
    credentials_file: str | None = None


@dataclass
class GoogleCloudClients:
    config: GoogleCloudConfig

    def _credentials(self):
        if self.config.credentials_file:
            try:
                from google.oauth2 import service_account
            except Exception as exc:  # noqa: BLE001
                raise GoogleCloudClientError("google-auth is required") from exc
            return service_account.Credentials.from_service_account_file(
                self.config.credentials_file
            )
        return None

    def get_secret_manager_client(self):
        try:
            from google.cloud import secretmanager
        except Exception as exc:  # noqa: BLE001
            raise GoogleCloudClientError("google-cloud-secret-manager is required") from exc
        creds = self._credentials()
        if creds:
            return secretmanager.SecretManagerServiceClient(credentials=creds)
        return secretmanager.SecretManagerServiceClient()

    def get_storage_client(self):
        try:
            from google.cloud import storage
        except Exception as exc:  # noqa: BLE001
            raise GoogleCloudClientError("google-cloud-storage is required") from exc
        creds = self._credentials()
        if creds:
            return storage.Client(project=self.config.project_id, credentials=creds)
        return storage.Client(project=self.config.project_id)

    def get_gmail_service(self):
        return self._build_workspace_service("gmail", "v1")

    def get_drive_service(self):
        return self._build_workspace_service("drive", "v3")

    def _build_workspace_service(self, service_name: str, version: str):
        try:
            from googleapiclient.discovery import build
        except Exception as exc:  # noqa: BLE001
            raise GoogleCloudClientError("google-api-python-client is required") from exc

        creds = self._credentials()
        if not creds:
            raise GoogleCloudClientError(
                "Workspace service clients require credentials_file configuration"
            )
        return build(service_name, version, credentials=creds, cache_discovery=False)


def get_google_cloud(config_path: str = "config/master_config.yaml") -> GoogleCloudClients:
    manager = ConfigManager(config_path=Path(config_path))
    try:
        config_data = manager.load_service("google_cloud")
    except ConfigManagerError as exc:
        raise GoogleCloudClientError("Failed to load google_cloud config") from exc

    try:
        config = GoogleCloudConfig.model_validate(config_data)
    except Exception as exc:  # noqa: BLE001
        raise GoogleCloudClientError("Invalid google_cloud client config") from exc

    if not config.project_id:
        raise GoogleCloudClientError("google_cloud.project_id is required")

    return GoogleCloudClients(config=config)
