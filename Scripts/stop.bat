@echo off
setlocal

taskkill /f /im drone-backend.exe >nul 2>nul
taskkill /f /im frontend-server.exe >nul 2>nul

echo Packaged release processes stopped.
exit /b 0
