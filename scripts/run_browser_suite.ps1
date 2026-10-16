# ResearchMind AI - Single-shot Browser Verification Runner
# Starts backend and frontend, executes acceptance tests in Google Chrome,
# and cleans up background processes.

$ErrorActionPreference = "Stop"
$ProjectRoot = (Resolve-Path "$PSScriptRoot\..").Path
$PythonExe = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$UvicornExe = Join-Path $ProjectRoot ".venv\Scripts\uvicorn.exe"
$ScraplingPython = "F:\dev\apps\scrapling\Scripts\python.exe"
$ChromeExe = "C:\Program Files\Google\Chrome\Application\chrome.exe"

if (-not (Test-Path $ScraplingPython)) {
    $ScraplingPython = $PythonExe
}

Write-Host "Starting temporary backend on http://127.0.0.1:8000..." -ForegroundColor Cyan
$backendProc = Start-Process -FilePath $UvicornExe -ArgumentList "backend.app.main:app", "--host", "127.0.0.1", "--port", "8000" -WorkingDirectory $ProjectRoot -PassThru -WindowStyle Hidden

Write-Host "Starting temporary frontend on http://127.0.0.1:5173..." -ForegroundColor Cyan
$frontendDir = Join-Path $ProjectRoot "frontend"
$frontendProc = Start-Process -FilePath "cmd.exe" -ArgumentList "/c", "npm", "run", "dev", "--", "--host", "127.0.0.1", "--port", "5173" -WorkingDirectory $frontendDir -PassThru -WindowStyle Hidden

$exitCode = 1
try {
    # Wait for both servers to be ready
    $ready = $false
    for ($i = 0; $i -lt 30; $i++) {
        Start-Sleep -Milliseconds 500
        try {
            $backendCheck = Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/ready" -TimeoutSec 2 -ErrorAction SilentlyContinue
            $frontendCheck = Invoke-WebRequest -Uri "http://127.0.0.1:5173" -UseBasicParsing -TimeoutSec 2 -ErrorAction SilentlyContinue
            if ($backendCheck.status -eq "ready" -and $frontendCheck.StatusCode -eq 200) {
                $ready = $true
                break
            }
        } catch {}
    }

    if (-not $ready) {
        Write-Error "Servers failed to initialize within 15 seconds."
        exit 1
    }

    Write-Host "Both servers ready. Executing browser verification suite..." -ForegroundColor Green
    & $ScraplingPython "$ProjectRoot\scripts\run_browser_verification.py" `
        --chrome-path $ChromeExe `
        --base-url "http://127.0.0.1:5173" `
        --output-dir "$ProjectRoot\artifacts\browser_verification" `
        --summary-path "$ProjectRoot\docs\browser_verification_summary.json"

    $exitCode = $LASTEXITCODE
} finally {
    Write-Host "Cleaning up server processes..." -ForegroundColor Cyan
    if ($backendProc -and -not $backendProc.HasExited) {
        Stop-Process -Id $backendProc.Id -Force -ErrorAction SilentlyContinue
    }
    if ($frontendProc -and -not $frontendProc.HasExited) {
        Stop-Process -Id $frontendProc.Id -Force -ErrorAction SilentlyContinue
    }
    # Also kill any node or uvicorn spawned under them
    Get-Process -Name "node", "uvicorn" -ErrorAction SilentlyContinue | Where-Object { $_.Path -like "*ResearchMind AI*" } | Stop-Process -Force -ErrorAction SilentlyContinue
}

exit $exitCode
