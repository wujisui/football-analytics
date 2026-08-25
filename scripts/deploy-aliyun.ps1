param(
    [Parameter(Mandatory = $true)]
    [string]$EcsHost,
    [Parameter(Mandatory = $true)]
    [string]$PackagePath,
    [string]$User = "root",
    [string]$RemoteDir = "/opt/football-analytics",
    [string]$IdentityFile = ""
)

$ErrorActionPreference = "Stop"
$PackagePath = (Resolve-Path $PackagePath).Path
if (-not (Test-Path $PackagePath -PathType Leaf)) {
    throw "Migration package not found: $PackagePath"
}

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

Write-Host "Creating $RemoteDir on $target..."
Invoke-Remote "mkdir -p $RemoteDir/backend/data/models $RemoteDir/backend/logs $RemoteDir/deploy"

Write-Host "Uploading authoritative migration package..."
& scp @sshArgs $PackagePath "${target}:/tmp/football-analytics-migration.tar.gz"
if ($LASTEXITCODE -ne 0) {
    throw "scp migration package failed"
}

Write-Host "Stopping any old backend, backing it up, and extracting package..."
Invoke-Remote @"
set -e
if [ -f $RemoteDir/docker-compose.yml ]; then
  cd $RemoteDir
  docker compose stop backend 2>/dev/null || true
fi
if [ -f $RemoteDir/backend/data/football.db ]; then
  cp $RemoteDir/backend/data/football.db \
    $RemoteDir/backend/data/football.db.pre-migration-`$(date +%Y%m%d-%H%M%S)
fi
tar -xzf /tmp/football-analytics-migration.tar.gz -C $RemoteDir
rm /tmp/football-analytics-migration.tar.gz
test -s $RemoteDir/backend/data/football.db
test -d $RemoteDir/backend/data/models
"@

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
