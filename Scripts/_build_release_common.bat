@echo off
setlocal

cd /d %~dp0
set "SCRIPTS=%CD%"
cd /d %SCRIPTS%\..
set "ROOT=%CD%"
set "RELEASE=%SCRIPTS%\release"
set "NPM="
set "ENV_TEMPLATE=%SCRIPTS%\release.env.example"
set "PYTHON_PREFIX="
set "PYTHON_BASE_PREFIX="

if not defined PYTHON (
  echo [ERROR] PYTHON was not configured before calling _build_release_common.bat.
  exit /b 1
)

if not defined PYTHON_SOURCE set "PYTHON_SOURCE=%PYTHON%"

if not exist "%PYTHON%" (
  echo [ERROR] Backend Python not found: %PYTHON%
  echo [INFO] Selected backend environment: %PYTHON_SOURCE%
  exit /b 1
)

call "%PYTHON%" -m PyInstaller --version >nul 2>nul
if errorlevel 1 (
  echo [ERROR] PyInstaller is not installed in the selected backend environment.
  echo [INFO] Selected backend environment: %PYTHON_SOURCE%
  echo [INFO] Python executable: %PYTHON%
  exit /b 1
)

for /f "delims=" %%I in ('call "%PYTHON%" -c "import sys; print(sys.prefix)" 2^>nul') do if not defined PYTHON_PREFIX set "PYTHON_PREFIX=%%I"
for /f "delims=" %%I in ('call "%PYTHON%" -c "import sys; print(sys.base_prefix)" 2^>nul') do if not defined PYTHON_BASE_PREFIX set "PYTHON_BASE_PREFIX=%%I"

if not defined PYTHON_PREFIX (
  echo [ERROR] Could not resolve sys.prefix from the selected backend Python.
  echo [INFO] Python executable: %PYTHON%
  exit /b 1
)
if not defined PYTHON_BASE_PREFIX set "PYTHON_BASE_PREFIX=%PYTHON_PREFIX%"

if defined NPM_CMD set "NPM=%NPM_CMD%"
if not defined NPM (
  for /f "delims=" %%I in ('where npm.cmd 2^>nul') do if not defined NPM set "NPM=%%I"
)
if not defined NPM if exist "%ProgramFiles%\nodejs\npm.cmd" set "NPM=%ProgramFiles%\nodejs\npm.cmd"
if not defined NPM (
  for /d %%I in ("%LocalAppData%\Programs\node-v*-win-x64") do if not defined NPM if exist "%%~fI\npm.cmd" set "NPM=%%~fI\npm.cmd"
)
if not defined NPM (
  for /d %%I in ("%UserProfile%\AppData\Local\Programs\node-v*-win-x64") do if not defined NPM if exist "%%~fI\npm.cmd" set "NPM=%%~fI\npm.cmd"
)
if not defined NPM (
  echo [ERROR] npm.cmd was not found in PATH.
  echo [INFO] Install Node.js 20 LTS, reopen the terminal, or set NPM_CMD before retrying.
  exit /b 1
)

if not exist "%ENV_TEMPLATE%" (
  echo [ERROR] Release env template not found: %ENV_TEMPLATE%
  exit /b 1
)

echo [INFO] Selected backend environment: %PYTHON_SOURCE%
echo [INFO] Python executable: %PYTHON%
echo [INFO] Python prefix: %PYTHON_PREFIX%
echo [INFO] Python base prefix: %PYTHON_BASE_PREFIX%

echo [1/4] Building frontend...
set "VITE_API_BASE_URL=http://127.0.0.1:8000"
set "VITE_WS_URL=ws://127.0.0.1:8000/ws"
set "VITE_API_HOST=127.0.0.1"
set "VITE_API_PORT=8000"
call "%NPM%" --prefix "%ROOT%\frontend" run build
if errorlevel 1 exit /b 1

if not exist "%RELEASE%" mkdir "%RELEASE%"
if exist "%RELEASE%\frontend\dist" rmdir /s /q "%RELEASE%\frontend\dist"
xcopy "%ROOT%\frontend\dist" "%RELEASE%\frontend\dist\" /e /i /y >nul

echo [2/4] Cleaning previous binaries...
if exist "%RELEASE%\backend\drone-backend" rmdir /s /q "%RELEASE%\backend\drone-backend"
if exist "%RELEASE%\tools\frontend-server" rmdir /s /q "%RELEASE%\tools\frontend-server"
if exist "%RELEASE%\_build" rmdir /s /q "%RELEASE%\_build"
if exist "%RELEASE%\.env" del /f /q "%RELEASE%\.env"

echo [3/4] Building backend executable...
call "%PYTHON%" -m PyInstaller ^
  --noconfirm ^
  --clean ^
  --onedir ^
  --name drone-backend ^
  --distpath "%RELEASE%\backend" ^
  --workpath "%RELEASE%\_build\backend" ^
  --specpath "%RELEASE%\_build\spec" ^
  --paths "%ROOT%\backend" ^
  --collect-submodules uvicorn ^
  --collect-submodules websockets ^
  --collect-submodules sqlalchemy ^
  --collect-submodules pydantic_settings ^
  --hidden-import aiosqlite ^
  "%SCRIPTS%\_src\backend_entry.py"
if errorlevel 1 exit /b 1
call :copy_runtime_dlls "%RELEASE%\backend\drone-backend"
if errorlevel 1 exit /b 1

echo [4/4] Building frontend server executable...
call "%PYTHON%" -m PyInstaller ^
  --noconfirm ^
  --clean ^
  --onedir ^
  --name frontend-server ^
  --distpath "%RELEASE%\tools" ^
  --workpath "%RELEASE%\_build\frontend-server" ^
  --specpath "%RELEASE%\_build\spec" ^
  "%SCRIPTS%\_src\frontend_static_server.py"
if errorlevel 1 exit /b 1
call :copy_runtime_dlls "%RELEASE%\tools\frontend-server"
if errorlevel 1 exit /b 1

if not exist "%RELEASE%\data\flights" mkdir "%RELEASE%\data\flights"
if not exist "%RELEASE%\logs" mkdir "%RELEASE%\logs"
copy /y "%ENV_TEMPLATE%" "%RELEASE%\.env" >nul

echo.
echo Packaged release folder is ready: %RELEASE%
echo Use Scripts\start.bat to run the packaged application.
exit /b 0

:copy_runtime_dlls
set "TARGET_DIR=%~1"
if not exist "%TARGET_DIR%" (
  echo [ERROR] Target runtime directory not found: %TARGET_DIR%
  exit /b 1
)

echo [INFO] Copying Python runtime DLLs into %TARGET_DIR%
for %%D in (
  "%PYTHON_PREFIX%"
  "%PYTHON_PREFIX%\DLLs"
  "%PYTHON_PREFIX%\Library\bin"
  "%PYTHON_BASE_PREFIX%"
  "%PYTHON_BASE_PREFIX%\DLLs"
  "%PYTHON_BASE_PREFIX%\Library\bin"
) do (
  if exist "%%~fD" call :copy_runtime_dlls_from_dir "%%~fD" "%TARGET_DIR%"
  if exist "%TARGET_DIR%\_internal" if exist "%%~fD" call :copy_runtime_dlls_from_dir "%%~fD" "%TARGET_DIR%\_internal"
)
exit /b 0

:copy_runtime_dlls_from_dir
set "SOURCE_DIR=%~1"
set "TARGET_DIR=%~2"
for %%F in ("%SOURCE_DIR%\*.dll") do (
  if exist "%%~fF" copy /y "%%~fF" "%TARGET_DIR%\" >nul
)
exit /b 0
