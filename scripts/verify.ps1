# Requires: Python available as 'py' and (optionally) Node/npm for frontend checks
param(
    [switch]$SkipFrontend
)

$ErrorActionPreference = "Stop"

Write-Host "== Backend: pytest ==" -ForegroundColor Cyan
$env:PYTHONPATH = "apps/backend;apps/backend/app"
py -m pytest -q

if (-not $SkipFrontend) {
  Write-Host "== Frontend: TypeScript build & lint ==" -ForegroundColor Cyan
  if (Get-Command npm -ErrorAction SilentlyContinue) {
    Push-Location apps/frontend
    try {
      npm ci
      if (Test-Path package.json) {
        if ((Get-Content package.json -Raw) -match '"build"\s*:\s*') {
          npm run build
        } else {
          npx tsc --noEmit
        }
        if ((Get-Content package.json -Raw) -match '"lint"\s*:\s*') {
          npm run lint
        } else {
          Write-Host "No 'lint' script found; skipping ESLint." -ForegroundColor Yellow
        }
      }
    } finally {
      Pop-Location
    }
  } else {
    Write-Host "npm not found in PATH. Skipping frontend build/lint. Use Docker compose or install Node 20+ to enable." -ForegroundColor Yellow
  }
}

Write-Host "Verification finished." -ForegroundColor Green
