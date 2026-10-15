# ResearchMind AI — Local Development Setup Script
$ErrorActionPreference = "Stop"

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host " ResearchMind AI — Development Environment Setup" -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan

# 1. Check or Create Virtual Environment
if (-not (Test-Path ".venv")) {
    Write-Host "[1/4] Creating virtual environment (.venv)..." -ForegroundColor Yellow
    uv venv --python 3.12 .venv
} else {
    Write-Host "[1/4] Virtual environment exists." -ForegroundColor Green
}

# 2. Install Python Dependencies
Write-Host "[2/4] Installing backend and testing dependencies..." -ForegroundColor Yellow
uv pip install -r backend/requirements.txt

# 3. Run Alembic Database Migrations
Write-Host "[3/4] Running Alembic database migrations..." -ForegroundColor Yellow
.venv\Scripts\alembic -c backend/alembic.ini upgrade head

# 4. Install Frontend Dependencies
Write-Host "[4/4] Installing frontend dependencies..." -ForegroundColor Yellow
Push-Location frontend
npm install
Pop-Location

Write-Host "==========================================================" -ForegroundColor Green
Write-Host " Setup complete! Start servers using:" -ForegroundColor Green
Write-Host "  Backend:  powershell -File scripts/start_backend.ps1" -ForegroundColor Cyan
Write-Host "  Frontend: powershell -File scripts/start_frontend.ps1" -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Green
