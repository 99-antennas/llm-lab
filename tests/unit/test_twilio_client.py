from __future__ import annotations

import json
import os

import pytest

from clients.twilio_client import TwilioClientError, get_twilio_client


def test_get_twilio_client_from_env_json_model():
    os.environ["TWILIO_CREDENTIALS"] = json.dumps(
        {
            "account_sid": "AC123",
            "auth_token": "token",
            "from_number": "+15550001111",
            "to_number": "+15550002222",
        }
    )
    client = get_twilio_client()
    assert client.config.account_sid == "AC123"


def test_get_twilio_client_invalid_json_raises(monkeypatch):
    monkeypatch.setenv("TWILIO_CREDENTIALS", "not-json")
    with pytest.raises(TwilioClientError):
        get_twilio_client()


def test_twilio_send_sms_dry_run(monkeypatch, capsys):
    monkeypatch.setenv(
        "TWILIO_CREDENTIALS",
        json.dumps(
            {
                "account_sid": "AC123",
                "auth_token": "token",
                "from_number": "+15550001111",
                "to_number": "+15550002222",
            }
        ),
    )
    client = get_twilio_client()
    client.send_sms("hello", dry_run=True)
    out = capsys.readouterr().out
    assert "[dry-run] sms -> +15550002222" in out
