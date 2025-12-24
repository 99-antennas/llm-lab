#!/usr/bin/env bash
set -e

if ! command -v docker >/dev/null 2>&1; then
  echo "Docker is not installed."
  exit 1
fi

if docker ps -a --format '{{.Names}}' | grep -q '^open-webui$'; then
  echo "Stopping Open WebUI container..."
  docker stop open-webui >/dev/null
  echo "Open WebUI stopped."
else
  echo "Open WebUI container not found. Nothing to stop."
fi
