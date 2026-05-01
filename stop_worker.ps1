$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$pidFile = Join-Path $root "worker.pid"

if (-not (Test-Path $pidFile)) {
    Write-Output "No worker.pid file found"
    exit 0
}

$pid = Get-Content $pidFile | Select-Object -First 1
if ($pid) {
    Stop-Process -Id $pid -ErrorAction SilentlyContinue
}

Remove-Item $pidFile -ErrorAction SilentlyContinue
Write-Output "Stopped worker PID $pid"
