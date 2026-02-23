from __future__ import annotations

import os
import traceback
from pathlib import Path

import pytest

from clients.config_manager import ConfigManager


def _run_live_check() -> None:
    credentials_file = os.getenv("GOOGLE_CLOUD_KEYFILE")
    if not credentials_file or not Path(credentials_file).expanduser().exists():
        raise RuntimeError("set GOOGLE_CLOUD_KEYFILE to an existing service account key file")

    manager = ConfigManager(config_path=Path("config/master_config.yaml"))
    values = manager.load_service("test")

    assert values["test_password"] == "test-password"


def test_live_gsm_reads_test_password():
    if os.getenv("RUN_LIVE_GSM_TESTS", "").lower() not in {"1", "true", "yes"}:
        pytest.skip("set RUN_LIVE_GSM_TESTS=1 to run live GSM secret test")
    _run_live_check()


if __name__ == "__main__":
    try:
        _run_live_check()
        print("PASS: test.test_password resolved from GSM and matched expected value.")
    except Exception as exc:  # noqa: BLE001
        print(f"FAIL: {exc}")
        if exc.__cause__ is not None:
            print(f"CAUSE: {exc.__cause__}")
        traceback.print_exc()
        raise SystemExit(1) from exc
