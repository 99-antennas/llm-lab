#!/usr/bin/env python3
"""Send email and/or SMS alerts when agent approval is required."""

from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

# Allow running this file directly (e.g., pytest subprocess / IDE run) while
# still importing repo packages like `clients`.
REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from clients.gmail_client import GmailClientError, get_gmail_client  # noqa: E402
from clients.twilio_client import TwilioClientError, get_twilio_client  # noqa: E402


def _build_message(reason: str, command: str, workspace: str) -> str:
    timestamp = datetime.now(timezone.utc).isoformat()
    return (
        "Codex needs your approval.\n"
        f"Reason: {reason}\n"
        f"Command: {command}\n"
        f"Workspace: {workspace}\n"
        f"Time (UTC): {timestamp}"
    )


def send_email(subject: str, body: str, dry_run: bool) -> None:
    client = get_gmail_client()
    to_email = getattr(client, "default_to_email")
    client.send_email(to_email=to_email, subject=subject, body=body, dry_run=dry_run)


def send_sms(body: str, dry_run: bool) -> None:
    client = get_twilio_client()
    client.send_sms(body=body, dry_run=dry_run)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reason", required=True, help="Short reason why approval is needed")
    parser.add_argument("--command", required=True, help="Command requiring approval")
    parser.add_argument("--workspace", required=True, help="Absolute workspace path")
    parser.add_argument(
        "--channel",
        choices=["email", "sms", "both"],
        default=os.getenv("APPROVAL_NOTIFY_CHANNEL", "email"),
        help="Delivery channel",
    )
    parser.add_argument("--dry-run", action="store_true", help="Validate config without sending")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    subject = "Codex approval needed"
    body = _build_message(args.reason, args.command, args.workspace)
    try:
        if args.channel in ("email", "both"):
            send_email(subject, body, args.dry_run)
        if args.channel in ("sms", "both"):
            send_sms(body, args.dry_run)
    except (GmailClientError, TwilioClientError, RuntimeError) as exc:
        print(f"Alert failed: {exc}", file=sys.stderr)
        return 1

    print(f"Alert sent via {args.channel}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
