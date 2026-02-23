from __future__ import annotations

import os
from dataclasses import dataclass
from dataclasses import field

from apps.api.core.config import Settings
from clients.secret_manager import GoogleSecretManager, SecretManagerError


class SecretResolutionError(RuntimeError):
    pass


@dataclass
class SecretStore:
    manager: GoogleSecretManager = field(default_factory=GoogleSecretManager)

    def read(self, reference: str) -> str:
        try:
            return self.manager.get_secret(reference)
        except SecretManagerError as exc:
            raise SecretResolutionError(
                f"Unable to read secret reference: {reference}"
            ) from exc


@dataclass
class ResolvedSecrets:
    external_api_key: str | None
    google_credentials_json: str | None


def resolve_required_secrets(
    settings: Settings,
    store: SecretStore | None = None,
) -> ResolvedSecrets:
    store = store or SecretStore()

    def _resolve(ref: str | None, env_var: str) -> str | None:
        if not ref:
            return None
        # Local override for tests and controlled local development only.
        override = os.getenv(env_var)
        if override:
            return override
        return store.read(ref)

    return ResolvedSecrets(
        external_api_key=_resolve(settings.external_api_key_ref, "EXTERNAL_API_KEY"),
        google_credentials_json=_resolve(
            settings.google_credentials_ref, "GOOGLE_CREDENTIALS_JSON"
        ),
    )
