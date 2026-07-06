# Start the MAPTIVA Migration Fingerprint dashboard (http://127.0.0.1:8000/).
# Run:  powershell -ExecutionPolicy Bypass -File .\start-dashboard.ps1
# Stop: Ctrl+C in this window.

$repo = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $repo

# Prefer the project venv directly (avoids uv/OneDrive hardlink hiccups);
# fall back to uv if the venv doesn't exist yet.
$venvPython = Join-Path $repo ".venv\Scripts\python.exe"
$env:PYTHONPATH = "."

Write-Host "MAPTIVA Migration Fingerprint - dashboard starting..." -ForegroundColor Cyan
Write-Host "Open http://127.0.0.1:8000/  (Ctrl+C here to stop)" -ForegroundColor Green

if (Test-Path $venvPython) {
    & $venvPython -m uvicorn src.api.app:app --port 8000
} else {
    Write-Host "No .venv found - running 'uv sync' first..." -ForegroundColor Yellow
    $env:UV_LINK_MODE = "copy"
    uv sync
    uv run uvicorn src.api.app:app --port 8000
}
