$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$venvPython = Join-Path $root ".venv\Scripts\python.exe"
$pyLauncher = Get-Command py -ErrorAction SilentlyContinue
$pythonCommand = $null
$pythonArgs = @()

if (Test-Path $venvPython) {
    $pythonCommand = $venvPython
} elseif ($pyLauncher) {
    $pythonCommand = $pyLauncher.Source
    $pythonArgs = @("-3")
} else {
    throw "Python runtime not found. Install Python 3 or create .venv in $root."
}

$logDir = Join-Path $root "logs"
$outLog = Join-Path $logDir "worker.out.log"
$errLog = Join-Path $logDir "worker.err.log"
$pidFile = Join-Path $root "worker.pid"

New-Item -ItemType Directory -Force $logDir | Out-Null

$existing = Get-CimInstance Win32_Process | Where-Object {
    $_.CommandLine -like "*src.main*" -and $_.CommandLine -like "*$root*"
}

if ($existing) {
    $existing.ProcessId | Set-Content $pidFile
    Write-Output "Worker already running with PID $($existing.ProcessId -join ', ')"
    exit 0
}

$process = Start-Process -FilePath $pythonCommand `
    -ArgumentList ($pythonArgs + @("-m", "src.main")) `
    -WorkingDirectory $root `
    -RedirectStandardOutput $outLog `
    -RedirectStandardError $errLog `
    -WindowStyle Hidden `
    -PassThru

$process.Id | Set-Content $pidFile
Write-Output "Started worker PID $($process.Id)"
