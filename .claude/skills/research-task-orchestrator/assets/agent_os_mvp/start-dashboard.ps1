param(
  [int]$BackendPort = 8010,
  [int]$FrontendPort = 5174,
  [switch]$Open,
  [int]$TimeoutSec = 30
)

$ErrorActionPreference = "Stop"

$root = $PSScriptRoot
$backendDir = Join-Path $root "backend"
$frontendDir = Join-Path $root "frontend"
$logDir = Join-Path $root "logs"
$stopScript = Join-Path $root "stop-dashboard.ps1"
$backendPython = Join-Path $backendDir ".venv\Scripts\python.exe"

function Get-CommandPath {
  param([string[]]$Names)
  foreach ($name in $Names) {
    $found = Get-Command $name -ErrorAction SilentlyContinue
    if ($found) {
      return $found.Source
    }
  }
  $userProfile = $env:USERPROFILE
  if ($userProfile) {
    $bundledPnpm = Join-Path $userProfile ".cache\codex-runtimes\codex-primary-runtime\dependencies\bin\pnpm.cmd"
    if (Test-Path $bundledPnpm) {
      return $bundledPnpm
    }
  }
  return $null
}

function Get-PortOwners {
  param([int]$Port)
  $connections = Get-NetTCPConnection -LocalAddress 127.0.0.1 -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
  if (-not $connections) {
    $connections = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
  }
  foreach ($connection in $connections) {
    $process = Get-CimInstance Win32_Process -Filter "ProcessId = $($connection.OwningProcess)" -ErrorAction SilentlyContinue
    [PSCustomObject]@{
      Port = $Port
      ProcessId = $connection.OwningProcess
      Name = if ($process) { $process.Name } else { "" }
      ExecutablePath = if ($process) { $process.ExecutablePath } else { "" }
      CommandLine = if ($process) { $process.CommandLine } else { "" }
    }
  }
}

function Assert-PortFree {
  param(
    [int]$Port,
    [string]$Label
  )
  $owners = @(Get-PortOwners -Port $Port)
  if ($owners.Count -eq 0) {
    return
  }

  Write-Error @"
$Label port $Port is already in use. Refusing to start because this could open the wrong dashboard workspace.

Owning process:
$($owners | Format-List | Out-String)

Stop the process or choose another port:
  .\start-dashboard.ps1 -BackendPort 8014 -FrontendPort 5180
"@
}

function Wait-HttpOk {
  param(
    [string]$Url,
    [string]$Label,
    [int]$TimeoutSec
  )
  $deadline = (Get-Date).AddSeconds($TimeoutSec)
  $lastError = ""
  while ((Get-Date) -lt $deadline) {
    try {
      $response = Invoke-WebRequest -UseBasicParsing -Uri $Url -TimeoutSec 3
      if ($response.StatusCode -ge 200 -and $response.StatusCode -lt 500) {
        return $response
      }
    } catch {
      $lastError = $_.Exception.Message
    }
    Start-Sleep -Milliseconds 500
  }
  throw "$Label did not become ready at $Url within ${TimeoutSec}s. Last error: $lastError"
}

function Assert-FrontendLooksLocal {
  param([string]$Html)
  $normalizedRoot = ($root -replace "\\", "/")
  if ($Html -match "D:/codex.*/agent_os_mvp/frontend" -and $Html -notmatch [regex]::Escape($normalizedRoot)) {
    throw "Frontend HTML appears to come from another workspace. Expected root: $root"
  }
}

New-Item -ItemType Directory -Force -Path $logDir | Out-Null

if (-not (Test-Path $backendPython)) {
  throw "Backend virtualenv not found: $backendPython. Run dashboard install first."
}

$pnpm = Get-CommandPath -Names @("pnpm.cmd", "pnpm")
if (-not $pnpm) {
  throw "pnpm was not found in PATH. Install dashboard dependencies first."
}

if (Test-Path $stopScript) {
  & $stopScript | Out-Null
}

Assert-PortFree -Port $BackendPort -Label "Backend"
Assert-PortFree -Port $FrontendPort -Label "Frontend"

$backendOut = Join-Path $logDir "backend-$BackendPort.out.log"
$backendErr = Join-Path $logDir "backend-$BackendPort.err.log"
$frontendOut = Join-Path $logDir "frontend-$FrontendPort.out.log"
$frontendErr = Join-Path $logDir "frontend-$FrontendPort.err.log"
$backendPidFile = Join-Path $logDir "backend.pid"
$frontendPidFile = Join-Path $logDir "frontend.pid"

Remove-Item -Force $backendOut, $backendErr, $frontendOut, $frontendErr -ErrorAction SilentlyContinue

$backendProcess = Start-Process `
  -FilePath $backendPython `
  -ArgumentList @("-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "$BackendPort") `
  -WorkingDirectory $backendDir `
  -RedirectStandardOutput $backendOut `
  -RedirectStandardError $backendErr `
  -WindowStyle Hidden `
  -PassThru

Set-Content -Path $backendPidFile -Value $backendProcess.Id -Encoding ASCII

$frontendCommand = @"
`$env:VITE_API_BASE_URL = 'http://127.0.0.1:$BackendPort'
Set-Location '$frontendDir'
& '$pnpm' run dev --host 127.0.0.1 --port $FrontendPort
"@

$frontendProcess = Start-Process `
  -FilePath "powershell.exe" `
  -ArgumentList @("-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", $frontendCommand) `
  -WorkingDirectory $frontendDir `
  -RedirectStandardOutput $frontendOut `
  -RedirectStandardError $frontendErr `
  -WindowStyle Hidden `
  -PassThru

Set-Content -Path $frontendPidFile -Value $frontendProcess.Id -Encoding ASCII

try {
  Wait-HttpOk -Url "http://127.0.0.1:$BackendPort/health" -Label "Backend" -TimeoutSec $TimeoutSec | Out-Null
  $frontendResponse = Wait-HttpOk -Url "http://127.0.0.1:$FrontendPort/" -Label "Frontend" -TimeoutSec $TimeoutSec
  Assert-FrontendLooksLocal -Html $frontendResponse.Content
} catch {
  if (Test-Path $stopScript) {
    & $stopScript | Out-Null
  }
  throw
}

Write-Host "Dashboard is ready."
Write-Host "Backend:  http://127.0.0.1:$BackendPort"
Write-Host "Frontend: http://127.0.0.1:$FrontendPort"
Write-Host "Logs:     $logDir"
Write-Host "Root:     $root"

if ($Open) {
  Start-Process "http://127.0.0.1:$FrontendPort"
}
