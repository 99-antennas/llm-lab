from __future__ import annotations

import json
import os
import traceback
from pathlib import Path

from clients.config_manager import ConfigManager
from clients.gmail_client import get_gmail_client
from clients.twilio_client import TwilioSecretsModel, get_twilio_client


def _require_keyfile() -> None:
    keyfile = os.getenv("GOOGLE_CLOUD_SM_KEYFILE")
    if not keyfile:
        raise RuntimeError("GOOGLE_CLOUD_SM_KEYFILE is not set")
    if not Path(keyfile).expanduser().exists():
        raise RuntimeError(f"GOOGLE_CLOUD_SM_KEYFILE does not exist: {keyfile}")


def _check_notification_config() -> dict[str, object]:
    manager = ConfigManager(config_path=Path("config/master_config.yaml"))
    profile = manager.load_service("profile")
    cfg = manager.load_service("notification")

    email_from = profile.get("email_from")
    email_to = profile.get("email_to")
    to_number = profile.get("to_number")
    twilio_credentials = cfg.get("twilio_credentials")

    if not email_from:
        raise RuntimeError("profile.email_from is missing")
    if not email_to:
        raise RuntimeError("profile.email_to is missing")
    if not to_number:
        raise RuntimeError("profile.to_number is missing")
    if not twilio_credentials:
        raise RuntimeError("notification.twilio_credentials is missing or unresolved")

    TwilioSecretsModel.model_validate(json.loads(str(twilio_credentials)))
    return {"email_from": email_from, "email_to": email_to, "to_number": to_number}


def run() -> None:
    _require_keyfile()
    profile = _check_notification_config()

    gmail = get_gmail_client()
    gmail.send_email(
        to_email=str(profile["email_to"]),
        subject="LLM-LAB notification setup check",
        body="dry-run email validation",
        dry_run=True,
    )

    twilio = get_twilio_client()
    twilio.send_sms(body="dry-run sms validation", dry_run=True)

    print("PASS: notification config and secret resolution checks completed.")


if __name__ == "__main__":
    try:
        run()
    except Exception as exc:  # noqa: BLE001
        print(f"FAIL: {exc}")
        if exc.__cause__ is not None:
            print(f"CAUSE: {exc.__cause__}")
        traceback.print_exc()
        raise SystemExit(1) from exc
