@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo Installing/updating PyInstaller...
py -3 -m pip install -q pyinstaller pillow pystray psutil
if errorlevel 1 (
  echo pip failed.
  pause
  exit /b 1
)

echo.
echo Building ZapretManager.exe ...
REM Relative paths after cd — avoid %%~dp0 trailing-backslash quote bug
py -3 -m PyInstaller --noconfirm --clean --name ZapretManager --windowed --onefile --uac-admin --icon "assets\icon.ico" --add-data "assets;assets" --paths "." --hidden-import=pystray._win32 --hidden-import=PIL._tkinter_finder --collect-all pystray app.py

if errorlevel 1 (
  echo Build failed.
  pause
  exit /b 1
)

copy /Y "dist\ZapretManager.exe" "..\ZapretManager.exe" >nul
echo.
echo Done: "%cd%\dist\ZapretManager.exe"
echo Also copied to: "%cd%\..\ZapretManager.exe"
pause
