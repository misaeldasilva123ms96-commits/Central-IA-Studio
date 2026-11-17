$ErrorActionPreference = 'Stop'
Set-Location (Join-Path $PSScriptRoot '..')
if (!(Test-Path 'frontend/dist/index.html')) { throw 'Compile o frontend antes do pacote.' }
python scripts/build_resources.py
if ($LASTEXITCODE -ne 0) { throw 'Recursos comuns incompletos' }
$versionResource=[IO.Path]::GetFullPath('work/freeze-resources/windows-version.txt')
$common = @('--version-file',$versionResource,'--noconfirm','--clean','--noupx','--console','--name','CentralIAStudio',
  '--collect-all','uvicorn','--collect-all','fastapi','--collect-all','pypdf',
  '--collect-data','mcp','--collect-submodules','mcp.client','--collect-submodules','mcp.shared','--collect-submodules','mcp.os',
  '--collect-all','yaml','--collect-all','jsonschema_specifications','--collect-all','referencing','--recursive-copy-metadata','mcp',
  '--hidden-import','PIL.PngImagePlugin','--hidden-import','PIL.JpegImagePlugin','--hidden-import','PIL.WebPImagePlugin','--hidden-import','PIL.GifImagePlugin','--hidden-import','PIL.BmpImagePlugin',
  '--recursive-copy-metadata','fastapi','--recursive-copy-metadata','uvicorn','--recursive-copy-metadata','httpx','--recursive-copy-metadata','psutil',
  '--add-data','work/freeze-resources/common/frontend;frontend','--add-data','work/freeze-resources/common/licencas;licencas',
  '--add-data','work/freeze-resources/common/LICENSE;.','--add-data','work/freeze-resources/common/NOTICES.md;.',
  '--add-data','work/freeze-resources/common/central-ia-studio-source.zip;.', '--add-binary','work/freeze-resources/common/engine/central-engine-nocuda.exe;engine')
foreach ($resource in Get-ChildItem 'work/freeze-resources/common/engine' -File) {
  if ($resource.Name -eq 'central-engine-nocuda.exe') { continue }
  $kind = if ($resource.Extension -eq '.dll') { '--add-binary' } else { '--add-data' }
  $common += @($kind, "$($resource.FullName);engine")
}
# CLI resource paths must be absolute when spec files live outside the project root.
for ($i=0; $i -lt $common.Count; $i++) {
  if ($common[$i] -in @('--add-data','--add-binary')) {
    $parts=$common[$i+1].Split(';',2)
    $common[$i+1]=[IO.Path]::GetFullPath($parts[0])+';'+$parts[1]
  }
}
foreach ($mode in @('onedir','onefile')) {
  $target = if ($mode -eq 'onedir') { 'dist' } else { 'dist/onefile' }
  $metadata=[IO.Path]::GetFullPath("work/freeze-resources/$mode/build-info.json")
  $entry=[IO.Path]::GetFullPath("run.py")
  python -m PyInstaller @common "--$mode" --distpath $target --workpath "work/pyinstaller-$mode" --specpath "work/spec-$mode" --add-data "$metadata;." $entry
  if ($LASTEXITCODE -ne 0) { throw "PyInstaller falhou: $mode" }
}
python scripts/package_windows.py
if ($LASTEXITCODE -ne 0) { throw 'Organizacao dos dois pacotes falhou' }
python scripts/verify_package.py
if ($LASTEXITCODE -ne 0) { throw 'Verificacao dos dois pacotes falhou' }
