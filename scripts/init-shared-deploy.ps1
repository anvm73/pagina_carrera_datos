param(
    [string]$AdminEmail = "ce.iccd@utem.cl",
    [string]$AdminPassword = "",
    [string]$TrustedHosts = "localhost,127.0.0.1",
    [string]$CorsAllowOrigins = "http://localhost:4321,http://localhost:8080",
    [string]$PostgresPassword = ""
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

$repoRoot = Split-Path -Parent $PSScriptRoot
$envExamplePath = Join-Path $repoRoot "backend/.env.example"
$envPath = Join-Path $repoRoot "backend/.env"

if (-not (Test-Path $envExamplePath)) {
    throw "No existe backend/.env.example"
}

if ([string]::IsNullOrWhiteSpace($AdminPassword)) {
    $AdminPassword = New-RandomSecret -Length 24
}

if ([string]::IsNullOrWhiteSpace($PostgresPassword)) {
    $PostgresPassword = New-RandomSecret -Length 24
}

$adminTokenSecret = New-RandomSecret -Length 64
$studentTokenSecret = New-RandomSecret -Length 64

$content = Get-Content -Path $envExamplePath -Raw -Encoding UTF8
$content = $content.Replace("ADMIN_EMAIL=ce.iccd@utem.cl", "ADMIN_EMAIL=$AdminEmail")
$content = $content.Replace("ADMIN_PASSWORD=CAMBIA_ESTA_CLAVE", "ADMIN_PASSWORD=$AdminPassword")
$content = $content.Replace("ADMIN_TOKEN_SECRET=CAMBIA_ESTE_SECRETO_ADMIN", "ADMIN_TOKEN_SECRET=$adminTokenSecret")
$content = $content.Replace("STUDENT_TOKEN_SECRET=CAMBIA_ESTE_SECRETO_ESTUDIANTES", "STUDENT_TOKEN_SECRET=$studentTokenSecret")
$content = $content.Replace("POSTGRES_PASSWORD=CAMBIA_PASSWORD_POSTGRES", "POSTGRES_PASSWORD=$PostgresPassword")
$content = $content.Replace("TRUSTED_HOSTS=localhost,127.0.0.1", "TRUSTED_HOSTS=$TrustedHosts")
$content = $content.Replace("CORS_ALLOW_ORIGINS=http://localhost:4321,http://localhost:8080", "CORS_ALLOW_ORIGINS=$CorsAllowOrigins")

Set-Content -Path $envPath -Value $content -Encoding UTF8

Write-Host "Archivo creado: $envPath"
Write-Host "ADMIN_EMAIL=$AdminEmail"
Write-Host "ADMIN_PASSWORD=$AdminPassword"
Write-Host "POSTGRES_PASSWORD=$PostgresPassword"
Write-Host "TRUSTED_HOSTS=$TrustedHosts"
Write-Host "CORS_ALLOW_ORIGINS=$CorsAllowOrigins"
