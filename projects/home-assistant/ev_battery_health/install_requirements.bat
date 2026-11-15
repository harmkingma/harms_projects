@echo off
setlocal
if "%~1"=="" goto setup
if "%~1"=="dev" goto setup
echo Unknown extra "%~1". Use install_requirements.bat dev.
exit /b 1
:setup
call "%~dp0..\..\..\tools\setup.cmd" home-assistant
exit /b %ERRORLEVEL%
