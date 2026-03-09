$ErrorActionPreference = "Stop"

if (!(Test-Path ".venv")) {
    Write-Host "Virtual environment not found"
    exit 1
}

.venv\Scripts\activate.ps1

pytest -q --maxfail=1
