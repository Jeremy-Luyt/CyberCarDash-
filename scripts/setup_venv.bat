@echo off
echo [INFO] Setting up Python Virtual Environment...
python -m venv .venv
if %errorlevel% neq 0 (
    echo [ERROR] Failed to create venv. Please ensure python is installed.
    pause
    exit /b %errorlevel%
)

echo [INFO] Activating venv and installing requirements...
call .venv\Scripts\activate.bat
pip install -r requirements.txt

echo [INFO] Setup complete. To run the app:
echo        .venv\Scripts\activate
echo        python app/main.py
pause
