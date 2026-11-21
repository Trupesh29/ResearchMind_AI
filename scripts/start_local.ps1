# ResearchMind AI - Single-Command Local Application Launcher
param (
    [string]$HostAddress = "127.0.0.1",
    [int]$BackendPort = 8000,
    [int]$FrontendPort = 5173,
    [switch]$BackendOnly,
    [switch]$FrontendOnly
)

$ErrorActionPreference = "Stop"
$ProjectRoot = (Resolve-Path "$PSScriptRoot\..").Path

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "          ResearchMind AI — Six-Week Local MVP Launch        " -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan

Push-Location $ProjectRoot
try {
    $pythonExe = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
    $uvicornExe = Join-Path $ProjectRoot ".venv\Scripts\uvicorn.exe"

    if (-not (Test-Path $pythonExe)) {
        Write-Error "Virtual environment not found at .venv. Run scripts/setup_dev.ps1 first."
        exit 1
    }

    # Verify Database Migrations
    Write-Host "[1/3] Verifying SQLite database and migrations..." -ForegroundColor Yellow
    & $pythonExe -m alembic -c backend/alembic.ini upgrade head

    if ($LASTEXITCODE -ne 0) {
        Write-Error "Database migration check failed."
        exit 1
    }
    Write-Host "Database is up to date at latest migration head." -ForegroundColor Green

    # Launch Servers
    if ($FrontendOnly) {
        Write-Host "[2/2] Launching Frontend only on http://${HostAddress}:${FrontendPort}..." -ForegroundColor Cyan
        Set-Location (Join-Path $ProjectRoot "frontend")
        npm run dev -- --host $HostAddress --port $FrontendPort
    } elseif ($BackendOnly) {
        Write-Host "[2/2] Launching Backend only on http://${HostAddress}:${BackendPort}..." -ForegroundColor Cyan
        & $uvicornExe backend.app.main:app --host $HostAddress --port $BackendPort --reload
    } else {
        Write-Host "[2/3] Backend API will run on: http://${HostAddress}:${BackendPort}" -ForegroundColor Green
        Write-Host "[3/3] Frontend UI will run on:  http://${HostAddress}:${FrontendPort}" -ForegroundColor Green
        Write-Host ""
        Write-Host "Starting FastAPI Backend..." -ForegroundColor Cyan
        & $uvicornExe backend.app.main:app --host $HostAddress --port $BackendPort
    }
} finally {
    Pop-Location
}
