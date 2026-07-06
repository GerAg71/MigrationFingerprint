#!/usr/bin/env bash
# check_env.sh — MAPTIVA Fingerprint POC environment readiness check (Mac / Linux / WSL)
# Usage:  bash check_env.sh          (run from the repo root for project-level checks)

FAILS=0; WARNS=0
GRN='\033[0;32m'; RED='\033[0;31m'; YEL='\033[0;33m'; CYN='\033[0;36m'; GRY='\033[0;90m'; NC='\033[0m'

pass() { echo -e "  ${GRN}[PASS]${NC} $1"; }
fail() { echo -e "  ${RED}[FAIL]${NC} $1"; [ -n "$2" ] && echo -e "         ${GRY}fix: $2${NC}"; FAILS=$((FAILS+1)); }
warn() { echo -e "  ${YEL}[WARN]${NC} $1"; [ -n "$2" ] && echo -e "         ${GRY}fix: $2${NC}"; WARNS=$((WARNS+1)); }

echo -e "\n${CYN}MAPTIVA Fingerprint POC — environment check${NC}"
echo "=============================================="

# ---------- Python ----------
echo -e "\n${CYN}Python${NC}"
PY=""
for c in python3.12 python3.11 python3 python; do
  command -v "$c" >/dev/null 2>&1 && PY="$c" && break
done
if [ -z "$PY" ]; then
  fail "Python not found on PATH" "install Python 3.11+ (apt/brew/pyenv or python.org)"
else
  VER=$("$PY" --version 2>&1 | awk '{print $2}')
  MAJ=$(echo "$VER" | cut -d. -f1); MIN=$(echo "$VER" | cut -d. -f2)
  if [ "$MAJ" -eq 3 ] && [ "$MIN" -ge 11 ]; then
    pass "Python $VER via '$PY' (need 3.11+)"
  else
    fail "Python $VER found — spec requires 3.11+" "install 3.11+ (e.g. 'brew install python@3.12' or pyenv)"
  fi
  if "$PY" -m pip --version >/dev/null 2>&1; then pass "pip available"; else fail "pip not available" "$PY -m ensurepip --upgrade"; fi
  if "$PY" -c "import venv" >/dev/null 2>&1; then pass "venv module available"; else fail "venv module missing" "install python3-venv (Debian/Ubuntu: apt install python3.11-venv)"; fi
fi

# ---------- Node ----------
echo -e "\n${CYN}Node.js / npm${NC}"
if command -v node >/dev/null 2>&1; then
  NV=$(node --version | sed 's/^v//'); NMAJ=$(echo "$NV" | cut -d. -f1)
  if [ "$NMAJ" -ge 18 ]; then pass "node v$NV (need 18+)"; else fail "node v$NV — need 18+" "install LTS via nvm or nodejs.org"; fi
else
  fail "node not found" "install Node.js LTS (nvm recommended)"
fi
command -v npm >/dev/null 2>&1 && pass "npm $(npm --version)" || fail "npm not found" "reinstall Node.js"

# ---------- Git ----------
echo -e "\n${CYN}Git${NC}"
command -v git >/dev/null 2>&1 && pass "$(git --version)" || fail "git not found" "apt install git / brew install git"

# ---------- Ports ----------
echo -e "\n${CYN}Ports (8000 API, 5173 UI)${NC}"
for PORT in 8000 5173; do
  if command -v lsof >/dev/null 2>&1 && lsof -iTCP:"$PORT" -sTCP:LISTEN >/dev/null 2>&1; then
    warn "port $PORT already in use" "stop the other process or use an alternate port"
  else
    pass "port $PORT free"
  fi
done

# ---------- Project checks ----------
if [ -f "./CLAUDE.md" ]; then
  echo -e "\n${CYN}Project (repo root detected)${NC}"
  if [ -x "./.venv/bin/python" ]; then
    pass "virtualenv .venv exists"
    VPY="./.venv/bin/python"
    for pkg in pydantic pandas pytest; do
      "$VPY" -c "import $pkg" >/dev/null 2>&1 && pass "$pkg installed in .venv" || warn "$pkg not in .venv" "source .venv/bin/activate && pip install -e ."
    done
    "$VPY" -c "import uvicorn" >/dev/null 2>&1 && pass "uvicorn installed (Phase 3 API ready)" || warn "uvicorn not installed (only needed from MS-3.1)" "pip install uvicorn fastapi"
  else
    warn "no .venv found in repo" "python3 -m venv .venv && source .venv/bin/activate && pip install -e ."
  fi

  if [ -d "./data/fingerprints" ]; then
    COUNT=$(find ./data/fingerprints -name fingerprint.json 2>/dev/null | wc -l | tr -d ' ')
    [ "$COUNT" -gt 0 ] && pass "seed fingerprint(s) present: $COUNT file(s)" || warn "no fingerprint.json under data/fingerprints" "restore the seed fingerprint from GitHub"
  else
    warn "data/fingerprints missing" "pull latest from GitHub"
  fi

  if [ -f "./ui/package.json" ]; then
    [ -d "./ui/node_modules" ] && pass "ui dependencies installed" || warn "ui/node_modules missing" "cd ui && npm install"
  else
    warn "ui/ not present yet (created at MS-3.2)"
  fi
else
  echo -e "\n${CYN}Project${NC}"
  warn "not running from the repo root (no CLAUDE.md here)" "cd into the MigrationFingerprint repo and re-run"
fi

# ---------- Summary ----------
echo ""
echo "=============================================="
if [ "$FAILS" -eq 0 ] && [ "$WARNS" -eq 0 ]; then
  echo -e "${GRN}READY — all checks passed.${NC}"
elif [ "$FAILS" -eq 0 ]; then
  echo -e "${YEL}READY with $WARNS warning(s) — nothing blocking.${NC}"
else
  echo -e "${RED}NOT READY — $FAILS failure(s), $WARNS warning(s). Fix [FAIL] items above.${NC}"
fi
echo ""
exit "$FAILS"
