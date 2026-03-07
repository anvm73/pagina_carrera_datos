param(
    [Parameter(Mandatory = $true)]
    [string]$InputPath
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$resolvedInput = if ([System.IO.Path]::IsPathRooted($InputPath)) {
    $InputPath
} else {
    Join-Path $repoRoot $InputPath
}

if (-not (Test-Path $resolvedInput)) {
    throw "No existe el archivo: $resolvedInput"
}

Get-Content -Raw $resolvedInput | docker compose exec -T postgres sh -lc 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"'

Write-Host "Backup restaurado desde $resolvedInput"
