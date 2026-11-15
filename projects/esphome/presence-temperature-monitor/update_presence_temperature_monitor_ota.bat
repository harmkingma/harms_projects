@echo off
setlocal
pushd "%~dp0"
set "TARGET=%~1"
if not defined TARGET set "TARGET=presence-temperature-monitor.local"
echo Compiling and updating %TARGET% via ESPHome OTA...
call "%~dp0esphome.cmd" run "%~dp0presence-temperature-monitor.yaml" --device "%TARGET%"
set "RC=%ERRORLEVEL%"
popd
exit /b %RC%
