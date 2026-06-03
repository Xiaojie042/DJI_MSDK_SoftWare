@echo off
setlocal

cd /d %~dp0
call "%CD%\build_release_venv.bat"
set "RESULT=%ERRORLEVEL%"
if "%RESULT%"=="0" exit /b 0

echo.
echo [WARN] backend\.venv packaging failed, trying conda packaging...
call "%CD%\build_release_conda.bat"
set "RESULT=%ERRORLEVEL%"
exit /b %RESULT%
