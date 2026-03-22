from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


def test_notification_dry_run_email_uses_gmail_config():
    script = Path("skills/notification/scripts/send_notification.py")

    env = os.environ.copy()
    env.update(
        {
            "APPROVAL_NOTIFY_CHANNEL": "email",
            "APPROVAL_EMAIL_TO": "kas@99antennas.com",
            "APPROVAL_EMAIL_FROM": "alerts@99antennas.com",
            "GOOGLE_APPLICATION_CREDENTIALS": "/tmp/fake-sa.json",
        }
    )

    result = subprocess.run(
        [
            sys.executable,
            str(script),
            "--reason",
            "test",
            "--command",
            "echo test",
            "--workspace",
            "/Users/kas/dev/llm-lab",
            "--dry-run",
        ],
        check=False,
        capture_output=True,
        text=True,
        env=env,
    )

    assert result.returncode == 0, result.stderr
    assert "[dry-run] email -> kas@99antennas.com via Gmail API" in result.stdout
    assert "Alert sent via email" in result.stdout


def test_notification_dry_run_sms_uses_twilio_model():
    script = Path("skills/notification/scripts/send_notification.py")

    env = os.environ.copy()
    env.update(
        {
            "APPROVAL_NOTIFY_CHANNEL": "sms",
            "APPROVAL_TO_NUMBER": "+15550002222",
            "TWILIO_CREDENTIALS": json.dumps(
                {
                    "account_sid": "AC123",
                    "auth_token": "token",
                    "from_number": "+15550001111",
                    "to_number": "+15550002222",
                }
            ),
        }
    )

    result = subprocess.run(
        [
            sys.executable,
            str(script),
            "--reason",
            "test",
            "--command",
            "echo test",
            "--workspace",
            "/Users/kas/dev/llm-lab",
            "--dry-run",
            "--channel",
            "sms",
        ],
        check=False,
        capture_output=True,
        text=True,
        env=env,
    )

    assert result.returncode == 0, result.stderr
    assert "[dry-run] sms -> +15550002222" in result.stdout
    assert "Alert sent via sms" in result.stdout
