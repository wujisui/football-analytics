param(
    [Parameter(Mandatory = $true)]
    [string]$EcsHost,
    [string]$User = "root",
    [string]$RemoteDir = "/opt/football-analytics",
    [string]$IdentityFile = ""
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

$sshArgs = @("-o", "StrictHostKeyChecking=accept-new")
if ($IdentityFile) {
    $sshArgs += @("-i", $IdentityFile)
}
$target = "${User}@${EcsHost}"

function Invoke-Remote {
    param([string]$Command)
    & ssh @sshArgs $target $Command
    if ($LASTEXITCODE -ne 0) {
        throw "ssh failed: $Command"
    }
}

Write-Host "Exporting a consistent SQLite copy..."
Push-Location (Join-Path $Root "backend")
if (Test-Path ".\.venv\Scripts\python.exe") {
    & .\.venv\Scripts\python.exe manage.py export-sqlite
} else {
    python manage.py export-sqlite
}
if ($LASTEXITCODE -ne 0) {
    throw "export-sqlite failed"
}
Pop-Location

$exportDb = Join-Path $Root "backend\data\football.export.db"
if (-not (Test-Path $exportDb)) {
    throw "Missing $exportDb"
}

$archive = Join-Path $env:TEMP "football-analytics-src.tar"
if (Test-Path $archive) {
    Remove-Item $archive -Force
}

Write-Host "Packing source (excluding venv, node_modules, live DB)..."
& tar -cf $archive `
    --exclude=.venv `
    --exclude=node_modules `
    --exclude=frontend/dist `
    --exclude=backend/logs `
    --exclude=backend/data/football.db `
    --exclude=backend/data/football.export.db `
    --exclude=backend/data/*.db-wal `
    --exclude=backend/data/*.db-shm `
    --exclude=__pycache__ `
    --exclude=.git `
    -C $Root .

if ($LASTEXITCODE -ne 0) {
    throw "tar failed"
}

Write-Host "Creating $RemoteDir on $target..."
Invoke-Remote "mkdir -p $RemoteDir/backend/data/models $RemoteDir/backend/logs $RemoteDir/deploy"

Write-Host "Uploading source archive..."
& scp @sshArgs $archive "${target}:/tmp/football-analytics-src.tar"
if ($LASTEXITCODE -ne 0) {
    throw "scp archive failed"
}

Invoke-Remote "tar -xf /tmp/football-analytics-src.tar -C $RemoteDir && rm /tmp/football-analytics-src.tar"

Write-Host "Uploading SQLite and models..."
& scp @sshArgs $exportDb "${target}:${RemoteDir}/backend/data/football.db"
if ($LASTEXITCODE -ne 0) {
    throw "scp database failed"
}

$modelsDir = Join-Path $Root "backend\data\models"
if (Test-Path $modelsDir) {
    & scp @sshArgs -r $modelsDir "${target}:${RemoteDir}/backend/data/"
    if ($LASTEXITCODE -ne 0) {
        throw "scp models failed"
    }
}

Write-Host "Ensuring deploy/cloud.env exists..."
Invoke-Remote @"
if [ ! -f $RemoteDir/deploy/cloud.env ]; then
  cp $RemoteDir/deploy/cloud.env.example $RemoteDir/deploy/cloud.env
  sed -i 's|^CORS_ALLOW_ORIGINS=.*|CORS_ALLOW_ORIGINS=http://$EcsHost|' $RemoteDir/deploy/cloud.env
  echo "Created deploy/cloud.env with CORS_ALLOW_ORIGINS=http://$EcsHost"
fi
"@

Write-Host "Building and starting containers (this can take several minutes)..."
Invoke-Remote "cd $RemoteDir && docker compose up -d --build"

Write-Host "Done. Open http://$EcsHost/ and http://$EcsHost/api/v1/health"
Write-Host "Then edit $RemoteDir/deploy/cloud.env CORS_ALLOW_ORIGINS if the browser cannot log in."
