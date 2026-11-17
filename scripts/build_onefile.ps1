# The official onefile build always produces its synchronized onedir counterpart.
$ErrorActionPreference = 'Stop'
& (Join-Path $PSScriptRoot 'build_windows.ps1')
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
