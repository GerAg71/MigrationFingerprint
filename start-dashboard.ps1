# Start the MAPTIVA Migration Fingerprint dashboard (http://127.0.0.1:8000/).
# Run:  powershell -ExecutionPolicy Bypass -File .\start-dashboard.ps1
# Stop: Ctrl+C in this window.

$repo = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $repo

# Already running? (a previous window, or a detached instance)
$listening = Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue
if ($listening) {
    try {
        $probe = Invoke-WebRequest -Uri "http://127.0.0.1:8000/ui" -UseBasicParsing -TimeoutSec 3
        if ($probe.StatusCode -eq 200) {
            Write-Host "Dashboard is ALREADY RUNNING - open http://127.0.0.1:8000/" -ForegroundColor Green
            Write-Host "(to stop it: Get-NetTCPConnection -LocalPort 8000 -State Listen | % { Stop-Process -Id `$_.OwningProcess -Force })" -ForegroundColor DarkGray
            exit 0
        }
    } catch {}
    Write-Host "Port 8000 is in use by something else. Stop that process or edit this script to use another port." -ForegroundColor Red
    exit 1
}

# Prefer the project venv directly (avoids uv/OneDrive hardlink hiccups);
# fall back to uv if the venv doesn't exist yet.
$venvPython = Join-Path $repo ".venv\Scripts\python.exe"
$env:PYTHONPATH = "."

Write-Host "MAPTIVA Migration Fingerprint - dashboard starting..." -ForegroundColor Cyan
Write-Host "Open http://127.0.0.1:8000/  (Ctrl+C here to stop)" -ForegroundColor Green

# --reload restarts the server automatically when source files change,
# so pulling new code never leaves a stale process serving old endpoints.
if (Test-Path $venvPython) {
    & $venvPython -m uvicorn src.api.app:app --port 8000 --reload
} else {
    Write-Host "No .venv found - running 'uv sync' first..." -ForegroundColor Yellow
    $env:UV_LINK_MODE = "copy"
    uv sync
    uv run uvicorn src.api.app:app --port 8000 --reload
}
