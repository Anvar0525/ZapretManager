@echo off
:: Thin wrapper: immediately hands off to VBS (no pip, minimal flash)
cd /d "%~dp0"
wscript.exe "%~dp0Zapret Manager.vbs"
exit /b 0
