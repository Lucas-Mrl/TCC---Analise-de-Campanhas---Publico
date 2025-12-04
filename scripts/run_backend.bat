@echo off
setlocal

rem Ativa a venv se existir
if exist .venv\Scripts\activate (
  call .venv\Scripts\activate
)

if "%BACKEND_HOST%"=="" set BACKEND_HOST=127.0.0.1
if "%BACKEND_PORT%"=="" set BACKEND_PORT=3000
echo Iniciando backend em %BACKEND_HOST%:%BACKEND_PORT% ...
python -m uvicorn backend.main:app --reload --host %BACKEND_HOST% --port %BACKEND_PORT%
