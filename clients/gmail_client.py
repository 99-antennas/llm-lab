from __future__ import annotations

import base64
import os
from dataclasses import dataclass
from email.message import EmailMessage

from clients.config_manager import ConfigManager, ConfigManagerError


GMAIL_SEND_SCOPE = "https://www.googleapis.com/auth/gmail.send"


class GmailClientError(RuntimeError):
    pass


@dataclass
class GmailConfig:
    sender_email: str
    credentials_file: str


class GmailClient:
    def __init__(self, config: GmailConfig):
        self.config = config

    def send_email(self, to_email: str, subject: str, body: str, dry_run: bool = False) -> None:
        if dry_run:
            print(f"[dry-run] email -> {to_email} via Gmail API")
            return

        try:
            from google.oauth2 import service_account
            from googleapiclient.discovery import build
        except Exception as exc:  # noqa: BLE001
            raise GmailClientError("Google API dependencies are required for Gmail notifications") from exc

        credentials = service_account.Credentials.from_service_account_file(
            self.config.credentials_file,
            scopes=[GMAIL_SEND_SCOPE],
            subject=self.config.sender_email,
        )
        service = build("gmail", "v1", credentials=credentials, cache_discovery=False)

        message = EmailMessage()
        message["To"] = to_email
        message["From"] = self.config.sender_email
        message["Subject"] = subject
        message.set_content(body)

        raw = base64.urlsafe_b64encode(message.as_bytes()).decode("utf-8")
        service.users().messages().send(userId="me", body={"raw": raw}).execute()


def _get_env(name: str) -> str | None:
    value = os.getenv(name)
    return value.strip() if value else None


def get_gmail_client() -> GmailClient:
    sender_email = _get_env("APPROVAL_EMAIL_FROM")
    to_email = _get_env("APPROVAL_EMAIL_TO")
    credentials_file = _get_env("GOOGLE_CLOUD_KEYFILE") or _get_env("GOOGLE_APPLICATION_CREDENTIALS")

    if not sender_email or not to_email:
        try:
            profile_cfg = ConfigManager().load_service("profile")
            sender_email = sender_email or profile_cfg.get("email_from")
            to_email = profile_cfg.get("email_to")
        except ConfigManagerError:
            pass

    if not to_email:
        to_email = _get_env("SUPPORT_EMAIL")

    if not credentials_file:
        try:
            gcfg = ConfigManager().load_service("google_cloud")
            credentials_file = gcfg.get("credentials_file")
        except ConfigManagerError:
            pass

    missing = []
    if not sender_email:
        missing.append("profile.email_from")
    if not to_email:
        missing.append("profile.email_to")
    if not credentials_file:
        missing.append("GOOGLE_CLOUD_KEYFILE")

    if missing:
        raise GmailClientError(f"Missing Gmail config values: {', '.join(missing)}")

    client = GmailClient(GmailConfig(sender_email=sender_email, credentials_file=credentials_file))
    setattr(client, "default_to_email", to_email)
    return client
