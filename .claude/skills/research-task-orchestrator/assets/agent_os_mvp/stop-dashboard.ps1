$ErrorActionPreference = "SilentlyContinue"

$root = $PSScriptRoot
$logDir = Join-Path $root "logs"
$pidFiles = @(
  Join-Path $logDir "backend.pid"
  Join-Path $logDir "frontend.pid"
)

function Stop-ProcessTree {
  param([int]$ProcessId)
  $children = Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object {
    $_.ParentProcessId -eq $ProcessId
  }
  foreach ($child in $children) {
    Stop-ProcessTree -ProcessId $child.ProcessId
  }
  Stop-Process -Id $ProcessId -Force -ErrorAction SilentlyContinue
}

foreach ($pidFile in $pidFiles) {
  if (-not (Test-Path $pidFile)) {
    continue
  }
  $pidText = (Get-Content $pidFile -ErrorAction SilentlyContinue | Select-Object -First 1)
  if ($pidText -match "^\d+$") {
    Stop-ProcessTree -ProcessId ([int]$pidText)
  }
  Remove-Item -Force $pidFile -ErrorAction SilentlyContinue
}

$escapedRoot = [regex]::Escape($root)
$leftovers = Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object {
  $_.CommandLine -and $_.CommandLine -match $escapedRoot -and $_.CommandLine -match "uvicorn|vite|pnpm"
}
foreach ($process in $leftovers) {
  Stop-ProcessTree -ProcessId $process.ProcessId
}

Write-Host "Stopped dashboard background processes if they existed."
