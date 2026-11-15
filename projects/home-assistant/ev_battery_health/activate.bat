@echo off
rem Activates the shared HA test environment in the CURRENT shell.
rem No setlocal here: it would discard the activation when this script exits.
if not exist "%~dp0..\..\..\.venvs\home-assistant\Scripts\activate.bat" (
    echo Shared Home Assistant environment is missing.
    echo Run "%~dp0install_requirements.bat" dev first.
    exit /b 1
)
call "%~dp0..\..\..\.venvs\home-assistant\Scripts\activate.bat"
python --version
