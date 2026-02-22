from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass

from apps.api.core.config import Settings


class SecretResolutionError(RuntimeError):
    pass


@dataclass
class SecretStore:
    op_binary: str = "op"

    def read(self, reference: str) -> str:
        if not reference.startswith("op://"):
            raise SecretResolutionError(
                "Secret reference must use 1Password URI format (op://...)."
            )
        try:
            result = subprocess.run(
                [self.op_binary, "read", reference],
                check=True,
                capture_output=True,
                text=True,
            )
        except subprocess.CalledProcessError as exc:
            raise SecretResolutionError(
                f"Unable to read secret reference: {reference}"
            ) from exc
        return result.stdout.strip()


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
