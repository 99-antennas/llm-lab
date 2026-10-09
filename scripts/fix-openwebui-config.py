#!/usr/bin/env python3
# Adds Hermes to Open WebUI without replacing llama.cpp or Pipelines connections.
# The Ollama connection shown in Open WebUI is configured separately.
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.request import Request, urlopen

HERMES_URL = "http://hermes:8642/v1"


def add_hermes_connection(config: dict[str, Any], api_key: str) -> None:
    if not api_key.strip():
        raise ValueError("Hermes API key must not be empty")
    openai = config.setdefault("openai", {})
    urls = openai.setdefault("api_base_urls", [])
    keys = openai.setdefault("api_keys", [])
    if not isinstance(urls, list) or not isinstance(keys, list) or len(urls) != len(keys):
        raise ValueError("Open WebUI connection URLs and keys must be matching lists")
    matches = [i for i, url in enumerate(urls) if url.rstrip("/") == HERMES_URL]
    if matches:
        for index in matches:
            keys[index] = api_key
    else:
        urls.append(HERMES_URL)
        keys.append(api_key)


def update_database(path: Path, api_key: str) -> Path:
    if not path.is_file():
        raise FileNotFoundError(f"Open WebUI database does not exist: {path}")
    with sqlite3.connect(path) as conn:
        row = conn.execute("SELECT id, data FROM config LIMIT 1").fetchone()
        if row is None:
            raise RuntimeError("Open WebUI has no saved config; finish its initial setup first")
        config = json.loads(row[1])
        add_hermes_connection(config, api_key)
        stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
        backup = path.with_name(f"{path.name}.before-hermes-{stamp}")
        with sqlite3.connect(backup) as destination:
            conn.backup(destination)
        backup.chmod(0o600)
        conn.execute("UPDATE config SET data = ? WHERE id = ?", (json.dumps(config), row[0]))
    return backup


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--container", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.container:
        api_key = sys.stdin.read().strip()
        if not api_key:
            raise ValueError("Hermes API key must be supplied on stdin")
        request = Request(
            f"{HERMES_URL}/models", headers={"Authorization": f"Bearer {api_key}"}
        )
        with urlopen(request, timeout=15) as response:
            models = json.load(response)
        if not models.get("data"):
            raise RuntimeError("Hermes did not advertise any models")
        backup = update_database(Path("/app/backend/data/webui.db"), api_key)
        print(f"SUCCESS: Added Hermes connection at {HERMES_URL}. Backup: {backup}")
        return

    from dotenv import load_dotenv

    from clients.secret_manager import GoogleSecretManager

    root = Path(__file__).resolve().parent
    load_dotenv(root / ".env")
    reference = os.environ.get("HERMES_API_KEY_REF")
    if not reference:
        raise RuntimeError("Set HERMES_API_KEY_REF in .env before configuring Open WebUI")
    api_key = GoogleSecretManager().get_secret(reference)
    subprocess.run(
        [
            "docker", "compose", "exec", "-T", "open-webui", "python",
            "-c", Path(__file__).read_text(), "--container",
        ],
        input=api_key,
        text=True,
        cwd=root,
        check=True,
    )
    subprocess.run(["docker", "compose", "restart", "open-webui"], cwd=root, check=True)


if __name__ == "__main__":
    main()
