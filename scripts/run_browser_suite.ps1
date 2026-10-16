# ResearchMind AI - Single-shot Browser Verification Runner
# Starts backend and frontend, executes acceptance tests in Google Chrome,
# and cleans up ONLY the processes created by this invocation.

[CmdletBinding()]
param(
    [switch]$Attach,
    [string]$BackendCommand = "",
    [string]$FrontendCommand = "",
    [string]$RunnerCommand = "",
    [int]$BackendPort = 8000,
    [int]$FrontendPort = 5173,
    [int]$TimeoutSeconds = 15,
    [string]$ChromePath = "C:\Program Files\Google\Chrome\Application\chrome.exe"
)

$ErrorActionPreference = "Stop"
$ProjectRoot = (Resolve-Path "$PSScriptRoot\..").Path
$PythonExe = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$UvicornExe = Join-Path $ProjectRoot ".venv\Scripts\uvicorn.exe"
$ScraplingPython = "F:\dev\apps\scrapling\Scripts\python.exe"

if (-not (Test-Path $ScraplingPython)) {
    $ScraplingPython = $PythonExe
}

function Test-PortListening([int]$port) {
    try {
        $conn = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
        if ($null -ne $conn) {
            return $true
        }
    } catch {}

    try {
        $client = New-Object System.Net.Sockets.TcpClient
        $async = $client.BeginConnect("127.0.0.1", $port, $null, $null)
        $wait = $async.AsyncWaitHandle.WaitOne(400, $false)
        if ($wait -and $client.Connected) {
            $client.EndConnect($async)
            $client.Close()
            return $true
        }
        $client.Close()
    } catch {}

    return $false
}

function Stop-OwnedProcessTree([int]$targetPid) {
    if (-not $targetPid -or $targetPid -le 0) { return }

    # 1. Kill process tree using Windows taskkill
    try {
        & taskkill.exe /PID $targetPid /T /F 2>$null | Out-Null
    } catch {}

    # 2. Defensive check for any lingering descendant processes
    try {
        $children = Get-CimInstance Win32_Process -Filter "ParentProcessId = $targetPid" -ErrorAction SilentlyContinue
        foreach ($child in $children) {
            Stop-OwnedProcessTree -targetPid $child.ProcessId
        }
        Stop-Process -Id $targetPid -Force -ErrorAction SilentlyContinue
    } catch {}
}

$backendProc = $null
$frontendProc = $null
$envModified = $false
$prevBackendUrl = [Environment]::GetEnvironmentVariable("VITE_BACKEND_URL", "Process")
$exitCode = 1

