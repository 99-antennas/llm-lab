#!/usr/bin/env bash
set -e

LAB_HOST="llm-lab"

if ! command -v docker >/dev/null 2>&1; then
  echo "Docker is not installed. Please install Docker Desktop from https://www.docker.com/products/docker-desktop/"
  exit 1
fi

BASE_URL="http://localhost:3000"
WEBUI_URL_ENV="http://localhost:3000"
NEED_HOSTS_SETUP=0

# Prefer friendly hostname if it resolves (after running setup_hostname.* once).
if command -v ping >/dev/null 2>&1; then
  if ping -c 1 "$LAB_HOST" >/dev/null 2>&1; then
    BASE_URL="http://$LAB_HOST:3000"
    WEBUI_URL_ENV="$BASE_URL"
  else
    NEED_HOSTS_SETUP=1
  fi
else
  NEED_HOSTS_SETUP=1
fi

docker volume create open-webui-data >/dev/null 2>&1 || true
docker rm -f open-webui >/dev/null 2>&1 || true

docker run -d \
  -p 3000:8080 \
  -e ENV=dev \
  -e ENABLE_API_KEYS=true \
  -e WEBUI_URL="$WEBUI_URL_ENV" \
  -e OLLAMA_BASE_URL=http://host.docker.internal:11434 \
  -v open-webui-data:/app/backend/data \
  --name open-webui \
  ghcr.io/open-webui/open-webui:main

echo "Open WebUI started."
echo "UI:  $BASE_URL"
echo "API: $BASE_URL/docs"
echo

if [ "$NEED_HOSTS_SETUP" = "1" ]; then
  echo "Optional: enable the friendly URL http://$LAB_HOST:3000"
  echo "Run:"
  echo "  scripts/setup_hostname.sh"
  echo
  echo "Or add this line to /etc/hosts:"
  echo "  127.0.0.1   $LAB_HOST"
fi
