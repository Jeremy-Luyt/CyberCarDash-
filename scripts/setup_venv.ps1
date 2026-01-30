Write-Host "[INFO] Setting up Python Virtual Environment..."
python -m venv .venv
if ($LASTEXITCODE -ne 0) {
    Write-Error "[ERROR] Failed to create venv. Please ensure python is installed."
    exit $LASTEXITCODE
}

Write-Host "[INFO] Activating venv and installing requirements..."
& .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

Write-Host "[INFO] Setup complete."
