param(
    [string]$OutputPath = ("backup-" + (Get-Date -Format "yyyyMMdd-HHmmss") + ".sql")
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$resolvedOutput = if ([System.IO.Path]::IsPathRooted($OutputPath)) {
    $OutputPath
} else {
    Join-Path $repoRoot $OutputPath
}

$outputDir = Split-Path -Parent $resolvedOutput
if ($outputDir -and -not (Test-Path $outputDir)) {
    New-Item -ItemType Directory -Path $outputDir | Out-Null
}

docker compose exec -T postgres sh -lc 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB"' | Set-Content -Encoding utf8 $resolvedOutput

Write-Host "Backup creado en $resolvedOutput"
