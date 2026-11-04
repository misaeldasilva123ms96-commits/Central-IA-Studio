$ErrorActionPreference = 'Stop'
Set-Location (Join-Path $PSScriptRoot '..')
if (!(Test-Path 'frontend/dist/index.html')) { throw 'Compile o frontend com npm ci e npm run build na pasta frontend.' }
python -m PyInstaller --noconfirm --clean --onedir --name CentralIAStudio --collect-all uvicorn --collect-all fastapi --collect-all pypdf --hidden-import PIL.PngImagePlugin --hidden-import PIL.JpegImagePlugin --hidden-import PIL.WebPImagePlugin --hidden-import PIL.GifImagePlugin --hidden-import PIL.BmpImagePlugin --recursive-copy-metadata fastapi --recursive-copy-metadata uvicorn --recursive-copy-metadata httpx --recursive-copy-metadata psutil --add-data "frontend/dist;frontend/dist" --add-data "LICENSE;." --add-data "NOTICES.md;." --add-data "central-ia-studio-source.zip;." run.py
if ($LASTEXITCODE -ne 0) { throw 'PyInstaller falhou' }
python scripts/package_windows.py
if ($LASTEXITCODE -ne 0) { throw 'Organizacao dos pacotes falhou' }
python scripts/verify_package.py
if ($LASTEXITCODE -ne 0) { throw 'Verificacao dos pacotes falhou' }
