# ResearchMind AI — Backend Development Server Launcher
$ErrorActionPreference = "Stop"

Write-Host "Starting ResearchMind AI FastAPI Backend on http://127.0.0.1:8000..." -ForegroundColor Cyan
.venv\Scripts\uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --reload
