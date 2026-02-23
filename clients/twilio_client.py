from __future__ import annotations

import base64
import json
import os
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass

from clients.config_manager import ConfigManager, ConfigManagerError
from pydantic import BaseModel, ValidationError


class TwilioClientError(RuntimeError):
    pass


class TwilioSecretsModel(BaseModel):
    account_sid: str
    auth_token: str
    from_number: str
    to_number: str | None = None


@dataclass
class TwilioConfig:
    account_sid: str
    auth_token: str
    from_number: str
    to_number: str


class TwilioClient:
    def __init__(self, config: TwilioConfig):
        self.config = config

    def send_sms(self, body: str, dry_run: bool = False) -> None:
        if dry_run:
            print(f"[dry-run] sms -> {self.config.to_number}")
            return

        token = base64.b64encode(
            f"{self.config.account_sid}:{self.config.auth_token}".encode("utf-8")
        ).decode("ascii")
        url = f"https://api.twilio.com/2010-04-01/Accounts/{self.config.account_sid}/Messages.json"
        payload = urllib.parse.urlencode(
            {
                "To": self.config.to_number,
                "From": self.config.from_number,
                "Body": body,
            }
        ).encode("utf-8")
        req = urllib.request.Request(url, data=payload, method="POST")
        req.add_header("Authorization", f"Basic {token}")
        req.add_header("Content-Type", "application/x-www-form-urlencoded")

        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                status = getattr(resp, "status", None)
                if status and status >= 300:
                    raise TwilioClientError(f"Twilio returned HTTP {status}")
                data = json.loads(resp.read().decode("utf-8"))
                if not data.get("sid"):
                    raise TwilioClientError("Twilio response missing message SID")
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise TwilioClientError(f"Twilio HTTP error {exc.code}: {detail}") from exc


def _get_env(name: str) -> str | None:
    value = os.getenv(name)
    return value.strip() if value else None


def get_twilio_client() -> TwilioClient:
    model_json = _get_env("TWILIO_CREDENTIALS")

    if not model_json:
        try:
            cfg = ConfigManager().load_service("notification")
            model_json = cfg.get("twilio_credentials")
        except ConfigManagerError:
            model_json = None

    if not model_json:
        raise TwilioClientError("Missing Twilio model secret: twilio_credentials")

    try:
        model = TwilioSecretsModel.model_validate(json.loads(model_json))
    except (json.JSONDecodeError, ValidationError) as exc:
        raise TwilioClientError("Invalid twilio_credentials JSON payload") from exc

    to_number = _get_env("APPROVAL_TO_NUMBER")
    if not to_number:
        try:
            profile_cfg = ConfigManager().load_service("profile")
            to_number = profile_cfg.get("to_number")
        except ConfigManagerError:
            to_number = None
    if not to_number:
        to_number = model.to_number

    if not to_number:
        raise TwilioClientError("Missing destination number: set profile.to_number or APPROVAL_TO_NUMBER")

    return TwilioClient(
        TwilioConfig(
            account_sid=model.account_sid,
            auth_token=model.auth_token,
            from_number=model.from_number,
            to_number=to_number,
        )
    )
