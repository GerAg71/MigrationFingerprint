# check_env.ps1 — MAPTIVA Fingerprint POC environment readiness check (Windows)
# Run from anywhere:  powershell -ExecutionPolicy Bypass -File .\check_env.ps1
# Run from the repo root to also check the project venv and sample data.

$script:fails = 0
$script:warns = 0

function Pass($msg) { Write-Host "  [PASS] $msg" -ForegroundColor Green }
function Fail($msg, $fix) {
    Write-Host "  [FAIL] $msg" -ForegroundColor Red
    if ($fix) { Write-Host "         fix: $fix" -ForegroundColor DarkGray }
    $script:fails++
}
function Warn($msg, $fix) {
    Write-Host "  [WARN] $msg" -ForegroundColor Yellow
    if ($fix) { Write-Host "         fix: $fix" -ForegroundColor DarkGray }
    $script:warns++
}

Write-Host "`nMAPTIVA Fingerprint POC — environment check" -ForegroundColor Cyan
Write-Host ("=" * 46)

# ---------- Python ----------
Write-Host "`nPython" -ForegroundColor Cyan
$pyCmd = $null
foreach ($candidate in @("python", "py")) {
    if (Get-Command $candidate -ErrorAction SilentlyContinue) { $pyCmd = $candidate; break }
}
if (-not $pyCmd) {
    Fail "Python not found on PATH" "install Python 3.11+ from python.org (check 'Add to PATH')"
} else {
    $verOut = & $pyCmd --version 2>&1
    if ($verOut -match "Python (\d+)\.(\d+)\.(\d+)") {
        $maj = [int]$Matches[1]; $min = [int]$Matches[2]
        if ($maj -eq 3 -and $min -ge 11) { Pass "$verOut (need 3.11+)" }
        else { Fail "$verOut found — spec requires Python 3.11+" "install 3.11+ from python.org; multiple versions can coexist via the 'py -3.11' launcher" }
    } else { Fail "could not parse Python version: $verOut" }

    # pip
    $pip = & $pyCmd -m pip --version 2>&1
    if ($LASTEXITCODE -eq 0) { Pass "pip available ($($pip -replace ' from .*',''))" }
    else { Fail "pip not available" "$pyCmd -m ensurepip --upgrade" }

    # venv module
    & $pyCmd -c "import venv" 2>$null
    if ($LASTEXITCODE -eq 0) { Pass "venv module available" }
    else { Fail "venv module missing" "reinstall Python with standard library intact" }
}

# ---------- Node ----------
Write-Host "`nNode.js / npm" -ForegroundColor Cyan
if (Get-Command node -ErrorAction SilentlyContinue) {
    $nv = (node --version) -replace "^v",""
    $nmaj = [int]($nv.Split(".")[0])
    if ($nmaj -ge 18) { Pass "node v$nv (need 18+)" }
    else { Fail "node v$nv — need 18+" "install LTS from nodejs.org" }
} else {
    Fail "node not found on PATH" "install Node.js LTS from nodejs.org"
}
if (Get-Command npm -ErrorAction SilentlyContinue) { Pass "npm $(npm --version)" }
else { Fail "npm not found" "reinstall Node.js (npm ships with it)" }

# ---------- Git ----------
Write-Host "`nGit" -ForegroundColor Cyan
if (Get-Command git -ErrorAction SilentlyContinue) { Pass "$(git --version)" }
else { Fail "git not found" "install from git-scm.com" }

# ---------- Ports ----------
Write-Host "`nPorts (8000 API, 5173 UI)" -ForegroundColor Cyan
foreach ($port in 8000, 5173) {
    $inUse = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
    if ($inUse) { Warn "port $port already in use" "stop the other process or run on an alternate port (--port)" }
    else { Pass "port $port free" }
}

# ---------- Project checks (only if run from the repo root) ----------
if (Test-Path ".\CLAUDE.md") {
    Write-Host "`nProject (repo root detected)" -ForegroundColor Cyan

    if (Test-Path ".\.venv\Scripts\python.exe") {
        Pass "virtualenv .venv exists"
        $vpy = ".\.venv\Scripts\python.exe"
        foreach ($pkg in "pydantic", "pandas", "pytest") {
            & $vpy -c "import $pkg" 2>$null
            if ($LASTEXITCODE -eq 0) { Pass "$pkg installed in .venv" }
            else { Warn "$pkg not in .venv" "activate .venv, then: pip install -e ." }
        }
        # uvicorn only matters from MS-3.1 on
        & $vpy -c "import uvicorn" 2>$null
        if ($LASTEXITCODE -eq 0) { Pass "uvicorn installed (Phase 3 API ready)" }
        else { Warn "uvicorn not installed (only needed from MS-3.1)" "pip install uvicorn fastapi" }
    } else {
        Warn "no .venv found in repo" "python -m venv .venv ; .\.venv\Scripts\activate ; pip install -e ."
    }

    if (Test-Path ".\data\fingerprints") {
        $fp = Get-ChildItem -Recurse -Filter "fingerprint.json" ".\data\fingerprints" -ErrorAction SilentlyContinue
        if ($fp) { Pass "seed fingerprint(s) present: $($fp.Count) file(s)" }
        else { Warn "data\fingerprints exists but no fingerprint.json found" "restore data/fingerprints/omni-zos-to-omni-linux/1.0.0/fingerprint.json" }
    } else { Warn "data\fingerprints missing" "pull latest from GitHub" }

    if (Test-Path ".\ui\package.json") {
        if (Test-Path ".\ui\node_modules") { Pass "ui dependencies installed" }
        else { Warn "ui\node_modules missing" "cd ui ; npm install" }
    } else { Warn "ui\ not present yet (created at MS-3.2)" }
} else {
    Write-Host "`nProject" -ForegroundColor Cyan
    Warn "not running from the repo root (no CLAUDE.md here)" "cd into the MigrationFingerprint repo and re-run for project-level checks"
}

# ---------- Summary ----------
Write-Host "`n$("=" * 46)"
if ($script:fails -eq 0 -and $script:warns -eq 0) {
    Write-Host "READY — all checks passed." -ForegroundColor Green
} elseif ($script:fails -eq 0) {
    Write-Host "READY with $script:warns warning(s) — nothing blocking." -ForegroundColor Yellow
} else {
    Write-Host "NOT READY — $script:fails failure(s), $script:warns warning(s). Fix [FAIL] items above." -ForegroundColor Red
}
Write-Host ""
exit $script:fails
