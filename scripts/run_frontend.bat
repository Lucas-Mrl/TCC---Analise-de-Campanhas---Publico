@echo off
setlocal

rem Ativa a venv se existir
if exist .venv\Scripts\activate (
  call .venv\Scripts\activate
)

if "%BACKEND_URL%"=="" set BACKEND_URL=http://127.0.0.1:3000
echo Usando BACKEND_URL=%BACKEND_URL%
set BACKEND_URL=%BACKEND_URL%

rem Usa python -m para evitar problemas de PATH do streamlit
python -m streamlit run frontend/app.py
