@echo off
setlocal

cd /d %~dp0
call "%CD%\build_release_venv.bat"
set "RESULT=%ERRORLEVEL%"
exit /b %RESULT%
