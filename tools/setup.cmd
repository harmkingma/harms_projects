@echo off
setlocal EnableExtensions
set "ROOT=%~dp0.."
set "PROFILE=%~1"
set "VERSION=3.13"
if "%PROFILE%"=="esphome" set "VERSION=3.12"
if "%PROFILE%"=="esphome" goto valid
if "%PROFILE%"=="watermeter" goto valid
if "%PROFILE%"=="home-assistant" goto valid
if "%PROFILE%"=="cad-tools" goto valid
echo Usage: tools\setup.cmd esphome^|watermeter^|home-assistant^|cad-tools
exit /b 1

:valid
set "ENVIRONMENT=%ROOT%\.venvs\%PROFILE%"
set "PYTHON=%ENVIRONMENT%\Scripts\python.exe"
if exist "%PYTHON%" goto install
uv venv --python "%VERSION%" "%ENVIRONMENT%"
if errorlevel 1 exit /b 1

:install
if exist "%USERPROFILE%\.certs\ca-bundle.pem" (
    set "SSL_CERT_FILE=%USERPROFILE%\.certs\ca-bundle.pem"
    set "REQUESTS_CA_BUNDLE=%USERPROFILE%\.certs\ca-bundle.pem"
)
if "%PROFILE%"=="home-assistant" goto home_assistant
uv pip install --python "%PYTHON%" -r "%ROOT%\dependencies\%PROFILE%.txt"
if errorlevel 1 exit /b 1
if not "%PROFILE%"=="watermeter" goto ready
uv pip install --python "%PYTHON%" --no-deps -e "%ROOT%\projects\espcam-water\cv"
if errorlevel 1 exit /b 1
goto ready

:home_assistant
uv pip install --python "%PYTHON%" -r "%ROOT%\dependencies\home-assistant.txt" --override "%ROOT%\projects\home-assistant\ev_battery_health\overrides-dev.txt"
if errorlevel 1 exit /b 1

:ready
echo Environment ready: "%PYTHON%"
exit /b 0
