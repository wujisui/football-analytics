param(
    [string]$OutputPath = "",
    [string]$Python = ""
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$SourceDb = Join-Path $Root "backend\data\football.db"
$ModelsDir = Join-Path $Root "backend\data\models"

if (-not (Test-Path $SourceDb -PathType Leaf)) {
    throw "Authoritative database not found: $SourceDb"
}
if (-not (Test-Path $ModelsDir -PathType Container)) {
    throw "Authoritative model directory not found: $ModelsDir"
}

if (-not $Python) {
    $venvPython = Join-Path $Root "backend\.venv\Scripts\python.exe"
    $Python = if (Test-Path $venvPython) { $venvPython } else { "python" }
}
if (-not $OutputPath) {
    $stamp = Get-Date -Format "yyyyMMdd-HHmmss"
    $OutputPath = Join-Path $Root "football-analytics-migration-$stamp.tar.gz"
}
$OutputPath = [System.IO.Path]::GetFullPath($OutputPath)

$TempRoot = Join-Path $env:TEMP ("football-migration-" + [guid]::NewGuid())
$Stage = Join-Path $TempRoot "stage"
$BackupDb = Join-Path $TempRoot "football.db"
$SourceTar = Join-Path $TempRoot "source.tar"

try {
    New-Item -ItemType Directory -Path $Stage -Force | Out-Null

    Write-Host "Creating a consistent SQLite backup from the authoritative device..."
    $backupCode = @'
import sqlite3
import sys
from pathlib import Path

source, destination = sys.argv[1], sys.argv[2]
src = sqlite3.connect(f"{Path(source).resolve().as_uri()}?mode=ro", uri=True)
try:
    dst = sqlite3.connect(destination)
    try:
        src.backup(dst)
        result = dst.execute("PRAGMA integrity_check").fetchone()
        if not result or result[0] != "ok":
            raise RuntimeError(f"SQLite integrity_check failed: {result}")
    finally:
        dst.close()
finally:
    src.close()
'@
    & $Python -c $backupCode $SourceDb $BackupDb
    if ($LASTEXITCODE -ne 0) {
        throw "SQLite backup failed"
    }

    Write-Host "Packing authoritative source code..."
    & tar -cf $SourceTar `
        --exclude=.git `
        --exclude=.idea `
        --exclude=.vscode `
        --exclude=.venv `
        --exclude=venv `
        --exclude=node_modules `
        --exclude=frontend/dist `
        --exclude=backend/logs `
        --exclude=backend/.env `
        --exclude=backend/secrets.local.env `
        --exclude=backend/*.local.env `
        --exclude=backend/data/football.db `
        --exclude=backend/data/football.export.db `
        --exclude=backend/data/*.db-journal `
        --exclude=backend/data/*.db-wal `
        --exclude=backend/data/*.db-shm `
        --exclude=backend/data/models `
        --exclude=deploy/cloud.env `
        --exclude=__pycache__ `
        -C $Root .
    if ($LASTEXITCODE -ne 0) {
        throw "Source packing failed"
    }
    & tar -xf $SourceTar -C $Stage
    if ($LASTEXITCODE -ne 0) {
        throw "Source extraction to staging failed"
    }

    $StageData = Join-Path $Stage "backend\data"
    New-Item -ItemType Directory -Path $StageData -Force | Out-Null
    Copy-Item $BackupDb (Join-Path $StageData "football.db") -Force
    Copy-Item $ModelsDir (Join-Path $StageData "models") -Recurse -Force

    $gitCommit = ""
    if (Test-Path (Join-Path $Root ".git")) {
        $gitCommit = (& git -C $Root rev-parse HEAD 2>$null)
    }
    $dbHash = (Get-FileHash $BackupDb -Algorithm SHA256).Hash
    $modelFiles = @(
        Get-ChildItem (Join-Path $StageData "models") -File -Recurse |
            ForEach-Object {
                [ordered]@{
                    path = $_.FullName.Substring($Stage.Length + 1).Replace("\", "/")
                    bytes = $_.Length
                    sha256 = (Get-FileHash $_.FullName -Algorithm SHA256).Hash
                }
            }
    )
    $manifest = [ordered]@{
        created_at = (Get-Date).ToUniversalTime().ToString("o")
        source_host = $env:COMPUTERNAME
        git_commit = $gitCommit
        database = [ordered]@{
            path = "backend/data/football.db"
            bytes = (Get-Item $BackupDb).Length
            sha256 = $dbHash
        }
        models = $modelFiles
    }
    $manifest | ConvertTo-Json -Depth 6 |
        Set-Content (Join-Path $Stage "migration-manifest.json") -Encoding utf8

    Write-Host "Creating migration archive..."
    if (Test-Path $OutputPath) {
        Remove-Item $OutputPath -Force
    }
    & tar -czf $OutputPath -C $Stage .
    if ($LASTEXITCODE -ne 0) {
        throw "Migration archive creation failed"
    }

    $sizeMb = (Get-Item $OutputPath).Length / 1MB
    Write-Host ("Created {0} ({1:N1} MB)" -f $OutputPath, $sizeMb)
    Write-Host "Upload this single file to the cloud drive. Do not upload the live DB separately."
}
finally {
    Remove-Item $TempRoot -Recurse -Force -ErrorAction SilentlyContinue
}
