@echo off
echo [INFO] Building CyberCarDash...
call .venv\Scripts\activate.bat
pyinstaller cybercardash.spec
echo [INFO] Build Complete. Output in dist/
pause
