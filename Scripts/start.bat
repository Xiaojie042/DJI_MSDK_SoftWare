@echo off
setlocal

cd /d %~dp0
set "SCRIPTS=%CD%"
set "RELEASE=%SCRIPTS%\release"
set "BACKEND_EXE=%RELEASE%\backend\drone-backend\drone-backend.exe"
set "FRONTEND_EXE=%RELEASE%\tools\frontend-server\frontend-server.exe"
set "FRONTEND_ROOT=%RELEASE%\frontend\dist"

if not exist "%BACKEND_EXE%" (
  echo [ERROR] Backend executable not found: %BACKEND_EXE%
  echo Run Scripts\build_release.bat first.
  exit /b 1
)

if not exist "%FRONTEND_EXE%" (
  echo [ERROR] Frontend server executable not found: %FRONTEND_EXE%
  echo Run Scripts\build_release.bat first.
  exit /b 1
)

if not exist "%FRONTEND_ROOT%\index.html" (
  echo [ERROR] Built frontend not found: %FRONTEND_ROOT%
  echo Run Scripts\build_release.bat first.
  exit /b 1
)

start "drone-backend" /D "%RELEASE%" "%BACKEND_EXE%"
timeout /t 3 >nul
start "frontend-server" /D "%RELEASE%" "%FRONTEND_EXE%" --root "%FRONTEND_ROOT%" --host 127.0.0.1 --port 3000
timeout /t 1 >nul
start "" "http://127.0.0.1:3000"
exit /b 0
