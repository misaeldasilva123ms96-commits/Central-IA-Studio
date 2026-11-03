$ErrorActionPreference = 'Stop'
Set-Location (Join-Path $PSScriptRoot '..')
if (!(Test-Path 'frontend/dist/index.html')) { throw 'Compile o frontend com npm ci e npm run build na pasta frontend.' }
python -m PyInstaller --noconfirm --clean --onedir --name CentralIAStudio --collect-all uvicorn --collect-all fastapi --recursive-copy-metadata fastapi --recursive-copy-metadata uvicorn --recursive-copy-metadata httpx --recursive-copy-metadata psutil --add-data "frontend/dist;frontend/dist" --add-data "LICENSE;." --add-data "NOTICES.md;." --add-data "central-ia-studio-source.zip;." run.py
if ($LASTEXITCODE -ne 0) { throw 'PyInstaller falhou' }
$packageDir = Join-Path 'work' ('windows-package-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Force $packageDir | Out-Null
Copy-Item -Recurse -Force 'dist/CentralIAStudio' $packageDir
Copy-Item INICIAR_CENTRAL_IA_STUDIO.cmd, README.md, LICENSE, NOTICES.md, THIRD_PARTY_FRONTEND.txt, THIRD_PARTY_PYTHON.txt $packageDir
Copy-Item -Recurse -Force docs $packageDir
Copy-Item central-ia-studio-source.zip $packageDir
Compress-Archive -Force -Path (Join-Path $packageDir '*') -DestinationPath 'Central-IA-Studio-Windows-x64.zip'
Get-FileHash 'Central-IA-Studio-Windows-x64.zip' -Algorithm SHA256 | Format-List

python scripts/verify_package.py
if ($LASTEXITCODE -ne 0) { throw 'Verificacao dos pacotes falhou' }
