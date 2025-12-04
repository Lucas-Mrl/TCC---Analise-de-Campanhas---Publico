@echo off
setlocal
if not exist .venv (
  echo Criando venv em .venv ...
  python -m venv .venv
)
call .venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt
echo Ambiente pronto. Para ativar depois: .venv\Scripts\activate

