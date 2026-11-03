<#
Build the SmartFlow desktop development package and installer. Exits nonzero on any failure.
  scripts\build-desktop.ps1 [-Version 0.1.0-dev] [-WebView2Installer C:\path\MicrosoftEdgeWebView2RuntimeInstallerX64.exe] [-SkipInstaller]
Needs: .venv-desktop (see desktop/requirements-desktop-lock.txt), node_modules, and Inno Setup 6 (ISCC.exe) for the installer.
Output: tmp\desktop-shell-experiment-*\dist\SmartFlowPrototype and tmp\installer\SmartFlow-Setup-<Version>.exe (unsigned).
#>
param([string]$Version = "0.0.0-dev", [string]$WebView2Installer = "", [switch]$SkipInstaller)
$ErrorActionPreference = "Stop"
$root = Split-Path $PSScriptRoot -Parent
Set-Location $root
$py = Join-Path $root ".venv-desktop\Scripts\python.exe"
if (-not (Test-Path $py)) { throw "Create .venv-desktop first." }
$frontend = Join-Path $root "tmp\fe-desktop"
if (Test-Path $frontend) { Remove-Item -Recurse -Force $frontend }
$env:VITE_SMARTFLOW_DESKTOP = "1"
npx.cmd vite build --outDir $frontend
if ($LASTEXITCODE) { throw "Frontend build failed" }
Remove-Item Env:VITE_SMARTFLOW_DESKTOP
& $py -m desktop.build_shell_prototype --with-ml --frontend $frontend
if ($LASTEXITCODE) { throw "Package build failed" }
if ($SkipInstaller) { return }
$package = Get-ChildItem (Join-Path $root "tmp") -Directory -Filter "desktop-shell-experiment-*" |
  Sort-Object LastWriteTime -Descending | Select-Object -First 1 | ForEach-Object { Join-Path $_.FullName "dist\SmartFlowPrototype" }
$iscc = (Get-Command iscc -ErrorAction SilentlyContinue).Source
if (-not $iscc) { $iscc = @("${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe", "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe") | Where-Object { Test-Path $_ } | Select-Object -First 1 }
if (-not $iscc) { throw "Inno Setup 6 (ISCC.exe) not found." }
$args = @("/DSourceDir=$package", "/DAppVersion=$Version", "/O$(Join-Path $root 'tmp\installer')")
if ($WebView2Installer) { $args += "/DWebView2Installer=$WebView2Installer" }
& $iscc @args (Join-Path $root "desktop\installer\SmartFlow.iss")
if ($LASTEXITCODE) { throw "Installer build failed" }
Get-FileHash (Join-Path $root "tmp\installer\SmartFlow-Setup-$Version.exe") -Algorithm SHA256
