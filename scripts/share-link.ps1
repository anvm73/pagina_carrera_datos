[CmdletBinding()]
param(
  [int]$FrontendPort = 4321,
  [int]$BackendPort = 8000,
  [switch]$SkipBackendStart,
  [switch]$NoOpenBrowser
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$frontendDir = Join-Path $root "frontend"
$backendDir = Join-Path $root "backend"
$runtimeDir = Join-Path $root ".runtime\share-link"
$statePath = Join-Path $runtimeDir "state.json"
$cloudflaredPath = Join-Path $root "cloudflared.exe"
$frontendEnvPath = Join-Path $frontendDir ".env"
$frontendEnvExisted = $false
$frontendEnvOriginal = ""

if (-not (Test-Path (Join-Path $frontendDir "package.json"))) {
  throw "No se encontro frontend/package.json en $frontendDir"
}
if (-not (Test-Path (Join-Path $backendDir "requirements.txt"))) {
  throw "No se encontro backend/requirements.txt en $backendDir"
}

function Write-Info([string]$Message) {
  Write-Host "[INFO] $Message" -ForegroundColor Cyan
}

function Write-Ok([string]$Message) {
  Write-Host "[OK]   $Message" -ForegroundColor Green
}

function Start-DetachedProcess(
  [string]$FilePath,
  [string[]]$ArgumentList,
  [string]$WorkingDirectory,
  [string]$OutLogPath,
  [string]$ErrLogPath
) {
  Remove-Item $OutLogPath, $ErrLogPath -Force -ErrorAction SilentlyContinue
  return Start-Process `
    -FilePath $FilePath `
    -ArgumentList $ArgumentList `
    -WorkingDirectory $WorkingDirectory `
    -RedirectStandardOutput $OutLogPath `
    -RedirectStandardError $ErrLogPath `
    -WindowStyle Hidden `
    -PassThru
}

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

function Wait-HttpReady([string]$Url, [int]$TimeoutSec = 60) {
  $deadline = (Get-Date).AddSeconds($TimeoutSec)
  while ((Get-Date) -lt $deadline) {
    try {
      $response = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 6
      if ($response.StatusCode -ge 200 -and $response.StatusCode -lt 500) {
        return
      }
    } catch {
      # Reintento
    }
    Start-Sleep -Milliseconds 700
  }
  throw "No fue posible conectar con $Url dentro de $TimeoutSec segundos."
}

function Wait-TunnelUrl([string]$LogPath, [int]$TimeoutSec = 90) {
  $deadline = (Get-Date).AddSeconds($TimeoutSec)
  $regex = "https://[a-z0-9-]+\.trycloudflare\.com"
  while ((Get-Date) -lt $deadline) {
    if (Test-Path $LogPath) {
      $raw = Get-Content -Path $LogPath -Raw -ErrorAction SilentlyContinue
      if ($raw) {
        $match = [regex]::Match($raw, $regex)
        if ($match.Success) {
          return $match.Value
        }
      }
    }
    Start-Sleep -Milliseconds 700
  }
  throw "No se pudo obtener la URL del tunel desde $LogPath"
}

function Start-CloudflaredTunnel(
  [string]$CloudflaredExe,
  [string]$LocalUrl,
  [string]$OutLogPath,
  [string]$ErrLogPath,
  [int]$MetricsPort
) {
  return Start-DetachedProcess `
    -FilePath $CloudflaredExe `
    -ArgumentList @("tunnel", "--url", $LocalUrl, "--no-autoupdate", "--metrics", "127.0.0.1:$MetricsPort") `
    -WorkingDirectory $root `
    -OutLogPath $OutLogPath `
    -ErrLogPath $ErrLogPath
}

if (-not (Test-Path $runtimeDir)) {
  New-Item -ItemType Directory -Path $runtimeDir | Out-Null
}

if (Test-Path $frontendEnvPath) {
  $frontendEnvExisted = $true
  $frontendEnvOriginal = Get-Content -Path $frontendEnvPath -Raw -ErrorAction SilentlyContinue
}

$startedByScript = @{
  backend_server = $false
}
$processes = @{
  backend_server = $null
  frontend_server = $null
  backend_tunnel = $null
  frontend_tunnel = $null
}

try {
  Write-Info "Preparando entorno temporal de comparticion..."
  Stop-ProcessOnPort -Port $FrontendPort
  Stop-ProcessOnPort -Port 20341
  Stop-ProcessOnPort -Port 20342

  if (-not (Get-Command npm -ErrorAction SilentlyContinue)) {
    throw "npm no esta disponible en PATH."
  }

  if (-not (Test-Path $cloudflaredPath)) {
    Write-Info "Descargando cloudflared.exe..."
    Invoke-WebRequest `
      -Uri "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe" `
      -OutFile $cloudflaredPath
  }

  $backendHealthy = $false
  try {
    $healthResponse = Invoke-WebRequest -Uri "http://localhost:$BackendPort/health" -UseBasicParsing -TimeoutSec 4
    $backendHealthy = $healthResponse.StatusCode -eq 200
  } catch {
    $backendHealthy = $false
  }

  if (-not $backendHealthy) {
    if ($SkipBackendStart) {
      throw "El backend no responde en http://localhost:$BackendPort/health y se uso -SkipBackendStart."
    }

    $venvPython = Join-Path $backendDir ".venv\Scripts\python.exe"
    $pythonCmd = if (Test-Path $venvPython) { $venvPython } else { "python" }
    if (-not (Get-Command $pythonCmd -ErrorAction SilentlyContinue) -and -not (Test-Path $venvPython)) {
      throw "No se encontro Python para iniciar backend."
    }

    $backendOutLog = Join-Path $runtimeDir "backend.out.log"
    $backendErrLog = Join-Path $runtimeDir "backend.err.log"
    Write-Info "Iniciando backend local en puerto $BackendPort..."
    $processes.backend_server = Start-DetachedProcess `
      -FilePath $pythonCmd `
      -ArgumentList @("-m", "uvicorn", "app.api:app", "--host", "0.0.0.0", "--port", "$BackendPort") `
      -WorkingDirectory $backendDir `
      -OutLogPath $backendOutLog `
      -ErrLogPath $backendErrLog
    $startedByScript.backend_server = $true

    Wait-HttpReady -Url "http://localhost:$BackendPort/health" -TimeoutSec 80
    Write-Ok "Backend local disponible."
  } else {
    Write-Ok "Backend local ya estaba corriendo."
  }

  $backendTunnelOutLog = Join-Path $runtimeDir "cloudflared-backend.out.log"
  $backendTunnelErrLog = Join-Path $runtimeDir "cloudflared-backend.err.log"
  Write-Info "Abriendo tunel publico para backend..."
  $processes.backend_tunnel = Start-CloudflaredTunnel `
    -CloudflaredExe $cloudflaredPath `
    -LocalUrl "http://localhost:$BackendPort" `
    -OutLogPath $backendTunnelOutLog `
    -ErrLogPath $backendTunnelErrLog `
    -MetricsPort 20342
  $backendPublicUrl = Wait-TunnelUrl -LogPath $backendTunnelErrLog
  Wait-HttpReady -Url "$backendPublicUrl/health" -TimeoutSec 80
  Write-Ok "Backend publico listo: $backendPublicUrl"

  @(
    "PUBLIC_CHATBOT_API_URL=$backendPublicUrl/chat"
    "PUBLIC_PROJECTS_API_URL=$backendPublicUrl"
  ) | Set-Content -Path $frontendEnvPath -Encoding ascii

  Write-Info "Compilando frontend..."
  Push-Location $frontendDir
  try {
    & npm run build
    if ($LASTEXITCODE -ne 0) {
      throw "Fallo npm run build"
    }
  } finally {
    Pop-Location
  }
  if ($frontendEnvExisted) {
    Set-Content -Path $frontendEnvPath -Value $frontendEnvOriginal -Encoding ascii
  } else {
    Remove-Item -Path $frontendEnvPath -Force -ErrorAction SilentlyContinue
  }
  Write-Ok "Frontend compilado."

  $frontendServeOutLog = Join-Path $runtimeDir "frontend-serve.out.log"
  $frontendServeErrLog = Join-Path $runtimeDir "frontend-serve.err.log"
  $npxCmd = (Get-Command npx.cmd -ErrorAction SilentlyContinue).Source
  if (-not $npxCmd) {
    $npxCmd = (Get-Command npx -ErrorAction SilentlyContinue).Source
  }
  if (-not $npxCmd) {
    throw "No se encontro npx para iniciar frontend."
  }
  Write-Info "Iniciando servidor estatico del frontend..."
  $processes.frontend_server = Start-DetachedProcess `
    -FilePath $npxCmd `
    -ArgumentList @("serve", "dist", "-l", "$FrontendPort") `
    -WorkingDirectory $frontendDir `
    -OutLogPath $frontendServeOutLog `
    -ErrLogPath $frontendServeErrLog
  Wait-HttpReady -Url "http://localhost:$FrontendPort" -TimeoutSec 60
  Write-Ok "Frontend local disponible."

  $frontendTunnelOutLog = Join-Path $runtimeDir "cloudflared-frontend.out.log"
  $frontendTunnelErrLog = Join-Path $runtimeDir "cloudflared-frontend.err.log"
  Write-Info "Abriendo tunel publico para frontend..."
  $processes.frontend_tunnel = Start-CloudflaredTunnel `
    -CloudflaredExe $cloudflaredPath `
    -LocalUrl "http://localhost:$FrontendPort" `
    -OutLogPath $frontendTunnelOutLog `
    -ErrLogPath $frontendTunnelErrLog `
    -MetricsPort 20341
  $frontendPublicUrl = Wait-TunnelUrl -LogPath $frontendTunnelErrLog
  Wait-HttpReady -Url $frontendPublicUrl -TimeoutSec 80
  Write-Ok "Frontend publico listo: $frontendPublicUrl"

  $state = [ordered]@{
    created_at = (Get-Date).ToString("o")
    frontend_url = $frontendPublicUrl
    backend_url = $backendPublicUrl
    backend_started_by_script = $startedByScript.backend_server
    pids = [ordered]@{
      backend_server = if ($processes.backend_server) { $processes.backend_server.Id } else { $null }
      frontend_server = if ($processes.frontend_server) { $processes.frontend_server.Id } else { $null }
      backend_tunnel = if ($processes.backend_tunnel) { $processes.backend_tunnel.Id } else { $null }
      frontend_tunnel = if ($processes.frontend_tunnel) { $processes.frontend_tunnel.Id } else { $null }
    }
  }
  ($state | ConvertTo-Json -Depth 5) | Set-Content -Path $statePath -Encoding utf8

  Write-Host ""
  Write-Host "==============================" -ForegroundColor Green
  Write-Host "Links listos para compartir" -ForegroundColor Green
  Write-Host "Frontend: $frontendPublicUrl"
  Write-Host "Backend : $backendPublicUrl"
  Write-Host "==============================" -ForegroundColor Green
  Write-Host ""
  Write-Host "Para detener todo: .\detener_compartir.bat"
  if (-not $NoOpenBrowser) {
    Write-Info "Abriendo frontend en navegador..."
    try {
      Start-Process -FilePath $frontendPublicUrl -ErrorAction Stop | Out-Null
      Write-Ok "Navegador abierto."
    } catch {
      Write-Host "[WARN] No se pudo abrir el navegador automaticamente. Abre manualmente: $frontendPublicUrl" -ForegroundColor Yellow
    }
  }
} catch {
  $errorMessage = $_.Exception.Message

  if ($frontendEnvExisted) {
    Set-Content -Path $frontendEnvPath -Value $frontendEnvOriginal -Encoding ascii
  } else {
    Remove-Item -Path $frontendEnvPath -Force -ErrorAction SilentlyContinue
  }

  foreach ($key in @("frontend_tunnel", "backend_tunnel", "frontend_server")) {
    $proc = $processes[$key]
    if ($proc) {
      Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
    }
  }
  if ($startedByScript.backend_server -and $processes.backend_server) {
    Stop-Process -Id $processes.backend_server.Id -Force -ErrorAction SilentlyContinue
  }

  throw "Error al compartir el proyecto: $errorMessage"
}
