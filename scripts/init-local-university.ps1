param(
    [string]$PublicHost = "",
    [string]$AdminEmail = "ce.iccd@utem.cl",
    [string]$AdminPassword = "",
    [int]$BackendPort = 8000,
    [int]$FrontendPort = 4321
)

$ErrorActionPreference = "Stop"

function New-RandomSecret {
    param(
        [int]$Length = 48
    )

    $allowed = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_"
    $chars = for ($i = 0; $i -lt $Length; $i += 1) {
        $allowed[(Get-Random -Minimum 0 -Maximum $allowed.Length)]
    }
    -join $chars
}

function Get-FirstLocalIpv4 {
    try {
        $candidate = Get-NetIPAddress -AddressFamily IPv4 |
            Where-Object {
                $_.IPAddress -notmatch "^(127|169\.254)\." -and
                $_.IPAddress -notmatch "^0\." -and
                $_.IPAddress
            } |
            Sort-Object InterfaceMetric, InterfaceIndex |
            Select-Object -First 1 -ExpandProperty IPAddress
        if ($candidate) {
            return $candidate
        }
    } catch {
    }

    try {
        $candidate = [System.Net.Dns]::GetHostAddresses($env:COMPUTERNAME) |
            Where-Object {
                $_.AddressFamily -eq [System.Net.Sockets.AddressFamily]::InterNetwork -and
                $_.IPAddressToString -notmatch "^(127|169\.254)\."
            } |
            Select-Object -First 1
        if ($candidate) {
            return $candidate.IPAddressToString
        }
    } catch {
    }

    "localhost"
}

function Read-EnvValue {
    param(
        [string]$Path,
        [string]$Key
    )

    if (-not (Test-Path $Path)) {
        return ""
    }

    foreach ($line in Get-Content -Path $Path -Encoding UTF8) {
        if ($line -match "^\s*#") {
            continue
        }
        $parts = $line.Split("=", 2)
        if ($parts.Count -eq 2 -and $parts[0].Trim() -eq $Key) {
            return $parts[1].Trim()
        }
    }
    ""
}

function Join-UniqueCsv {
    param(
        [string[]]$Values
    )

    $seen = @{}
    $items = foreach ($value in $Values) {
        $clean = ($value -as [string]).Trim()
        if ($clean -and -not $seen.ContainsKey($clean)) {
            $seen[$clean] = $true
            $clean
        }
    }
    $items -join ","
}

$repoRoot = Split-Path -Parent $PSScriptRoot
$backendEnvPath = Join-Path $repoRoot "backend/.env"
$frontendEnvPath = Join-Path $repoRoot "frontend/.env"

if ([string]::IsNullOrWhiteSpace($PublicHost)) {
    $PublicHost = Get-FirstLocalIpv4
}
$PublicHost = $PublicHost.Trim()

if ([string]::IsNullOrWhiteSpace($AdminEmail)) {
    $AdminEmail = "ce.iccd@utem.cl"
}
$AdminEmail = $AdminEmail.Trim().ToLowerInvariant()

if ([string]::IsNullOrWhiteSpace($AdminPassword)) {
    $existingPassword = Read-EnvValue -Path $backendEnvPath -Key "ADMIN_PASSWORD"
    if ($existingPassword) {
        $AdminPassword = $existingPassword
    } else {
        $AdminPassword = New-RandomSecret -Length 24
    }
}

$adminTokenSecret = Read-EnvValue -Path $backendEnvPath -Key "ADMIN_TOKEN_SECRET"
if (-not $adminTokenSecret) {
    $adminTokenSecret = New-RandomSecret -Length 64
}

$studentTokenSecret = Read-EnvValue -Path $backendEnvPath -Key "STUDENT_TOKEN_SECRET"
if (-not $studentTokenSecret) {
    $studentTokenSecret = New-RandomSecret -Length 64
}

$trustedHosts = Join-UniqueCsv @("localhost", "127.0.0.1", $PublicHost, $env:COMPUTERNAME)
$corsOrigins = Join-UniqueCsv @(
    "http://localhost:$FrontendPort",
    "http://127.0.0.1:$FrontendPort",
    "http://${PublicHost}:$FrontendPort"
)

$backendEnv = @"
# Archivo local generado por scripts/init-local-university.ps1.
# No subir este archivo al repositorio.

# Runtime
APP_ENV=production
UNIVERSITY_PUBLIC_HOST=$PublicHost
FRONTEND_PORT=$FrontendPort
BACKEND_PORT=$BackendPort
TRUSTED_HOSTS=$trustedHosts
CORS_ALLOW_ORIGINS=$corsOrigins
MAX_UPLOAD_SIZE_MB=12
MAX_REQUEST_SIZE_MB=20
OUTBOUND_REQUEST_TIMEOUT_S=12
ALLOWED_REMOTE_IMAGE_HOSTS=media.licdn.com,media-exp1.licdn.com,media-exp2.licdn.com,static.licdn.com,linkedin.com,www.linkedin.com
DATABASE_CONNECT_RETRIES=3
DATABASE_CONNECT_RETRY_DELAY_S=1

# Database
# Camino principal para la universidad: SQLite local versionada en backend/data/ce_iccd.db.
# No definas DATABASE_URL ni POSTGRES_* para usar SQLite.

# Ollama
OLLAMA_URL=http://localhost:11434
CHAT_MODEL=llama3.1:8b
EMBED_MODEL=nomic-embed-text
OLLAMA_TIMEOUT_S=240

# Admin
ADMIN_EMAIL=$AdminEmail
ADMIN_PASSWORD=$AdminPassword
ADMIN_TOKEN_SECRET=$adminTokenSecret
ADMIN_TOKEN_TTL_S=86400

# Student accounts
STUDENT_TOKEN_SECRET=$studentTokenSecret
STUDENT_TOKEN_TTL_S=2592000
STUDENT_PASSWORD_ITERATIONS=260000
"@

$frontendEnv = @"
# Archivo local generado por scripts/init-local-university.ps1.
# No subir este archivo al repositorio.
PUBLIC_CHATBOT_API_URL=http://${PublicHost}:$BackendPort/chat
PUBLIC_PROJECTS_API_URL=http://${PublicHost}:$BackendPort
"@

Set-Content -Path $backendEnvPath -Value $backendEnv -Encoding ASCII
Set-Content -Path $frontendEnvPath -Value $frontendEnv -Encoding ASCII

Write-Host "Configuracion local creada:"
Write-Host "  backend/.env"
Write-Host "  frontend/.env"
Write-Host ""
Write-Host "URLs esperadas:"
Write-Host "  Frontend local: http://localhost:$FrontendPort"
Write-Host "  Frontend red:   http://${PublicHost}:$FrontendPort"
Write-Host "  Backend local:  http://localhost:$BackendPort"
Write-Host "  Backend red:    http://${PublicHost}:$BackendPort"
Write-Host ""
Write-Host "Cuenta admin local:"
Write-Host "  ADMIN_EMAIL=$AdminEmail"
Write-Host "  ADMIN_PASSWORD=$AdminPassword"
Write-Host ""
Write-Host "La clave queda guardada en backend/.env, que esta ignorado por Git."
