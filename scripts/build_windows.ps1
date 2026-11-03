$ErrorActionPreference = 'Stop'
Set-Location (Join-Path $PSScriptRoot '..')
if (!(Test-Path 'frontend/dist/index.html')) { throw 'Compile o frontend com npm ci e npm run build na pasta frontend.' }
python -m PyInstaller --noconfirm --clean --onedir --name CentralIAStudio --collect-all uvicorn --collect-all fastapi --recursive-copy-metadata fastapi --recursive-copy-metadata uvicorn --recursive-copy-metadata httpx --recursive-copy-metadata psutil --add-data "frontend/dist;frontend/dist" --add-data "LICENSE;." --add-data "NOTICES.md;." --add-data "central-ia-studio-source.zip;." run.py
if ($LASTEXITCODE -ne 0) { throw 'PyInstaller falhou' }
New-Item -ItemType Directory -Force 'work/windows-package' | Out-Null
Copy-Item -Recurse -Force 'dist/CentralIAStudio' 'work/windows-package/'
Copy-Item INICIAR_CENTRAL_IA_STUDIO.cmd, README.md, LICENSE, NOTICES.md, THIRD_PARTY_FRONTEND.txt, THIRD_PARTY_PYTHON.txt 'work/windows-package/'
Copy-Item -Recurse -Force docs 'work/windows-package/'
Copy-Item central-ia-studio-source.zip 'work/windows-package/'
Compress-Archive -Force -Path 'work/windows-package/*' -DestinationPath 'Central-IA-Studio-Windows-x64.zip'
Get-FileHash 'Central-IA-Studio-Windows-x64.zip' -Algorithm SHA256 | Format-List
