@echo off
setlocal

cd /d %~dp0
set "SCRIPTS=%CD%"
cd /d %SCRIPTS%\..
set "ROOT=%CD%"

set "PYTHON=%ROOT%\backend\.venv\Scripts\python.exe"
set "PYTHON_SOURCE=backend\.venv"

call "%SCRIPTS%\_build_release_common.bat"
set "RESULT=%ERRORLEVEL%"
exit /b %RESULT%