try {
    if ($Attach) {
        Write-Host "Attach mode: verifying existing servers on ports $BackendPort and $FrontendPort..." -ForegroundColor Cyan
        if (-not (Test-PortListening $BackendPort)) {
            throw "Attach mode failed: No process is listening on port $BackendPort."
        }
        if (-not (Test-PortListening $FrontendPort)) {
            throw "Attach mode failed: No process is listening on port $FrontendPort."
        }
    } else {
        # Strict port protection: ensure ports are free before starting anything
        if (Test-PortListening $BackendPort) {
            throw "Port $BackendPort is already occupied by a pre-existing server. Aborting to avoid conflicts. Use -Attach to run against running servers."
        }
        if (Test-PortListening $FrontendPort) {
            throw "Port $FrontendPort is already occupied by a pre-existing server. Aborting to avoid conflicts. Use -Attach to run against running servers."
        }

        # 1. Launch Backend
        Write-Host "Starting temporary backend on http://127.0.0.1:$BackendPort..." -ForegroundColor Cyan
        if ($BackendCommand) {
            $backendProc = Start-Process -FilePath "powershell.exe" -ArgumentList "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", $BackendCommand -WorkingDirectory $ProjectRoot -PassThru -WindowStyle Hidden
        } else {
            $backendProc = Start-Process -FilePath $UvicornExe -ArgumentList "backend.app.main:app", "--host", "127.0.0.1", "--port", "$BackendPort" -WorkingDirectory $ProjectRoot -PassThru -WindowStyle Hidden
        }

        Start-Sleep -Milliseconds 300
        if ($backendProc.HasExited) {
            throw "Backend process exited prematurely with code $($backendProc.ExitCode)."
        }

        # Propagate backend URL to Vite development server
        $env:VITE_BACKEND_URL = "http://127.0.0.1:$BackendPort"
        $envModified = $true

        # 2. Launch Frontend
        Write-Host "Starting temporary frontend on http://127.0.0.1:$FrontendPort..." -ForegroundColor Cyan
        $frontendDir = Join-Path $ProjectRoot "frontend"
        if ($FrontendCommand) {
            $frontendProc = Start-Process -FilePath "powershell.exe" -ArgumentList "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", $FrontendCommand -WorkingDirectory $frontendDir -PassThru -WindowStyle Hidden
        } else {
            $frontendProc = Start-Process -FilePath "cmd.exe" -ArgumentList "/c", "npm", "run", "dev", "--", "--host", "127.0.0.1", "--port", "$FrontendPort", "--strictPort" -WorkingDirectory $frontendDir -PassThru -WindowStyle Hidden
        }

        Start-Sleep -Milliseconds 300
        if ($frontendProc.HasExited) {
            throw "Frontend process exited prematurely with code $($frontendProc.ExitCode)."
        }
    }

    # 3. Wait for readiness
    Write-Host "Waiting for servers to become ready (timeout: $TimeoutSeconds s)..." -ForegroundColor Cyan
    $ready = $false
    $maxAttempts = [int]($TimeoutSeconds * 2)
    for ($i = 0; $i -lt $maxAttempts; $i++) {
        Start-Sleep -Milliseconds 500

        if (-not $Attach) {
            if ($backendProc -and $backendProc.HasExited) {
                throw "Backend process crashed during startup with code $($backendProc.ExitCode)."
            }
            if ($frontendProc -and $frontendProc.HasExited) {
                throw "Frontend process crashed during startup with code $($frontendProc.ExitCode)."
            }
        }

        try {
            $backendCheck = Invoke-RestMethod -Uri "http://127.0.0.1:$BackendPort/api/ready" -TimeoutSec 2 -ErrorAction SilentlyContinue
            $frontendCheck = Invoke-WebRequest -Uri "http://127.0.0.1:$FrontendPort" -UseBasicParsing -TimeoutSec 2 -ErrorAction SilentlyContinue
            if ($backendCheck.status -eq "ready" -and $frontendCheck.StatusCode -eq 200) {
                $ready = $true
                break
            }
        } catch {}
    }

    if (-not $ready) {
        throw "Servers failed to become ready within $TimeoutSeconds seconds."
    }

    # 4. Execute Browser Verification Suite
    Write-Host "Both servers ready. Executing browser verification..." -ForegroundColor Green
    if ($RunnerCommand) {
        Invoke-Expression $RunnerCommand
        $exitCode = $LASTEXITCODE
    } else {
        & $ScraplingPython "$ProjectRoot\scripts\run_browser_verification.py" `
            --chrome-path $ChromePath `
            --base-url "http://127.0.0.1:$FrontendPort" `
            --output-dir "$ProjectRoot\artifacts\browser_verification" `
            --summary-path "$ProjectRoot\docs\browser_verification_summary.json"
        $exitCode = $LASTEXITCODE
    }
} catch {
    Write-Error $_
    $exitCode = 1
} finally {
    Write-Host "Cleaning up owned processes..." -ForegroundColor Cyan
    if ($backendProc) {
        Stop-OwnedProcessTree -targetPid $backendProc.Id
    }
    if ($frontendProc) {
        Stop-OwnedProcessTree -targetPid $frontendProc.Id
    }

    # Restore previous environment state if modified by this invocation
    if ($envModified) {
        if ($null -ne $prevBackendUrl) {
            $env:VITE_BACKEND_URL = $prevBackendUrl
        } else {
            [Environment]::SetEnvironmentVariable("VITE_BACKEND_URL", $null, "Process")
        }
    }
}

exit $exitCode
