@echo off
rem Usage: update_espcam.bat [device]   e.g. COM49 for serial (IO0->GND + RST first)
setlocal
set "ROOT=%~dp0"
set "DEVICE=%~1"
if "%DEVICE%"=="" set "DEVICE=espcam-water.local"

pushd "%ROOT%"
call "%ROOT%..\..\tools\esphome.cmd" run "%ROOT%..\esphome\espcam-water\espcam-water.yaml" --device "%DEVICE%" --no-logs
set "RC=%ERRORLEVEL%"
popd

if not "%RC%"=="0" echo Update FAILED (exit code %RC%).
if "%RC%"=="0" echo Update OK.
pause
exit /b %RC%
