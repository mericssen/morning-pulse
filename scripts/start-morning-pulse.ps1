# Starts Morning Pulse silently in the background and opens the morning card
# as an app-style window. Used by the Windows Startup shortcut, safe to run by hand.
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$url = "http://127.0.0.1:8000"
$log = Join-Path $env:LOCALAPPDATA "MorningPulse"
New-Item -ItemType Directory -Force $log | Out-Null

function Test-Up {
    try { (Invoke-WebRequest "$url/api/stats" -UseBasicParsing -TimeoutSec 2).StatusCode -eq 200 } catch { $false }
}

if (-not (Test-Up)) {
    $py = Join-Path $root "backend\.venv\Scripts\python.exe"
    Start-Process -FilePath $py -WorkingDirectory (Join-Path $root "backend") -WindowStyle Hidden `
        -ArgumentList "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8000" `
        -RedirectStandardOutput (Join-Path $log "server.log") -RedirectStandardError (Join-Path $log "server.err.log")
    $deadline = (Get-Date).AddSeconds(30)
    while (-not (Test-Up) -and (Get-Date) -lt $deadline) { Start-Sleep -Milliseconds 500 }
}

# App-style window (no tabs/address bar) via Edge; fall back to the default browser.
try {
    Start-Process "msedge" -ArgumentList "--app=$url", "--window-size=600,860"
} catch {
    Start-Process $url
}
