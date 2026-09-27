param(
    [Parameter(Mandatory = $true)]
    [string]$InstallDir
)

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"
$releaseBase = "https://github.com/kodexmaster7772/toy-booker/releases/latest/download"
$assetName = "KTX-Auto-Booker-Windows.zip"
$tempRoot = Join-Path $env:TEMP ("ktx-auto-booker-update-" + [guid]::NewGuid().ToString("N"))
$zipPath = Join-Path $tempRoot $assetName
$checksumPath = Join-Path $tempRoot "SHA256SUMS.txt"
$extractPath = Join-Path $tempRoot "extracted"
$backupRoot = Join-Path $InstallDir "data\update-backups"
$backupPath = Join-Path $backupRoot (Get-Date -Format "yyyyMMdd-HHmmss")
$backupCreated = $false

function Invoke-RobocopyChecked {
    param(
        [string]$Source,
        [string]$Destination,
        [string[]]$ExtraArguments
    )

    New-Item -ItemType Directory -Force -Path $Destination | Out-Null
    & robocopy $Source $Destination /E /R:2 /W:1 /NFL /NDL /NJH /NJS /NP @ExtraArguments | Out-Null
    if ($LASTEXITCODE -ge 8) {
        throw "File copy failed (robocopy exit code $LASTEXITCODE)."
    }
}

function Stop-BookerServer {
    $pidFile = Join-Path $InstallDir "data\server.pid"
    if (Test-Path $pidFile) {
        $serverPid = (Get-Content $pidFile -ErrorAction SilentlyContinue | Select-Object -First 1)
        if ($serverPid -match '^\d+$') {
            Stop-Process -Id ([int]$serverPid) -Force -ErrorAction SilentlyContinue
        }
        Remove-Item $pidFile -Force -ErrorAction SilentlyContinue
        Start-Sleep -Seconds 1
    }
}

function Start-BookerServer {
    $launcher = Join-Path $InstallDir "START_SERVER.bat"
    if (Test-Path $launcher) {
        Start-Process -FilePath $launcher -WorkingDirectory $InstallDir
    }
}

try {
    Write-Host ""
    Write-Host "KTX Auto Booker update"
    Write-Host "1/6  Stopping the server..."
    Stop-BookerServer

    Write-Host "2/6  Backing up the current version..."
    New-Item -ItemType Directory -Force -Path $backupRoot | Out-Null
    $exclusions = @(
        "/XD", ".venv", "data", ".git", "frontend\node_modules", ".pytest_cache", "__pycache__",
        "/XF", ".env", "*.pyc", "*.pyo", "*.db", "*.db-*", "*.pid", "*.log"
    )
    Invoke-RobocopyChecked -Source $InstallDir -Destination $backupPath -ExtraArguments $exclusions
    $backupCreated = $true

    Write-Host "3/6  Downloading the latest release..."
    New-Item -ItemType Directory -Force -Path $tempRoot | Out-Null
    Invoke-WebRequest -Uri "$releaseBase/$assetName" -OutFile $zipPath -UseBasicParsing
    Invoke-WebRequest -Uri "$releaseBase/SHA256SUMS.txt" -OutFile $checksumPath -UseBasicParsing

    Write-Host "4/6  Verifying the download..."
    $checksumLine = Get-Content $checksumPath | Where-Object { $_ -match [regex]::Escape($assetName) } | Select-Object -First 1
    if (-not $checksumLine) {
        throw "The release checksum is missing."
    }
    $expectedHash = (($checksumLine -split '\s+')[0]).ToUpperInvariant()
    $actualHash = (Get-FileHash -Path $zipPath -Algorithm SHA256).Hash.ToUpperInvariant()
    if ($expectedHash -ne $actualHash) {
        throw "The downloaded file did not pass SHA-256 verification."
    }

    Write-Host "5/6  Installing the update..."
    Expand-Archive -Path $zipPath -DestinationPath $extractPath -Force
    $sourcePath = Join-Path $extractPath "ktx-auto-booker-backend"
    $requiredFiles = @(
        "backend\app\main.py",
        "frontend\dist\index.html",
        "START_SERVER.bat",
        "VERSION"
    )
    foreach ($requiredFile in $requiredFiles) {
        if (-not (Test-Path (Join-Path $sourcePath $requiredFile))) {
            throw "The release is incomplete: $requiredFile"
        }
    }

    Invoke-RobocopyChecked -Source $sourcePath -Destination $InstallDir -ExtraArguments @(
        "/XD", ".git", ".github", "data", ".venv", "frontend\node_modules", ".pytest_cache", "__pycache__",
        "/XF", ".env", "*.pyc", "*.pyo", "*.db", "*.db-*", "*.pid", "*.log"
    )

    $python = Join-Path $InstallDir ".venv\Scripts\python.exe"
    if (Test-Path $python) {
        & $python -m pip install -r (Join-Path $InstallDir "requirements.txt")
        if ($LASTEXITCODE -ne 0) { throw "Python package update failed." }
        & $python -m playwright install chromium
        if ($LASTEXITCODE -ne 0) { throw "Browser component update failed." }
    }

    Write-Host "6/6  Cleaning up and restarting..."
    $version = (Get-Content (Join-Path $InstallDir "VERSION") | Select-Object -First 1).Trim()
    New-Item -ItemType Directory -Force -Path (Join-Path $InstallDir "data") | Out-Null
    "Updated to $version at $(Get-Date -Format o)" | Set-Content -Encoding UTF8 (Join-Path $InstallDir "data\last-update.txt")

    Get-ChildItem -Path $backupRoot -Directory | Sort-Object Name -Descending | Select-Object -Skip 3 | Remove-Item -Recurse -Force
    Remove-Item $tempRoot -Recurse -Force -ErrorAction SilentlyContinue
    Start-BookerServer

    Write-Host ""
    Write-Host "Update completed successfully. Version: $version" -ForegroundColor Green
    Write-Host "The server is starting now."
}
catch {
    Write-Host ""
    Write-Host "Update failed: $($_.Exception.Message)" -ForegroundColor Red
    if ($backupCreated -and (Test-Path $backupPath)) {
        Write-Host "Restoring the previous version..."
        try {
            Invoke-RobocopyChecked -Source $backupPath -Destination $InstallDir -ExtraArguments @(
                "/XD", ".git", "data", ".venv", "frontend\node_modules",
                "/XF", ".env", "*.db", "*.db-*", "*.pid", "*.log"
            )
            Write-Host "The previous version was restored." -ForegroundColor Yellow
            Start-BookerServer
        }
        catch {
            Write-Host "Automatic restore also failed: $($_.Exception.Message)" -ForegroundColor Red
        }
    }
    Write-Host "No account, database, or browser-profile data was overwritten."
}
finally {
    Remove-Item $tempRoot -Recurse -Force -ErrorAction SilentlyContinue
    Write-Host ""
    Read-Host "Press Enter to close"
    Remove-Item $PSCommandPath -Force -ErrorAction SilentlyContinue
}
