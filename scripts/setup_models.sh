#!/usr/bin/env bash
set -e

if ! command -v ollama >/dev/null 2>&1; then
  echo "Ollama is not installed. Please install it from https://ollama.com"
  exit 1
fi

echo "Pulling models..."
while read model; do
  ollama pull "$model"
done < "$(dirname "$0")/../models/models.txt"

echo "Models installed."
