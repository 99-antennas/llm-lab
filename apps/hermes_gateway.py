"""Start the native Hermes gateway with API and optional Slack credentials from GSM."""

from __future__ import annotations

import json
import os
import sys

from clients.secret_manager import GoogleSecretManager


def resolve_gateway_secrets() -> dict[str, str]:
    reference = os.environ.get("HERMES_API_KEY_REF")
    if not reference:
        raise RuntimeError("HERMES_API_KEY_REF is required to enable the Hermes API")
    secrets = {"API_SERVER_KEY": GoogleSecretManager().get_secret(reference)}
    slack_reference = os.environ.get("HERMES_SLACK_CREDENTIALS_REF")
    if slack_reference:
        credentials = json.loads(GoogleSecretManager().get_secret(slack_reference))
        for name in ("SLACK_BOT_TOKEN", "SLACK_APP_TOKEN"):
            value = credentials.get(name)
            if not isinstance(value, str) or not value.strip():
                raise RuntimeError(f"Slack credentials secret is missing {name}")
            secrets[name] = value
    return secrets


def main() -> None:
    os.environ.update(resolve_gateway_secrets())
    os.execvp("hermes", ["hermes", *sys.argv[1:]])


if __name__ == "__main__":
    main()
