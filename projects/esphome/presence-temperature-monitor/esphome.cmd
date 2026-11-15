@echo off
rem Compatibility launcher. Every device uses the archive's shared ESPHome environment.
setlocal
pushd "%~dp0"
call "%~dp0..\..\..\tools\esphome.cmd" %*
set "RC=%ERRORLEVEL%"
popd
exit /b %RC%
