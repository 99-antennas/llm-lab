#!/bin/bash
set -e

echo "Running database migrations..."
aerich upgrade

echo "Starting API server..."
exec uvicorn apps.api.main:app --host 0.0.0.0 --port 8000
