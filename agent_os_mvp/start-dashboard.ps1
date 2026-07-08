param(
  [int]$BackendPort = 8010,
  [int]$FrontendPort = 5174,
  [switch]$Open,
  [int]$TimeoutSec = 30,
  [switch]$SelfTestEnvironmentNormalization,
  [switch]$SelfTestSuccessOutput
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

function ConvertTo-EncodedPowerShellCommand {
  param([string]$Command)
  return [Convert]::ToBase64String([Text.Encoding]::Unicode.GetBytes($Command))
}

function Quote-PowerShellLiteral {
  param([string]$Value)
  return "'" + ($Value -replace "'", "''") + "'"
}

function Set-CleanProcessEnvironment {
  param([System.Diagnostics.ProcessStartInfo]$StartInfo)
  $environment = $StartInfo.Environment
  if ($null -eq $environment) {
    $environment = $StartInfo.EnvironmentVariables
  }
  if ($null -eq $environment) {
    throw "ProcessStartInfo environment collection is not available."
  }

  $environment.Clear()
  $seen = @{}
  $pathValue = $null

  $processEnvironment = [System.Environment]::GetEnvironmentVariables("Process")
  foreach ($nameValue in $processEnvironment.GetEnumerator()) {
    $name = [string]$nameValue.Key
    $value = [string]$nameValue.Value
    $key = $name.ToLowerInvariant()
    if ($key -eq "path") {
      if (-not $pathValue -or $name -ceq "Path") {
        $pathValue = $value
      }
      continue
    }
    if (-not $seen.ContainsKey($key)) {
      $environment[$name] = $value
      $seen[$key] = $true
    }
  }

  if ($pathValue) {
    $environment["Path"] = $pathValue
  }
}

function New-CleanPowerShellStartInfo {
  param(
    [string]$Command,
    [string]$WorkingDirectory
  )
  $startInfo = New-Object System.Diagnostics.ProcessStartInfo
  $startInfo.FileName = "powershell.exe"
  $encodedCommand = ConvertTo-EncodedPowerShellCommand -Command $Command
  $startInfo.Arguments = "-NoProfile -ExecutionPolicy Bypass -EncodedCommand $encodedCommand"
  $startInfo.WorkingDirectory = $WorkingDirectory
  $startInfo.UseShellExecute = $false
  $startInfo.CreateNoWindow = $true
  Set-CleanProcessEnvironment -StartInfo $startInfo
  return $startInfo
}

function Start-CleanPowerShellProcess {
  param(
    [string]$Command,
    [string]$WorkingDirectory
  )
  $startInfo = New-CleanPowerShellStartInfo -Command $Command -WorkingDirectory $WorkingDirectory
  return [System.Diagnostics.Process]::Start($startInfo)
}

function Format-DashboardReadyMessage {
  param(
    [int]$BackendPort,
    [int]$FrontendPort,
    [int]$BackendPid,
    [int]$FrontendPid,
    [string]$LogDir,
    [string]$Root
  )
  return @"
Dashboard is ready.
Backend:  http://127.0.0.1:$BackendPort
Frontend: http://127.0.0.1:$FrontendPort
Backend PID:  $BackendPid
Frontend PID: $FrontendPid
Logs:     $LogDir
Root:     $Root
Stop:     .\agent_os_mvp\stop-dashboard.ps1
"@
}

if ($SelfTestEnvironmentNormalization) {
  $originalPath = $env:Path
  $originalPATH = $env:PATH
  try {
    $env:Path = "C:\FirstPath"
    $env:PATH = "C:\DuplicatePath"
    $startInfo = New-CleanPowerShellStartInfo -Command "exit 0" -WorkingDirectory $root
    $environment = $startInfo.Environment
    if ($null -eq $environment) {
      $environment = $startInfo.EnvironmentVariables
    }
    $pathKeys = @($environment.Keys | Where-Object { $_ -ieq "Path" })
    if ($pathKeys.Count -ne 1 -or $pathKeys[0] -cne "Path") {
      throw "Expected exactly one canonical Path entry after normalization; got: $($pathKeys -join ', ')"
    }
    Write-Host "Environment normalization self-test passed."
    exit 0
  } finally {
    $env:Path = $originalPath
    if ($null -ne $originalPATH) {
      $env:PATH = $originalPATH
    }
  }
}

if ($SelfTestSuccessOutput) {
  $message = Format-DashboardReadyMessage -BackendPort 8010 -FrontendPort 5174 -BackendPid 1234 -FrontendPid 5678 -LogDir $logDir -Root $root
  foreach ($expected in @("Dashboard is ready.", "Backend:", "Frontend:", "Backend PID:", "Frontend PID:", "Logs:", "Stop:")) {
    if ($message -notmatch [regex]::Escape($expected)) {
      throw "Success output self-test failed; missing: $expected"
    }
  }
  Write-Host "Success output self-test passed."
  exit 0
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

$backendCommand = @"
Set-Location -LiteralPath $(Quote-PowerShellLiteral -Value $backendDir)
& $(Quote-PowerShellLiteral -Value $backendPython) -m uvicorn app.main:app --host 127.0.0.1 --port $BackendPort > $(Quote-PowerShellLiteral -Value $backendOut) 2> $(Quote-PowerShellLiteral -Value $backendErr)
"@

$backendProcess = Start-CleanPowerShellProcess -Command $backendCommand -WorkingDirectory $backendDir

Set-Content -Path $backendPidFile -Value $backendProcess.Id -Encoding ASCII

$frontendCommand = @"
`$env:VITE_API_BASE_URL = 'http://127.0.0.1:$BackendPort'
Set-Location -LiteralPath $(Quote-PowerShellLiteral -Value $frontendDir)
& $(Quote-PowerShellLiteral -Value $pnpm) run dev --host 127.0.0.1 --port $FrontendPort > $(Quote-PowerShellLiteral -Value $frontendOut) 2> $(Quote-PowerShellLiteral -Value $frontendErr)
"@

$frontendProcess = Start-CleanPowerShellProcess -Command $frontendCommand -WorkingDirectory $frontendDir

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

Write-Host (Format-DashboardReadyMessage -BackendPort $BackendPort -FrontendPort $FrontendPort -BackendPid $backendProcess.Id -FrontendPid $frontendProcess.Id -LogDir $logDir -Root $root)

if ($Open) {
  Start-Process "http://127.0.0.1:$FrontendPort"
}
