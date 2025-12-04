#!/usr/bin/env bash
set -euo pipefail
if [ ! -d .venv ]; then
  echo "Criando venv em .venv ..."
  python -m venv .venv
fi
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
echo "Ambiente pronto. Para ativar depois: source .venv/bin/activate"

