# Start the backend (uvicorn :9000) and the frontend (vite :5173) in separate windows.
# Assumes both are installed (see README) and each has its .env. Stop with Ctrl+C in each window.
$ErrorActionPreference = "Stop"
$here = Split-Path $PSScriptRoot -Parent

Start-Process powershell -ArgumentList @(
    "-NoExit", "-Command",
    "Set-Location '$here\backend'; .\.venv\Scripts\Activate.ps1; uvicorn app.main:app --host 127.0.0.1 --port 9000 --reload"
)
Start-Process powershell -ArgumentList @(
    "-NoExit", "-Command",
    "Set-Location '$here\frontend'; npm run dev"
)
Write-Host "Backend  -> http://127.0.0.1:9000  (docs at /docs)" -ForegroundColor Green
Write-Host "Frontend -> http://localhost:5173" -ForegroundColor Green
