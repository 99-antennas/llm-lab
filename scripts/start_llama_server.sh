#!/usr/bin/env bash
# Starts llama-server with settings tuned for 64 GB unified memory Apple Silicon.
#
# Model: Qwen3.6-35B-A3B-UD-Q4_K_M (GGUF)
#   - Model size:  quantized single-file GGUF
#   - KV cache:    ~8 GB  (128K context, q4_0 quantization)
#   - Total:       fits comfortably within 64 GB unified memory
#
# Setup and download instructions live in README.md.
# This script only starts llama-server using the model file at $LLAMA_MODEL
# or the default path shown below.
#
# Usage: ./scripts/start_llama_server.sh

set -euo pipefail

MODEL="${LLAMA_MODEL:-$HOME/models/Qwen3.6-35B-A3B-UD-Q4_K_M.gguf}"
HOST="${LLAMA_HOST:-0.0.0.0}"
PORT="${LLAMA_PORT:-8080}"

if [[ ! -f "$MODEL" ]]; then
  echo "Model not found at $MODEL"
  echo "Download it with:"
  echo "  hf download unsloth/Qwen3.6-35B-A3B-GGUF Qwen3.6-35B-A3B-UD-Q4_K_M.gguf --local-dir ~/models"
  exit 1
fi

echo "Starting llama-server on $HOST:$PORT with model: $MODEL"

llama-server \
  -m "$MODEL" \
  -ngl 99 \
  -c 131072 \
  -np 1 \
  -fa on \
  --cache-type-k q4_0 \
  --cache-type-v q4_0 \
  --host "$HOST" \
  --port "$PORT"
