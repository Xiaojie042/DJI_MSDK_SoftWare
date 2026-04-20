@echo off
setlocal

cd /d %~dp0
set "SCRIPTS=%CD%"

if defined CONDA_PYTHON (
  set "PYTHON=%CONDA_PYTHON%"
  set "PYTHON_SOURCE=conda python override"
  call "%SCRIPTS%\_build_release_common.bat"
  set "RESULT=%ERRORLEVEL%"
  exit /b %RESULT%
)

if not defined CONDA_ENV_NAME set "CONDA_ENV_NAME=drone-monitor"
set "CONDA_CMD="

if defined CONDA_EXE set "CONDA_CMD=%CONDA_EXE%"
if not defined CONDA_CMD (
  for /f "delims=" %%I in ('where conda.bat 2^>nul') do if not defined CONDA_CMD set "CONDA_CMD=%%I"
)
if not defined CONDA_CMD (
  for /f "delims=" %%I in ('where conda.exe 2^>nul') do if not defined CONDA_CMD set "CONDA_CMD=%%I"
)

if not defined CONDA_CMD (
  echo [ERROR] conda was not found in PATH.
  echo [INFO] Install Miniconda or Anaconda, reopen the terminal, or set CONDA_EXE before retrying.
  exit /b 1
)

for /f "delims=" %%I in ('call "%CONDA_CMD%" run -n "%CONDA_ENV_NAME%" python -c "import sys; print(sys.executable)" 2^>nul') do if not defined PYTHON set "PYTHON=%%I"

if not defined PYTHON (
  echo [ERROR] Could not resolve python.exe from conda env: %CONDA_ENV_NAME%
  echo [INFO] Check the env name, or set CONDA_ENV_NAME / CONDA_PYTHON before retrying.
  exit /b 1
)

set "PYTHON_SOURCE=conda env %CONDA_ENV_NAME%"

call "%SCRIPTS%\_build_release_common.bat"
set "RESULT=%ERRORLEVEL%"
exit /b %RESULT%
