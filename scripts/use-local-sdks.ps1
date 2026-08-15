# Build the platform SDKs from the sibling `auth` monorepo and link them into this app — for
# development BEFORE the 0.2.0 packages are published to npm / PyPI. Re-run after you pull new
# SDK changes. Safe to run repeatedly.
#
#   powershell -ExecutionPolicy Bypass -File scripts\use-local-sdks.ps1
#   powershell -ExecutionPolicy Bypass -File scripts\use-local-sdks.ps1 -AuthRepo C:\path\to\auth
param(
    [string]$AuthRepo = (Join-Path (Split-Path $PSScriptRoot -Parent) "..\auth")
)
$ErrorActionPreference = "Stop"
$AuthRepo = (Resolve-Path $AuthRepo).Path
$here = Split-Path $PSScriptRoot -Parent
Write-Host "Monorepo: $AuthRepo" -ForegroundColor Cyan

# 1. Build the two React SDKs (each emits dist/ via tsc).
# react-auth only. `react-login` was dropped when sign-in became a redirect to login-web, which
# renders and translates its own page — the embedded <LoginForm> is no longer used.
foreach ($pkg in @("packages\react\react-auth")) {
    $path = Join-Path $AuthRepo $pkg
    Write-Host "Building $pkg ..." -ForegroundColor Cyan
    Push-Location $path
    npm install
    npm run build
    Pop-Location
}

# 2. Install them into the frontend (overrides the published ^0.2.0 range with the local build).
Write-Host "Linking SDKs into frontend ..." -ForegroundColor Cyan
Push-Location (Join-Path $here "frontend")
npm install
npm install --no-save (Join-Path $AuthRepo "packages\react\react-auth")
Pop-Location

# 3. Install the Python admin SDK (editable) into the backend venv, if it exists.
$venvPip = Join-Path $here "backend\.venv\Scripts\pip.exe"
$adminSdk = Join-Path $AuthRepo "packages\python\admin-sdk-python"
if (Test-Path $venvPip) {
    Write-Host "Installing admin SDK into backend venv ..." -ForegroundColor Cyan
    & $venvPip install -e $adminSdk
} else {
    Write-Host "Backend venv not found. After creating it, run:" -ForegroundColor Yellow
    Write-Host "  pip install -e `"$adminSdk`"" -ForegroundColor Yellow
}

Write-Host "Done. Local SDKs linked." -ForegroundColor Green
