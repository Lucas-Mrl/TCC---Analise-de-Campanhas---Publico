#!/usr/bin/env bash
set -euo pipefail
BACKEND_HOST=${BACKEND_HOST:-127.0.0.1}
BACKEND_PORT=${BACKEND_PORT:-3000}
echo "Iniciando backend em ${BACKEND_HOST}:${BACKEND_PORT} ..."
python -m uvicorn backend.main:app --reload --host "$BACKEND_HOST" --port "$BACKEND_PORT"

