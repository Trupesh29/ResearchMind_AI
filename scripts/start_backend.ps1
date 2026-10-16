# ResearchMind AI - Backend Development Server Launcher
param (
    [string]$HostAddress = "127.0.0.1",
    [int]$Port = 8000
)

$ErrorActionPreference = "Stop"
$ProjectRoot = (Resolve-Path "$PSScriptRoot\..").Path

Push-Location $ProjectRoot
try {
    $uvicornExe = Join-Path $ProjectRoot ".venv\Scripts\uvicorn.exe"
    if (-not (Test-Path $uvicornExe)) {
        Write-Error "Virtual environment not found at .venv. Please run powershell -File scripts/setup_dev.ps1 first."
        exit 1
    }

    Write-Host "Starting ResearchMind AI FastAPI Backend on http://${HostAddress}:${Port}..." -ForegroundColor Cyan
    & $uvicornExe backend.app.main:app --host $HostAddress --port $Port --reload
} finally {
    Pop-Location
}
