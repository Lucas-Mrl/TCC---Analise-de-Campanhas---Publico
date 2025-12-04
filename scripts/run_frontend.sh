#!/usr/bin/env bash
set -euo pipefail
BACKEND_URL=${BACKEND_URL:-http://127.0.0.1:3000}
echo "Usando BACKEND_URL=${BACKEND_URL}"
export BACKEND_URL
streamlit run frontend/app.py

