# Removes the Morning Pulse sign-in shortcut and stops the background server if it is running.
$lnk = Join-Path ([Environment]::GetFolderPath("Startup")) "Morning Pulse.lnk"
if (Test-Path $lnk) { Remove-Item $lnk -Confirm:$false; Write-Host "Removed: $lnk" } else { Write-Host "No autostart shortcut found." }

$procs = Get-CimInstance Win32_Process -Filter "Name='python.exe' OR Name='pythonw.exe'" |
    Where-Object { $_.CommandLine -like "*uvicorn*app.main:app*" }
foreach ($p in $procs) {
    Stop-Process -Id $p.ProcessId -Confirm:$false -ErrorAction SilentlyContinue
    Write-Host "Stopped server (pid $($p.ProcessId))."
}
