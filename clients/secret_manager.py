from __future__ import annotations

import os
from dataclasses import dataclass

class SecretManagerError(RuntimeError):
    pass


@dataclass
class GoogleSecretManager:
    def get_secret(self, secret_ref: str) -> str:
        resource_name = self._parse_ref(secret_ref)
        try:
            from google.cloud import secretmanager

            kwargs = {}
            credentials_file = os.getenv("GOOGLE_CLOUD_KEYFILE")
            if credentials_file:
                from google.oauth2 import service_account

                kwargs["credentials"] = service_account.Credentials.from_service_account_file(
                    credentials_file
                )
            sm_client = secretmanager.SecretManagerServiceClient(**kwargs)
            response = sm_client.access_secret_version(name=resource_name)
            value = response.payload.data.decode("utf-8").strip()
        except Exception as exc:  # noqa: BLE001
            raise SecretManagerError(f"Failed to read secret from GSM: {secret_ref}") from exc

        if not value:
            raise SecretManagerError(f"Secret reference resolved to empty value: {secret_ref}")
        return value

    @staticmethod
    def _parse_ref(secret_ref: str) -> str:
        # Supported formats:
        # 1) gsm://projects/<project>/secrets/<secret>/versions/<version>
        # 2) gsm://<project>/<secret>/<version>
        if not secret_ref.startswith("gsm://"):
            raise SecretManagerError("Secret reference must start with gsm://")

        path = secret_ref[len("gsm://") :].strip("/")
        if not path:
            raise SecretManagerError("Invalid gsm reference")

        if path.startswith("projects/"):
            parts = path.split("/")
            if len(parts) != 6 or parts[2] != "secrets" or parts[4] != "versions":
                raise SecretManagerError(
                    "Use gsm://projects/<project>/secrets/<secret>/versions/<version>"
                )
            return path

        parts = path.split("/")
        if len(parts) != 3:
            raise SecretManagerError(
                "Use gsm://<project>/<secret>/<version> or full projects/... format"
            )

        project, secret, version = parts
        return f"projects/{project}/secrets/{secret}/versions/{version}"
