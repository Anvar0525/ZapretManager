@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo Installing/updating PyInstaller...
py -3 -m pip install -q pyinstaller pillow pystray psutil

echo.
echo Building ZapretManager.exe ...
py -3 -m PyInstaller --noconfirm --clean ^
  --name ZapretManager ^
  --windowed ^
  --onefile ^
  --uac-admin ^
  --icon "%~dp0assets\icon.ico" ^
  --add-data "%~dp0assets;assets" ^
  --paths "%~dp0" ^
  --hidden-import=pystray._win32 ^
  --hidden-import=PIL._tkinter_finder ^
  --collect-all pystray ^
  app.py

if errorlevel 1 (
  echo Build failed.
  pause
  exit /b 1
)

copy /Y "%~dp0dist\ZapretManager.exe" "%~dp0..\ZapretManager.exe" >nul
echo.
echo Done: "%~dp0dist\ZapretManager.exe"
echo Also copied to: "%~dp0..\ZapretManager.exe"
pause
