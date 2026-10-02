$ErrorActionPreference = 'Stop'
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
Push-Location $projectRoot
try {
    $python = Join-Path $projectRoot '.venv/Scripts/python.exe'
    if (-not (Test-Path -LiteralPath $python)) {
        throw 'Project Python environment missing. Recreate .venv from requirements.txt.'
    }
    & $python -m tools.deployment_preflight
    if ($LASTEXITCODE -ne 0) { throw 'Deployment preflight failed.' }
    & $python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --workers 1
    exit $LASTEXITCODE
} finally {
    Pop-Location
}
