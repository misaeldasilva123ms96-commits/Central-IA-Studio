@echo off
setlocal
cd /d "%~dp0"
echo Este procedimento baixa dependencias Python do PyPI.
echo Execute somente se desejar preparar a versao de codigo-fonte.
choice /C SN /N /M "Baixar e instalar as dependencias? [S/N] "
if errorlevel 2 exit /b 0
py -3.12 -m venv .venv
if errorlevel 1 goto erro
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto erro
echo Pronto. Abra INICIAR_CENTRAL_IA_STUDIO.cmd.
pause
exit /b 0
:erro
echo Falha. Confira a instalacao do Python 3.12 x64 e a conexao.
pause
exit /b 1
