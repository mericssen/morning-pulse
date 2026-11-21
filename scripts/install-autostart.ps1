# Makes Morning Pulse open automatically at Windows sign-in (current user, no admin needed).
# Prepares the Python venv and the built UI, then adds a shortcut to the user's Startup folder.
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)

if (-not (Test-Path "$root\backend\.venv")) {
    python -m venv "$root\backend\.venv"
    & "$root\backend\.venv\Scripts\python.exe" -m pip install -q -r "$root\backend\requirements.txt"
}
if (-not (Test-Path "$root\frontend\dist")) {
    Push-Location "$root\frontend"; npm install --no-audit --no-fund; npm run build; Pop-Location
}

$startup = [Environment]::GetFolderPath("Startup")
$lnk = Join-Path $startup "Morning Pulse.lnk"
$shell = New-Object -ComObject WScript.Shell
$s = $shell.CreateShortcut($lnk)
$s.TargetPath = "powershell.exe"
$s.Arguments = "-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$root\scripts\start-morning-pulse.ps1`""
$s.WorkingDirectory = $root
$s.WindowStyle = 7   # minimized
$s.Description = "Morning Pulse - 10-second morning check-up"
$s.Save()

Write-Host "Installed: $lnk"
Write-Host "Morning Pulse will open at your next sign-in. To remove: .\scripts\uninstall-autostart.ps1"
