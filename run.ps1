# Morning Pulse - one-command start (Windows PowerShell)
# Usage:  .\run.ps1          -> builds UI if needed, starts API + UI on http://127.0.0.1:8000
#         .\run.ps1 -Dev     -> API only (run `npm run dev` in frontend/ for hot reload on :5173)
param([switch]$Dev)

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location "$root\backend"

if (-not (Test-Path ".venv")) {
    python -m venv .venv
    .\.venv\Scripts\python -m pip install -q -r requirements.txt
}

if (-not $Dev -and -not (Test-Path "$root\frontend\dist")) {
    Push-Location "$root\frontend"
    npm install --no-audit --no-fund
    npm run build
    Pop-Location
}

if (-not $Dev) { Start-Process "http://127.0.0.1:8000" }
.\.venv\Scripts\python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
