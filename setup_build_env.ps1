# Setup Build Environment for Tunevia
# Run this to create a clean virtual environment for Nuitka compilation

$VENV_DIR = "venv_build"

if (-not (Test-Path $VENV_DIR)) {
    Write-Host "Creating virtual environment in $VENV_DIR..." -ForegroundColor Cyan
    python -m venv $VENV_DIR
}

Write-Host "Activating virtual environment..." -ForegroundColor Cyan
& ".\$VENV_DIR\Scripts\Activate.ps1"

Write-Host "Installing dependencies from requirements.txt..." -ForegroundColor Cyan
pip install -r requirements.txt

# Explicitly ensure ytmusicapi and build tools are installed
Write-Host "Installing build tools (Nuitka, zstandard, ytmusicapi)..." -ForegroundColor Cyan
pip install nuitka zstandard ytmusicapi

Write-Host "Build environment ready!" -ForegroundColor Green
Write-Host "To compile, run the command in docs/compile.txt after activating this venv."
