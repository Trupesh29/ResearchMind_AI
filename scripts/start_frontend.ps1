# ResearchMind AI — Frontend Development Server Launcher
$ErrorActionPreference = "Stop"

Write-Host "Starting ResearchMind AI React/Vite Frontend on http://127.0.0.1:5173..." -ForegroundColor Cyan
Push-Location frontend
npm run dev -- --host 127.0.0.1 --port 5173
Pop-Location
