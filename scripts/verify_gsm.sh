#!/usr/bin/env bash
set -euo pipefail

CONFIG_FILE="${1:-config/master_config.yaml}"

if [[ ! -f "$CONFIG_FILE" ]]; then
  echo "ERROR: Config file not found: $CONFIG_FILE" >&2
  exit 1
fi

if ! command -v uv >/dev/null 2>&1; then
  echo "ERROR: uv is required but not found in PATH." >&2
  exit 1
fi

if [[ -z "${GOOGLE_CLOUD_PROJECT:-}" ]]; then
  echo "ERROR: GOOGLE_CLOUD_PROJECT is not set." >&2
  exit 1
fi

if [[ -z "${GOOGLE_APPLICATION_CREDENTIALS:-}" ]]; then
  echo "ERROR: GOOGLE_APPLICATION_CREDENTIALS is not set." >&2
  exit 1
fi

if [[ ! -f "$GOOGLE_APPLICATION_CREDENTIALS" ]]; then
  echo "ERROR: GOOGLE_APPLICATION_CREDENTIALS file does not exist: $GOOGLE_APPLICATION_CREDENTIALS" >&2
  exit 1
fi

echo "Verifying Google Secret Manager access using: $CONFIG_FILE"

UV_CACHE_DIR="${UV_CACHE_DIR:-$(pwd)/.uv-cache}" uv run python - "$CONFIG_FILE" <<'PY'
from __future__ import annotations

import sys
from pathlib import Path

import yaml

from clients.secret_manager import GoogleSecretManager


def collect_secret_refs(node):
    refs = []
    if isinstance(node, dict):
        if "type" in node and node.get("type") == "secret" and "secret_ref" in node:
            refs.append(str(node["secret_ref"]))
        for value in node.values():
            refs.extend(collect_secret_refs(value))
    elif isinstance(node, list):
        for item in node:
            refs.extend(collect_secret_refs(item))
    return refs


config_path = Path(sys.argv[1])
raw = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
refs = sorted(set(collect_secret_refs(raw)))

if not refs:
    print("No secret_ref entries found. Nothing to verify.")
    raise SystemExit(0)

manager = GoogleSecretManager()
errors = 0

for ref in refs:
    try:
        value = manager.get_secret(ref)
        print(f"OK   {ref} (len={len(value)})")
    except Exception as exc:  # noqa: BLE001
        errors += 1
        print(f"FAIL {ref} -> {exc}")

if errors:
    raise SystemExit(1)

print("All GSM secret references resolved successfully.")
PY
