@echo off
setlocal
cd /d "%~dp0"
if exist "CentralIAStudio\CentralIAStudio.exe" (
  "CentralIAStudio\CentralIAStudio.exe"
  if errorlevel 1 pause
  exit /b
)
if exist "CentralIAStudio.exe" (
  "CentralIAStudio.exe"
  if errorlevel 1 pause
  exit /b
)
if not exist ".venv\Scripts\python.exe" (
  echo Execute PREPARAR_WINDOWS.cmd uma vez, ou utilize o pacote compilado.
  echo Esta versao de codigo-fonte requer Python 3.12 x64 instalado.
  pause
  exit /b 1
)
".venv\Scripts\python.exe" run.py
if errorlevel 1 pause
