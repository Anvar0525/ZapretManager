@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo Installing Zapret Manager dependencies...
py -3 -m pip install -r requirements.txt
if errorlevel 1 python -m pip install -r requirements.txt
echo.
echo Done. Now use run.bat
pause
