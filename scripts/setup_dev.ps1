# ResearchMind AI - Local Development Setup Script
$ErrorActionPreference = "Stop"

$ProjectRoot = (Resolve-Path "$PSScriptRoot\..").Path
Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host " ResearchMind AI - Development Environment Setup" -ForegroundColor Cyan
Write-Host " Project Root: $ProjectRoot" -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan

Push-Location $ProjectRoot
try {
    # 0. Check Required Host Tools
    if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
        Write-Error "Required tool 'uv' was not found on PATH. Please install uv (https://github.com/astral-sh/uv)."
        exit 1
    }
    if (-not (Get-Command npm -ErrorAction SilentlyContinue)) {
        Write-Error "Required tool 'npm' was not found on PATH. Please install Node.js."
        exit 1
    }

    # 1. Check or Create Virtual Environment
    $venvPath = Join-Path $ProjectRoot ".venv"
    if (-not (Test-Path $venvPath)) {
        Write-Host "[1/4] Creating virtual environment (.venv)..." -ForegroundColor Yellow
        uv venv --python 3.12 .venv
        if ($LASTEXITCODE -ne 0) {
            Write-Error "Failed to create virtual environment."
            exit $LASTEXITCODE
        }
    } else {
        Write-Host "[1/4] Virtual environment exists." -ForegroundColor Green
    }

    # 2. Install Python Dependencies
    Write-Host "[2/4] Installing backend and testing dependencies..." -ForegroundColor Yellow
    uv pip install -r backend/requirements.txt
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Failed to install Python dependencies."
        exit $LASTEXITCODE
    }

    # 3. Run Alembic Database Migrations
    Write-Host "[3/4] Running Alembic database migrations..." -ForegroundColor Yellow
    $alembicExe = Join-Path $venvPath "Scripts\alembic.exe"
    & $alembicExe -c backend/alembic.ini upgrade head
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Failed to run Alembic database migrations."
        exit $LASTEXITCODE
    }

    # 4. Install Frontend Dependencies (using reproducible npm ci / lockfile)
    Write-Host "[4/4] Installing frontend dependencies via lockfile..." -ForegroundColor Yellow
    Push-Location frontend
    try {
        if (Test-Path "package-lock.json") {
            npm ci
        } else {
            npm install
        }
        if ($LASTEXITCODE -ne 0) {
            Write-Error "Failed to install frontend dependencies."
            exit $LASTEXITCODE
        }
    } finally {
        Pop-Location
    }

    Write-Host "==========================================================" -ForegroundColor Green
    Write-Host " Setup complete! Start servers using:" -ForegroundColor Green
    Write-Host "  Backend:  powershell -File scripts/start_backend.ps1" -ForegroundColor Cyan
    Write-Host "  Frontend: powershell -File scripts/start_frontend.ps1" -ForegroundColor Cyan
    Write-Host "==========================================================" -ForegroundColor Green
} finally {
    Pop-Location
}
