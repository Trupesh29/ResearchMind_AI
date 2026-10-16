# ResearchMind AI - Frontend Development Server Launcher
param (
    [string]$HostAddress = "127.0.0.1",
    [int]$Port = 5173
)

$ErrorActionPreference = "Stop"
$ProjectRoot = (Resolve-Path "$PSScriptRoot\..").Path
$FrontendDir = Join-Path $ProjectRoot "frontend"

Push-Location $FrontendDir
try {
    if (-not (Test-Path "node_modules")) {
        Write-Error "Frontend dependencies not installed. Please run powershell -File scripts/setup_dev.ps1 first."
        exit 1
    }

    Write-Host "Starting ResearchMind AI React/Vite Frontend on http://${HostAddress}:${Port}..." -ForegroundColor Cyan
    npm run dev -- --host $HostAddress --port $Port
} finally {
    Pop-Location
}
