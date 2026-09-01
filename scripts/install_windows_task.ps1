param(
  [Parameter(Mandatory=$true)][string]$ProjectRoot,
  [string]$TaskName = "AI Swing Trading Daily",
  [string]$RunTime = "16:15"
)
$backend = Join-Path $ProjectRoot "backend"
$python = Join-Path $backend ".venv\Scripts\python.exe"
if (!(Test-Path $python)) { throw "Virtual environment python not found: $python" }
$command = "cmd /c cd /d `"$backend`" && `"$python`" -m app.daily_runner >> daily_runner.log 2>&1"
schtasks /Create /F /TN $TaskName /TR $command /SC WEEKLY /D MON,TUE,WED,THU,FRI /ST $RunTime
Write-Host "Created '$TaskName' for weekdays at $RunTime. The runner remains research-only and does not place orders."
