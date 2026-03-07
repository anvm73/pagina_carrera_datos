[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$runtimeDir = Join-Path $root ".runtime\share-link"
$statePath = Join-Path $runtimeDir "state.json"

function Stop-ProcessOnPort([int]$Port) {
  $connections = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
  if (-not $connections) {
    return
  }
  $owningPids = $connections | Select-Object -ExpandProperty OwningProcess -Unique
  foreach ($procId in $owningPids) {
    if ($procId -and $procId -ne $PID) {
      Stop-Process -Id $procId -Force -ErrorAction SilentlyContinue
    }
  }
}

function Stop-IfRunning($Value) {
  if ($null -eq $Value) {
    return
  }
  $procId = 0
  if (-not [int]::TryParse($Value.ToString(), [ref]$procId)) {
    return
  }
  if ($procId -gt 0 -and $procId -ne $PID) {
    Stop-Process -Id $procId -Force -ErrorAction SilentlyContinue
  }
}

$backendStartedByScript = $false

if (Test-Path $statePath) {
  try {
    $state = Get-Content -Path $statePath -Raw | ConvertFrom-Json

    $startedProp = $state.PSObject.Properties["backend_started_by_script"]
    if ($startedProp -and $startedProp.Value) {
      $backendStartedByScript = $true
    }

    $pidsProp = $state.PSObject.Properties["pids"]
    if ($pidsProp) {
      $pids = $pidsProp.Value

      $frontendTunnelProp = $pids.PSObject.Properties["frontend_tunnel"]
      if ($frontendTunnelProp) { Stop-IfRunning $frontendTunnelProp.Value }

      $backendTunnelProp = $pids.PSObject.Properties["backend_tunnel"]
      if ($backendTunnelProp) { Stop-IfRunning $backendTunnelProp.Value }

      $frontendServerProp = $pids.PSObject.Properties["frontend_server"]
      if ($frontendServerProp) { Stop-IfRunning $frontendServerProp.Value }

      if ($backendStartedByScript) {
        $backendServerProp = $pids.PSObject.Properties["backend_server"]
        if ($backendServerProp) { Stop-IfRunning $backendServerProp.Value }
      }
    }
  } catch {
    Write-Host "[WARN] No se pudo leer state.json, aplicando limpieza por puertos." -ForegroundColor Yellow
  }
}

Stop-ProcessOnPort -Port 4321
Stop-ProcessOnPort -Port 20341
Stop-ProcessOnPort -Port 20342

if ($backendStartedByScript) {
  Stop-ProcessOnPort -Port 8000
}

Remove-Item -Path $runtimeDir -Recurse -Force -ErrorAction SilentlyContinue

Write-Host "[OK] Proceso de comparticion temporal detenido."
