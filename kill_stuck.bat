@echo off
:: Emergency: kill stuck Zapret Manager tray processes
powershell -NoProfile -Command "Start-Process powershell -Verb RunAs -ArgumentList '-NoProfile -Command Stop-Process -Name pythonw -Force -ErrorAction SilentlyContinue' -Wait"
del "%~dp0zapret_manager.lock" >nul 2>&1
echo Done.
pause
