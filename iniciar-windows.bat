@echo off
cd /d "%~dp0"
where py >nul 2>&1
if %errorlevel%==0 (
  set "PYTHON=py -3"
) else (
  set "PYTHON=python"
)
if not exist ".venv\Scripts\python.exe" (
  echo Criando ambiente virtual Python...
  %PYTHON% -m venv .venv || goto :erro
)
echo Instalando dependencias, se necessario...
".venv\Scripts\python.exe" -m pip install -r requirements.txt || goto :erro
echo Abrindo Central IA Studio em http://127.0.0.1:8765
echo Copie esse endereco no navegador se ele nao abrir automaticamente.
start "" powershell -NoProfile -WindowStyle Hidden -Command "Start-Sleep -Seconds 3; Start-Process 'http://127.0.0.1:8765'"
".venv\Scripts\python.exe" run.py
goto :fim
:erro
echo Ocorreu um erro. Confira a instalacao do Python e a conexao para instalar dependencias.
pause
:fim
